from typing import Dict, List
import json
from datetime import datetime
from pathlib import Path
from backend.services.ai_client import ai_client
from backend.config import config

class EvaluatorService:
    def __init__(self):
        self.ai_client = ai_client
        self.feedback_dir = Path("./data/feedback")
        self.feedback_dir.mkdir(parents=True, exist_ok=True)
        self.feedback_file = self.feedback_dir / "reply_feedback.jsonl"

    def evaluate_reply(self, reply: str, user_profile: Dict, contact_profile: Dict,
                      context: str) -> Dict:
        """评估推荐回复是否符合用户和对方画像

        Returns:
            {
                "is_appropriate": bool,
                "score": float (0-1),
                "issues": List[str],
                "suggestions": str
            }
        """
        system_prompt = """你是一个回复评估专家。评估推荐回复是否符合用户画像和对话场景。

返回 JSON 格式：
{
    "is_appropriate": true/false,
    "score": 0.85,
    "issues": ["问题1", "问题2"],
    "suggestions": "改进建议"
}

评估维度：
1. 语气是否符合用户说话风格
2. 用词是否符合用户习惯
3. 回复是否考虑了与对方的关系
4. 回复是否适合当前对话场景
5. 是否有明显的不当或冒犯内容"""

        prompt = f"""用户画像：
{json.dumps(user_profile, ensure_ascii=False, indent=2)}

联系人画像：
{json.dumps(contact_profile, ensure_ascii=False, indent=2)}

当前对话上下文：
{context}

推荐回复：
{reply}

请评估这条回复是否合适。"""

        response = self.ai_client.generate(prompt, 'reply_generation', system_prompt)

        try:
            evaluation = json.loads(response)
            return evaluation
        except json.JSONDecodeError:
            return {
                "is_appropriate": True,
                "score": 0.5,
                "issues": ["评估失败"],
                "suggestions": response
            }

    def record_feedback(self, contact_id: str, reply: str, evaluation: Dict,
                       user_profile: Dict, contact_profile: Dict, context: str,
                       user_feedback: str = None):
        """记录不合适的回复案例，用于后续改进

        Args:
            contact_id: 联系人ID
            reply: 推荐的回复
            evaluation: 评估结果
            user_profile: 用户画像
            contact_profile: 联系人画像
            context: 对话上下文
            user_feedback: 用户反馈（可选）
        """
        feedback_entry = {
            "timestamp": datetime.now().isoformat(),
            "contact_id": contact_id,
            "reply": reply,
            "evaluation": evaluation,
            "user_profile_summary": {
                "speaking_style": user_profile.get('speaking_style'),
                "tone": user_profile.get('tone')
            },
            "contact_profile_summary": {
                "relationship": contact_profile.get('relationship'),
                "tone": contact_profile.get('tone')
            },
            "context": context,
            "user_feedback": user_feedback
        }

        with open(self.feedback_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(feedback_entry, ensure_ascii=False) + '\n')

    def get_feedback_context(self, contact_id: str = None, limit: int = 10) -> str:
        """获取历史反馈作为上下文，用于改进后续生成

        Args:
            contact_id: 可选，只获取特定联系人的反馈
            limit: 最多返回多少条记录
        """
        if not self.feedback_file.exists():
            return ""

        feedbacks = []
        with open(self.feedback_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if contact_id is None or entry['contact_id'] == contact_id:
                        feedbacks.append(entry)
                except json.JSONDecodeError:
                    continue

        feedbacks = feedbacks[-limit:]

        if not feedbacks:
            return ""

        context_lines = ["历史反馈（避免重复以下错误）：\n"]
        for fb in feedbacks:
            context_lines.append(f"- 不当回复：{fb['reply']}")
            context_lines.append(f"  问题：{', '.join(fb['evaluation'].get('issues', []))}")
            context_lines.append(f"  建议：{fb['evaluation'].get('suggestions', '')}")
            if fb.get('user_feedback'):
                context_lines.append(f"  用户反馈：{fb['user_feedback']}")
            context_lines.append("")

        return '\n'.join(context_lines)

def create_evaluator_service() -> EvaluatorService:
    return EvaluatorService()
