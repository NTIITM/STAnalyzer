"""
Project Agent API routes.
"""
import asyncio
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Query, status
from fastapi.responses import JSONResponse, StreamingResponse

from textmsa.logging_config import get_logger
from textmsa.services.agent.agent_service import get_agent_service
from textmsa.services.api.schemas import (
    AgentConversationMessage,
    AgentConversationResponse,
)
from textmsa.services.auth.auth_service import get_current_user_from_header

logger = get_logger(__name__)
agent_router = APIRouter(prefix="/api/agent", tags=["Project Agent"])


def _standard_response(data: dict, message: str = "success", code: int = 200, status_code: int = status.HTTP_200_OK):
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "data": data,
        },
    )

@agent_router.post("/conversation/{project_id}/stream")
async def send_message_stream(
    project_id: str,
    request: Request,
    message: str = Query(..., description="用户消息"),
    context_files: list[str] = Query(None, description="上下文文件ID（可选）"),
):
    """
    流式发送消息给Agent，SSE 返回进度和结果
    
    Args:
        project_id: 项目ID
        message: 用户输入消息
        context_files: 上下文文件ID（可选）
    
    Returns:
        SSE 流式响应，包含进度和最终结果
    """
    try:
        user_info = await get_current_user_from_header(request=request)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录",
            )

        user_id = user_info["user_id"]
        agent_service = get_agent_service()

        # 立即存储用户消息到数据库
        await agent_service.save_conversation_message(
            user_id=user_id,
            project_id=project_id,
            role="user",
            content=message,
            extra={"context_files": context_files or []},
        )

        async def event_stream():
            queue: asyncio.Queue[str | None] = asyncio.Queue()

            def progress_cb(progress: dict) -> None:
                queue.put_nowait(
                    f"event: progress\ndata: {json.dumps(progress, ensure_ascii=False)}\n\n"
                )
                # 直接在回调中异步持久化进度，失败忽略
                asyncio.create_task(
                    agent_service.save_conversation_message(
                        user_id=user_id,
                        project_id=project_id,
                        role="assistant",
                        content=progress.get("message", json.dumps(progress, ensure_ascii=False)),
                        extra=progress.get("extra") or {"type": "progress"},
                    )
                )

            async def run_agent():
                try:
                    result = await agent_service.send_message(
                        user_id=user_id,
                        project_id=project_id,
                        message=message,
                        context_files=context_files,
                        progress_cb=progress_cb,
                    )
                    queue.put_nowait("event: end\ndata: success\n\n")
                except Exception as e:
                    logger.error(
                        f"Agent流式处理失败: {e}",
                        extra={"project_id": project_id, "user_message": message[:100] if message else ""},
                        exc_info=True,
                    )
                    await agent_service.save_conversation_message(
                        user_id=user_id,
                        project_id=project_id,
                        role="assistant",
                        content="处理消息失败",
                        extra={"error": str(e), "type": "error"},
                    )
                    error_payload = {
                        "code": 500,
                        "message": "处理消息失败",
                        "data": {"error": str(e)},
                    }
                    queue.put_nowait(
                        f"event: error\ndata: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
                    )
                finally:
                    queue.put_nowait(None)

            asyncio.create_task(run_agent())

            while True:
                chunk = await queue.get()
                if chunk is None:
                    break
                yield chunk

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"流式对话接口失败: {e}",
            extra={"project_id": project_id, "user_message": message[:100] if message else ""},
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 500,
                "message": "处理消息失败",
                "data": {"error": str(e)},
            },
        )





@agent_router.delete("/conversation/{project_id}")
async def clear_conversation(project_id: str, request: Request):
    """
    清空项目的对话内容
    
    删除指定项目的所有对话消息
    
    Returns:
        { "success": bool }
    """
    user_info = await get_current_user_from_header(request=request)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="未授权，请先登录"
        )
    
    try:
        service = get_agent_service()
        success = service.clear_conversation(
            user_id=user_info["user_id"],
            project_id=project_id
        )
        return _standard_response({"success": success}, message="对话内容已清空")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to clear conversation: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="清空对话内容失败",
        ) from exc


@agent_router.get("/conversation/{project_id}")
async def get_conversation(project_id: str, request: Request):
    """
    获取项目的对话内容
    
    返回指定项目的对话历史，如果不存在则自动创建空对话
    
    Returns:
        { "conversation": dict }
    """
    user_info = await get_current_user_from_header(request=request)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="未授权，请先登录"
        )

    try:
        service = get_agent_service()
        conversation_dict = service.get_conversation(
            user_id=user_info["user_id"],
            project_id=project_id,
        )

        # 将底层 dict 转换为统一的 AgentConversationResponse 模型
        messages: list[AgentConversationMessage] = []
        for item in conversation_dict.get("messages", []):
            messages.append(
                AgentConversationMessage(
                    message_id=item.get("message_id"),
                    role=item.get("role", "user"),
                    message=item.get("message", "") or "",
                    time=item.get("time"),
                    extra=item.get("extra") or {},
                )
            )

        conversation = AgentConversationResponse(
            conversation_id=conversation_dict.get("conversation_id", ""),
            project_id=conversation_dict.get("project_id", project_id),
            context_summary=conversation_dict.get("context_summary"),
            updated_at=conversation_dict.get("updated_at"),
            messages=messages,
        )

        return _standard_response(
            {"conversation": conversation.model_dump()},
            message="获取对话成功",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to get conversation: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取对话失败",
        ) from exc


