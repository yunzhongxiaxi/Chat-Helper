from typing import List, Dict
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict
from openai import AsyncOpenAI
import hashlib
import json
import math
import re
import sqlite3
import asyncio
from backend.config import config

class RAGService:
    def __init__(self):
        rag_cfg = config.lightrag
        self.working_dir = Path(rag_cfg.get('working_dir', './data/hybrid_rag'))
        self.working_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.working_dir / 'hybrid_rag.db'
        self.embedding_cfg = config.get_model_config('embedding')

        self.time_gap_minutes = rag_cfg.get('time_gap_minutes', 45)
        self.topic_similarity_threshold = rag_cfg.get('topic_similarity_threshold', 0.18)
        self.max_topic_messages = rag_cfg.get('max_topic_messages', 120)
        self.max_topic_chars = rag_cfg.get('max_topic_chars', 10000)
        self.max_chunk_messages = rag_cfg.get('max_chunk_messages', 30)
        self.max_chunk_chars = rag_cfg.get('max_chunk_chars', 2500)
        self.bm25_top_k = rag_cfg.get('bm25_top_k', 20)
        self.vector_top_k = rag_cfg.get('vector_top_k', 20)
        self.final_top_k = rag_cfg.get('final_top_k', 5)
        self.bm25_k1 = 1.5
        self.bm25_b = 0.75
        self.transition_words = ['对了', '还有', '话说', '突然想起来', '另外', '顺便', '换个话题']

        self._init_db()

    def _init_db(self):
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rag_topics (
                id TEXT PRIMARY KEY,
                contact_id TEXT NOT NULL,
                topic_summary TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                message_count INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rag_chunks (
                id TEXT PRIMARY KEY,
                topic_id TEXT NOT NULL,
                contact_id TEXT NOT NULL,
                chunk_text TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                message_count INTEGER NOT NULL,
                terms_json TEXT NOT NULL,
                embedding_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(topic_id) REFERENCES rag_topics(id)
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rag_chunks_contact ON rag_chunks(contact_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rag_topics_contact ON rag_topics(contact_id)')
        conn.commit()
        conn.close()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def insert_records(self, contact_id: str, records: List[Dict]):
        if not records:
            return

        sorted_records = sorted(records, key=lambda record: record['timestamp'])
        topics = self._split_topics(sorted_records)
        chunks = []

        for topic in topics:
            topic_id = self._make_topic_id(contact_id, topic)
            topic_summary = self._summarize_topic(topic)
            sub_chunks = self._split_topic_chunks(topic)
            chunks.extend((topic_id, topic_summary, sub_chunk) for sub_chunk in sub_chunks)

        chunk_texts = [self._format_chunk(chunk, topic_summary) for _, topic_summary, chunk in chunks]
        embeddings = asyncio.run(self._get_embeddings(chunk_texts)) if chunk_texts else []

        conn = self._get_connection()
        cursor = conn.cursor()

        for index, (topic_id, topic_summary, chunk) in enumerate(chunks):
            cursor.execute('''
                INSERT OR IGNORE INTO rag_topics (id, contact_id, topic_summary, start_time, end_time, message_count)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                topic_id, contact_id, topic_summary,
                chunk[0]['timestamp'], chunk[-1]['timestamp'], len(chunk)
            ))

            chunk_text = chunk_texts[index]
            chunk_id = self._make_chunk_id(contact_id, chunk)
            terms = self._tokenize(chunk_text)
            embedding = embeddings[index] if index < len(embeddings) else []

            cursor.execute('''
                INSERT OR IGNORE INTO rag_chunks
                (id, topic_id, contact_id, chunk_text, start_time, end_time, message_count, terms_json, embedding_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                chunk_id, topic_id, contact_id, chunk_text,
                chunk[0]['timestamp'], chunk[-1]['timestamp'], len(chunk),
                json.dumps(terms, ensure_ascii=False),
                json.dumps(embedding)
            ))

        conn.commit()
        conn.close()
        print(f"✓ Hybrid RAG：{len(records)} 条消息 → {len(topics)} 个话题 → {len(chunks)} 个 chunk")

    def search(self, query: str, mode: str = "hybrid") -> str:
        chunks = self._load_chunks()
        if not chunks:
            return ""

        query_terms = self._tokenize(query)
        bm25_scores = self._bm25_scores(query_terms, chunks)
        vector_scores = {}

        if mode in ["hybrid", "vector"]:
            query_embedding = asyncio.run(self._get_embeddings([query]))[0]
            vector_scores = {
                chunk['id']: self._cosine_similarity(query_embedding, chunk['embedding'])
                for chunk in chunks if chunk['embedding']
            }

        if mode == "bm25":
            candidate_ids = self._top_ids(bm25_scores, self.bm25_top_k)
        elif mode == "vector":
            candidate_ids = self._top_ids(vector_scores, self.vector_top_k)
        else:
            candidate_ids = self._top_ids(bm25_scores, self.bm25_top_k) | self._top_ids(vector_scores, self.vector_top_k)

        ranked = self._rerank(candidate_ids, chunks, bm25_scores, vector_scores)
        return self._format_search_results(ranked[:self.final_top_k])

    def _split_topics(self, records: List[Dict]) -> List[List[Dict]]:
        topics = []
        current_topic = [records[0]]

        for record in records[1:]:
            if self._should_start_new_topic(current_topic, record):
                topics.append(current_topic)
                current_topic = [record]
            else:
                current_topic.append(record)

        if current_topic:
            topics.append(current_topic)
        return topics

    def _should_start_new_topic(self, current_topic: List[Dict], record: Dict) -> bool:
        previous = current_topic[-1]
        if self._minutes_between(previous['timestamp'], record['timestamp']) > self.time_gap_minutes:
            return True

        topic_chars = sum(len(item['message']) for item in current_topic)
        if len(current_topic) >= self.max_topic_messages or topic_chars >= self.max_topic_chars:
            return True

        message = record['message'].strip()
        if any(message.startswith(word) for word in self.transition_words):
            return True

        previous_terms = set(self._tokenize(previous['message']))
        current_terms = set(self._tokenize(record['message']))
        if previous_terms and current_terms:
            overlap = len(previous_terms & current_terms) / len(previous_terms | current_terms)
            return overlap < self.topic_similarity_threshold and len(message) > 8
        return False

    def _split_topic_chunks(self, topic: List[Dict]) -> List[List[Dict]]:
        chunks = []
        current_chunk = []
        current_chars = 0

        for record in topic:
            message_chars = len(record['message'])
            should_split = (
                current_chunk and (
                    len(current_chunk) >= self.max_chunk_messages or
                    current_chars + message_chars > self.max_chunk_chars
                )
            )

            if should_split:
                chunks.append(current_chunk)
                current_chunk = []
                current_chars = 0

            current_chunk.append(record)
            current_chars += message_chars

        if current_chunk:
            chunks.append(current_chunk)
        return chunks

    def _summarize_topic(self, topic: List[Dict]) -> str:
        start = topic[0]['timestamp']
        end = topic[-1]['timestamp']
        keywords = self._top_terms(' '.join(record['message'] for record in topic), 8)
        return f"{start} 至 {end}，双方围绕 {', '.join(keywords) or '日常对话'} 展开交流，共 {len(topic)} 条消息。"

    def _format_chunk(self, records: List[Dict], topic_summary: str) -> str:
        lines = ["=== 相关历史对话片段 ==="]
        lines.append(f"话题摘要: {topic_summary}")
        lines.append(f"时间范围: {records[0]['timestamp']} ~ {records[-1]['timestamp']}")
        lines.append(f"消息数量: {len(records)}")
        lines.append("")

        for record in records:
            lines.append(f"[{record['timestamp']}] {record['sender']}: {record['message']}")
        return '\n'.join(lines)

    def _tokenize(self, text: str) -> List[str]:
        normalized = re.sub(r'\s+', '', text.lower())
        ascii_terms = re.findall(r'[a-z0-9]+', text.lower())
        chinese_chars = [char for char in normalized if '一' <= char <= '鿿']
        chinese_bigrams = [normalized[i:i + 2] for i in range(len(normalized) - 1)]
        return ascii_terms + chinese_chars + chinese_bigrams

    def _top_terms(self, text: str, limit: int) -> List[str]:
        terms = [term for term in self._tokenize(text) if len(term) >= 2]
        return [term for term, _ in Counter(terms).most_common(limit)]

    def _bm25_scores(self, query_terms: List[str], chunks: List[Dict]) -> Dict[str, float]:
        if not query_terms:
            return {}

        document_terms = {chunk['id']: chunk['terms'] for chunk in chunks}
        document_lengths = {chunk_id: len(terms) for chunk_id, terms in document_terms.items()}
        avg_doc_len = sum(document_lengths.values()) / len(document_lengths)
        doc_freq = defaultdict(int)

        for terms in document_terms.values():
            for term in set(terms):
                doc_freq[term] += 1

        scores = {}
        total_docs = len(chunks)
        for chunk_id, terms in document_terms.items():
            term_counts = Counter(terms)
            score = 0.0
            for term in query_terms:
                if term not in term_counts:
                    continue
                idf = math.log(1 + (total_docs - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
                tf = term_counts[term]
                denominator = tf + self.bm25_k1 * (1 - self.bm25_b + self.bm25_b * document_lengths[chunk_id] / avg_doc_len)
                score += idf * tf * (self.bm25_k1 + 1) / denominator
            if score > 0:
                scores[chunk_id] = score
        return self._normalize_scores(scores)

    def _rerank(self, candidate_ids: set, chunks: List[Dict], bm25_scores: Dict[str, float], vector_scores: Dict[str, float]) -> List[Dict]:
        chunks_by_id = {chunk['id']: chunk for chunk in chunks}
        topic_hits = Counter(chunks_by_id[chunk_id]['topic_id'] for chunk_id in candidate_ids if chunk_id in chunks_by_id)
        now = datetime.now()
        ranked = []

        for chunk_id in candidate_ids:
            chunk = chunks_by_id.get(chunk_id)
            if not chunk:
                continue

            recency_score = self._recency_score(chunk['end_time'], now)
            topic_bonus = min(topic_hits[chunk['topic_id']] / 5, 1.0)
            score = (
                0.35 * bm25_scores.get(chunk_id, 0.0) +
                0.45 * max(vector_scores.get(chunk_id, 0.0), 0.0) +
                0.10 * recency_score +
                0.10 * topic_bonus
            )
            ranked.append({**chunk, 'score': score})

        return sorted(ranked, key=lambda item: item['score'], reverse=True)

    def _format_search_results(self, chunks: List[Dict]) -> str:
        if not chunks:
            return "未检索到相关历史上下文。"

        lines = ["相关历史上下文："]
        for index, chunk in enumerate(chunks, 1):
            lines.append(f"\n--- 片段 {index} | score={chunk['score']:.3f} ---")
            lines.append(chunk['chunk_text'])
        return '\n'.join(lines)

    def _load_chunks(self, contact_id: str = None) -> List[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        query = '''
            SELECT id, topic_id, contact_id, chunk_text, start_time, end_time, message_count, terms_json, embedding_json
            FROM rag_chunks
        '''
        params = ()
        if contact_id:
            query += ' WHERE contact_id = ?'
            params = (contact_id,)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [{
            'id': row[0],
            'topic_id': row[1],
            'contact_id': row[2],
            'chunk_text': row[3],
            'start_time': row[4],
            'end_time': row[5],
            'message_count': row[6],
            'terms': json.loads(row[7]),
            'embedding': json.loads(row[8]) if row[8] else []
        } for row in rows]

    async def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        client = AsyncOpenAI(
            api_key=self.embedding_cfg['api_key'],
            base_url=self.embedding_cfg.get('base_url', 'https://api.openai.com/v1')
        )
        response = await client.embeddings.create(
            model=self.embedding_cfg['model'],
            input=texts
        )
        return [item.embedding for item in response.data]

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(value * value for value in vec1))
        norm2 = math.sqrt(sum(value * value for value in vec2))
        return dot_product / (norm1 * norm2) if norm1 > 0 and norm2 > 0 else 0.0

    def _normalize_scores(self, scores: Dict[str, float]) -> Dict[str, float]:
        if not scores:
            return {}
        max_score = max(scores.values())
        return {key: value / max_score for key, value in scores.items()} if max_score > 0 else scores

    def _top_ids(self, scores: Dict[str, float], limit: int) -> set:
        return {chunk_id for chunk_id, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit]}

    def _recency_score(self, timestamp: str, now: datetime) -> float:
        try:
            end_time = datetime.fromisoformat(timestamp)
        except ValueError:
            return 0.0
        days = max((now - end_time).days, 0)
        return math.exp(-days / 180)

    def _minutes_between(self, earlier: str, later: str) -> float:
        try:
            start = datetime.fromisoformat(earlier)
            end = datetime.fromisoformat(later)
            return (end - start).total_seconds() / 60
        except ValueError:
            return 0.0

    def _make_topic_id(self, contact_id: str, topic: List[Dict]) -> str:
        raw = f"{contact_id}|{topic[0]['timestamp']}|{topic[-1]['timestamp']}|{len(topic)}"
        return hashlib.sha1(raw.encode('utf-8')).hexdigest()

    def _make_chunk_id(self, contact_id: str, chunk: List[Dict]) -> str:
        raw = f"{contact_id}|{chunk[0]['timestamp']}|{chunk[-1]['timestamp']}|{len(chunk)}|{chunk[0]['message']}|{chunk[-1]['message']}"
        return hashlib.sha1(raw.encode('utf-8')).hexdigest()

def create_rag_service() -> RAGService:
    return RAGService()
