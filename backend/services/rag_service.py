from typing import List, Dict
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict
from openai import AsyncOpenAI
from ollama import AsyncClient
from pydantic import BaseModel, Field
from urllib import request as urlrequest
from urllib.error import URLError, HTTPError
import jieba
import hashlib
import json
import math
import re
import sqlite3
import asyncio
from backend.config import config

class TopicSplitResult(BaseModel):
    split_after_indices: List[int] = Field(default_factory=list)

class TopicSummaryResult(BaseModel):
    summary: str = ''
    keywords: List[str] = Field(default_factory=list)
    salience: float = 0.5
    category: str = '日常对话'
    indexable: bool = True

class RAGService:
    STOPWORDS = {
        '我', '你', '他', '她', '它', '俺', '咱', '我们', '你们', '他们', '她们', '自己',
        '这个', '那个', '这些', '那些', '这里', '那里', '什么', '怎么', '为什么', '哪个',
        '就是', '然后', '所以', '因为', '但是', '不过', '如果', '还是', '或者', '而且',
        '一个', '一下', '一样', '一直', '已经', '现在', '时候', '感觉', '觉得', '可能',
        '可以', '应该', '需要', '没有', '不是', '也是', '还有', '比较', '其实', '真的',
        '啊', '呀', '吗', '呢', '吧', '啦', '哦', '嗯', '哈', '哈哈', '哈哈哈', '额', '呃',
        '的', '了', '和', '是', '在', '就', '都', '也', '还', '很', '又', '再', '会', '把',
        '被', '给', '跟', '对', '从', '到', '有', '没', '不', '要', '去', '来', '说', '看',
        '引用', '罅隙', '链接', '知道', '本来', '表情', '图片', '消息', '聊天', '开始',
        '刚刚', '甚至', '有点', '相信', '早年', '空间', '这么', '那么', '这样', '那样',
        '用户', '对方', '双方', 'contact', 'user'
    }
    TOPIC_TERM_LIMIT = 6
    CHUNK_TERM_LIMIT = 8

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
        self.topic_top_k = rag_cfg.get('topic_top_k', 5)
        self.topic_expand_chunk_limit = rag_cfg.get('topic_expand_chunk_limit', 6)
        self.embedding_batch_size = rag_cfg.get('embedding_batch_size', 10)
        self.final_top_k = rag_cfg.get('final_top_k', 5)
        self.final_score_relative_threshold = rag_cfg.get('final_score_relative_threshold', 0.75)
        self.final_score_min = rag_cfg.get('final_score_min', 0.38)
        self.topic_segmentation_cfg = rag_cfg.get('topic_segmentation', {})
        self.topic_segmentation_enabled = self.topic_segmentation_cfg.get('enabled', False)
        self.topic_segmentation_window_size = self.topic_segmentation_cfg.get('window_size', 40)
        self.topic_segmentation_timeout = self.topic_segmentation_cfg.get('timeout_seconds', 120)
        self.topic_summary_cfg = rag_cfg.get('topic_summary', {})
        self.topic_summary_enabled = self.topic_summary_cfg.get('enabled', False)
        self.topic_summary_timeout = self.topic_summary_cfg.get('timeout_seconds', 120)
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
                terms_json TEXT NOT NULL DEFAULT '[]',
                salience REAL NOT NULL DEFAULT 0.5,
                category TEXT NOT NULL DEFAULT '',
                indexable INTEGER NOT NULL DEFAULT 1,
                embedding_json TEXT,
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

        self._ensure_column(cursor, 'rag_topics', 'terms_json', "TEXT NOT NULL DEFAULT '[]'")
        self._ensure_column(cursor, 'rag_topics', 'salience', 'REAL NOT NULL DEFAULT 0.5')
        self._ensure_column(cursor, 'rag_topics', 'category', "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(cursor, 'rag_topics', 'indexable', 'INTEGER NOT NULL DEFAULT 1')
        self._ensure_column(cursor, 'rag_topics', 'embedding_json', 'TEXT')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rag_chunks_contact ON rag_chunks(contact_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rag_chunks_topic ON rag_chunks(topic_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rag_topics_contact ON rag_topics(contact_id)')
        conn.commit()
        conn.close()

    def _ensure_column(self, cursor: sqlite3.Cursor, table: str, column: str, column_type: str):
        cursor.execute(f'PRAGMA table_info({table})')
        existing_columns = {row[1] for row in cursor.fetchall()}
        if column not in existing_columns:
            cursor.execute(f'ALTER TABLE {table} ADD COLUMN {column} {column_type}')

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def insert_records(self, contact_id: str, records: List[Dict]):
        if not records:
            return

        sorted_records = sorted(records, key=lambda record: record['timestamp'])
        strong_segments = self._split_by_strong_boundaries(sorted_records)
        total_topics = 0
        total_chunks = 0
        inserted_topics = 0
        inserted_chunks = 0
        embedded_texts = 0

        for segment_index, segment in enumerate(strong_segments, 1):
            topic_records = []
            topic_records.extend(self._split_segment_by_llm(segment))
            topics = []
            chunks = []

            for topic in topic_records:
                topic_id = self._make_topic_id(contact_id, topic)
                topic_summary = self._summarize_topic(topic)
                topic_terms = self._topic_terms(topic, topic_summary)
                topic_text = self._format_topic(topic, topic_summary, topic_terms)
                topic_embedding_text = self._format_topic_embedding_text(topic, topic_summary, topic_terms)
                topics.append({
                    'id': topic_id,
                    'contact_id': contact_id,
                    'summary': topic_summary,
                    'text': topic_text,
                    'embedding_text': topic_embedding_text,
                    'records': topic,
                    'terms': topic_terms,
                    'kind': 'topic'
                })

                for sub_chunk in self._split_topic_chunks(topic):
                    chunk_text = self._format_chunk(sub_chunk)
                    chunks.append({
                        'id': self._make_chunk_id(contact_id, sub_chunk),
                        'topic_id': topic_id,
                        'contact_id': contact_id,
                        'topic_summary': topic_summary,
                        'records': sub_chunk,
                        'text': chunk_text,
                        'embedding_text': self._format_chunk_embedding_text(sub_chunk),
                        'terms': self._chunk_terms(sub_chunk),
                        'kind': 'chunk'
                    })

            total_topics += len(topics)
            total_chunks += len(chunks)
            existing_topic_ids = self._existing_ids('rag_topics', [topic['id'] for topic in topics])
            existing_chunk_ids = self._existing_ids('rag_chunks', [chunk['id'] for chunk in chunks])
            new_topics = [topic for topic in topics if topic['id'] not in existing_topic_ids]
            new_chunks = [chunk for chunk in chunks if chunk['id'] not in existing_chunk_ids]
            pending_items = new_topics + new_chunks

            for batch in self._embedding_item_batches(pending_items):
                embeddings = asyncio.run(self._get_embeddings([item['embedding_text'] for item in batch]))
                self._insert_embedded_items(batch, embeddings)
                embedded_texts += len(batch)
                inserted_topics += sum(1 for item in batch if item['kind'] == 'topic')
                inserted_chunks += sum(1 for item in batch if item['kind'] == 'chunk')

            if segment_index % 50 == 0 or segment_index == len(strong_segments):
                print(
                    f"  RAG 构建进度：{segment_index}/{len(strong_segments)} 个分段"
                    f"，已写入 {inserted_topics} 个话题 / {inserted_chunks} 个 chunk"
                )

        print(
            f"✓ Hybrid RAG：{len(records)} 条消息 → {total_topics} 个话题 → {total_chunks} 个 chunk"
            f"，新增 {inserted_topics} 个话题 / {inserted_chunks} 个 chunk，embedding {embedded_texts} 段文本"
        )

    def _embedding_item_batches(self, items: List[Dict]) -> List[List[Dict]]:
        batch_size = max(int(self.embedding_batch_size), 1)
        return [items[start:start + batch_size] for start in range(0, len(items), batch_size)]

    def _insert_embedded_items(self, items: List[Dict], embeddings: List[List[float]]):
        conn = self._get_connection()
        cursor = conn.cursor()

        for item, embedding in zip(items, embeddings):
            records = item['records']
            if item['kind'] == 'topic':
                cursor.execute('''
                    INSERT OR IGNORE INTO rag_topics
                    (id, contact_id, topic_summary, start_time, end_time, message_count, terms_json, salience, category, indexable, embedding_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    item['id'], item['contact_id'], item['summary']['summary'],
                    records[0]['timestamp'], records[-1]['timestamp'], len(records),
                    json.dumps(item['terms'], ensure_ascii=False),
                    item['summary']['salience'], item['summary']['category'], int(item['summary']['indexable']),
                    json.dumps(embedding)
                ))
            else:
                cursor.execute('''
                    INSERT OR IGNORE INTO rag_chunks
                    (id, topic_id, contact_id, chunk_text, start_time, end_time, message_count, terms_json, embedding_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    item['id'], item['topic_id'], item['contact_id'], item['text'],
                    records[0]['timestamp'], records[-1]['timestamp'], len(records),
                    json.dumps(item['terms'], ensure_ascii=False),
                    json.dumps(embedding)
                ))

        conn.commit()
        conn.close()

    def search(self, query: str, mode: str = "hybrid") -> str:
        chunks = self._load_chunks()
        if not chunks:
            return ""

        topics = self._load_topics()
        query_terms = self._tokenize(query)
        bm25_scores = self._bm25_scores(query_terms, chunks)
        topic_bm25_scores = self._bm25_scores(query_terms, topics)
        vector_scores = {}
        topic_vector_scores = {}

        if mode in ["hybrid", "vector"]:
            query_embedding = asyncio.run(self._get_embeddings([query]))[0]
            vector_scores = {
                chunk['id']: self._cosine_similarity(query_embedding, chunk['embedding'])
                for chunk in chunks if chunk['embedding']
            }
            topic_vector_scores = {
                topic['id']: self._cosine_similarity(query_embedding, topic['embedding'])
                for topic in topics if topic['embedding']
            }

        if mode == "bm25":
            candidate_ids = self._top_ids(bm25_scores, self.bm25_top_k)
            topic_ids = self._top_ids(topic_bm25_scores, self.topic_top_k)
        elif mode == "vector":
            candidate_ids = self._top_ids(vector_scores, self.vector_top_k)
            topic_ids = self._top_ids(topic_vector_scores, self.topic_top_k)
        else:
            candidate_ids = self._top_ids(bm25_scores, self.bm25_top_k) | self._top_ids(vector_scores, self.vector_top_k)
            topic_ids = self._top_ids(topic_bm25_scores, self.topic_top_k) | self._top_ids(topic_vector_scores, self.topic_top_k)

        topic_scores = self._merge_scores(topic_bm25_scores, topic_vector_scores)
        candidate_ids |= self._expand_topic_chunks(topic_ids, chunks, topic_scores)

        ranked = self._rerank(candidate_ids, chunks, bm25_scores, vector_scores, topic_scores)
        return self._format_search_results(self._select_final_chunks(ranked))

    def _existing_ids(self, table: str, ids: List[str]) -> set:
        if not ids:
            return set()

        conn = self._get_connection()
        cursor = conn.cursor()
        existing_ids = set()

        for start in range(0, len(ids), 900):
            batch = ids[start:start + 900]
            placeholders = ','.join('?' for _ in batch)
            cursor.execute(f'SELECT id FROM {table} WHERE id IN ({placeholders})', batch)
            existing_ids.update(row[0] for row in cursor.fetchall())

        conn.close()
        return existing_ids

    def _split_topics(self, records: List[Dict]) -> List[List[Dict]]:
        strong_segments = self._split_by_strong_boundaries(records)
        topics = []
        for segment in strong_segments:
            topics.extend(self._split_segment_by_llm(segment))
        return topics

    def _split_by_strong_boundaries(self, records: List[Dict]) -> List[List[Dict]]:
        segments = []
        current_segment = [records[0]]

        for record in records[1:]:
            previous = current_segment[-1]
            segment_chars = sum(len(item['message']) for item in current_segment)
            should_split = (
                self._minutes_between(previous['timestamp'], record['timestamp']) > self.time_gap_minutes or
                len(current_segment) >= self.max_topic_messages or
                segment_chars >= self.max_topic_chars
            )

            if should_split:
                segments.append(current_segment)
                current_segment = [record]
            else:
                current_segment.append(record)

        if current_segment:
            segments.append(current_segment)
        return segments

    def _split_segment_by_llm(self, records: List[Dict]) -> List[List[Dict]]:
        if not self.topic_segmentation_enabled or len(records) <= 1:
            return [records]

        topics = []
        start = 0
        window_size = max(int(self.topic_segmentation_window_size), 2)
        while start < len(records):
            end = min(start + window_size, len(records))
            window = records[start:end]
            split_indices = self._llm_topic_split_indices(window)
            window_start = 0
            for split_index in split_indices:
                if 0 <= split_index < len(window) - 1:
                    topics.append(window[window_start:split_index + 1])
                    window_start = split_index + 1
            if window_start < len(window):
                topics.append(window[window_start:])
            start = end

        return [topic for topic in topics if topic]

    def _llm_topic_split_indices(self, records: List[Dict]) -> List[int]:
        try:
            result = asyncio.run(self._request_topic_segmentation(records))
            return self._valid_topic_split_indices(result.split_after_indices, len(records))
        except Exception as exc:
            print(f"⚠ LLM 话题切分失败，保守合并当前窗口：{exc}")
            return []

    async def _request_topic_segmentation(self, records: List[Dict]) -> TopicSplitResult:
        provider = self.topic_segmentation_cfg.get('provider')
        if provider != 'ollama':
            return TopicSplitResult()

        prompt = self._build_topic_segmentation_prompt(records)
        base_url = self.topic_segmentation_cfg.get('base_url', 'http://localhost:11434')
        model = self.topic_segmentation_cfg.get('model', 'qwen3.5:9b')
        client = AsyncClient(host=base_url)
        response = await client.chat(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            format=TopicSplitResult.model_json_schema(),
            options={
                'temperature': 0,
                'num_predict': 128,
            },
            think=False
        )
        return TopicSplitResult.model_validate_json(response.message.content)

    def _valid_topic_split_indices(self, indices: List[int], record_count: int) -> List[int]:
        valid_indices = []
        for index in indices:
            if isinstance(index, int) and 0 <= index < record_count - 1:
                valid_indices.append(index)
        return sorted(set(valid_indices))

    def _build_topic_segmentation_prompt(self, records: List[Dict]) -> str:
        lines = [
            '你是聊天记录话题切分器。判断下面连续消息中，哪些消息之后应该切换到新话题。',
            '只在语义主题明显变化时切分；短句补充、自我介绍、围绕同一背景的追问和回应应保持同一话题。',
            '返回严格JSON：{"split_after_indices": [整数索引]}。索引是下面消息前的方括号数字，表示该条消息之后切分。',
            ''
        ]
        for index, record in enumerate(records):
            message = record['message'].replace('\n', ' ').strip()
            lines.append(f"[{index}] {record['sender']}: {message}")
        return '\n'.join(lines)

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

    def _summarize_topic(self, topic: List[Dict]) -> Dict:
        if self.topic_summary_enabled:
            try:
                result = asyncio.run(self._request_topic_summary(topic))
                summary = result.summary.strip()
                keywords = self._unique_terms(result.keywords)
                if summary:
                    return {
                        'summary': summary,
                        'keywords': keywords,
                        'salience': self._normalize_salience(result.salience),
                        'category': result.category.strip() or '日常对话',
                        'indexable': bool(result.indexable)
                    }
            except Exception as exc:
                print(f"⚠ LLM 话题摘要失败，使用关键词摘要：{exc}")
        return self._fallback_topic_summary(topic)

    async def _request_topic_summary(self, topic: List[Dict]) -> TopicSummaryResult:
        provider = self.topic_summary_cfg.get('provider')
        if provider != 'ollama':
            return TopicSummaryResult()

        prompt = self._build_topic_summary_prompt(topic)
        base_url = self.topic_summary_cfg.get('base_url', 'http://localhost:11434')
        model = self.topic_summary_cfg.get('model', 'qwen3.5:9b')
        client = AsyncClient(host=base_url)
        response = await client.chat(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            format=TopicSummaryResult.model_json_schema(),
            options={
                'temperature': 0,
                'num_predict': 256,
            },
            think=False
        )
        return TopicSummaryResult.model_validate_json(response.message.content)

    def _build_topic_summary_prompt(self, topic: List[Dict]) -> str:
        lines = [
            '你是聊天记录话题摘要器。根据下面同一话题内的连续消息，生成自然、简短、语义明确的话题摘要。',
            '摘要应概括双方实际讨论的主题，不要罗列无意义口癖、表情或碎片词。',
            'summary 控制在 60 个中文字符以内；keywords 给出 0 到 6 个真正有检索价值的语义关键词，只保留人物、地点、事件、偏好、关系、计划、经历等可用于未来查询的标签。',
            '不要输出寒暄词、动作泛词、语气词、媒介噪声或拆碎的子词，例如：引用、链接、表情、图片、知道、本来、聊天、开始、第二、故乡。',
            'salience 是 0 到 1 的信息价值分数：寒暄、表情、打招呼、无实质内容为 0.0-0.25；普通闲聊为 0.25-0.45；包含偏好、经历、地点、关系、计划、事件为 0.55-0.85；强长期记忆或重要事件为 0.85-1.0。',
            'category 用短中文类别，如 寒暄闲聊、生活偏好、个人经历、关系互动、计划安排、地点经历、重要事件。',
            'indexable 表示是否适合作为历史记忆召回；纯寒暄、表情、无信息量闲聊设为 false，但不要因为语气日常就设为 false。',
            '返回严格JSON：{"summary": "摘要", "keywords": ["关键词"], "salience": 0.0, "category": "类别", "indexable": false}。',
            ''
        ]
        for index, record in enumerate(topic):
            message = record['message'].replace('\n', ' ').strip()
            lines.append(f"[{index}] {record['sender']}: {message}")
        return '\n'.join(lines)

    def _fallback_topic_summary(self, topic: List[Dict]) -> Dict:
        start = topic[0]['timestamp']
        end = topic[-1]['timestamp']
        keywords = self._top_terms(' '.join(record['message'] for record in topic), 8)
        summary = f"{start} 至 {end}，双方围绕 {', '.join(keywords) or '日常对话'} 展开交流，共 {len(topic)} 条消息。"
        return {
            'summary': summary,
            'keywords': keywords,
            'salience': 0.5,
            'category': '日常对话',
            'indexable': True
        }

    def _normalize_salience(self, salience: float) -> float:
        try:
            return min(max(float(salience), 0.0), 1.0)
        except (TypeError, ValueError):
            return 0.5

    def _topic_terms(self, records: List[Dict], topic_summary: Dict) -> List[str]:
        llm_keywords = topic_summary.get('keywords', []) if topic_summary else []
        terms = self._semantic_terms(llm_keywords, self.TOPIC_TERM_LIMIT)
        if len(terms) < 3:
            message_terms = self._top_terms(' '.join(record['message'] for record in records), self.TOPIC_TERM_LIMIT)
            terms = self._semantic_terms([*terms, *message_terms], self.TOPIC_TERM_LIMIT)
        return terms

    def _chunk_terms(self, records: List[Dict]) -> List[str]:
        message_terms = self._top_terms(' '.join(record['message'] for record in records), self.CHUNK_TERM_LIMIT * 2)
        return self._semantic_terms(message_terms, self.CHUNK_TERM_LIMIT)

    def _semantic_terms(self, terms: List[str], limit: int) -> List[str]:
        unique_terms = self._unique_terms(terms)
        compact_terms = []
        for term in unique_terms:
            if any(term != existing and term in existing for existing in compact_terms):
                continue
            compact_terms = [existing for existing in compact_terms if not (term != existing and existing in term)]
            compact_terms.append(term)
            if len(compact_terms) >= limit:
                break
        return compact_terms

    def _unique_terms(self, terms: List[str]) -> List[str]:
        unique_terms = []
        seen = set()
        for term in terms:
            normalized = term.strip()
            key = normalized.lower()
            if not normalized or key in seen or not self._is_valid_term(normalized):
                continue
            seen.add(key)
            unique_terms.append(normalized)
        return unique_terms

    def _format_topic(self, records: List[Dict], topic_summary: Dict, topic_terms: List[str]) -> str:
        lines = ["=== 历史话题 ==="]
        lines.append(f"话题摘要: {topic_summary['summary']}")
        lines.append(f"时间范围: {records[0]['timestamp']} ~ {records[-1]['timestamp']}")
        lines.append(f"消息数量: {len(records)}")
        lines.append(f"关键词: {', '.join(topic_terms)}")
        return '\n'.join(lines)

    def _format_topic_embedding_text(self, records: List[Dict], topic_summary: Dict, topic_terms: List[str]) -> str:
        return f"话题摘要: {topic_summary['summary']}\n关键词: {', '.join(topic_terms)}"

    def _format_chunk_embedding_text(self, records: List[Dict]) -> str:
        return '\n'.join(f"{record['sender']}: {record['message']}" for record in records)

    def _format_chunk(self, records: List[Dict]) -> str:
        return '\n'.join(f"[{record['timestamp']}] {record['sender']}: {record['message']}" for record in records)

    def _tokenize(self, text: str) -> List[str]:
        lowered = text.lower()
        ascii_terms = [term for term in re.findall(r'[a-z][a-z0-9_]+', lowered) if self._is_valid_term(term)]
        number_terms = [term for term in re.findall(r'\d+(?:\.\d+)?', lowered) if self._is_valid_number_term(term)]
        chinese_terms = [term for term in jieba.lcut(text) if self._is_valid_term(term)]
        return ascii_terms + number_terms + chinese_terms

    def _is_valid_term(self, term: str) -> bool:
        term = term.strip().lower()
        if not term or term in self.STOPWORDS:
            return False
        if re.fullmatch(r'[\W_]+', term):
            return False
        if re.fullmatch(r'\d+', term):
            return self._is_valid_number_term(term)
        if re.fullmatch(r'[a-z0-9_]+', term):
            return len(term) >= 2 and any(char.isalpha() for char in term)
        if not any('一' <= char <= '鿿' for char in term):
            return False
        if len(term) < 2:
            return False
        if len(term) == 2 and term in {'第二', '故乡', '本地', '以来', '这句', '哪里', '工程'}:
            return False
        return True

    def _is_valid_number_term(self, term: str) -> bool:
        digits = re.sub(r'\D', '', term)
        if len(digits) < 4:
            return False
        if digits.startswith(('19', '20')) and len(digits) == 4:
            return True
        return len(digits) >= 6

    def _top_terms(self, text: str, limit: int) -> List[str]:
        terms = self._tokenize(text)
        return [term for term, _ in Counter(terms).most_common(limit)]

    def _bm25_scores(self, query_terms: List[str], documents: List[Dict]) -> Dict[str, float]:
        if not query_terms or not documents:
            return {}

        document_terms = {document['id']: document['terms'] for document in documents}
        document_lengths = {document_id: len(terms) for document_id, terms in document_terms.items()}
        avg_doc_len = sum(document_lengths.values()) / len(document_lengths)
        if avg_doc_len == 0:
            return {}

        doc_freq = defaultdict(int)
        for terms in document_terms.values():
            for term in set(terms):
                doc_freq[term] += 1

        scores = {}
        total_docs = len(documents)
        for document_id, terms in document_terms.items():
            term_counts = Counter(terms)
            score = 0.0
            for term in query_terms:
                if term not in term_counts:
                    continue
                idf = math.log(1 + (total_docs - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
                tf = term_counts[term]
                denominator = tf + self.bm25_k1 * (1 - self.bm25_b + self.bm25_b * document_lengths[document_id] / avg_doc_len)
                score += idf * tf * (self.bm25_k1 + 1) / denominator
            if score > 0:
                scores[document_id] = score
        return self._normalize_scores(scores)

    def _expand_topic_chunks(self, topic_ids: set, chunks: List[Dict], topic_scores: Dict[str, float]) -> set:
        expanded_ids = set()
        chunks_by_topic = defaultdict(list)
        for chunk in chunks:
            chunks_by_topic[chunk['topic_id']].append(chunk)

        ranked_topic_ids = sorted(topic_ids, key=lambda topic_id: topic_scores.get(topic_id, 0.0), reverse=True)
        for topic_id in ranked_topic_ids:
            topic_chunks = sorted(
                chunks_by_topic.get(topic_id, []),
                key=lambda chunk: (chunk['start_time'], chunk['id'])
            )
            for chunk in topic_chunks[:self.topic_expand_chunk_limit]:
                expanded_ids.add(chunk['id'])
        return expanded_ids

    def _rerank(self, candidate_ids: set, chunks: List[Dict], bm25_scores: Dict[str, float], vector_scores: Dict[str, float], topic_scores: Dict[str, float]) -> List[Dict]:
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
            parent_score = topic_scores.get(chunk['topic_id'], 0.0)
            salience = self._normalize_salience(chunk.get('salience', 0.5))
            salience_multiplier = 0.35 + 0.65 * salience
            if not chunk.get('indexable', True):
                salience_multiplier *= 0.45
            score = salience_multiplier * (
                0.30 * bm25_scores.get(chunk_id, 0.0) +
                0.40 * max(vector_scores.get(chunk_id, 0.0), 0.0) +
                0.10 * recency_score +
                0.10 * topic_bonus +
                0.10 * parent_score
            )
            ranked.append({**chunk, 'score': score})

        return sorted(ranked, key=lambda item: item['score'], reverse=True)

    def _select_final_chunks(self, ranked: List[Dict]) -> List[Dict]:
        if not ranked:
            return []

        selected = [ranked[0]]
        top_score = ranked[0]['score']
        relative_cutoff = top_score * self.final_score_relative_threshold
        cutoff = max(relative_cutoff, self.final_score_min)

        for chunk in ranked[1:]:
            if len(selected) >= self.final_top_k:
                break
            if chunk['score'] >= cutoff:
                selected.append(chunk)
        return selected

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
            SELECT c.id, c.topic_id, c.contact_id, c.chunk_text, c.start_time, c.end_time, c.message_count,
                   c.terms_json, c.embedding_json, COALESCE(t.salience, 0.5), COALESCE(t.category, ''), COALESCE(t.indexable, 1)
            FROM rag_chunks c
            LEFT JOIN rag_topics t ON c.topic_id = t.id
        '''
        params = ()
        if contact_id:
            query += ' WHERE c.contact_id = ?'
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
            'embedding': json.loads(row[8]) if row[8] else [],
            'salience': row[9],
            'category': row[10],
            'indexable': bool(row[11])
        } for row in rows]

    def _load_topics(self, contact_id: str = None) -> List[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        query = '''
            SELECT id, contact_id, topic_summary, start_time, end_time, message_count, terms_json,
                   salience, category, indexable, embedding_json
            FROM rag_topics
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
            'contact_id': row[1],
            'topic_summary': row[2],
            'start_time': row[3],
            'end_time': row[4],
            'message_count': row[5],
            'terms': json.loads(row[6]) if row[6] else [],
            'salience': row[7],
            'category': row[8],
            'indexable': bool(row[9]),
            'embedding': json.loads(row[10]) if row[10] else []
        } for row in rows]

    async def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        provider = self.embedding_cfg.get('provider')
        if provider == 'ollama':
            return await asyncio.to_thread(self._get_ollama_embeddings, texts)
        return await self._get_openai_compatible_embeddings(texts)

    async def _get_openai_compatible_embeddings(self, texts: List[str]) -> List[List[float]]:
        client = AsyncOpenAI(
            api_key=self.embedding_cfg['api_key'],
            base_url=self.embedding_cfg.get('base_url', 'https://api.openai.com/v1')
        )
        embeddings = []
        batch_size = max(int(self.embedding_batch_size), 1)

        for start in range(0, len(texts), batch_size):
            batch = texts[start:start + batch_size]
            response = await client.embeddings.create(
                model=self.embedding_cfg['model'],
                input=batch
            )
            embeddings.extend(item.embedding for item in response.data)

        return embeddings

    def _get_ollama_embeddings(self, texts: List[str]) -> List[List[float]]:
        embeddings = []
        base_url = self.embedding_cfg.get('base_url', 'http://localhost:11434').rstrip('/')
        model = self.embedding_cfg['model']
        batch_size = max(int(self.embedding_batch_size), 1)

        for start in range(0, len(texts), batch_size):
            batch = texts[start:start + batch_size]
            embeddings.extend(self._request_ollama_embeddings(base_url, model, batch))
        return embeddings

    def _request_ollama_embeddings(self, base_url: str, model: str, texts: List[str]) -> List[List[float]]:
        payload = json.dumps({'model': model, 'input': texts}).encode('utf-8')
        req = urlrequest.Request(
            f'{base_url}/api/embed',
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        try:
            with urlrequest.urlopen(req, timeout=120) as response:
                data = json.loads(response.read().decode('utf-8'))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            return [self._request_ollama_embedding(base_url, model, text) for text in texts]

        if 'embeddings' in data:
            return data['embeddings']
        if 'embedding' in data:
            return [data['embedding']]
        raise ValueError('Ollama embedding 响应缺少 embeddings 字段')

    def _request_ollama_embedding(self, base_url: str, model: str, text: str) -> List[float]:
        payload = json.dumps({'model': model, 'prompt': text}).encode('utf-8')
        req = urlrequest.Request(
            f'{base_url}/api/embeddings',
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urlrequest.urlopen(req, timeout=120) as response:
            data = json.loads(response.read().decode('utf-8'))
        if 'embedding' not in data:
            raise ValueError('Ollama embedding 响应缺少 embedding 字段')
        return data['embedding']

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

    def _merge_scores(self, bm25_scores: Dict[str, float], vector_scores: Dict[str, float]) -> Dict[str, float]:
        merged = {}
        for item_id in set(bm25_scores) | set(vector_scores):
            merged[item_id] = 0.45 * bm25_scores.get(item_id, 0.0) + 0.55 * max(vector_scores.get(item_id, 0.0), 0.0)
        return merged

    def _top_ids(self, scores: Dict[str, float], limit: int) -> set:
        return {item_id for item_id, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit]}

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
