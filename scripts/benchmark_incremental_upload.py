import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import config
from backend.models.db import Database
from backend.services.parser_agent import parser_agent


def format_seconds(seconds: float) -> str:
    return f"{seconds:.2f}s"


def print_import_result(label: str, total_records: int, inserted_count: int, elapsed: float) -> None:
    skipped_count = total_records - inserted_count
    skip_rate = skipped_count / total_records * 100 if total_records else 0
    print(f"{label}:")
    print(f"  新增记录数: {inserted_count}")
    print(f"  跳过记录数: {skipped_count}")
    print(f"  跳过率: {skip_rate:.2f}%")
    print(f"  入库耗时: {format_seconds(elapsed)}")


def main() -> None:
    sample_path = PROJECT_ROOT / "chat_history_sample.xlsx"
    db_path = config.database.get("path", "./data/chathelper.db")

    content = sample_path.read_bytes()

    parse_start = time.perf_counter()
    parsed = parser_agent.parse_xlsx(content)
    parse_elapsed = time.perf_counter() - parse_start

    metadata = parsed["metadata"]
    records = parsed["records"]
    contact_id = metadata.get("contact_id")
    if not contact_id:
        raise ValueError("XLSX metadata 中未解析到 contact_id")

    db = Database(db_path)

    first_start = time.perf_counter()
    first_inserted = db.insert_new_chat_records(contact_id, records)
    first_elapsed = time.perf_counter() - first_start

    duplicate_start = time.perf_counter()
    duplicate_inserted = db.insert_new_chat_records(contact_id, records)
    duplicate_elapsed = time.perf_counter() - duplicate_start

    print("XLSX 增量导入 benchmark")
    print(f"样例文件: {sample_path}")
    print(f"数据库: {db_path}")
    print(f"contact_id: {contact_id}")
    print(f"昵称: {metadata.get('nickname', '')}")
    print(f"解析记录数: {len(records)}")
    print(f"解析耗时: {format_seconds(parse_elapsed)}")
    print_import_result("当前导入", len(records), len(first_inserted), first_elapsed)
    print_import_result("紧接着重复导入", len(records), len(duplicate_inserted), duplicate_elapsed)


if __name__ == "__main__":
    main()
