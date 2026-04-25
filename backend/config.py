import yaml
from pathlib import Path
from typing import Dict

class Config:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self._config = self._load_config()

    def _load_config(self) -> dict:
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def get_model_config(self, purpose: str) -> Dict:
        """获取指定用途的模型配置

        Args:
            purpose: 用途，可选值：profile_generation, entity_extraction, reply_generation, embedding
        """
        models = self._config.get('models', {})
        if purpose not in models:
            raise ValueError(f"未找到用途 '{purpose}' 的模型配置")
        return models[purpose]

    @property
    def lightrag(self) -> dict:
        return self._config.get('lightrag', {})

    @property
    def database(self) -> dict:
        return self._config.get('database', {})

config = Config()
