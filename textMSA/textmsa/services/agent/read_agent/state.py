"""
Files Deep Read Agent 状态定义
"""

from __future__ import annotations

from typing import Optional, TypedDict

try:  # Python <3.11
    from typing import NotRequired  # type: ignore
except ImportError:
    from typing_extensions import NotRequired

from textmsa.logging_config import get_logger

logger = get_logger(__name__)


class FileInfo(TypedDict, total=False):
    """阅读计划"""
    file_name: str
    file_path: str
    description: str
    preview: str


class PlanHistory(TypedDict, total=False):
    """计划历史记录"""

    file_id: str  # 文件ID
    file_name: str  # 文件名
    file_path: str  # 文件路径
    plan_detail: str  # 计划详情
    result: str | None  # 执行结果
    order_reasoning: NotRequired[str]  # 顺序理由（为什么该文件在此位置读取）


class ReadAgentState(TypedDict, total=False):
    """Files Deep Read Agent 的状态"""
    # 用户查询
    user_query: str
    # 文件树
    file_tree_list: list[dict]
    # 语言
    language: NotRequired[str]
    # 历史计划，记录读取文件的计划和结果
    history_plans: list[PlanHistory]
    # 当前计划索引
    current_plan_index: int
    # 最终答案
    final_answer: NotRequired[str | None]
    # 下一步路由
    next_route: NotRequired[str]
    # 用户ID
    user_id: NotRequired[str]
    # 项目ID
    project_id: NotRequired[str]  # 新增：项目ID
    # 消息（用于外部异步调用返回信息）
    message: NotRequired[dict]
    # 规划理由（说明为什么按这个顺序读取文件）
    plan_reasoning: NotRequired[str]


def build_initial_state(
    user_query: str,
    file_tree_list: list[dict],
    user_id: Optional[str] = None,
    project_id: Optional[str] = None,
    language: str = "zh",
) -> ReadAgentState:
    """构建初始状态"""
    state: ReadAgentState = {
        "user_query": user_query,
        "file_tree_list": file_tree_list,
        "language": language,
        "history_plans": [],
        "current_plan_index": 0,
    }
    
    # 添加 user_id 和 project_id（如果提供）
    if user_id:
        state["user_id"] = user_id
    if project_id:
        state["project_id"] = project_id
    
    logger.info(
        "Read Agent initial state ready",
        extra={
            "file_tree_len": len(file_tree_list) if isinstance(file_tree_list, list) else "n/a",
            "user_id": user_id,
            "project_id": project_id,
            "language": language,
        },
    )
    return state


