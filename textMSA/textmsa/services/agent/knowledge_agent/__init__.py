"""
Knowledge Agent 入口
"""

from typing import Any, Callable, Optional

from textmsa.logging_config import get_logger

from .state import KnowledgeAgentState, build_initial_state
from .workflow import build_knowledge_agent_workflow, compile_knowledge_agent_workflow

logger = get_logger(__name__)


def run_knowledge_agent(
    user_query: str,
    project_id: str,
    user_id: Optional[str] = None,
    language: str = "zh",
) -> dict:
    """运行 Knowledge Agent（同步）"""
    initial_state = build_initial_state(
        user_query=user_query,
        project_id=project_id,
        user_id=user_id,
        language=language,
    )
    workflow = compile_knowledge_agent_workflow()
    final_state = workflow.invoke(initial_state)
    return {
        "final_answer": final_state.get("final_answer", ""),
    }


async def astream_knowledge_agent(
    user_query: str,
    project_id: str,
    user_id: Optional[str] = None,
    language: str = "zh",
    on_event: Optional[Callable[[dict[str, Any]], None]] = None,
) -> dict:
    """运行 Knowledge Agent（异步流式）"""
    initial_state = build_initial_state(
        user_query=user_query,
        project_id=project_id,
        user_id=user_id,
        language=language,
    )
    workflow = compile_knowledge_agent_workflow()
    final_state: dict[str, Any] = {}

    # 流式执行时保留最后一个事件作为最终状态，同时透传消息事件
    async for event in workflow.astream(initial_state, stream_mode="values"):
        final_state = event
        if on_event:
            msg = event.get("message")
            if msg:
                on_event(msg)
    return {
        "final_answer": final_state.get("final_answer", "") or initial_state.get("final_answer", ""),
    }


__all__ = [
    "KnowledgeAgentState",
    "build_knowledge_agent_workflow",
    "compile_knowledge_agent_workflow",
    "run_knowledge_agent",
    "astream_knowledge_agent",
]

