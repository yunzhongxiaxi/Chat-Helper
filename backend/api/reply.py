from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.services.ai_client import ai_client
from backend.services.rag_service import create_rag_service
from backend.services.evaluator_service import create_evaluator_service
from backend.services.mcp_tool_registry import mcp_tool_registry, extract_tool_call
from backend.services.message_rewriter_agent import message_rewriter_agent
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

        max_retries = 2
        retry_count = 0
        all_failed_evaluations = []
        rewritten = None
        evaluated_replies = []

        while retry_count <= max_retries:
            if retry_count > 0:
                rewritten = message_rewriter_agent.rewrite_with_subtext(
                    request.current_context,
                    profile['contact_profile'],
                    rag_context
                )

                retry_context = f"""
【重试第 {retry_count} 次】

原始消息：{rewritten['original']}

潜台词分析：
- 重写后的消息：{rewritten['rewritten']}
- 潜台词：{rewritten['subtext']}
- 真实意图：{rewritten['intent']}
- 情绪基调：{rewritten['emotional_tone']}

上次失败原因：
{_format_failed_evaluations(all_failed_evaluations)}

请基于潜台词和真实意图重新生成回复，避免上次的错误。"""

                current_context = retry_context
            else:
                current_context = f"当前对话：\n{request.current_context}"

            evaluated_replies = await _generate_and_evaluate(
                profile, rag_context, feedback_context, current_context
            )

            all_appropriate = all(r['evaluation']['is_appropriate'] for r in evaluated_replies if r['evaluation'])
            has_good_score = any(r['evaluation']['score'] >= 0.7 for r in evaluated_replies if r['evaluation'])

            if all_appropriate or has_good_score:
                return {
                    "replies": evaluated_replies,
                    "retry_count": retry_count,
                    "message_analysis": rewritten
                }

            for reply_item in evaluated_replies:
                if reply_item['evaluation'] and not reply_item['evaluation']['is_appropriate']:
                    all_failed_evaluations.append(reply_item['evaluation'])
                    evaluator.record_feedback(
                        request.contact_id, reply_item['reply'], reply_item['evaluation'],
                        profile['user_profile'], profile['contact_profile'],
                        request.current_context
                    )

            retry_count += 1

        return {
            "replies": evaluated_replies,
            "retry_count": retry_count,
            "warning": "所有重试均未通过评估，返回最后一次生成的结果"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def _generate_and_evaluate(profile, rag_context, feedback_context, current_context):
    """生成并评估回复"""
    tools = await mcp_tool_registry.get_tool_definitions()

    system_prompt = """你是一个智能回复助手。基于用户和联系人的画像、历史聊天上下文，生成符合用户人设的推荐回复。

画像可能包含 current_profile、stable_traits、changed_traits、recent_signals：生成当前回复时优先遵循 current_profile 和 recent_signals；stable_traits 作为长期人设约束；changed_traits 用于避免把早期特征误当成当前特征。

如果对话需要外部信息，可以调用已提供的工具。只能调用工具列表中存在的工具；如果没有合适工具，不要编造工具调用或实时信息，请基于已有上下文生成回复。

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

{current_context}

请生成推荐回复。"""

    response = ai_client.generate(prompt, 'reply_generation', system_prompt, tools)

    tool_call = extract_tool_call(response)
    if tool_call:
        tool_name, arguments = tool_call
        try:
            tool_result = await mcp_tool_registry.call_tool(tool_name, arguments)
            prompt_with_tool_result = f"{prompt}\n\n工具 {tool_name} 返回结果：\n{tool_result}\n\n请结合工具结果生成推荐回复。"
        except Exception as e:
            prompt_with_tool_result = f"{prompt}\n\n工具调用失败：{str(e)}。请不要使用工具，直接基于已有信息生成推荐回复。"

        response = ai_client.generate(prompt_with_tool_result, 'reply_generation', system_prompt)

    try:
        result = json.loads(response if isinstance(response, str) else response.content)
    except json.JSONDecodeError:
        result = {"replies": [response if isinstance(response, str) else response.content]}

    evaluator = create_evaluator_service()
    evaluated_replies = []

    for reply in result.get('replies', []):
        evaluation = evaluator.evaluate_reply(
            reply,
            profile['user_profile'],
            profile['contact_profile'],
            current_context
        )
        evaluated_replies.append({
            "reply": reply,
            "evaluation": evaluation
        })

    return evaluated_replies

def _format_failed_evaluations(evaluations):
    """格式化失败的评估结果"""
    if not evaluations:
        return "无"

    lines = []
    for i, evaluation in enumerate(evaluations[-3:], 1):
        lines.append(f"{i}. 问题：{', '.join(evaluation.get('issues', []))}")
        lines.append(f"   建议：{evaluation.get('suggestions', '')}")

    return '\n'.join(lines)

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
