import sys
import time
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.parser_agent import parser_agent
from backend.services.rag_service import RAGService


class BenchmarkRAGService(RAGService):
    def __init__(self):
        self.embedding_text_counts = []
        super().__init__()

    async def _get_embeddings(self, texts):
        self.embedding_text_counts.append(len(texts))
        return await super()._get_embeddings(texts)


def format_seconds(seconds):
    return f"{seconds:.2f}s"


def load_records():
    sample_path = PROJECT_ROOT / "chat_history_sample.xlsx"
    content = sample_path.read_bytes()
    parsed = parser_agent.parse_xlsx(content)
    contact_id = parsed["metadata"].get("contact_id")
    if not contact_id:
        raise ValueError("XLSX metadata 中未解析到 contact_id")
    return sample_path, contact_id, parsed["metadata"], parsed["records"]


def pick_queries(service, topics, limit=5):
    queries = []
    for topic in sorted(topics, key=lambda item: item["message_count"], reverse=True):
        terms = [term for term, _ in Counter(topic["terms"]).most_common(20) if len(term) >= 2]
        query_terms = []
        for term in terms:
            if term not in query_terms:
                query_terms.append(term)
            if len(query_terms) >= 4:
                break
        if query_terms:
            queries.append({
                "query": " ".join(query_terms),
                "topic_id": topic["id"],
                "topic_summary": topic["topic_summary"],
            })
        if len(queries) >= limit:
            break
    return queries


def evaluate_query(service, query, expected_topic_id):
    chunks = service._load_chunks()
    topics = service._load_topics()
    query_terms = service._tokenize(query)
    bm25_scores = service._bm25_scores(query_terms, chunks)
    topic_bm25_scores = service._bm25_scores(query_terms, topics)

    query_embedding = __import__("asyncio").run(service._get_embeddings([query]))[0]
    vector_scores = {
        chunk["id"]: service._cosine_similarity(query_embedding, chunk["embedding"])
        for chunk in chunks if chunk["embedding"]
    }
    topic_vector_scores = {
        topic["id"]: service._cosine_similarity(query_embedding, topic["embedding"])
        for topic in topics if topic["embedding"]
    }

    chunk_only_ids = service._top_ids(bm25_scores, service.bm25_top_k) | service._top_ids(vector_scores, service.vector_top_k)
    topic_ids = service._top_ids(topic_bm25_scores, service.topic_top_k) | service._top_ids(topic_vector_scores, service.topic_top_k)
    topic_scores = service._merge_scores(topic_bm25_scores, topic_vector_scores)
    expanded_ids = service._expand_topic_chunks(topic_ids, chunks, topic_scores)
    parent_child_ids = chunk_only_ids | expanded_ids
    relevant_ids = {chunk["id"] for chunk in chunks if chunk["topic_id"] == expected_topic_id}

    chunk_only_hits = len(chunk_only_ids & relevant_ids)
    parent_child_hits = len(parent_child_ids & relevant_ids)
    relevant_total = len(relevant_ids)
    chunk_only_coverage = chunk_only_hits / relevant_total * 100 if relevant_total else 0
    parent_child_coverage = parent_child_hits / relevant_total * 100 if relevant_total else 0

    return {
        "query": query,
        "relevant_total": relevant_total,
        "chunk_only_candidates": len(chunk_only_ids),
        "parent_child_candidates": len(parent_child_ids),
        "expanded_candidates": len(expanded_ids),
        "extra_sibling_chunks": len(parent_child_ids - chunk_only_ids),
        "chunk_only_coverage": chunk_only_coverage,
        "parent_child_coverage": parent_child_coverage,
        "coverage_lift": parent_child_coverage - chunk_only_coverage,
    }


def main():
    sample_path, contact_id, metadata, records = load_records()
    service = BenchmarkRAGService()

    print("真实聊天数据 RAG benchmark")
    print(f"样例文件: {sample_path}")
    print(f"contact_id: {contact_id}")
    print(f"昵称: {metadata.get('nickname', '')}")
    print(f"记录数: {len(records)}")
    print(f"RAG 数据库: {service.db_path}")

    build_start = time.perf_counter()
    service.insert_records(contact_id, records)
    build_elapsed = time.perf_counter() - build_start

    topics = service._load_topics(contact_id)
    chunks = service._load_chunks(contact_id)
    queries = pick_queries(service, topics)

    print(f"topic 数: {len(topics)}")
    print(f"chunk 数: {len(chunks)}")
    print(f"构建耗时: {format_seconds(build_elapsed)}")
    print(f"embedding 调用次数: {len(service.embedding_text_counts)}")
    print(f"embedding 文本数: {sum(service.embedding_text_counts)}")

    query_start = time.perf_counter()
    results = [evaluate_query(service, item["query"], item["topic_id"]) for item in queries]
    query_elapsed = time.perf_counter() - query_start

    print(f"query 数: {len(results)}")
    print(f"查询评估耗时: {format_seconds(query_elapsed)}")
    print("")

    if not results:
        print("未生成可评估 query")
        return

    avg_chunk_only = sum(item["chunk_only_coverage"] for item in results) / len(results)
    avg_parent_child = sum(item["parent_child_coverage"] for item in results) / len(results)
    avg_lift = sum(item["coverage_lift"] for item in results) / len(results)
    total_extra = sum(item["extra_sibling_chunks"] for item in results)

    for index, result in enumerate(results, 1):
        print(f"Query {index}: {result['query']}")
        print(f"  相关 chunks: {result['relevant_total']}")
        print(f"  chunk-only 覆盖率: {result['chunk_only_coverage']:.2f}%")
        print(f"  parent-child 覆盖率: {result['parent_child_coverage']:.2f}%")
        print(f"  覆盖率提升: {result['coverage_lift']:.2f} 个百分点")
        print(f"  额外召回 sibling chunks: {result['extra_sibling_chunks']}")

    print("汇总:")
    print(f"  平均 chunk-only 覆盖率: {avg_chunk_only:.2f}%")
    print(f"  平均 parent-child 覆盖率: {avg_parent_child:.2f}%")
    print(f"  平均覆盖率提升: {avg_lift:.2f} 个百分点")
    print(f"  总额外召回 sibling chunks: {total_extra}")


if __name__ == "__main__":
    main()
