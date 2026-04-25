from typing import List, Dict
from pathlib import Path
from lightrag import LightRAG, QueryParam
from lightrag.llm import openai_complete_if_cache, openai_embedding
from backend.config import config

class RAGService:
    def __init__(self):
        self.working_dir = Path(config.lightrag.get('working_dir', './data/lightrag'))
        self.working_dir.mkdir(parents=True, exist_ok=True)

        entity_cfg = config.get_model_config('entity_extraction')
        embedding_cfg = config.get_model_config('embedding')

        self.rag = LightRAG(
            working_dir=str(self.working_dir),
            llm_model_func=self._create_llm_func(entity_cfg),
            embedding_func=self._create_embedding_func(embedding_cfg)
        )

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
        text = self._format_records(records)
        self.rag.insert(text)

    def search(self, query: str, mode: str = "hybrid") -> str:
        return self.rag.query(query, param=QueryParam(mode=mode))

    def _format_records(self, records: List[Dict]) -> str:
        lines = []
        for record in records:
            lines.append(f"[{record['timestamp']}] {record['sender']}: {record['message']}")
        return '\n'.join(lines)

def create_rag_service() -> RAGService:
    return RAGService()
