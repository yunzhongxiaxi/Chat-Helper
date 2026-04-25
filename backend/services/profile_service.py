from typing import Dict, List
import json
from backend.services.ai_client import ai_client
from backend.models.db import Database
from backend.config import config

class ProfileService:
    def __init__(self, db: Database):
        self.db = db
        self.ai_client = ai_client

    def generate_profile(self, contact_id: str, records: List[Dict]) -> Dict:
        existing_profile = self.db.get_profile(contact_id)

        if existing_profile and existing_profile['user_profile'] and existing_profile['contact_profile']:
            return self._update_profile(contact_id, records, existing_profile)
        else:
            return self._create_profile(contact_id, records)

    def _create_profile(self, contact_id: str, records: List[Dict]) -> Dict:
        system_prompt = """你是一个人物画像分析专家。基于聊天记录，生成用户和联系人的详细画像。

返回 JSON 格式：
{
    "user_profile": {
        "personality": "性格特点",
        "speaking_style": "说话风格",
        "reply_habits": "回复习惯",
        "interests": "关注点/兴趣",
        "tone": "语气特点"
    },
    "contact_profile": {
        "personality": "性格特点",
        "speaking_style": "说话风格",
        "interests": "关注点/兴趣",
        "tone": "语气特点",
        "relationship": "与用户的关系"
    }
}"""

        chat_text = self._format_records(records)
        prompt = f"""分析以下聊天记录，生成双方的人物画像：

```
{chat_text}
```

请生成详细的画像 JSON。"""

        response = self.ai_client.generate(prompt, 'profile_generation', system_prompt)

        try:
            profiles = json.loads(response)
            self.db.upsert_profile(contact_id, profiles['user_profile'], profiles['contact_profile'])
            return profiles
        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"画像生成失败: {str(e)}")

    def _update_profile(self, contact_id: str, new_records: List[Dict], existing_profile: Dict) -> Dict:
        system_prompt = """你是一个人物画像更新专家。基于新的聊天记录和现有画像，进行增量更新。

返回 JSON 格式：
{
    "user_profile": {...},
    "contact_profile": {...}
}

注意：
1. 保留原有画像的核心特征
2. 根据新记录补充或修正细节
3. 如果新记录显示明显变化，更新相应字段"""

        chat_text = self._format_records(new_records)
        prompt = f"""现有画像：
{json.dumps(existing_profile, ensure_ascii=False, indent=2)}

新增聊天记录：
```
{chat_text}
```

请进行增量更新，返回更新后的完整画像 JSON。"""

        response = self.ai_client.generate(prompt, 'profile_generation', system_prompt)

        try:
            profiles = json.loads(response)
            self.db.upsert_profile(contact_id, profiles['user_profile'], profiles['contact_profile'])
            return profiles
        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"画像更新失败: {str(e)}")

    def _format_records(self, records: List[Dict]) -> str:
        lines = []
        for record in records:
            lines.append(f"[{record['timestamp']}] {record['sender']}: {record['message']}")
        return '\n'.join(lines)

def create_profile_service() -> ProfileService:
    db = Database(config.database.get('path', './data/chathelper.db'))
    return ProfileService(db)
