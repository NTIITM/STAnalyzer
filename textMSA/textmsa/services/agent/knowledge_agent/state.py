"""
Knowledge Agent 状态定义
"""

from __future__ import annotations

from typing import Optional, TypedDict

try:  # Python <3.11
    from typing import NotRequired  # type: ignore
except ImportError:
    from typing_extensions import NotRequired

from textmsa.logging_config import get_logger
from textmsa.services.knowledge_service.models import KnowledgeSearchResult

logger = get_logger(__name__)


class ReadingPlan(TypedDict, total=False):
    """阅读计划"""
    document_id: str  # 文档标识（可以是 title 或 doi）
    title: str  # 文献标题
    snippet: str  # 摘要片段
    url: Optional[str]  # 文献链接
    doi: Optional[str]  # DOI
    plan_detail: str  # 计划详情（根据 query 提取相关内容）
    result: Optional[str]  # 执行结果


class KnowledgeAgentState(TypedDict, total=False):
    """Knowledge Agent 的状态"""
    # 用户查询
    user_query: str
    # 项目ID
    project_id: str
    # 语言
    language: NotRequired[str]
    # 搜索到的文献结果
    search_result: NotRequired[KnowledgeSearchResult]
    # 历史计划，记录读取文献的计划和结果
    reading_plans: list[ReadingPlan]
    # 当前计划索引
    current_plan_index: int
    # 最终答案
    final_answer: NotRequired[str | None]
    # 下一步路由
    next_route: NotRequired[str]
    # 用户ID
    user_id: NotRequired[str]
    # 消息（用于外部异步调用返回信息）
    message: NotRequired[dict]
    # 经过意图识别后的检索查询
    search_query: NotRequired[str]
    # 基因关系API查询结果
    gene_relation_result: NotRequired[str | None]


def build_initial_state(
    user_query: str,
    project_id: str,
    user_id: Optional[str] = None,
    language: str = "zh",
) -> KnowledgeAgentState:
    """构建初始状态"""
    state: KnowledgeAgentState = {
        "user_query": user_query,
        "project_id": project_id,
        "language": language,
        "reading_plans": [],
        "current_plan_index": 0,
    }
    
    # 添加 user_id（如果提供）
    if user_id:
        state["user_id"] = user_id
    
    logger.info(
        "Knowledge Agent initial state ready",
        extra={
            "user_id": user_id,
            "project_id": project_id,
            "language": language,
        },
    )
    return state

