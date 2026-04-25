from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.services.ai_client import ai_client
from backend.services.rag_service import create_rag_service
from backend.services.evaluator_service import create_evaluator_service
from backend.services.web_search_tool import web_search_tool, get_search_tool_definition
from backend.models.db import Database
from backend.config import config
import json

router = APIRouter(prefix="/api", tags=["reply"])

class ReplyRequest(BaseModel):
    contact_id: str
    current_context: str

class FeedbackRequest(BaseModel):
    contact_id: str
    reply: str
    feedback: str

@router.post("/reply")
async def generate_reply(request: ReplyRequest):
    try:
        db = Database(config.database.get('path', './data/chathelper.db'))
        profile = db.get_profile(request.contact_id)

        if not profile:
            raise HTTPException(status_code=404, detail="画像不存在，请先上传聊天记录")

        rag_service = create_rag_service()
        rag_context = rag_service.search(request.current_context, mode="hybrid")

        evaluator = create_evaluator_service()
        feedback_context = evaluator.get_feedback_context(request.contact_id)

        tools = [get_search_tool_definition()]

        system_prompt = """你是一个智能回复助手。基于用户和联系人的画像、历史聊天上下文，生成符合用户人设的推荐回复。

如果对话涉及实时信息（如天气、新闻、最新事件等），可以调用 search_web 工具获取最新信息。

返回 JSON 格式：
{
    "replies": ["回复1", "回复2", "回复3"]
}

要求：
1. 回复必须符合用户的说话风格和语气
2. 考虑与联系人的关系和对话场景
3. 提供 1-3 条不同风格的候选回复
4. 避免历史反馈中提到的错误"""

        prompt = f"""用户画像：
{json.dumps(profile['user_profile'], ensure_ascii=False, indent=2)}

联系人画像：
{json.dumps(profile['contact_profile'], ensure_ascii=False, indent=2)}

相关历史上下文：
{rag_context}

{feedback_context}

当前对话：
{request.current_context}

请生成推荐回复。"""

        response = ai_client.generate(prompt, 'reply_generation', system_prompt, tools)

        if hasattr(response, 'tool_calls') and response.tool_calls:
            tool_call = response.tool_calls[0]
            if tool_call.function.name == 'search_web':
                args = json.loads(tool_call.function.arguments)
                search_result = web_search_tool.search(args['query'], args.get('num_results', 3))

                prompt_with_search = f"{prompt}\n\n实时信息：\n{search_result}\n\n请结合实时信息生成推荐回复。"
                response = ai_client.generate(prompt_with_search, 'reply_generation', system_prompt)

        try:
            result = json.loads(response if isinstance(response, str) else response.content)

            evaluated_replies = []
            for reply in result.get('replies', []):
                evaluation = evaluator.evaluate_reply(
                    reply,
                    profile['user_profile'],
                    profile['contact_profile'],
                    request.current_context
                )
                evaluated_replies.append({
                    "reply": reply,
                    "evaluation": evaluation
                })

                if not evaluation['is_appropriate']:
                    evaluator.record_feedback(
                        request.contact_id, reply, evaluation,
                        profile['user_profile'], profile['contact_profile'],
                        request.current_context
                    )

            return {"replies": evaluated_replies}
        except json.JSONDecodeError:
            return {"replies": [{"reply": response, "evaluation": None}]}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reply/feedback")
async def submit_feedback(request: FeedbackRequest):
    """用户提交对推荐回复的反馈"""
    try:
        db = Database(config.database.get('path', './data/chathelper.db'))
        profile = db.get_profile(request.contact_id)

        if not profile:
            raise HTTPException(status_code=404, detail="画像不存在")

        evaluator = create_evaluator_service()
        evaluation = {
            "is_appropriate": False,
            "score": 0.0,
            "issues": ["用户反馈不合适"],
            "suggestions": request.feedback
        }

        evaluator.record_feedback(
            request.contact_id, request.reply, evaluation,
            profile['user_profile'], profile['contact_profile'],
            "", request.feedback
        )

        return {"success": True, "message": "反馈已记录"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
