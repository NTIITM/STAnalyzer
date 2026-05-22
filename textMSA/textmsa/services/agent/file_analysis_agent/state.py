"""
File Analysis Agent 状态定义和管理

定义 FileAnalysisAgentState TypedDict 和状态构建函数。
"""

from typing import TypedDict

try:  # Python <3.11 compatibility
    from typing import NotRequired  # type: ignore
except ImportError:  # pragma: no cover - typing_extensions fallback
    from typing_extensions import NotRequired

from textmsa.logging_config import get_logger

logger = get_logger(__name__)


class GeneratedFileInfo(TypedDict, total=False):
    """生成的文件信息"""
    file_name: str                   # 文件名
    description: str                 # 文件描述（说明文件包含什么内容、用途等）


class SubAgentInfo(TypedDict, total=False):
    """子Agent信息定义（单个元素，非list）"""
    name: str                        # 子Agent的名称（用于标识和追踪）
    prompt: str                      # 子Agent的完整prompt
    expected_output: str             # 期望的输出结果描述
    expected_files: list[GeneratedFileInfo]  # 期望生成的文件列表（文件名和描述）


class FileAnalysisAgentState(TypedDict, total=False):
    """File Analysis Agent 的状态定义"""
    
    # 必需字段（从 files_deep_read_agent 传入）
    user_query: str                  # 用户原始查询
    read_results: dict               # 已读取的文件预览结果（单个元素）
    # 格式：
    # {
    #     "file_id": str,
    #     "file_name": str,
    #     "preview": str,  # 文件预览信息（字符串格式）
    # }
    work_dir_path: str               # 工作目录路径，用于保存子Agent生成的文件
    
    # 子Agent相关
    sub_agent_info: NotRequired[SubAgentInfo]      # 子Agent信息定义（单个元素，非list）
    sub_agent_code: NotRequired[str]               # 子Agent生成的代码（字符串）
    sub_agent_feedback: NotRequired[str]           # 子Agent执行反馈
    # 格式：
    # - 执行失败：f"生成代码{code}，执行失败{reason}"
    # - 执行成功：f"按照预期生成文件xxxxx" 或返回的生成的结果文本
    
    # 生成的文件信息（返回结果属性）
    generated_files_info: NotRequired[list[GeneratedFileInfo]]  # 已生成的文件信息列表
    # 每个元素格式：
    # {
    #     "file_name": str,
    #     "description": str,
    # }
    
    # 执行历史（区分两种）
    sub_agent_execution_history: NotRequired[list[dict]]  # 子Agent代码执行历史（代码和错误信息）
    # 每个元素格式：
    # {
    #     "code": str,        # 生成的代码
    #     "error": str | None,  # 错误信息（如果有）
    # }
    # 注意：执行成功则清空此历史
    sub_agent_info_execution_history: NotRequired[list[dict]]  # 子Agent信息生成历史（子Agent信息和执行反馈）
    # 每个元素格式：
    # {
    #     "sub_agent_info": SubAgentInfo,  # 生成的子Agent信息
    #     "feedback": str,                  # 执行结果反馈
    # }
    
    # 路由决策（内部使用）
    route_decision: NotRequired[str]    # 路由决策（"generate_code", "return_result"），仅用于 generate_sub_agent_info_node
    
    
    # 最终答案
    final_answer: NotRequired[str]       # 最终分析结果
    
    # 消息列表（用于实时对话）
    read_plan: NotRequired[dict]  # 消息列表


def build_initial_state(
    user_query: str,
    read_results: dict,
    work_dir_path: str,
) -> FileAnalysisAgentState:
    """
    构建初始状态
    
    Args:
        user_query: 用户查询
        read_results: 已读取的文件预览结果（单个元素）
        work_dir_path: 工作目录路径，用于保存子Agent生成的文件
    
    Returns:
        初始化的 FileAnalysisAgentState
    """
    logger.info(
        "Building initial FileAnalysisAgentState",
        extra={
            "user_query": user_query,
            "file_id": read_results.get("file_id"),
            "file_name": read_results.get("file_name"),
            "work_dir_path": work_dir_path,
            "query_length": len(user_query),
        },
    )
    
    state: FileAnalysisAgentState = {
        "user_query": user_query,
        "read_results": read_results,
        "work_dir_path": work_dir_path,
        "generated_files_info": [],
        "sub_agent_execution_history": [],
        "sub_agent_info_execution_history": [],
        "messages": [],  # 初始化 messages 字段，用于流式传输
    }
    
    logger.debug(
        "Initial state built",
        extra={
            "state_keys": list(state.keys()),
            "has_read_results": "read_results" in state,
            "work_dir_path": state.get("work_dir_path"),
        },
    )
    
    return state

