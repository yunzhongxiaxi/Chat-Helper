import sys
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.rag_service import RAGService


class BenchmarkRAGService(RAGService):
    async def _get_embeddings(self, texts):
        embeddings = []
        for text in texts:
            embeddings.append([
                float(text.count("面试") + text.count("offer") + text.count("入职")),
                float(text.count("旅游") + text.count("机票") + text.count("酒店")),
                float(text.count("论文") + text.count("导师") + text.count("实验")),
                float(len(text) % 23),
            ])
        return embeddings


def build_records():
    return [
        {"timestamp": "2026-01-01 10:00:00", "sender": "contact", "message": "我今天准备面试，正在看简历和项目经历"},
        {"timestamp": "2026-01-01 10:02:00", "sender": "user", "message": "面试岗位是什么方向"},
        {"timestamp": "2026-01-01 10:04:00", "sender": "contact", "message": "如果拿到offer我就考虑搬家"},
        {"timestamp": "2026-01-01 10:06:00", "sender": "user", "message": "offer下来以后可以比较一下薪资和通勤"},
        {"timestamp": "2026-01-01 10:08:00", "sender": "contact", "message": "还有入职后的试用期我也有点担心"},
        {"timestamp": "2026-01-01 10:10:00", "sender": "user", "message": "试用期主要看团队氛围和直属领导"},
    ]


def collect_candidates(service, query):
    chunks = service._load_chunks("benchmark-contact")
    topics = service._load_topics("benchmark-contact")
    query_terms = service._tokenize(query)

    chunk_bm25_scores = service._bm25_scores(query_terms, chunks)
    topic_bm25_scores = service._bm25_scores(query_terms, topics)
    chunk_only_ids = service._top_ids(chunk_bm25_scores, service.bm25_top_k)
    topic_scores = service._merge_scores(topic_bm25_scores, {})
    topic_ids = service._top_ids(topic_scores, service.topic_top_k)
    expanded_ids = service._expand_topic_chunks(topic_ids, chunks, topic_scores)
    parent_child_ids = chunk_only_ids | expanded_ids

    topic_id = topics[0]["id"]
    relevant_ids = {chunk["id"] for chunk in chunks if chunk["topic_id"] == topic_id}

    return {
        "total_chunks": len(chunks),
        "chunk_only_ids": chunk_only_ids,
        "expanded_ids": expanded_ids,
        "parent_child_ids": parent_child_ids,
        "relevant_ids": relevant_ids,
    }


def coverage(candidate_ids, relevant_ids):
    return len(candidate_ids & relevant_ids) / len(relevant_ids) * 100 if relevant_ids else 0


def main():
    query = "她之前面试offer聊到什么"

    with TemporaryDirectory() as tmp:
        service = BenchmarkRAGService()
        service.working_dir = Path(tmp)
        service.db_path = Path(tmp) / "hybrid_rag.db"
        service.bm25_top_k = 2
        service.topic_top_k = 1
        service.topic_expand_chunk_limit = 10
        service.max_chunk_messages = 2
        service._init_db()
        service._should_start_new_topic = lambda current_topic, record: False
        service.insert_records("benchmark-contact", build_records())

        metrics = collect_candidates(service, query)
        chunk_only_count = len(metrics["chunk_only_ids"])
        parent_child_count = len(metrics["parent_child_ids"])
        extra_count = len(metrics["parent_child_ids"] - metrics["chunk_only_ids"])
        relevant_count = len(metrics["relevant_ids"])
        chunk_only_coverage = coverage(metrics["chunk_only_ids"], metrics["relevant_ids"])
        parent_child_coverage = coverage(metrics["parent_child_ids"], metrics["relevant_ids"])
        improvement = parent_child_coverage - chunk_only_coverage

        print("RAG 父子索引召回 benchmark")
        print(f"query: {query}")
        print(f"总子 chunks: {metrics['total_chunks']}")
        print(f"相关父 topic 下 chunks: {relevant_count}")
        print("")
        print("chunk-only:")
        print(f"  候选 chunks: {chunk_only_count}")
        print(f"  相关覆盖率: {chunk_only_coverage:.2f}%")
        print("")
        print("parent-child:")
        print(f"  候选 chunks: {parent_child_count}")
        print(f"  额外召回 sibling chunks: {extra_count}")
        print(f"  相关覆盖率: {parent_child_coverage:.2f}%")
        print("")
        print(f"覆盖率提升: {improvement:.2f} 个百分点")


if __name__ == "__main__":
    main()
