"""
Files Deep Read Agent 入口
"""

from typing import Any, Callable, Optional

from textmsa.logging_config import get_logger

from .state import FileTreeNode, FilesDeepReadAgentState, build_initial_state
from .workflow import build_files_deep_read_agent_workflow, compile_files_deep_read_agent_workflow

logger = get_logger(__name__)


def run_files_deep_read_agent(
    user_query: str,
    file_tree_list: list[FileTreeNode],
    work_dir_path: str,
    user_id: Optional[str] = None,  # 新增
    project_id: Optional[str] = None,  # 新增
) -> dict:
    initial_state = build_initial_state(
        user_query=user_query,
        file_tree_list=file_tree_list,
        work_dir_path=work_dir_path,
        user_id=user_id,  # 新增
        project_id=project_id,  # 新增
    )
    workflow = compile_files_deep_read_agent_workflow()
    final_state = workflow.invoke(initial_state)
    return {
        "final_answer": final_state.get("final_answer", ""),
        "generated_files": final_state.get("generated_files", []),
        "work_dir_path": work_dir_path,
    }


async def astream_files_deep_read_agent(
    user_query: str,
    file_tree_list: list[FileTreeNode],
    work_dir_path: str,
    user_id: Optional[str] = None,  # 新增
    project_id: Optional[str] = None,  # 新增
    on_event: Optional[Callable[[dict[str, Any]], None]] = None,
) -> dict:
    initial_state = build_initial_state(
        user_query=user_query,
        file_tree_list=file_tree_list,
        work_dir_path=work_dir_path,
        user_id=user_id,  # 新增
        project_id=project_id,  # 新增
    )
    workflow = compile_files_deep_read_agent_workflow()
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
        "generated_files": final_state.get("generated_files", []) or initial_state.get("generated_files", []),
        "work_dir_path": work_dir_path,
    }


__all__ = [
    "FilesDeepReadAgentState",
    "build_files_deep_read_agent_workflow",
    "compile_files_deep_read_agent_workflow",
    "run_files_deep_read_agent",
    "astream_files_deep_read_agent",
]


