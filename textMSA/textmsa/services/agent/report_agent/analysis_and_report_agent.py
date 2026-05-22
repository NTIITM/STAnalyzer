"""
Analysis and Report Agent

该模块提供执行分析和报告生成功能：
1. 调用 Plan Agent 执行服务
2. 收集所有 execution 信息（成功和失败的）
3. 对成功的执行调用 Read Agent 进行分析
4. 对失败的执行获取失败原因
5. 整合所有信息并生成结构化报告
"""

import asyncio
from typing import Any, Callable, Optional

from textmsa.logging_config import get_logger
from textmsa.services.agent.plan_agent import astream_plan_agent
from textmsa.services.agent.read_agent import astream_read_agent_from_execution
from textmsa.services.service.service_service import get_service_service

logger = get_logger(__name__)


async def astream_analysis_and_report_agent(
    user_id: str,
    project_id: str,
    context_files: list[str],
    language: str = "zh",
    user_query: Optional[str] = None,
    on_event: Optional[Callable[[dict[str, Any]], None]] = None,
) -> dict[str, Any]:
    """
    异步流式运行 Analysis and Report Agent
    
    Args:
        user_id: 用户ID
        project_id: 项目ID
        context_files: 上下文文件ID列表
        language: 语言（默认中文）
        user_query: 用户查询（可选，如果不提供则使用默认查询）
        on_event: 可选的事件回调函数，用于接收实时消息
    
    Returns:
        包含分析和报告结果的字典：
        {
            "final_answer": str,                    # Plan Agent 的最终答案
            "all_executions": list[dict],           # 所有 execution 信息
            "execution_analyses": list[dict],       # 执行分析结果列表
            "report_data": dict,                    # 报告数据（用于生成结构化报告）
        }
    """
    # 如果没有提供 user_query，使用默认查询
    if user_query is None:
        user_query = (
            "请对于该次执行获得的结果进行分析，判断此次生信分析的结果是否正常，是否有在生物上的关键发现。"
            if language == "zh"
            else "Please analyze the results obtained from this execution, determine whether the results of this bioinformatics analysis are normal, and identify any key biological findings."
        )
    
    service_service = get_service_service()
    
    # 1. 调用 Plan Agent 执行服务
    if on_event:
        progress_msg = (
            "正在执行服务分析..."
            if language == "zh"
            else "Executing service analysis..."
        )
        on_event({"message": progress_msg})
    
    plan_result = await astream_plan_agent(
        user_query=user_query,
        user_id=user_id,
        project_id=project_id,
        context_files=context_files,
        language=language,
        on_event=on_event,
    )
    
    final_answer = plan_result.get("final_answer", "")
    all_executions = plan_result.get("all_executions", [])
    
    logger.info(
        f"Plan Agent completed: {len(all_executions)} executions found",
        extra={"execution_count": len(all_executions)},
    )
    
    # 2. 对每个 execution 进行分析
    execution_analyses = []
    
    if on_event:
        progress_msg = (
            f"正在分析 {len(all_executions)} 个执行结果..."
            if language == "zh"
            else f"Analyzing {len(all_executions)} execution results..."
        )
        on_event({"message": progress_msg})
    
    for idx, execution_info in enumerate(all_executions, 1):
        execution_id = execution_info.get("execution_id")
        status = str(execution_info.get("status", "")).lower()
        
        if not execution_id:
            # 如果没有 execution_id，跳过分析
            logger.warning(
                f"Execution record {idx} has no execution_id, skipping analysis",
                extra={"execution_info": execution_info},
            )
            execution_analyses.append({
                "execution_id": None,
                "status": status,
                "analysis": None,
                "error": "No execution_id available",
            })
            continue
        
        try:
            if on_event:
                service_name = execution_info.get("service_name", execution_id)
                progress_msg = (
                    f"正在分析执行 {idx}/{len(all_executions)}: {service_name} (ID: {execution_id})..."
                    if language == "zh"
                    else f"Analyzing execution {idx}/{len(all_executions)}: {service_name} (ID: {execution_id})..."
                )
                on_event({"message": progress_msg})
            
            if status == "completed":
                # 成功的执行：调用 Read Agent 分析结果和输出文件
                analysis_query = (
                    "请分析这个执行的结果和输出文件，评估执行质量和输出质量。"
                    if language == "zh"
                    else "Please analyze the results and output files of this execution, evaluate execution quality and output quality."
                )
                
                try:
                    analysis_result = await astream_read_agent_from_execution(
                        execution_id=execution_id,
                        user_id=user_id,
                        query=analysis_query,
                        language=language,
                        on_event=on_event,
                    )
                    
                    analysis_answer = analysis_result.get("final_answer", "")
                    execution_analyses.append({
                        "execution_id": execution_id,
                        "status": status,
                        "analysis": analysis_answer,
                        "error": None,
                    })
                except Exception as e:
                    logger.error(
                        f"分析 execution {execution_id} 失败: {e}",
                        exc_info=True,
                        extra={"execution_id": execution_id},
                    )
                    execution_analyses.append({
                        "execution_id": execution_id,
                        "status": status,
                        "analysis": None,
                        "error": f"分析失败: {str(e)}",
                    })
            else:
                # 失败的执行：获取失败原因
                try:
                    # 从数据库获取完整的 execution 信息（包括 error_message）
                    execution_detail = await asyncio.to_thread(
                        service_service.get_execution, execution_id
                    )
                    error_message = execution_detail.get("error_message", "")
                    feedback = execution_info.get("feedback", "")
                    
                    # 组合失败原因
                    failure_reason = error_message or feedback or (
                        f"执行状态: {status}"
                        if language == "zh"
                        else f"Execution status: {status}"
                    )
                    
                    execution_analyses.append({
                        "execution_id": execution_id,
                        "status": status,
                        "analysis": None,
                        "error": failure_reason,
                    })
                except Exception as e:
                    logger.error(
                        f"获取 execution {execution_id} 失败原因失败: {e}",
                        exc_info=True,
                        extra={"execution_id": execution_id},
                    )
                    execution_analyses.append({
                        "execution_id": execution_id,
                        "status": status,
                        "analysis": None,
                        "error": f"获取失败原因失败: {str(e)}",
                    })
        except Exception as e:
            logger.error(
                f"处理 execution {execution_id} 时出错: {e}",
                exc_info=True,
                extra={"execution_id": execution_id},
            )
            execution_analyses.append({
                "execution_id": execution_id,
                "status": status,
                "analysis": None,
                "error": f"处理失败: {str(e)}",
            })
    
    # 3. 构建报告数据
    report_data = {
        "user_query": user_query,
        "total_executions": len(all_executions),
        "successful_count": sum(1 for e in all_executions if str(e.get("status", "")).lower() == "completed"),
        "failed_count": sum(1 for e in all_executions if str(e.get("status", "")).lower() != "completed"),
        "executions": [],
    }
    
    # 将 execution 信息和分析结果合并
    for execution_info, analysis_info in zip(all_executions, execution_analyses):
        execution_data = {
            "execution_id": execution_info.get("execution_id"),
            "service_id": execution_info.get("service_id", ""),
            "service_name": execution_info.get("service_name", ""),
            "status": execution_info.get("status", ""),
            "input_file_ids": execution_info.get("input_file_ids", []),
            "output_file_ids": execution_info.get("output_file_ids", []),
            "parameters": execution_info.get("parameters", {}),
            "error_message": execution_info.get("error_message", ""),
            "analysis": analysis_info.get("analysis"),
            "error": analysis_info.get("error"),
        }
        report_data["executions"].append(execution_data)
    
    logger.info(
        "Analysis and Report Agent completed",
        extra={
            "total_executions": len(all_executions),
            "successful_count": report_data["successful_count"],
            "failed_count": report_data["failed_count"],
        },
    )
    
    return {
        "final_answer": final_answer,
        "all_executions": all_executions,
        "execution_analyses": execution_analyses,
        "report_data": report_data,
    }

