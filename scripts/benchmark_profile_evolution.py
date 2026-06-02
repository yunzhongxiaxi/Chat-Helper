import argparse
import json
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import config
from backend.models.db import Database
from backend.services.profile_service import ProfileService

CHAT_LINE_PATTERN = re.compile(r"^\[(?P<timestamp>[^\]]+)\]\s+(?P<sender>[^:]+):\s*(?P<message>.*)$")


def resolve_path(path_text: str) -> Path:
    path = Path(path_text)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def rag_db_path() -> Path:
    working_dir = config.lightrag.get("working_dir", "./data/hybrid_rag")
    return resolve_path(working_dir) / "hybrid_rag.db"


def profile_db_path() -> Path:
    return resolve_path(config.database.get("path", "./data/chathelper.db"))


def load_chunks(contact_id: str | None, limit: int | None) -> List[Dict]:
    db_path = rag_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    query = """
        SELECT id, contact_id, chunk_text, start_time, end_time, message_count
        FROM rag_chunks
    """
    params = []
    if contact_id:
        query += " WHERE contact_id = ?"
        params.append(contact_id)
    query += " ORDER BY start_time, end_time, id"
    if limit:
        query += " LIMIT ?"
        params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "contact_id": row[1],
            "chunk_text": row[2],
            "start_time": row[3],
            "end_time": row[4],
            "message_count": row[5],
        }
        for row in rows
    ]


def pick_contact_id() -> str:
    conn = sqlite3.connect(rag_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        SELECT contact_id, COUNT(*) AS chunk_count
        FROM rag_chunks
        GROUP BY contact_id
        ORDER BY chunk_count DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise ValueError("rag_chunks 为空，无法测评画像演化")
    return row[0]


def parse_chunk_records(chunk: Dict) -> List[Dict]:
    records = []
    for line in chunk["chunk_text"].splitlines():
        match = CHAT_LINE_PATTERN.match(line.strip())
        if match:
            records.append({
                "timestamp": match.group("timestamp"),
                "sender": match.group("sender"),
                "message": match.group("message"),
            })
    if records:
        return records
    return [{
        "timestamp": chunk["start_time"],
        "sender": "chunk",
        "message": chunk["chunk_text"],
    }]


def batched(items: List[Dict], batch_size: int):
    for index in range(0, len(items), batch_size):
        yield items[index:index + batch_size]


def count_profile_fields(profile: Dict) -> Dict:
    current_profile = profile.get("current_profile") or {}
    stable_traits = profile.get("stable_traits") or []
    changed_traits = profile.get("changed_traits") or []
    recent_signals = profile.get("recent_signals") or []
    return {
        "current_fields": sum(1 for value in current_profile.values() if value),
        "stable": len(stable_traits),
        "changed": len(changed_traits),
        "recent": len(recent_signals),
    }


def print_profile_preview(title: str, profile: Dict):
    print(title)
    current_profile = profile.get("current_profile") or {}
    for key, value in current_profile.items():
        print(f"  {key}: {value}")

    for field in ("stable_traits", "recent_signals", "changed_traits"):
        values = profile.get(field) or []
        preview = values[:3]
        print(f"  {field}: {json.dumps(preview, ensure_ascii=False)}")


def main():
    parser = argparse.ArgumentParser(description="基于已有 RAG chunks 测评人物画像演化")
    parser.add_argument("--contact-id", help="要读取的 RAG contact_id；默认选择 chunk 数最多的 contact")
    parser.add_argument("--profile-contact-id", help="写入 profiles 表的 contact_id；默认等于 --contact-id")
    parser.add_argument("--batch-chunks", type=int, default=8, help="每批送入画像流程的 chunk 数")
    parser.add_argument("--max-batches", type=int, default=3, help="最多处理批次数，用于控制 API 成本")
    parser.add_argument("--max-chunks", type=int, help="最多读取 chunk 数")
    args = parser.parse_args()

    contact_id = args.contact_id or pick_contact_id()
    profile_contact_id = args.profile_contact_id or contact_id
    chunk_limit = args.max_chunks or args.batch_chunks * args.max_batches
    chunks = load_chunks(contact_id, chunk_limit)
    if not chunks:
        raise ValueError(f"未找到 contact_id={contact_id} 的 rag_chunks")

    db = Database(str(profile_db_path()))
    service = ProfileService(db)

    print("人物画像演化 benchmark")
    print(f"RAG 数据库: {rag_db_path()}")
    print(f"Profile 数据库: {profile_db_path()}")
    print(f"读取 contact_id: {contact_id}")
    print(f"写入 profile contact_id: {profile_contact_id}")
    print(f"chunk 数: {len(chunks)}")
    print(f"batch_chunks: {args.batch_chunks}")
    print(f"max_batches: {args.max_batches}")
    print("")

    total_messages = 0
    processed_chunks = 0
    started_at = time.perf_counter()
    latest_profiles = None

    for batch_index, chunk_batch in enumerate(batched(chunks, args.batch_chunks), 1):
        if batch_index > args.max_batches:
            break

        records = []
        for chunk in chunk_batch:
            records.extend(parse_chunk_records(chunk))

        batch_started_at = time.perf_counter()
        latest_profiles = service.generate_profile(profile_contact_id, records)
        batch_elapsed = time.perf_counter() - batch_started_at

        processed_chunks += len(chunk_batch)
        total_messages += len(records)

        user_counts = count_profile_fields(latest_profiles.get("user_profile") or {})
        contact_counts = count_profile_fields(latest_profiles.get("contact_profile") or {})

        print(f"Batch {batch_index}")
        print(f"  chunks: {len(chunk_batch)} / messages: {len(records)} / elapsed: {batch_elapsed:.2f}s")
        print(
            "  user: "
            f"fields={user_counts['current_fields']} "
            f"stable={user_counts['stable']} "
            f"recent={user_counts['recent']} "
            f"changed={user_counts['changed']}"
        )
        print(
            "  contact: "
            f"fields={contact_counts['current_fields']} "
            f"stable={contact_counts['stable']} "
            f"recent={contact_counts['recent']} "
            f"changed={contact_counts['changed']}"
        )

    elapsed = time.perf_counter() - started_at
    print("")
    print("汇总:")
    print(f"  已处理 chunk 数: {processed_chunks}")
    print(f"  已处理消息数: {total_messages}")
    print(f"  已处理批次数: {min(args.max_batches, (len(chunks) + args.batch_chunks - 1) // args.batch_chunks)}")
    print(f"  总耗时: {elapsed:.2f}s")

    if latest_profiles:
        print("")
        print_profile_preview("最终 user_profile 预览:", latest_profiles.get("user_profile") or {})
        print("")
        print_profile_preview("最终 contact_profile 预览:", latest_profiles.get("contact_profile") or {})


if __name__ == "__main__":
    main()
