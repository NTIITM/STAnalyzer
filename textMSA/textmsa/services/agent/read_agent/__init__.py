"""
Read Agent 入口
"""
import asyncio
import json
import os
from typing import Any, Callable, Optional

from textmsa.logging_config import get_logger
from textmsa.services.agent.tools.file_reader_tool import FileReaderTool
from textmsa.services.file.file_service import get_file_service
from textmsa.services.service.service_service import get_service_service

from .state import ReadAgentState, build_initial_state
from .workflow import build_read_agent_workflow, compile_read_agent_workflow

logger = get_logger(__name__)


def run_read_agent(
    user_query: str,
    file_tree_list: list[dict],
    user_id: Optional[str] = None,
    project_id: Optional[str] = None,
    language: str = "zh",
) -> dict:
    """运行 Read Agent（同步）"""
    initial_state = build_initial_state(
        user_query=user_query,
        file_tree_list=file_tree_list,
        user_id=user_id,
        project_id=project_id,
        language=language,
    )
    workflow = compile_read_agent_workflow()
    final_state = workflow.invoke(initial_state)
    return {
        "final_answer": final_state.get("final_answer", ""),
    }


async def astream_read_agent(
    user_query: str,
    file_tree_list: list[dict],
    user_id: Optional[str] = None,
    project_id: Optional[str] = None,
    language: str = "zh",
    on_event: Optional[Callable[[dict[str, Any]], None]] = None,
) -> dict:
    """运行 Read Agent（异步流式）"""
    initial_state = build_initial_state(
        user_query=user_query,
        file_tree_list=file_tree_list,
        user_id=user_id,
        project_id=project_id,
        language=language,
    )
    workflow = compile_read_agent_workflow()
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


async def astream_read_agent_from_execution(
    execution_id: str,
    user_id: str,
    query: str = "",
    language: str = "zh",
    on_event: Optional[Callable[[dict[str, Any]], None]] = None,
) -> dict:
    """
    从 execution_id 读取并解读过程相关结果（异步流式）
    
    Args:
        execution_id: 执行ID
        user_id: 用户ID
        query: 分析查询/问题（可选，默认为空时使用默认查询）
        language: 语言（默认中文）
        on_event: 事件回调函数，用于流式返回进度和结果
        
    Returns:
        包含 final_answer 的字典
    """
    service_service = get_service_service()
    file_service = get_file_service()
    file_reader_tool = FileReaderTool(max_text_bytes=2000)
    
    def progress_cb(progress: dict) -> None:
        """进度回调，转发给 on_event"""
        if on_event:
            on_event(progress)
    
    # Get execution record information
    if on_event:
        progress_cb({"message": "Fetching execution record information..."})
    execution = await asyncio.to_thread(
        service_service.get_execution, execution_id
    )
    
    # Organize files in parent-child relationship
    # Input files are parents, output files are children
    input_file_ids = execution.get("input_file_ids", [])
    output_file_ids = execution.get("output_file_ids", [])
    
    if not input_file_ids and not output_file_ids:
        raise ValueError("No related files found in execution record")
    
    # Remove duplicates and filter out None/empty values
    input_file_ids = list(dict.fromkeys([fid for fid in input_file_ids if fid]))
    output_file_ids = list(dict.fromkeys([fid for fid in output_file_ids if fid]))
    
    # Organize files in parent-child relationship
    # Input files are parents, output files are children
    # If a file appears in both, prioritize it as a parent (input) to avoid duplicate analysis
    input_set = set(input_file_ids)
    output_set = set(output_file_ids)
    
    # Parent files: files that are inputs (even if they're also outputs)
    parent_file_ids = list(input_set)
    
    # Child files: files that are outputs but not inputs
    child_file_ids = list(output_set - input_set)
    
    if on_event:
        progress_cb({
            "message": f"Found {len(parent_file_ids)} parent file(s) and {len(child_file_ids)} child file(s), building file tree...",
        })
    
    # Get file information for all files
    if on_event:
        progress_cb({"message": "Fetching file information..."})
    
    # Build child nodes (output files) first - shared by all parent nodes
    child_nodes: list[dict] = []
    for child_file_id in child_file_ids:
        if not child_file_id:
            continue
        try:
            child_file_info = await asyncio.to_thread(
                file_service.get_file_info, child_file_id, user_id
            )
            child_filename = child_file_info.get("filename", "unknown")
            child_file_path = child_file_info.get("file_path")
            child_description = child_file_info.get("description", "")
            child_file_type_id = child_file_info.get("file_type_id")
            
            if not child_file_path:
                continue
            
            # 获取文件预览
            child_preview = ""
            try:
                child_file_ext = os.path.splitext(child_filename)[1].lower()
                child_file_type_name = child_file_ext[1:] if child_file_ext else "unknown"
                child_preview_dict = file_reader_tool._read_preview(
                    file_path=child_file_path,
                    file_type=child_file_type_name,
                    filename=child_filename,
                )
                child_preview = json.dumps(child_preview_dict, ensure_ascii=False)
            except Exception as e:
                logger.warning(
                    f"Failed to get child file preview: {child_file_id}, error: {e}",
                    extra={"file_id": child_file_id},
                )
            
            child_node: dict = {
                "file_id": child_file_id,
                "file_name": child_filename,
                "file_path": child_file_path,
                "description": child_description,
                "preview": child_preview,
                "children": [],
            }
            if child_file_type_id:
                child_node["file_type_id"] = child_file_type_id
            child_nodes.append(child_node)
        except Exception as e:
            logger.warning(
                f"Failed to get child file info: {child_file_id}, error: {e}",
                extra={"file_id": child_file_id},
            )
    
    # Build parent nodes (input files) with child nodes
    parent_file_nodes: list[dict] = []
    for parent_file_id in parent_file_ids:
        if not parent_file_id:
            continue
        try:
            file_info = await asyncio.to_thread(
                file_service.get_file_info, parent_file_id, user_id
            )
            filename = file_info.get("filename", "unknown")
            file_path = file_info.get("file_path")
            description = file_info.get("description", "")
            file_type_id = file_info.get("file_type_id")
            
            if not file_path:
                logger.warning(
                    f"File path not found for file: {parent_file_id}",
                    extra={"file_id": parent_file_id},
                )
                continue
            
            # 获取文件预览
            preview = ""
            try:
                file_ext = os.path.splitext(filename)[1].lower()
                file_type_name = file_ext[1:] if file_ext else "unknown"
                preview_dict = file_reader_tool._read_preview(
                    file_path=file_path,
                    file_type=file_type_name,
                    filename=filename,
                )
                preview = json.dumps(preview_dict, ensure_ascii=False)
            except Exception as e:
                logger.warning(
                    f"Failed to get parent file preview: {parent_file_id}, error: {e}",
                    extra={"file_id": parent_file_id, "execution_id": execution_id},
                )
            
            # Each parent node gets a copy of child nodes
            parent_node: dict = {
                "file_id": parent_file_id,
                "file_name": filename,
                "file_path": file_path,
                "description": description,
                "preview": preview,
                "children": child_nodes.copy(),  # Copy to avoid shared reference
            }
            if file_type_id:
                parent_node["file_type_id"] = file_type_id
            parent_file_nodes.append(parent_node)
        except Exception as e:
            logger.error(
                f"Failed to get parent file info: {parent_file_id}, error: {e}",
                extra={"file_id": parent_file_id, "execution_id": execution_id},
                exc_info=True,
            )
    
    if not parent_file_nodes:
        raise ValueError("No valid files found to analyze")
    
    # Build file tree list: single element list containing the file tree
    # If multiple parent nodes, create a virtual root; otherwise use the single parent
    if len(parent_file_nodes) == 1:
        file_tree_list = parent_file_nodes
    else:
        # Create a virtual root node with all parent nodes as children
        virtual_root: dict = {
            "file_id": f"virtual_root_{execution_id}",
            "file_name": "Execution Files",
            "file_path": "",
            "description": f"Files from execution {execution_id}",
            "preview": "",
            "children": parent_file_nodes,
        }
        file_tree_list = [virtual_root]
    
    logger.info(
        "Starting analysis with Read Agent",
        extra={
            "execution_id": execution_id,
            "file_tree_nodes": len(file_tree_list),
        },
    )
    
    if on_event:
        progress_cb({"message": "Starting analysis with Read Agent..."})
    
    # 获取 project_id（从第一个父文件）
    project_id = None
    if parent_file_ids:
        try:
            from textmsa.services.data.user_data_manager_mongodb import get_user_data_manager
            user_data_manager = get_user_data_manager()
            project_ids = await asyncio.to_thread(
                user_data_manager.find_project_ids_by_file,
                user_id=user_id,
                file_id=parent_file_ids[0]
            )
            if project_ids:
                project_id = project_ids[0]
        except Exception as e:
            logger.warning(
                f"无法获取 project_id: {parent_file_ids[0]}, {e}",
                extra={"file_id": parent_file_ids[0], "execution_id": execution_id}
            )
    
    # Call Read Agent
    user_query = query or "请分析这些文件的基本信息和内容。"
    result = await astream_read_agent(
        user_query=user_query,
        file_tree_list=file_tree_list,
        user_id=user_id,
        project_id=project_id,
        language=language,
        on_event=on_event,
    )
    
    return result


__all__ = [
    "ReadAgentState",
    "build_read_agent_workflow",
    "compile_read_agent_workflow",
    "run_read_agent",
    "astream_read_agent",
    "astream_read_agent_from_execution",
]


