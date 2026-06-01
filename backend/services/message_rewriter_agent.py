from typing import Dict
import json
from backend.services.ai_client import ai_client

class MessageRewriterAgent:
    def __init__(self):
        self.ai_client = ai_client

    def rewrite_with_subtext(self, message: str, contact_profile: Dict, context: str = "") -> Dict:
        """重写消息，分析潜台词和真实意图

        Args:
            message: 对方发送的消息
            contact_profile: 对方的画像
            context: 对话上下文

        Returns:
            {
                "original": "原始消息",
                "rewritten": "重写后的消息（包含潜台词分析）",
                "subtext": "潜台词分析",
                "intent": "真实意图",
                "emotional_tone": "情绪基调"
            }
        """
        system_prompt = """你是一个消息分析专家，擅长识别对话中的潜台词和真实意图。

返回 JSON 格式：
{
    "original": "原始消息",
    "rewritten": "重写后的消息（明确表达潜台词和真实意图）",
    "subtext": "潜台词分析（对方真正想表达但没有明说的内容）",
    "intent": "真实意图（对方希望得到什么样的回应）",
    "emotional_tone": "情绪基调（如：期待、抱怨、试探、关心等）"
}

分析维度：
1. 字面意思 vs 真实意图
2. 情绪暗示（语气词、标点、表情等）
3. 关系暗示（基于双方关系推断期待）
4. 文化/社交规范（礼貌性表达背后的真实需求）"""

        prompt = f"""对方画像：
{json.dumps(contact_profile, ensure_ascii=False, indent=2)}

对话上下文：
{context}

对方发送的消息：
{message}

请分析这条消息的潜台词和真实意图。"""

        response = self.ai_client.generate(prompt, 'reply_generation', system_prompt)

        try:
            result = json.loads(response)
            result['original'] = message
            return result
        except json.JSONDecodeError:
            return {
                "original": message,
                "rewritten": message,
                "subtext": "分析失败",
                "intent": "未知",
                "emotional_tone": "中性"
            }

message_rewriter_agent = MessageRewriterAgent()
