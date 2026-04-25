from typing import List, Dict
import json
from datetime import datetime
from backend.services.ai_client import ai_client

class ParserAgent:
    def __init__(self):
        self.ai_client = ai_client

    def identify_format(self, file_content: str) -> Dict:
        system_prompt = """你是一个聊天记录格式识别专家。分析用户上传的聊天记录文件内容，识别其格式并返回解析规则。

返回 JSON 格式：
{
    "format_type": "格式类型（如 wechat_txt, csv, json 等）",
    "pattern": "消息提取的正则表达式或规则描述",
    "sample_parse": "示例解析结果"
}"""

        prompt = f"""分析以下聊天记录内容（前500字符）：

```
{file_content[:500]}
```

请识别格式并返回解析规则。"""

        response = self.ai_client.generate(prompt, 'entity_extraction', system_prompt)

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"format_type": "unknown", "pattern": "", "sample_parse": ""}

    def parse_records(self, file_content: str, contact_id: str) -> List[Dict]:
        format_info = self.identify_format(file_content)

        system_prompt = """你是一个聊天记录解析专家。根据识别的格式规则，将聊天记录解析为统一的 JSON 格式。

每条消息返回格式：
{
    "timestamp": "YYYY-MM-DD HH:MM:SS",
    "sender": "user 或 contact",
    "message": "消息内容"
}

返回 JSON 数组。"""

        prompt = f"""格式识别结果：
{json.dumps(format_info, ensure_ascii=False, indent=2)}

聊天记录内容：
```
{file_content}
```

请解析为统一格式的 JSON 数组。注意：
1. sender 只能是 "user" 或 "contact"
2. 如果无法确定发送者，根据上下文推断
3. timestamp 必须是有效的日期时间格式"""

        response = self.ai_client.generate(prompt, 'entity_extraction', system_prompt)

        try:
            records = json.loads(response)
            for record in records:
                if 'timestamp' not in record or 'sender' not in record or 'message' not in record:
                    raise ValueError("解析结果缺少必要字段")
            return records
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"解析失败: {str(e)}")

parser_agent = ParserAgent()
