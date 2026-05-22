"""
Orchestrator Agent 入口
"""

import uuid
from typing import Any, Callable, Optional

from langgraph.types import Command

from textmsa.logging_config import get_logger

from .state import OrchestratorAgentState, build_initial_state
from .workflow import compile_orchestrator_agent_workflow

logger = get_logger(__name__)

# 在模块级别编译图，确保 run 和 resume 使用同一个图实例和 checkpointer
workflow = compile_orchestrator_agent_workflow()


def run_orchestrator_agent(
    user_query: str,
    user_id: str,
    project_id: str,
    thread_id: str,
    context_file_ids: list[str] | None = None,
    language: str = "zh",
) -> dict[str, Any]:
    """
    运行 Orchestrator Agent（同步）
    
    Args:
        user_query: 用户查询
        user_id: 用户ID
        project_id: 项目ID
        thread_id: 线程ID（用于 langgraph checkpoint 恢复）
        context_file_ids: 上下文文件ID列表
        language: 语言（zh/en）
    
    Returns:
        包含 __interrupt__ 或最终结果的字典
    """
    initial_state = build_initial_state(
        user_query=user_query,
        user_id=user_id,
        project_id=project_id,
        context_file_ids=context_file_ids,
        language=language,
    )
    config = {"configurable": {"thread_id": thread_id}}
    result = workflow.invoke(initial_state, config=config)
    return result


def resume_orchestrator_agent(
    result: str,
    thread_id: str,
) -> dict[str, Any]:
    """
    恢复 Orchestrator Agent 执行
    
    Args:
        result: 动作执行结果（字符串）
        thread_id: 线程ID（用于 langgraph checkpoint 恢复）
    
    Returns:
        包含 __interrupt__ 或最终结果的字典
    """
    config = {"configurable": {"thread_id": thread_id}}
    # 直接基于现有状态恢复执行（使用模块级别的 workflow 实例）
    return workflow.invoke(Command(resume=result), config=config)


__all__ = [
    "OrchestratorAgentState",
    "build_initial_state",
    "run_orchestrator_agent",
    "resume_orchestrator_agent",
]

