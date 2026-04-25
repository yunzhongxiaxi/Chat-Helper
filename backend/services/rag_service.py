from typing import List, Dict
from pathlib import Path
from lightrag import LightRAG, QueryParam
from lightrag.llm import openai_complete_if_cache, openai_embedding
from backend.config import config
import asyncio
import numpy as np

class RAGService:
    def __init__(self):
        self.working_dir = Path(config.lightrag.get('working_dir', './data/lightrag'))
        self.working_dir.mkdir(parents=True, exist_ok=True)

        entity_cfg = config.get_model_config('entity_extraction')
        self.embedding_cfg = config.get_model_config('embedding')

        self.rag = LightRAG(
            working_dir=str(self.working_dir),
            llm_model_func=self._create_llm_func(entity_cfg),
            embedding_func=self._create_embedding_func(self.embedding_cfg)
        )

        self.similarity_threshold = 0.75
        self.max_chunk_size = 20
        self.min_chunk_size = 3

    def _create_llm_func(self, entity_cfg: dict):
        async def llm_func(prompt, system_prompt=None, **kwargs):
            return await openai_complete_if_cache(
                model=entity_cfg['model'],
                prompt=prompt,
                system_prompt=system_prompt,
                api_key=entity_cfg['api_key'],
                base_url=entity_cfg.get('base_url', 'https://api.openai.com/v1'),
                **kwargs
            )
        return llm_func

    def _create_embedding_func(self, embedding_cfg: dict):
        async def embedding_func(texts: List[str]):
            return await openai_embedding(
                texts=texts,
                model=embedding_cfg['model'],
                api_key=embedding_cfg['api_key'],
                base_url=embedding_cfg.get('base_url', 'https://api.openai.com/v1')
            )
        return embedding_func

    def insert_records(self, contact_id: str, records: List[Dict]):
        """将聊天记录按语义相关性分片后插入 RAG"""
        chunks = asyncio.run(self._chunk_by_semantic_similarity(records))

        print(f"✓ 智能分片：{len(records)} 条消息 → {len(chunks)} 个语义 chunk")

        for i, chunk in enumerate(chunks):
            chunk_text = self._format_chunk(chunk, i)
            self.rag.insert(chunk_text)

    def search(self, query: str, mode: str = "hybrid") -> str:
        return self.rag.query(query, param=QueryParam(mode=mode))

    async def _chunk_by_semantic_similarity(self, records: List[Dict]) -> List[List[Dict]]:
        """基于语义相似度将聊天记录分片

        策略：
        1. 计算相邻消息的语义相似度
        2. 相似度高于阈值 → 同一个 chunk
        3. 相似度低于阈值 → 新 chunk
        4. 限制 chunk 大小避免过长
        """
        if len(records) <= self.min_chunk_size:
            return [records]

        messages = [record['message'] for record in records]
        embeddings = await self._get_embeddings(messages)

        chunks = []
        current_chunk = [records[0]]

        for i in range(1, len(records)):
            similarity = self._cosine_similarity(embeddings[i-1], embeddings[i])

            should_continue_chunk = (
                similarity >= self.similarity_threshold and
                len(current_chunk) < self.max_chunk_size
            )

            if should_continue_chunk:
                current_chunk.append(records[i])
            else:
                if len(current_chunk) >= self.min_chunk_size:
                    chunks.append(current_chunk)
                    current_chunk = [records[i]]
                else:
                    current_chunk.append(records[i])

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    async def _get_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """批量获取文本的 embedding"""
        embedding_func = self._create_embedding_func(self.embedding_cfg)
        embeddings = await embedding_func(texts)
        return [np.array(emb) for emb in embeddings]

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """计算两个向量的余弦相似度"""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        return dot_product / (norm1 * norm2) if norm1 > 0 and norm2 > 0 else 0.0

    def _format_chunk(self, records: List[Dict], chunk_id: int) -> str:
        """格式化一个 chunk 的内容"""
        lines = [f"=== 对话片段 {chunk_id + 1} ==="]
        lines.append(f"时间范围: {records[0]['timestamp']} ~ {records[-1]['timestamp']}")
        lines.append(f"消息数量: {len(records)}")
        lines.append("")

        for record in records:
            lines.append(f"[{record['timestamp']}] {record['sender']}: {record['message']}")

        return '\n'.join(lines)

def create_rag_service() -> RAGService:
    return RAGService()
