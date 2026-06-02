from typing import Dict, List
import json
import re
from backend.services.ai_client import ai_client
from backend.models.db import Database
from backend.config import config

class ProfileService:
    EVOLVING_PROFILE_SCHEMA = """{
    "user_profile": {
        "current_profile": {
            "personality": "当前性格特点",
            "speaking_style": "当前说话风格",
            "reply_habits": "当前回复习惯",
            "interests": "当前关注点/兴趣",
            "tone": "当前语气特点"
        },
        "stable_traits": ["跨时间段反复出现的长期稳定特征"],
        "changed_traits": [
            {
                "field": "变化的字段，如 speaking_style",
                "from": "早期表现",
                "to": "近期表现",
                "period": "可识别的变化时间段",
                "confidence": "low/medium/high",
                "evidence": ["支持该变化的聊天表现"]
            }
        ],
        "recent_signals": ["只代表近期状态、应优先影响当前回复的信号"]
    },
    "contact_profile": {
        "current_profile": {
            "personality": "当前性格特点",
            "speaking_style": "当前说话风格",
            "interests": "当前关注点/兴趣",
            "tone": "当前语气特点",
            "relationship": "当前与用户的关系"
        },
        "stable_traits": ["跨时间段反复出现的长期稳定特征"],
        "changed_traits": [
            {
                "field": "变化的字段，如 tone",
                "from": "早期表现",
                "to": "近期表现",
                "period": "可识别的变化时间段",
                "confidence": "low/medium/high",
                "evidence": ["支持该变化的聊天表现"]
            }
        ],
        "recent_signals": ["只代表近期状态、应优先影响当前回复的信号"]
    }
}"""

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
        system_prompt = f"""你是一个人物画像分析专家。基于聊天记录，生成能体现时间演变的人物画像。

返回 JSON 格式：
{self.EVOLVING_PROFILE_SCHEMA}

要求：
1. current_profile 表示当前最适合用于生成回复的人设，近期聊天权重最高
2. stable_traits 只放跨多个时间段反复出现的稳定特征
3. changed_traits 记录从早期到近期的明确变化，不要把变化平均成模糊描述
4. recent_signals 记录近期明显但尚未证明长期稳定的状态
5. 如果聊天记录时间跨度不足以判断变化，changed_traits 返回空数组"""

        chat_text = self._format_records(records)
        prompt = f"""分析以下按时间排序的聊天记录，生成双方的人物画像：

```
{chat_text}
```

请生成完整画像 JSON。"""

        response = self.ai_client.generate(prompt, 'profile_generation', system_prompt)

        try:
            profiles = self._parse_profile_response(response)
            self.db.upsert_profile(contact_id, profiles['user_profile'], profiles['contact_profile'])
            return profiles
        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"画像生成失败: {str(e)}")

    def _update_profile(self, contact_id: str, new_records: List[Dict], existing_profile: Dict) -> Dict:
        system_prompt = f"""你是一个人物画像更新专家。你维护的不是静态画像，而是随时间变化的人物画像。

返回 JSON 格式：
{self.EVOLVING_PROFILE_SCHEMA}

更新原则：
1. current_profile 必须优先反映近期聊天中最适合用于当前回复生成的特征
2. stable_traits 保留被长期反复证明的核心特征，不要因为少量近期记录轻易删除
3. changed_traits 要显式记录旧特征被削弱、消失、反转或转向的新表现
4. recent_signals 记录近期明显但还不能证明长期稳定的兴趣、情绪、关系和表达方式
5. 遇到新旧冲突时，不要平均化；判断它是短期状态、长期转变，还是证据不足
6. 对已有旧格式画像，先理解其中字段，再升级为新的演变画像结构"""

        chat_text = self._format_records(new_records)
        prompt = f"""现有画像：
{json.dumps(existing_profile, ensure_ascii=False, indent=2)}

新增聊天记录（按时间排序，代表最新观察）：
```
{chat_text}
```

请完成画像更新：
1. 判断哪些旧特征仍然成立
2. 判断哪些旧特征被新增记录削弱或修正
3. 判断哪些新增表现只是近期信号
4. 判断哪些新增表现构成明确的人物转变
5. 返回更新后的完整画像 JSON"""

        response = self.ai_client.generate(prompt, 'profile_generation', system_prompt)

        try:
            profiles = self._parse_profile_response(response)
            self.db.upsert_profile(contact_id, profiles['user_profile'], profiles['contact_profile'])
            return profiles
        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"画像更新失败: {str(e)}")

    def _parse_profile_response(self, response: str) -> Dict:
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            match = re.search(r"\{.*\}", response, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            raise

    def _format_records(self, records: List[Dict]) -> str:
        lines = []
        for record in records:
            lines.append(f"[{record['timestamp']}] {record['sender']}: {record['message']}")
        return '\n'.join(lines)

def create_profile_service() -> ProfileService:
    db = Database(config.database.get('path', './data/chathelper.db'))
    return ProfileService(db)
