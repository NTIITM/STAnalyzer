"""
Plan Agent 模块

提供基于 LangGraph 的智能规划执行系统。

主要接口：
- run_plan_agent: 运行 Plan Agent，处理用户查询并返回结果
- astream_plan_agent: 异步流式运行 Plan Agent，支持实时消息监听
- build_plan_agent_workflow: 构建工作流图
- compile_plan_agent_workflow: 编译工作流图（使用享元模式）
"""

import asyncio
from typing import Any, Callable, Optional

from textmsa.logging_config import get_logger

from .state import PlanAgentState, build_initial_state
from .workflow import build_plan_agent_workflow, compile_plan_agent_workflow

logger = get_logger(__name__)


async def astream_plan_agent(
    user_query: str,
    user_id: str,
    project_id: str,
    context_files: list[str],
    language: str = "zh",
    on_event: Optional[Callable[[dict[str, Any]], None]] = None,
) -> dict[str, Any]:
    """
    异步流式运行 Plan Agent，支持实时消息监听
    
    Args:
        user_query: 用户查询
        user_id: 用户ID
        project_id: 项目ID
        context_files: 上下文文件ID列表
        on_event: 可选的事件回调函数，用于接收实时消息
    
    Returns:
        最终状态字典，包含：
        {
            "final_answer": str,                    # 最终答案
            "successful_executions": list[str],     # 成功执行的 execution_id 列表
            "all_executions": list[dict],           # 所有 execution 信息列表（包括成功和失败的）
        }
    """
    # 构建初始状态
    initial_state = build_initial_state(
        user_query=user_query,
        user_id=user_id,
        project_id=project_id,
        context_files=context_files,
        language=language,
    )
    
    # 编译工作流（使用享元模式）
    workflow = compile_plan_agent_workflow()
    
    # 异步流式运行工作流
    logger.info("Starting async stream Plan Agent workflow")
    
    final_state: dict[str, Any] = {}
    
    # 流式执行时保留最后一个事件作为最终状态，同时透传消息事件
    async for event in workflow.astream(initial_state, stream_mode="values"):
        final_state = event
        if on_event:
            msg = event.get("message")
            if msg:
                on_event(msg)
    
    # 从执行历史中提取所有 execution 信息（包括成功和失败的）
    execution_history = final_state.get("execution_history", [])
    all_executions = []
    successful_executions = []
    
    # 获取 service_service 用于查询完整的 execution 信息
    from textmsa.services.service.service_service import get_service_service
    service_service = get_service_service()
    
    for record in execution_history:
        execution_id = record.get("execution_id")
        if not execution_id:
            # 如果没有 execution_id，使用记录中的基本信息
            execution_info = {
                "execution_id": None,
                "service_id": record.get("service_id", ""),
                "service_name": record.get("service_name", ""),
                "status": record.get("status", "unknown"),
                "input_file_ids": record.get("input_file_ids", []),
                "output_file_ids": record.get("output_file_ids", []),
                "parameters": record.get("parameters", {}),
                "feedback": record.get("feedback", ""),
                "error_message": record.get("error_message", ""),
            }
            all_executions.append(execution_info)
            continue
        
        # 从数据库获取完整的 execution 信息
        try:
            execution_detail = await asyncio.to_thread(
                service_service.get_execution, execution_id
            )
            execution_info = {
                "execution_id": execution_id,
                "service_id": execution_detail.get("service_id", ""),
                "service_name": execution_detail.get("service_name", ""),
                "status": execution_detail.get("status", "unknown"),
                "input_file_ids": execution_detail.get("input_file_ids", []),
                "output_file_ids": execution_detail.get("output_file_ids", []),
                "parameters": execution_detail.get("parameters", {}),
                "error_message": execution_detail.get("error_message", ""),
                "response_data": execution_detail.get("response_data"),
                "created_at": execution_detail.get("created_at"),
                "started_at": execution_detail.get("started_at"),
                "completed_at": execution_detail.get("completed_at"),
                "duration_seconds": execution_detail.get("duration_seconds"),
            }
            all_executions.append(execution_info)
            
            # 状态为 "completed" 的视为成功
            status = str(execution_info.get("status", "")).lower()
            if status == "completed":
                successful_executions.append(execution_id)
        except Exception as e:
            logger.warning(
                f"获取 execution {execution_id} 详细信息失败: {e}",
                extra={"execution_id": execution_id},
            )
            # 如果获取失败，使用记录中的基本信息
            execution_info = {
                "execution_id": execution_id,
                "service_id": record.get("service_id", ""),
                "service_name": record.get("service_name", ""),
                "status": record.get("status", "unknown"),
                "input_file_ids": record.get("input_file_ids", []),
                "output_file_ids": record.get("output_file_ids", []),
                "parameters": record.get("parameters", {}),
                "feedback": record.get("feedback", ""),
                "error_message": record.get("error_message", ""),
            }
            all_executions.append(execution_info)
    
    logger.info(
        "Async stream Plan Agent workflow completed",
        extra={
            "has_final_answer": bool(final_state.get("final_answer")),
            "execution_history_count": len(execution_history),
            "all_executions_count": len(all_executions),
            "successful_executions_count": len(successful_executions),
        },
    )
    
    # 返回最终状态
    return {
        "final_answer": final_state.get("final_answer", "") or initial_state.get("final_answer", ""),
        "successful_executions": successful_executions,
        "all_executions": all_executions,  # 包含所有 execution 信息（成功和失败）
    }


__all__ = [
    "PlanAgentState",
    "build_initial_state",
    "build_plan_agent_workflow",
    "compile_plan_agent_workflow",
    "astream_plan_agent",
]
