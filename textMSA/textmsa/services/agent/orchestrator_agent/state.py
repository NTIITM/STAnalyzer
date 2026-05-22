"""
Orchestrator Agent 状态定义
"""

from __future__ import annotations

from typing import Any, Optional, TypedDict

try:  # Python <3.11
    from typing import NotRequired  # type: ignore
except ImportError:
    from typing_extensions import NotRequired

from textmsa.logging_config import get_logger

logger = get_logger(__name__)


class DecisionHistoryItem(TypedDict):
    """决策历史项"""
    action: str
    parameter: NotRequired[dict[str, Any]]  # 动作参数，answer_question 动作没有 parameter
    reasoning: str  # 决策理由
    result: NotRequired[str]  # 动作执行结果


class OrchestratorAgentState(TypedDict, total=False):
    """Orchestrator Agent 的状态"""
    # 基础信息
    user_id: str
    project_id: str
    context_file_ids: list[str]  # 上下文文件ID列表
    user_query: str  # 原始用户查询
    language: NotRequired[str]  # 语言（zh/en）
    
    # 意图和计划
    intent: NotRequired[str]  # 用户意图
    plan: NotRequired[str]  # 执行计划
    
    # 决策历史
    decision_history: list[DecisionHistoryItem]
    
    # 执行反馈（从 astream_analysis_and_report_agent 获取）
    execution_feedback: NotRequired[str]  # 最近的执行反馈
    
    # 知识查询反馈（从 astream_knowledge_agent 获取）
    knowledge_feedback: NotRequired[str]  # 最近的知识查询反馈
    
    # 最终答案
    final_answer: NotRequired[str]
    
    # 消息（用于流式返回）
    message: NotRequired[dict]


def build_initial_state(
    user_query: str,
    user_id: str,
    project_id: str,
    context_file_ids: list[str] | None = None,
    language: str = "zh",
) -> OrchestratorAgentState:
    """构建初始状态"""
    state: OrchestratorAgentState = {
        "user_query": user_query,
        "user_id": user_id,
        "project_id": project_id,
        "context_file_ids": context_file_ids or [],
        "language": language,
        "decision_history": [],
    }
    
    logger.info(
        "Orchestrator Agent initial state ready",
        extra={
            "user_id": user_id,
            "project_id": project_id,
            "context_file_ids_count": len(context_file_ids or []),
            "language": language,
        },
    )
    return state

