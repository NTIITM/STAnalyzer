"""
H5AD Agent 状态定义和管理

定义 H5ADAgentState TypedDict 和状态构建函数。
"""

from typing import TypedDict

try:  # Python <3.11 compatibility
    from typing import NotRequired  # type: ignore
except ImportError:  # pragma: no cover - typing_extensions fallback
    from typing_extensions import NotRequired

from textmsa.logging_config import get_logger

logger = get_logger(__name__)


class H5ADAgentState(TypedDict, total=False):
    """H5AD Agent 的状态定义"""
    
    # 必需字段
    user_query: str              # 用户原始查询
    h5ad_file_path: str         # H5AD 文件路径（必需）
    
    # 文件预览信息
    file_preview: NotRequired[dict]  # H5AD 文件预览信息（如细胞数、基因数、是否有空间信息等）
    
    # 查询解析结果
    parsed_intent: NotRequired[str]      # 解析出的查询意图
    parsed_params: NotRequired[dict]      # 解析出的参数（如基因名、细胞类型等）
    
    # 代码生成和执行
    generated_code: NotRequired[str]      # LLM 生成的 Python 代码
    code_execution_result: NotRequired[dict]  # 代码执行结果 {"stdout": str, "stderr": str}
    execution_attempts: NotRequired[int]  # 执行尝试次数（用于限制重试，初始为 0）
    
    # 结果处理
    raw_result: NotRequired[str]         # 原始执行输出
    structured_result: NotRequired[dict] # 结构化结果
    final_answer: NotRequired[str]       # 最终答案
    
    # 工作流控制
    should_retry: NotRequired[bool]      # 是否需要重试代码生成
    is_complete: NotRequired[bool]       # 是否完成
    
    # 错误信息
    error_message: NotRequired[str]      # 错误信息


def build_initial_state(
    user_query: str,
    h5ad_file_path: str,
    file_preview: dict | None = None,
) -> H5ADAgentState:
    """
    构建初始状态
    
    Args:
        user_query: 用户查询
        h5ad_file_path: H5AD 文件路径
        file_preview: H5AD 文件预览信息（可选）
    
    Returns:
        初始化的 H5ADAgentState
    """
    logger.info(
        "Building initial H5ADAgentState",
        extra={
            "user_query": user_query,
            "h5ad_file_path": h5ad_file_path,
            "query_length": len(user_query),
            "has_file_preview": file_preview is not None,
        },
    )
    
    state: H5ADAgentState = {
        "user_query": user_query,
        "h5ad_file_path": h5ad_file_path,
        "execution_attempts": 0,
    }
    
    # 如果提供了文件预览信息，添加到状态中
    if file_preview:
        state["file_preview"] = file_preview
    
    logger.debug(
        "Initial state built",
        extra={
            "state_keys": list(state.keys()),
            "execution_attempts": state.get("execution_attempts", 0),
            "has_file_preview": "file_preview" in state,
        },
    )
    
    return state

