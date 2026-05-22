"""
Plan Agent 状态定义和管理

定义 PlanAgentState TypedDict 和状态构建函数。
"""

from typing import Any, TypedDict

try:  # Python <3.11 compatibility
    from typing import NotRequired  # type: ignore
except ImportError:  # pragma: no cover - typing_extensions fallback
    from typing_extensions import NotRequired

from textmsa.logging_config import get_logger

logger = get_logger(__name__)


class MessageDict(TypedDict, total=False):
    """消息字典，用于实时对话"""
    role: str              # 角色：user, assistant, system
    content: str           # 消息内容
    node: NotRequired[str] # 节点名称（用于标识消息来源）
    timestamp: NotRequired[float]  # 时间戳


class Plan(TypedDict, total=False):
    """执行计划"""
    service_id: str              # 服务ID
    input_file_ids: list[str]    # 输入文件ID列表
    expect_output: str           # 期望输出描述

class PlanAgentState(TypedDict, total=False):
    """Plan Agent 的状态定义"""
    
    # 必需字段
    user_query: str              # 用户原始查询
    user_id: str                # 用户ID（必需）
    project_id: str             # 项目ID（必需）
    context_files: list[str]    # 上下文文件ID列表（必需）
    
    history_messages: list[str] # 历史消息（必需，兼容旧版本）
    # 语言
    language: NotRequired[str]
    
    # 消息（用于外部异步调用返回信息）
    message: NotRequired[dict]
    
    # 生成的计划消息
    next_plan: NotRequired[Plan]

    pending_execution_id: NotRequired[str]
    pending_execution: NotRequired[dict[str, Any]]
    # 当前服务图谱（JSON字符串）
    current_service_graph: NotRequired[str]
    
    # 执行历史记录
    execution_history: NotRequired[list[dict[str, Any]]]
    
    # 生成的执行反馈消息
    execute_feedback: NotRequired[str]
    
    # 生成的最终答案
    final_answer: NotRequired[str]

    # 规划循环控制（用于避免无限 plan -> execute 循环）
    # max_plan_loops: 允许的最大规划轮数；<=0 表示不限制
    max_plan_loops: NotRequired[int]
    # plan_loop_count: 当前已经经历的规划轮数（每进入一次 plan_node 自增）
    plan_loop_count: NotRequired[int]
    # stop_reason_code: 停止/中止原因的机器可读代码，例如 "max_plan_loops_exceeded"
    stop_reason_code: NotRequired[str]
    # stop_reason: 面向用户/报告的停止原因描述
    stop_reason: NotRequired[str]
    


def build_initial_state(
    user_query: str,
    user_id: str,
    project_id: str,
    context_files: list[str],
    language: str = "zh",
) -> PlanAgentState:
    """
    构建初始状态
    
    Args:
        user_query: 用户查询
        user_id: 用户ID
        project_id: 项目ID
        context_files: 上下文文件ID列表
        language: 语言（默认为中文）
    
    Returns:
        初始化的 PlanAgentState
    """
    logger.info(
        "Building initial PlanAgentState",
    )
    
    state: PlanAgentState = {
        "user_query": user_query,
        "user_id": user_id,
        "project_id": project_id,
        "context_files": context_files,
        "history_messages": [],
        "execution_history": [],
        "language": language,
        # 默认限制规划循环次数，避免极端情况下无限 plan → execute 循环
        "max_plan_loops": 10,
        "plan_loop_count": 0,
    }
    
    logger.debug(
        "Initial state built",
        extra={
            "state_keys": list(state.keys()),
        },
    )
    
    return state


# def build_initial_state(
#     user_query: str,
#     h5ad_file_path: str,
#     file_preview: dict | None = None,
# ) -> H5ADAgentState:
#     """
#     构建初始状态
    
#     Args:
#         user_query: 用户查询
#         h5ad_file_path: H5AD 文件路径
#         file_preview: H5AD 文件预览信息（可选）
    
#     Returns:
#         初始化的 H5ADAgentState
#     """
#     logger.info(
#         "Building initial H5ADAgentState",
#         extra={
#             "user_query": user_query,
#             "h5ad_file_path": h5ad_file_path,
#             "query_length": len(user_query),
#             "has_file_preview": file_preview is not None,
#         },
#     )
    
#     state: H5ADAgentState = {
#         "user_query": user_query,
#         "h5ad_file_path": h5ad_file_path,
#         "execution_attempts": 0,
#     }
    
#     # 如果提供了文件预览信息，添加到状态中
#     if file_preview:
#         state["file_preview"] = file_preview
    
#     logger.debug(
#         "Initial state built",
#         extra={
#             "state_keys": list(state.keys()),
#             "execution_attempts": state.get("execution_attempts", 0),
#             "has_file_preview": "file_preview" in state,
#         },
#     )
    
#     return state

