"""
File Analysis Agent 模块

提供文件分析执行的 Agent 功能。

主要接口：
- run_file_analysis_agent: 运行 File Analysis Agent，处理用户查询并返回结果
- build_file_analysis_agent_workflow: 构建工作流图
- compile_file_analysis_agent_workflow: 编译工作流图
"""

from typing import Any, AsyncIterator, Callable, Optional

from textmsa.logging_config import get_logger

from .state import FileAnalysisAgentState, build_initial_state
from .workflow import build_file_analysis_agent_workflow, compile_file_analysis_agent_workflow

logger = get_logger(__name__)


def run_file_analysis_agent(
    user_query: str,
    read_results: dict,
    work_dir_path: str,
) -> dict:
    """
    运行 File Analysis Agent，处理用户查询并返回结果
    
    Args:
        user_query: 用户查询
        read_results: 已读取的文件预览结果（单个元素）
        work_dir_path: 工作目录路径，用于保存子Agent生成的文件
    
    Returns:
        包含最终答案和生成文件信息的字典：
        {
            "final_answer": str,                    # 最终分析报告
            "generated_files_info": list[dict],     # 已生成的文件信息列表
            "work_dir_path": str,                   # 工作目录路径
        }
    """
    logger.info(
        "Running File Analysis Agent",
        extra={
            "user_query": user_query,
            "file_id": read_results.get("file_id"),
            "file_name": read_results.get("file_name"),
            "work_dir_path": work_dir_path,
            "query_length": len(user_query),
        },
    )
    
    # 构建初始状态
    initial_state = build_initial_state(
        user_query=user_query,
        read_results=read_results,
        work_dir_path=work_dir_path,
    )
    
    # 编译工作流
    workflow = compile_file_analysis_agent_workflow()
    
    # 运行工作流
    final_state = workflow.invoke(initial_state)
    
    
    # 返回结果
    result = {
        "final_answer": final_state.get("final_answer", ""),
        "generated_files_info": final_state.get("generated_files_info", []),
    }
    
    return result


async def astream_file_analysis_agent(
    user_query: str,
    read_results: dict,
    work_dir_path: str,
    on_event: Optional[Callable[[dict[str, Any]], None]] = None,
) -> dict:
    """
    异步流式运行 File Analysis Agent，实时回传节点更新事件。
    
    Args:
        user_query: 用户查询
        read_results: 已读取的文件预览结果（单个元素）
        work_dir_path: 工作目录路径，用于保存子Agent生成的文件
        on_event: 可选事件回调，形如 on_event({"node": str, "state": dict})
    
    Returns:
        与 run_file_analysis_agent 相同的结果字典
    """
    # 构建初始状态
    state = build_initial_state(
        user_query=user_query,
        read_results=read_results,
        work_dir_path=work_dir_path,
    )
    
    # 编译工作流
    workflow = compile_file_analysis_agent_workflow()
    
    async for event in workflow.astream(state, stream_mode="values"):
        if not on_event:
            continue   
        messages = event.get("messages")
        if not messages:
            continue
        on_event(messages[-1])
    
    return {
        "final_answer": state.get("final_answer", ""),
        "generated_files_info": state.get("generated_files_info", []),
    }


__all__ = [
    "FileAnalysisAgentState",
    "build_initial_state",
    "build_file_analysis_agent_workflow",
    "compile_file_analysis_agent_workflow",
    "run_file_analysis_agent",
    "astream_file_analysis_agent",
]

