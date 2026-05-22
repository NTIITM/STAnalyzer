"""
Analyst 子图
负责执行 planner 分配的任务，整合服务调用 / sandbox / LLM 执行。
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Mapping, Sequence, NoReturn

from langgraph.graph import END, StateGraph

from textmsa.logging_config import get_logger
from textmsa.services.agent.llm_client import LLMClient, LLMRequest, get_llm_client
from textmsa.services.agent.langgraph import jobs
from textmsa.services.agent.langgraph.state import GraphState, PlannerTask, PlannerTodo, StateUpdate
from textmsa.services.agent.langgraph.subgraphs.utils import (
    fail_job_and_raise,
    format_log_extra,
    parse_json_from_llm_response,
)
from textmsa.services.agent.tools import (
    FileReaderTool,
    ServiceDispatchClient,
    ServiceDispatchResult,
    PythonREPLTool,
    MultiModalReaderTool,
)
from textmsa.services.data.mongodb_models import AgentJobStepStatus
from textmsa.services.file.file_service import get_file_info

logger = get_logger(__name__)

DEFAULT_NO_TASK_MESSAGE = "暂无可执行任务"
DEFAULT_ERROR_MESSAGE = "抱歉，分析任务执行失败，请稍后重试。"

ServiceHandler = Callable[[PlannerTask, GraphState], ServiceDispatchResult]


# ============= 失败处理 =============


def _fail_analyst(
    job_id: str,
    *,
    message: str,
    code: str = "unexpected_state",
    details: Mapping[str, Any] | None = None,
) -> NoReturn:
    fail_job_and_raise(
        job_id=job_id,
        role="analyst",
        message=message,
        code=code,
        details=details,
        log_extra=details,
    )


# ============= 工具函数 =============

def _require_active_todo(
    state: GraphState,
    job_id: str,
    *,
    error_message: str,
) -> PlannerTodo:
    """
    获取 active_todo，不存在时直接失败，避免在每个节点重复编写相同校验。
    """
    todo: PlannerTodo | None = state.get("active_todo")
    if not todo:
        _fail_analyst(
            job_id,
            message=error_message,
            code="missing_active_todo",
        )
    return todo


def _normalize_catalog(raw: Any) -> list[Mapping[str, Any]] | None:
    """
    规范化服务目录数据格式。
    
    Args:
        raw: 原始服务目录数据，可能是字典、列表或其他格式
        
    Returns:
        规范化后的服务列表，如果无法规范化则返回 None
    """
    if not raw:
        return None
    if isinstance(raw, Mapping):
        for key in ("services", "items", "data", "results"):
            if isinstance(raw.get(key), Sequence):
                raw = raw[key]
                break
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        normalized: list[Mapping[str, Any]] = []
        for item in raw:
            if isinstance(item, Mapping):
                normalized.append(dict(item))
        return normalized
    return None


def _extract_service_id(service: Mapping[str, Any]) -> str | None:
    """
    从服务对象中提取服务ID。
    
    Args:
        service: 服务对象字典
        
    Returns:
        服务ID字符串，如果未找到则返回 None
    """
    for key in ("service_id", "id", "_id", "uuid"):
        if service.get(key):
            return str(service[key])
    return None


# ============= LangGraph 节点（准备 / 执行 / 收尾） =============

def node_analyst_execute(
    state: GraphState,
) -> StateUpdate:
    """
    入口节点：检查是否有 active_todo，如果有则进入选择文件步骤。

    Args:
        state: LangGraph 全局状态。

    Returns:
        StateUpdate：初始化执行历史（如果需要）
    """
    job_id = state.get("job_id", "unknown")
    logger.info("Analyst node started", extra=format_log_extra({"job_id": job_id}))

    todo = _require_active_todo(
        state,
        job_id,
        error_message="Analyst node started without an active todo",
    )
    
    logger.info(
        "Analyst processing todo",
        extra=format_log_extra({"job_id": job_id, "goal": todo.get("goal")}),
    )
    
    # 初始化执行历史（如果还没有）
    if not state.get("execution_history"):
        return StateUpdate(execution_history=[])
    # 初始化 active_task, 在初始为空时，将 todo 的 goal 设置为 active_task，后续反思过程中会根据获得结果重写 goal
    if not state.get("active_task"):
        return StateUpdate(active_task=todo.get("goal"))
    # LangGraph 要求每个节点必须写入至少一个状态字段
    # 如果都已经初始化，返回 job_id 保持状态不变
    return StateUpdate({"job_id": state.get("job_id")})


def node_analyst_select_file(
    state: GraphState,
    *,
    llm_client: LLMClient | None = None,
) -> StateUpdate:
    """
    步骤1：为 todo/active_task 选择最合适的输入文件。

    设计调整后：
    - 不再依赖 analyst_output_file_ids，而是基于全局 context_files 进行选择。
    - 如果 context_files 为空，则回退为使用已有的 selected_file_id（如有）。

    Args:
        state: LangGraph 全局状态，应包含 active_todo / active_task
        llm_client: LLM 客户端（可注入）

    Returns:
        StateUpdate：更新 selected_file_id
    """
    job_id = state.get("job_id", "unknown")
    todo = _require_active_todo(
        state,
        job_id,
        error_message="Analyst select-file node invoked without active todo",
    )
    
    goal = todo.get("goal") or ""
    
    logger.info(
        "Analyst selecting input file for todo",
        extra={"job_id": job_id, "goal": goal},
    )
    
    llm = llm_client or get_llm_client()
    user_id = str(state.get("user_id") or "")

    # 从全局 context_files 中收集候选文件
    context_files = state.get("context_files") or []
    context_file_ids: list[str] = []
    for cf in context_files:
        try:
            fid = cf.get("file_id")
        except AttributeError:
            # 兼容旧结构（直接存 id）
            fid = cf
        if fid:
            fid_str = str(fid)
            if fid_str not in context_file_ids:
                context_file_ids.append(fid_str)

    selected_file_id: str | None = None
    file_type_id: str | None = None

    # 如果没有任何上下文文件，则回退到已有的 selected_file_id
    if not context_file_ids:
        selected_file_id = state.get("selected_file_id")
        if not selected_file_id:
            _fail_analyst(
                job_id,
                message="No context files or selected_file_id available for analyst selection",
                code="missing_context_files",
                details={},
            )

        try:
            file_info = get_file_info(str(selected_file_id), user_id)
            file_type_id = file_info.get("file_type_id")
            if not file_type_id:
                _fail_analyst(
                    job_id,
                    message="Selected file does not have a file_type_id",
                    code="missing_file_type_id",
                    details={"selected_file_id": selected_file_id},
                )
            logger.info(
                "Using selected_file_id from state (no context_files available)",
                extra={
                    "job_id": job_id,
                    "selected_file_id": selected_file_id,
                    "file_type_id": file_type_id,
                },
            )
        except Exception as exc:
            _fail_analyst(
                job_id,
                message="Failed to resolve selected_file_id for analyst selection",
                code="file_info_lookup_failed",
                details={"error": str(exc)},
            )

        return StateUpdate(selected_file_id=selected_file_id)

    # 基于 context_files 构造候选列表
    file_candidates = []
    for file_id in context_file_ids:
        try:
            info = get_file_info(str(file_id), user_id)
            file_candidates.append(
                {
                    "file_id": str(file_id),
                    "filename": info.get("filename", ""),
                    "description": info.get("description") or "",
                    "file_type": (info.get("file_type") or {}).get("name", ""),
                }
            )
        except Exception as exc:
            _fail_analyst(
                job_id,
                message="Failed to get file info for context file",
                code="file_info_lookup_failed",
                details={"file_id": str(file_id), "error": str(exc)},
            )

    if not file_candidates:
        _fail_analyst(
            job_id,
            message="No valid context files available for analyst selection",
            code="no_valid_context_files",
            details={},
        )

    if len(file_candidates) == 1:
        # 只有一个候选，直接返回
        selected_file_id = file_candidates[0]["file_id"]
        try:
            info = get_file_info(selected_file_id, user_id)
            file_type_id = info.get("file_type_id")
            logger.info(
                "Only one context file candidate, using it directly",
                extra={
                    "job_id": job_id,
                    "selected_file_id": selected_file_id,
                    "file_type_id": file_type_id,
                },
            )
        except Exception as exc:
            _fail_analyst(
                job_id,
                message="Failed to get file info for only context candidate",
                code="file_info_lookup_failed",
                details={"error": str(exc)},
            )
    else:
        # 使用 LLM 从候选文件中选择最合适的一个
        user_message = state.get("user_message", "")

        prompt = f"""你是一个智能助手。根据用户任务，从候选文件中选择一个最合适的输入文件。

用户问题：{user_message}
任务目标：{goal}

候选文件列表：
{json.dumps(file_candidates, ensure_ascii=False, indent=2)}

请根据任务需求，从候选文件列表中选择一个最合适的文件。

请以 JSON 格式返回结果，格式如下：
{{
  "selected_file_id": "file_id"
}}

只返回 JSON，不要包含其他文字说明。"""

        try:
            logger.info(
                "Using LLM to select file from context_files",
                extra={
                    "job_id": job_id,
                    "candidates_count": len(file_candidates),
                },
            )
            request = LLMRequest(
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个专业的助手，擅长根据任务需求从候选文件中选择最合适的一个。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            response = llm.chat(request)
            content = response.content.strip()
            result = parse_json_from_llm_response(content, default={})

            selected_file_id = result.get("selected_file_id")
            valid_file_ids = {c["file_id"] for c in file_candidates}
            if not selected_file_id or selected_file_id not in valid_file_ids:
                _fail_analyst(
                    job_id,
                    message="LLM selected invalid file for analyst",
                    code="invalid_llm_selection",
                    details={
                        "selected_file_id": selected_file_id,
                        "valid_file_ids": list(valid_file_ids),
                    },
                )

            info = get_file_info(selected_file_id, user_id)
            file_type_id = info.get("file_type_id")
            logger.info(
                "File selected by LLM from context_files",
                extra={
                    "job_id": job_id,
                    "selected_file_id": selected_file_id,
                    "file_type_id": file_type_id,
                },
            )
        except Exception as exc:
            _fail_analyst(
                job_id,
                message="LLM file selection from context files failed",
                code="llm_file_selection_failed",
                details={"error": str(exc)},
            )
    
    logger.info(
        "File selected successfully",
        extra={
            "job_id": job_id,
            "selected_file_id": selected_file_id,
            "file_type_id": file_type_id,
        },
    )
    
    return StateUpdate(selected_file_id=selected_file_id)


def _record_tool_step(
    *,
    state: GraphState,
    task_id: str,
    tool_name: str,
    inputs: Mapping[str, Any],
    outputs: Mapping[str, Any],
    metadata: Mapping[str, Any],
    artifacts: Sequence[str] | None,
    status: AgentJobStepStatus,
) -> None:
    job_id = state.get("job_id")
    if not job_id:
        return
    jobs.record_tool_step(
        job_id=job_id,
        role="analyst",
        name=f"{tool_name}:{task_id}",
        tool=tool_name,
        inputs=dict(inputs),
        outputs=dict(outputs),
        metadata={"task_id": task_id, **dict(metadata)},
        artifacts=artifacts or (),
        status=status,
    )


def _record_failure_step(
    state: GraphState,
    *,
    task_id: str,
    task_type: str,
    description: str | None,
    error_message: str,
) -> None:
    job_id = state.get("job_id")
    if not job_id:
        return
    jobs.record_tool_step(
        job_id=job_id,
        role="analyst",
        name=f"{task_type}:{task_id}",
        tool=task_type,
        inputs={"task_id": task_id, "description": description},
        outputs={"error": error_message},
        metadata={"task_id": task_id, "error": error_message},
        status=AgentJobStepStatus.FAILED,
    )


def node_analyst_match_service(
    state: GraphState,
) -> StateUpdate:
    """
    步骤1：读取 todo，获取可用服务，使用 LLM 匹配最合适的服务。
    
    Args:
        state: LangGraph 全局状态，应包含 active_todo
        llm_client: LLM 客户端（可注入）
    
    Returns:
        StateUpdate：更新 service_id 和相关信息到 execution_history
    """
    job_id = state.get("job_id", "unknown")
    todo: PlannerTodo | None = state.get("active_todo")
    
    if not todo:
        _fail_analyst(
            job_id,
            message="Analyst service matching invoked without active todo",
            code="missing_active_todo",
        )
    
    goal = todo.get("goal") or ""

    logger.info(
        "Analyst matching service for todo",
        extra={"job_id": job_id, "goal": goal},
    )
    
    llm = get_llm_client()
    service_client = ServiceDispatchClient()
    
    # 从 execution_history 获取最后一次 select_file 步骤的文件信息
    selected_file_id: str | None = state.get("selected_file_id")

    file_info = get_file_info(selected_file_id, str(state.get("user_id") or ""))
    file_type_id = file_info.get("file_type_id")
    # 获取可用服务列表（根据文件类型筛选）
    try:
        logger.info(
            "Fetching available services",
            extra={
                "job_id": job_id,
                "user_id": str(state.get("user_id") or ""),
                "project_id": state.get("project_id"),
                "file_type_id": file_type_id,
            },
        )
        services_response = service_client.list_available_services(
            user_id=str(state.get("user_id") or ""),
            project_id=state.get("project_id"),
            file_type_id=file_type_id,  # 根据文件类型筛选服务
            limit=1000,
        )
        logger.info(
            "Received services response",
            extra={
                "job_id": job_id,
                "response_type": type(services_response).__name__,
                "response_keys": list(services_response.keys()) if isinstance(services_response, dict) else None,
                "response_preview": str(services_response)[:500] if services_response else None,
            },
        )
        # 规范化服务列表
        catalog = _normalize_catalog(services_response) or []
        logger.info(
            "Normalized service catalog",
            extra={
                "job_id": job_id,
                "catalog_size": len(catalog),
                "catalog_preview": [
                    {
                        "service_id": _extract_service_id(svc),
                        "name": svc.get("name"),
                    }
                    for svc in catalog[:5]
                ] if catalog else None,
            },
        )
    except Exception as exc:
        _fail_analyst(
            job_id,
            message="Failed to list services for analyst matching",
            code="service_catalog_unavailable",
            details={"error": str(exc)},
        )
    
    if not catalog:
        _fail_analyst(
            job_id,
            message="No services available for analyst matching",
            code="missing_services",
            details={"goal": goal},
        )
    
    # 使用 LLM 匹配服务
    logger.info(
        "Starting LLM service matching",
        extra={
            "job_id": job_id,
            "catalog_size": len(catalog),
            "goal": goal,
        },
    )
    matched_service = _match_service_with_llm(
        todo=todo,
        catalog=catalog,
        llm=llm,
        state=state,
    )
    
    if not matched_service:
        _fail_analyst(
            job_id,
            message="LLM failed to match a service",
            code="service_matching_failed",
            details={"goal": goal, "catalog_size": len(catalog)},
        )
    
    service_id = _extract_service_id(matched_service)
    if not service_id:
        _fail_analyst(
            job_id,
            message="Matched service does not have an ID",
            code="service_missing_id",
            details={
                "matched_service_keys": list(matched_service.keys())
                if isinstance(matched_service, dict)
                else None,
                "matched_service_preview": str(matched_service)[:500],
            },
        )
    
    logger.info(
        "Service matched by LLM",
        extra={
            "job_id": job_id,
            "service_id": service_id,
            "service_name": matched_service.get("name"),
        },
    )
    
    # 获取服务元信息
    try:
        logger.info(
            "Fetching service metadata",
            extra={
                "job_id": job_id,
                "service_id": service_id,
                "user_id": str(state.get("user_id") or ""),
                "project_id": state.get("project_id"),
            },
        )
        service_metadata = service_client.fetch_service_metadata(
            service_id,
            user_id=str(state.get("user_id") or ""),
            project_id=state.get("project_id"),
        )
        logger.info(
            "Service metadata fetched",
            extra={
                "job_id": job_id,
                "service_id": service_id,
                "has_parameter_template": "parameter_template" in service_metadata,
                "has_parameter_schema": "parameter_schema" in service_metadata,
                "service_name": service_metadata.get("name"),
            },
        )
    except Exception as exc:
        _fail_analyst(
            job_id,
            message="Failed to fetch metadata for matched service",
            code="service_metadata_unavailable",
            details={"service_id": service_id, "error": str(exc)},
        )
    
    logger.info(
        "Service matched successfully",
        extra={
            "job_id": job_id,
            "service_id": service_id,
            "service_name": service_metadata.get("name"),
        },
    )
    
    return StateUpdate(matched_service_id=service_id)


def _match_service_with_llm(
    todo: Mapping[str, Any],
    catalog: list[Mapping[str, Any]],
    llm: LLMClient,
    state: GraphState,
) -> Mapping[str, Any] | None:
    """
    使用 LLM 匹配最合适的服务。
    
    Returns:
        匹配的服务字典，如果未匹配则返回 None
    """
    job_id = state.get("job_id", "unknown")
    goal = todo.get("goal") or ""
    user_message = state.get("user_message", "")
    evidence_summary = state.get("evidence_summary") or ""
    
    # 构建服务列表摘要
    services_summary = []
    for idx, service in enumerate(catalog):
        service_id = _extract_service_id(service)
        if not service_id:
            logger.debug(
                "Skipping service without ID",
                extra=format_log_extra({"index": idx, "service_keys": list(service.keys()) if isinstance(service, dict) else None}),
            )
            continue
        services_summary.append({
            "index": idx,
            "service_id": service_id,
            "name": service.get("name") or "",
            "description": (service.get("description") or "")[:200],
        })
    
    if not services_summary:
        _fail_analyst(
            job_id,
            message="No valid services available for LLM matching",
            code="no_valid_services",
            details={"catalog_size": len(catalog)},
        )
    
    logger.info(
        "Built services summary for LLM matching",
        extra={
            "services_count": len(services_summary),
            "services_preview": services_summary[:3],
        },
    )
    
    # 构建 prompt
    prompt = f"""你是一个智能服务匹配助手。根据用户任务，从可用服务列表中选择最匹配的服务。

用户问题：{user_message}
任务目标：{goal}

对当前数据，可用的服务列表（共 {len(services_summary)} 个）：
{json.dumps(services_summary, ensure_ascii=False, indent=2)}

请分析任务需求，找到最合适的、能够满足任务需求或推进任务目标的服务，即使只是完成最终目标的一个阶段。
给出匹配分数（0-100，分数越高表示匹配度越高）。

请以 JSON 格式返回结果，格式如下：
{{
  "service_id": "服务ID",
  "score": 匹配分数,
  "reason": "匹配原因"
}}

只返回 JSON，不要包含其他文字说明。"""
    
    try:
        logger.info(
            "Sending LLM request for service matching",
            extra={
                "prompt_length": len(prompt),
                "services_count": len(services_summary),
                "goal": goal,
            },
        )
        request = LLMRequest(
            messages=[
                {"role": "system", "content": "你是一个专业的服务匹配助手，擅长根据任务需求匹配最合适的服务。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
        )
        response = llm.chat(request)
        
        logger.info(
            "Received LLM response for service matching",
            extra={
                "response_length": len(response.content) if response.content else 0,
                "response_preview": response.content[:300] if response.content else None,
            },
        )
        
        # 解析响应
        content = response.content.strip()
        original_content = content
        result = parse_json_from_llm_response(content, default={})
        
        logger.debug(
            "Parsing LLM response",
            extra=format_log_extra({
                "original_length": len(original_content),
                "parsed_length": len(content),
                "parsed_content": content[:500],
            }),
        )
        
        service_id = result.get("service_id")
        score = result.get("score")
        reason = result.get("reason")
        
        logger.info(
            "Parsed LLM matching result",
            extra=format_log_extra({
                "service_id": service_id,
                "score": score,
                "reason": reason,
            }),
        )
        
        if not service_id:
            _fail_analyst(
                job_id,
                message="LLM response missing service_id",
                code="missing_service_id",
                details={"parsed_result": result},
            )
        
        # 查找对应的服务
        matched_service = None
        for service in catalog:
            if _extract_service_id(service) == service_id:
                matched_service = service
                break
        
        if matched_service:
            logger.info(
                "Successfully matched service from catalog",
                extra={
                    "service_id": service_id,
                    "service_name": matched_service.get("name"),
                },
            )
        else:
            _fail_analyst(
                job_id,
                message="LLM matched service_id not found in catalog",
                code="service_not_in_catalog",
                details={
                    "service_id": service_id,
                    "catalog_service_ids": [
                        _extract_service_id(svc) for svc in catalog[:10]
                    ],
                },
            )
        
        return matched_service
        
    except json.JSONDecodeError as exc:
        _fail_analyst(
            job_id,
            message="Failed to parse LLM response for service matching",
            code="service_matching_parse_error",
            details={
                "error": str(exc),
                "response_content": response.content[:500]
                if response and response.content
                else None,
            },
        )
    except Exception as exc:
        _fail_analyst(
            job_id,
            message="LLM service matching failed",
            code="service_matching_exception",
            details={"error": str(exc)},
        )


def node_analyst_execute_service(
    state: GraphState,
    *,
    llm_client: LLMClient | None = None,
) -> StateUpdate:
    """
    步骤2：根据 parameter_template 生成参数，调用服务执行。
    
    Args:
        state: LangGraph 全局状态
        llm_client: LLM 客户端（可注入）
    
    Returns:
        StateUpdate：更新执行结果和 output_file_ids
    """
    job_id = state.get("job_id", "unknown")
    todo: PlannerTodo | None = state.get("active_todo")
    execution_history = state.get("execution_history") or []
    
    # 提前提取 goal，确保在异常处理中也能使用
    goal = todo.get("goal") or "" if todo else ""

    
    # 获取最后一次匹配的服务信息
    matched_service_id = state.get("matched_service_id")
    if not matched_service_id:
        _fail_analyst(
            job_id,
            message="No matched service found for analyst execution",
            code="missing_matched_service",
        )
    
    # 获取已选中的文件ID（从 match_service 步骤中）
    selected_file_id = state.get("selected_file_id")
    service_id = state.get("matched_service_id")
    llm = llm_client or get_llm_client()
    service_client = ServiceDispatchClient()
    
    # 获取服务元信息
    try:
        logger.info(
            "Fetching service metadata for execution",
        extra={
            "job_id": job_id,
                "service_id": service_id,
                "user_id": str(state.get("user_id") or ""),
                "project_id": state.get("project_id"),
            },
        )
        service_metadata = service_client.fetch_service_metadata(
            service_id,
            user_id=str(state.get("user_id") or ""),
            project_id=state.get("project_id"),
        )
        # 提前提取 parameter_template 和 parameter_schema，用于日志记录
        parameter_template = service_metadata.get("parameter_template") or {}
        parameter_schema = service_metadata.get("parameter_schema") or {}
        
        logger.info(
            "Service metadata fetched for execution",
            extra=format_log_extra({
                "job_id": job_id,
                "service_id": service_id,
                "has_parameter_template": "parameter_template" in service_metadata,
                "has_parameter_schema": "parameter_schema" in service_metadata,
                "parameter_template_keys": list(parameter_template.keys()) if parameter_template else [],
                "parameter_schema_keys": list(parameter_schema.keys()) if parameter_schema else [],
            }),
        )
    except Exception as exc:
        _fail_analyst(
            job_id,
            message="Failed to fetch service metadata for execution",
            code="service_metadata_unavailable",
            details={"service_id": service_id, "error": str(exc)},
        )
    
    logger.info(
        "Generating service parameters with LLM",
        extra={
            "job_id": job_id,
            "service_id": service_id,
            "parameter_template_size": len(parameter_template),
            "parameter_schema_size": len(parameter_schema),
        },
    )
    
    # 使用 LLM 生成参数（文件已在匹配阶段选择）
    generated_params, input_file_ids = _generate_service_parameters_with_llm(
        todo=todo,
        service_metadata=service_metadata,
        parameter_template=parameter_template,
        parameter_schema=parameter_schema,
        state=state,
        llm=llm,
        selected_file_id=selected_file_id,  # 传入已选中的文件ID
    )
    
    logger.info(
        "Service parameters generated",
        extra={
            "job_id": job_id,
            "service_id": service_id,
            "generated_params": generated_params,
            "input_file_ids": input_file_ids,
            "input_file_count": len(input_file_ids),
        },
    )
    
    if not input_file_ids:
        _fail_analyst(
            job_id,
            message="No input files available for analyst service execution",
            code="missing_input_files",
            details={
                "service_id": service_id,
                "selected_file_id": state.get("selected_file_id"),
            },
        )
    
    # 执行服务
    logger.info(
        "Invoking service",
        extra={
            "job_id": job_id,
            "service_id": service_id,
            "input_file_ids": input_file_ids,
            "input_file_count": len(input_file_ids),
            "parameters": generated_params,
            "user_id": str(state.get("user_id") or ""),
            "project_id": state.get("project_id"),
        },
    )
    try:
        service_result = service_client.invoke_service(
            service_id=service_id,
            input_files=input_file_ids,
            parameters=generated_params,
            user_id=str(state.get("user_id") or ""),
            project_id=state.get("project_id"),
        )
        logger.info(
            "Service invocation completed",
            extra={
                "job_id": job_id,
                "service_id": service_id,
                "execution_id": service_result.metadata.get("execution_id"),
                "status": service_result.metadata.get("status"),
                "output_file_count": len(service_result.artifacts),
                "output_preview": service_result.output[:200] if service_result.output else None,
            },
        )
        
        execution_id = service_result.metadata.get("execution_id")
        initial_status = service_result.metadata.get("status", "").lower()
        output_file_ids = list(service_result.artifacts)
        
        # 如果服务状态是 "running"，等待服务执行完成
        if initial_status == "running" and execution_id:
            logger.info(
                "Service is running asynchronously, waiting for completion",
                extra={
                    "job_id": job_id,
                    "service_id": service_id,
                    "execution_id": execution_id,
                },
            )
            try:
                # 等待服务执行完成（默认最多等待5分钟，每2秒轮询一次）
                completed_execution = service_client.wait_for_execution(
                    execution_id=execution_id,
                    max_wait_seconds=300.0,  # 5分钟
                    poll_interval_seconds=2.0,
                    timeout_error=True,  # 超时抛出异常
                )
                
                # 更新状态和输出文件ID
                final_status = completed_execution.get("status", "").lower()
                final_output_file_ids = completed_execution.get("output_file_ids", [])
                
                logger.info(
                    "Service execution completed after waiting",
                    extra={
                        "job_id": job_id,
                        "service_id": service_id,
                        "execution_id": execution_id,
                        "final_status": final_status,
                        "final_output_file_count": len(final_output_file_ids),
                    },
                )
                
                # 使用完成后的状态和输出文件ID
                output_file_ids = [str(fid) for fid in final_output_file_ids if fid]
                final_status_value = final_status
                
            except Exception as wait_exc:
                logger.error(
                    "Failed to wait for service execution completion",
                    extra={
                        "job_id": job_id,
                        "service_id": service_id,
                        "execution_id": execution_id,
                        "error": str(wait_exc),
                    },
                    exc_info=True,
                )
                # 如果等待失败（超时或执行失败），抛出异常，让外层处理
                # 这样可以让整个任务标记为失败，而不是继续使用可能不完整的结果
                raise
        else:
            # 如果状态不是 "running"，直接使用初始状态
            final_status_value = initial_status
        
        # 更新执行历史
        # 重要：保存 service_name 和 service_description，以便后续评估时使用
        execution_history.append({
            "step": "execute_service",
            "service_id": service_id,
            "service_name": service_metadata.get("name"),
            "service_description": service_metadata.get("description"),
            "input_file_ids": input_file_ids,
            "parameters": generated_params,
            "output_file_ids": output_file_ids,
            "execution_id": execution_id,
            "status": final_status_value,  # 使用最终状态（可能是 "completed" 或 "failed"）
            "output": service_result.output,
        })
        
        # 记录执行步骤
        _record_tool_step(
            state=state,
            task_id=goal,
            tool_name=service_metadata.get("name") or service_id,
            inputs={
                "goal": goal,
                "input_file_ids": input_file_ids,
                "parameters": generated_params,
            },
            outputs={"summary": service_result.output, "output_file_ids": output_file_ids},
            metadata=service_result.metadata,
            artifacts=service_result.artifacts,
            status=AgentJobStepStatus.COMPLETED,
        )
        
        logger.info(
            "Service executed successfully",
            extra={
                "job_id": job_id,
                "service_id": service_id,
                "execution_id": service_result.metadata.get("execution_id"),
                "output_file_count": len(output_file_ids),
            },
        )
        
        return StateUpdate(
            execution_history=execution_history,
        )
        
    except Exception as exc:
        logger.error(
            "Service execution failed",
            extra={"job_id": job_id, "service_id": service_id, "error": str(exc)},
            exc_info=True,
        )
        
        # 在失败时也保存 service_name 和 service_description（如果可用）
        execution_history.append({
            "step": "execute_service",
            "service_id": service_id,
            "service_name": service_metadata.get("name") if 'service_metadata' in locals() else None,
            "service_description": service_metadata.get("description") if 'service_metadata' in locals() else None,
            "error": str(exc),
            "status": "failed",
        })
        

        _record_failure_step(
            state,
            task_id=goal,
            task_type="service",
            description=goal,
            error_message=str(exc),
        )
        
        return StateUpdate(execution_history=execution_history)


def _generate_service_parameters_with_llm(
    todo: Mapping[str, Any],
    service_metadata: Mapping[str, Any],
    parameter_template: Mapping[str, Any],
    parameter_schema: Mapping[str, Any],
    state: GraphState,
    llm: LLMClient,
    selected_file_id: str,
) -> tuple[dict[str, Any], list[str]]:
    """
    使用 LLM 根据 parameter_template 和 parameter_schema 生成服务调用参数。
    文件已在匹配阶段选择，这里直接使用。
    
    Args:
        selected_file_id: 已选中的文件ID（必需）
    
    Returns:
        (parameters, input_file_ids): 生成的参数和输入文件ID列表（固定为 [selected_file_id]）
    """
    goal = todo.get("goal") or ""
    user_message = state.get("user_message", "")
    evidence_summary = state.get("evidence_summary") or ""
    
    # 直接使用传入的文件ID
    input_file_ids = [str(selected_file_id)]
    
    logger.info(
        "Starting parameter generation",
        extra={
            "selected_file_id": selected_file_id,
            "parameter_template_size": len(parameter_template),
            "parameter_schema_size": len(parameter_schema),
        },
    )
    
    # 构建参数定义说明
    param_definitions = []
    for param_name, param_def in parameter_schema.items():
        if isinstance(param_def, dict):
            param_type = param_def.get("type", "string")
            param_desc = param_def.get("description", "")
            default_value = param_def.get("default_value")
            required = param_def.get("required", False)
            
            param_info = {
                "name": param_name,
                "type": param_type,
                "description": param_desc,
                "required": required,
            }
            
            if param_type == "enum":
                param_info["enum_values"] = param_def.get("enum_values", [])
            elif param_type in ["continuous", "discrete"]:
                if param_def.get("min_value") is not None:
                    param_info["min_value"] = param_def.get("min_value")
                if param_def.get("max_value") is not None:
                    param_info["max_value"] = param_def.get("max_value")
            elif param_type == "string":
                if param_def.get("min_length") is not None:
                    param_info["min_length"] = param_def.get("min_length")
                if param_def.get("max_length") is not None:
                    param_info["max_length"] = param_def.get("max_length")
            
            if default_value is not None:
                param_info["default_value"] = default_value
            
            param_definitions.append(param_info)
    
    # 构建 prompt（只关注参数生成）
    prompt = f"""你是一个智能参数生成助手。根据用户任务和服务的参数定义，生成合适的参数值。

用户问题：{user_message}
任务目标：{goal}
已知证据：{evidence_summary}

服务名称: {service_metadata.get("name", "")}
服务描述: {service_metadata.get("description", "")}

参数模板（默认值）:
{json.dumps(parameter_template, ensure_ascii=False, indent=2)}

参数定义（约束和类型）:
{json.dumps(param_definitions, ensure_ascii=False, indent=2)}

请根据任务需求，为所有参数生成合适的值。规则：
1. 必须遵循参数类型和约束（如 enum 值、数值范围、字符串长度等）
2. 必填参数（required=true）必须提供值
3. 可选参数如果任务中没有明确要求，可以使用默认值或合理的值
4. 参数值必须符合参数定义中的类型和约束

请以 JSON 格式返回结果，格式如下：
{{
  "parameters": {{
    "参数名1": "参数值1",
    "参数名2": 参数值2,
    ...
  }}
}}

只返回 JSON，不要包含其他文字说明。"""
    
    try:
        system_content = "你是一个专业的参数生成助手，擅长根据任务需求生成符合参数定义的服务调用参数。"
        
        logger.info(
            "Sending LLM request for parameter generation",
            extra={
                "prompt_length": len(prompt),
                "parameter_template_size": len(parameter_template),
                "parameter_schema_size": len(parameter_schema),
            },
        )
        
        request = LLMRequest(
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
        )
        response = llm.chat(request)
        
        logger.info(
            "Received LLM response for parameter generation",
            extra={
                "response_length": len(response.content) if response.content else 0,
                "response_preview": response.content[:300] if response.content else None,
            },
        )
        
        # 解析响应
        content = response.content.strip()
        result = parse_json_from_llm_response(content, default={})
        
        logger.info(
            "Parsed LLM parameter generation result",
            extra=format_log_extra({
                "has_parameters": "parameters" in result,
                "parameters_keys": list(result.get("parameters", {}).keys()) if result.get("parameters") else [],
            }),
        )
        
        # 处理参数生成
        parameters = result.get("parameters", {})
        logger.info(
            "Extracted parameters from LLM response",
            extra={
                "parameters": parameters,
                "parameter_count": len(parameters),
            },
        )
        
        # 合并默认值
        final_parameters = dict(parameter_template)
        final_parameters.update(parameters)
        
        logger.info(
            "Parameter generation completed successfully",
            extra={
                "final_params": final_parameters,
                "input_file_ids": input_file_ids,
            },
        )
        
        return final_parameters, input_file_ids
        
    except json.JSONDecodeError as exc:
        _fail_analyst(
            state.get("job_id", "unknown"),
            message="Failed to parse LLM parameter response as JSON",
            code="parameter_parse_error",
            details={
                "error": str(exc),
                "response_content": response.content[:500] if response.content else None,
            },
        )
    except Exception as exc:
        _fail_analyst(
            state.get("job_id", "unknown"),
            message="LLM parameter generation failed",
            code="parameter_generation_failed",
            details={"error": str(exc)},
        )


def node_analyst_reflect(
    state: GraphState,
) -> StateUpdate:
    """
    步骤3：总结执行结果并反思是否完成 todo，维护 context_files，并通过 analyst_next_step 决定后续路由。

    功能：
    1. 将本轮产生的输出文件合并进全局 context_files（去重）。
    2. 基于任务目标 / active_task 与完整执行历史，让 LLM 评估当前任务是否完成。
    3. 未完成：重写 active_todo（goal / metadata.execution_history），设置 analyst_next_step = "select_file"。
    4. 已完成：生成 completed_task / 标记 todo 完成，设置 analyst_next_step = "summarize" 以进入总结子流程。
    """

    job_id = state.get("job_id", "unknown")
    jobs.check_job_cancelled(job_id)
    todo: PlannerTodo | None = state.get("active_todo")
    goal = todo.get("goal") or "" if todo else ""
    active_task = state.get("active_task") or goal

    llm = get_llm_client()
    user_id = str(state.get("user_id") or "")

    # 1. 维护 context_files：从本轮执行历史中提取 output_file_ids，并合并到全局 context_files
    execution_history = list(state.get("execution_history") or [])
    existing_context_files = list(state.get("context_files") or [])

    existing_ids: set[str] = set()
    normalized_context_files: list[dict[str, Any]] = []
    for cf in existing_context_files:
        if isinstance(cf, Mapping):
            fid = cf.get("file_id")
            if fid:
                fid_str = str(fid)
                if fid_str not in existing_ids:
                    existing_ids.add(fid_str)
                    normalized_context_files.append(
                        {"file_id": fid_str, "file_path": cf.get("file_path", ""), "file_name": cf.get("file_name")}
                    )
        else:
            # 兼容旧格式：直接是 file_id
            fid_str = str(cf)
            if fid_str not in existing_ids:
                existing_ids.add(fid_str)
                normalized_context_files.append({"file_id": fid_str, "file_path": ""})

    new_file_ids: list[str] = []
    for entry in execution_history:
        for fid in entry.get("output_file_ids") or []:
            fid_str = str(fid)
            if fid_str not in existing_ids:
                existing_ids.add(fid_str)
                new_file_ids.append(fid_str)
                normalized_context_files.append({"file_id": fid_str, "file_path": ""})

    updated_context_files = normalized_context_files

    # 2. 构造执行历史文本与文件概览，用于 LLM 评估
    todo_metadata = todo.get("metadata") or {}
    previous_execution_history = todo_metadata.get("execution_history") or []
    if not isinstance(previous_execution_history, list):
        previous_execution_history = []

    # 合并之前的执行历史与当前轮执行历史（简单拼接，按需要可去重）
    full_execution_history = list(previous_execution_history) + execution_history
    # 控制长度，避免 prompt 过大
    try:
        execution_history_text = json.dumps(full_execution_history[-20:], ensure_ascii=False, indent=2)
    except Exception:
        execution_history_text = str(full_execution_history[-20:])

    # 文件概览（只用元信息，不读内容）
    file_overview_lines: list[str] = []
    for cf in updated_context_files:
        fid = cf.get("file_id")
        if not fid:
            continue
        try:
            info = get_file_info(str(fid), user_id)
            filename = info.get("filename", "")
            file_type = info.get("file_type") or {}
            file_type_name = file_type.get("name", "") if isinstance(file_type, Mapping) else ""
            description = info.get("description") or ""
            file_overview_lines.append(
                f"- ID: {fid}, 名称: {filename}, 类型: {file_type_name}, 描述: {description[:100]}"
            )
        except Exception as exc:
            _fail_analyst(
                job_id,
                message="Failed to get file info for reflect overview",
                code="file_info_lookup_failed",
                details={"file_id": str(fid), "error": str(exc)},
            )

    files_overview_text = "\n".join(file_overview_lines) if file_overview_lines else "无可用文件"

    user_message = state.get("user_message", "")
    evidence_summary = state.get("evidence_summary") or ""

    prompt = f"""你是一个任务完成度评估和执行结果总结助手。根据任务目标、当前正在执行的任务以及执行历史，总结本次执行结果并判断任务是否已完成。

用户原始问题：{user_message}
任务目标（goal）：{goal}
当前 active_task：{active_task}
已知证据：{evidence_summary}

完整执行历史：
{execution_history_text}

当前可用文件列表（仅包含元信息，不含内容）：
{files_overview_text}


重要提示：
1. 如果执行历史显示多次尝试执行相同或类似的任务，但任务目标仍未达成，这可能意味着当前没有可用的服务能够支持完成该任务。此时应该将任务标记为完成（is_completed=true），并在 reason 中明确告知用户："经过多次尝试，当前系统中没有可用的服务能够支持完成此任务。建议检查是否有其他方式可以达成目标，或者联系管理员添加相应的服务支持。"
2. 如果执行历史显示任务已经取得实质性进展或已经完成，应该标记为完成。
3. 如果任务未完成但仍有明确的下一步可执行，可以继续执行。

请完成以下任务：
1. 总结本次执行结果：本次调用了什么服务，获得了什么文件，执行状态如何。
2. 判断任务目标是否已经达成，任务是否可以视为完成。
3. 特别关注：如果多次执行同一任务且没有实质性进展，应该考虑是否因为缺少服务支持而无法继续，此时应标记为完成并在原因中说明。
4. 如果未完成，请根据当前进展，给出更新后的下一步任务描述（updated_task），用于指导下一轮服务选择。
5. 给出下一步建议动作（next_action），例如"继续匹配服务"、"尝试特定服务"等。

请以 JSON 格式返回结果，格式如下：
{{
  "execution_summary": "本次执行结果总结（调用了什么服务，获得了什么文件等）",
  "is_completed": true,
  "reason": "完成或未完成的原因。如果是因为缺少服务支持而无法继续，请明确说明。",
  "updated_task": "如果未完成，更新后的正在进行任务描述；如果已完成，可以为空字符串",
  "next_action": "如果需要继续，建议下一步操作（如：select_file、summarize等）"
}}

只返回 JSON，不要包含其他文字说明。"""

    try:
        request = LLMRequest(
            messages=[
                {
                    "role": "system",
                    "content": "你是一个专业的任务完成度评估和执行结果总结助手，能够准确总结执行结果并判断任务是否已完成。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        response = llm.chat(request)

        content = response.content.strip()
        result = parse_json_from_llm_response(content, default={})
        execution_summary_text = result.get("execution_summary", "")
        is_completed = bool(result.get("is_completed", False))
        reason = result.get("reason", "")
        updated_task = result.get("updated_task", "") or ""
        next_action = result.get("next_action", "") or ""

        logger.info(
            "Analyst reflection completed",
            extra=format_log_extra(
                {
                    "job_id": job_id,
                    "is_completed": is_completed,
                    "reason": reason,
                    "updated_task": updated_task,
                }
            ),
        )

        # 合并完整执行历史，用于保存到 todo / completed_task 中
        final_execution_history = full_execution_history

        if is_completed:
            # 标记 todo 完成，记录上下文文件和执行历史到 todo.metadata
            planner_todos = list(state.get("planner_todos") or [])
            updated_todos: list[PlannerTodo] = []
            for t in planner_todos:
                # 使用 goal 来匹配 todo
                if t.get("goal") == goal:
                    new_t = dict(t)
                    new_t["status"] = "completed"
                    meta = dict(new_t.get("metadata") or {})
                    meta["output_file_ids"] = [
                        cf.get("file_id") for cf in updated_context_files if cf.get("file_id")
                    ]
                    meta["result_summary"] = reason
                    meta["execution_summary"] = execution_summary_text
                    meta["execution_history"] = final_execution_history
                    new_t["metadata"] = meta
                    updated_todos.append(new_t)
                else:
                    updated_todos.append(t)

            return StateUpdate(
                context_files=updated_context_files,
                planner_todos=updated_todos,
                active_todo=None,
                execution_history=[],
                analyst_next_step="summarize",
            )

        # 未完成：更新 active_todo.metadata 中的执行历史和反思信息，并重写 active_task
        logger.info(
            "Todo not completed, updating active_todo and active_task based on reflection",
            extra={
                "job_id": job_id,
                "updated_task": updated_task,
                "next_action": next_action,
            },
        )

        updated_todo = dict(todo)
        metadata = dict(updated_todo.get("metadata") or {})
        metadata["execution_summary"] = execution_summary_text
        metadata["reflection_reason"] = reason
        metadata["reflection_next_action"] = next_action
        metadata["reflection_count"] = int(metadata.get("reflection_count", 0)) + 1
        metadata["execution_history"] = final_execution_history
        updated_todo["metadata"] = metadata

        new_active_task = updated_task or active_task

        return StateUpdate(
            context_files=updated_context_files,
            active_todo=updated_todo,
            active_task=new_active_task,
            execution_history=[],
            analyst_next_step="select_file",
        )

    except Exception as exc:
        logger.error(
            "Reflection failed",
            extra={"job_id": job_id, "error": str(exc)},
            exc_info=True,
        )
        # 失败时仅更新 context_files，默认继续选择文件
        return StateUpdate(
            context_files=updated_context_files,
            analyst_next_step="select_file",
        )


def node_analyst_summary_plan(
    state: GraphState,
    *,
    llm_client: LLMClient | None = None,
) -> StateUpdate:
    """
    总结子流程第一步：基于 goal / 执行历史与 context_files 的文件元信息，规划是否需要深度读取以及重点文件。
    """

    job_id = state.get("job_id", "unknown")
    todo: PlannerTodo | None = state.get("active_todo")
    goal = (todo.get("goal") if todo else "") or (state.get("active_task") or "")
    user_message = state.get("user_message", "")
    user_id = str(state.get("user_id") or "")

    # 选取可用的执行历史：直接使用全局 execution_history
    execution_history = state.get("execution_history") or []

    try:
        execution_history_text = json.dumps(execution_history[-30:], ensure_ascii=False, indent=2)
    except Exception:
        execution_history_text = str(execution_history[-30:])

    # 基于 context_files 构造文件元信息列表
    context_files = state.get("context_files") or []
    file_summaries: list[dict[str, Any]] = []
    for cf in context_files:
        fid = None
        if isinstance(cf, Mapping):
            fid = cf.get("file_id")
        else:
            fid = cf
        if not fid:
            continue
        fid_str = str(fid)
        try:
            info = get_file_info(fid_str, user_id)
            file_type = info.get("file_type") or {}
            file_summaries.append(
                {
                    "file_id": fid_str,
                    "filename": info.get("filename", ""),
                    "description": info.get("description") or "",
                    "file_type": file_type.get("name") if isinstance(file_type, Mapping) else "",
                }
            )
        except Exception as exc:
            _fail_analyst(
                job_id,
                message="Failed to get file info for summary plan",
                code="file_info_lookup_failed",
                details={"file_id": fid_str, "error": str(exc)},
            )

    if not file_summaries:
        # 没有任何可用文件时，给出空的规划
        logger.info(
            "No context_files available in summary_plan, returning empty plan",
            extra={"job_id": job_id},
        )
        return StateUpdate(
            analyst_summary_plan={
                "need_deep_read_file": {},
                "full_read_file": [],
            }
        )

    llm = llm_client or get_llm_client()

    # 单独定义 JSON 模板，避免在 f-string 中直接写花括号导致格式化错误
    json_template = """
请严格按以下 JSON 结构返回结果：
{
    "file_id_1": {
        "reason": "需要的目的说明",
        "question": "针对该文件的阅读问题",
    },
    "file_id_2": {
        "reason": "需要的目的说明",
        "question": "针对该文件的阅读问题",
    },
    ...
}
"""

    prompt = f"""你是一个总结规划助手。现在需要根据任务目标与已有的执行历史，决定在总结阶段是否需要深入读取某些文件，以及需要优先关注哪些文件。

用户原始问题：{user_message}
任务目标（goal）：{goal}

执行历史（最近若干条，仅供参考，不需要逐条复述）：
{execution_history_text}

当前可用文件及其元信息如下（不含内容）：
{json.dumps(file_summaries, ensure_ascii=False, indent=2)}

请根据以上信息，给出一个总结阶段的文件读取规划。

{json_template}

只返回 JSON，不要包含其他文字说明。"""

    try:
        request = LLMRequest(
            messages=[
                {
                    "role": "system",
                    "content": "你是一个专业的总结规划助手，擅长基于任务和已有文件规划后续阅读策略。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        response = llm.chat(request)
        content = response.content.strip()
        result = parse_json_from_llm_response(content, default={})



        return StateUpdate(
            analyst_summary_plan=result
        )
    except Exception as exc:
        logger.error(
            "Summary plan generation failed",
            extra={"job_id": job_id, "error": str(exc)},
            exc_info=True,
        )
        # 失败时返回一个空规划
        return StateUpdate(
            analyst_summary_plan={}
        )




def node_analyst_summary_answer(
    state: GraphState,
    *,
    llm_client: LLMClient | None = None,
) -> StateUpdate:
    """
    总结子流程第二步：根据 summary_plan 和执行历史，生成最终对用户的详细回答。

    - 读取关键文件的元信息和内容预览，为 LLM 提供完整的上下文信息。
    - 输出：
        - analyst_final_answer：面向用户的完整回答
        - final_answer：兼容旧字段，便于上层读取
    """

    job_id = state.get("job_id", "unknown")
    user_id = str(state.get("user_id") or "")
    todo: PlannerTodo | None = state.get("active_todo")
    goal = (todo.get("goal") if todo else "") or (state.get("active_task") or "")
    user_message = state.get("user_message", "")
    summary_plan = state.get("analyst_summary_plan") or {}
    file_summary_text = ""
    file_reader_tool = FileReaderTool()
    python_repl_tool = PythonREPLTool()
    multi_modal_reader_tool = MultiModalReaderTool()
    for file_id, meta in summary_plan.items():
        file_info = file_reader_tool.read_file(file_id=file_id, user_id=user_id)
        # 根据文件名判断文件类型，决定读取方式，如果是txt\log\md\json则读取全文，如果是csv\excel\h5ad则通过python—repl工具读取,如果是png\jpg\jpeg则读取图片内容
        filename = file_info.get("filename") or ""
        file_type = filename.split(".")[1].lower()
        if file_type in ["txt", "log", "md", "json"]:
            content = json.dumps(file_reader_tool.read_file(file_id=file_id, user_id=user_id).preview, ensure_ascii=False, indent=2)
            file_summary_text += f"文件ID：{file_id}\n文件名：{filename}\n文件类型：{file_type}\n文件内容：{content}\n"
        elif file_type in ["csv", "excel", "h5ad"]:
            content = python_repl_tool.execute(question=meta.get("question") or "", file_id=file_id, user_id=user_id)
            file_summary_text += f"文件ID：{file_id}\n文件名：{filename}\n文件类型：{file_type}\n文件内容：{content}\n"
        elif file_type in ["png", "jpg", "jpeg"]:
            content = multi_modal_reader_tool.read_file(file_id=file_id, user_id=user_id)
            file_summary_text += f"文件ID：{file_id}\n文件名：{filename}\n文件类型：{file_type}\n文件内容：{content}\n"
    # 获取完整执行历史：直接使用全局 execution_history
    execution_history = state.get("execution_history") or []

    try:
        execution_history_text = json.dumps(execution_history[-30:], ensure_ascii=False, indent=2)
    except Exception:
        execution_history_text = str(execution_history[-30:])

    # 为 summary_answer 节点创建带有更长超时的 LLM 客户端
    # 因为 prompt 包含大量文件内容预览，需要更长的处理时间
    if llm_client is None:
        from textmsa.settings import get_llm_config
        
        llm_config = get_llm_config()
        # 为 summary 节点设置更长的超时时间（120 秒）
        llm_config_with_timeout = {**llm_config, "timeout_seconds": 120}
        llm = LLMClient(config=llm_config_with_timeout)
    else:
        llm = llm_client

    prompt = f"""你现在需要基于整个 analyst 调用过程，为用户生成最终的、结构化且详细的回答。

请综合以下信息：
1. 用户原始问题
2. 任务目标（goal）与期望输出（如果有）
3. 每一轮执行历史（调用了哪些服务、用了哪些文件、产生了哪些结果）
4. 总结规划阶段选出的关键文件及其元信息、阅读意图和内容

【用户原始问题】
{user_message}

【当前子任务目标】
{goal}

【执行历史（最近若干条）】
{execution_history_text}

【总结规划选出的关键文件内容】
{file_summary_text}

请按照下面的思路组织回答：
1. 先用分点的方式，按时间顺序简要回顾每一轮做了什么、使用了哪些服务、围绕哪些文件展开。
2. 然后结合上述过程，特别是关键文件的实际内容，给出对用户问题的最终结论和详细解释，必要时可以分小节说明。

请以 JSON 格式返回，结构如下：
{{
  "final_answer": "面向用户的最终完整回答（可以包含多段落和列表）"
}}

只返回 JSON，不要包含其他文字说明。"""

    try:
        request = LLMRequest(
            messages=[
                {
                    "role": "system",
                    "content": "你是一个专业的数据分析与任务编排助手，擅长基于多轮执行历史给出总结性的解释和回答。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        response = llm.chat(request)
        content = response.content.strip()
        result = parse_json_from_llm_response(content, default={})

        final_answer = result.get("final_answer") or ""
        logger.info(
            "Summary answer generated",
            extra={"job_id": job_id, "has_final_answer": bool(final_answer)},
        )

        return StateUpdate(
            analyst_final_answer=final_answer,
            final_answer=final_answer,
        )
    except Exception as exc:
        logger.error(
            "Summary answer generation failed",
            extra={"job_id": job_id, "error": str(exc)},
            exc_info=True,
        )
        # LangGraph 要求每个节点必须写入至少一个状态字段
        # 即使失败也返回 job_id 保持状态不变
        return StateUpdate({"job_id": state.get("job_id")})


def _analyst_reflection_router(state: GraphState) -> str:
    """
    路由函数：根据反思结果的 analyst_next_step 决定后续走向。
    """
    next_step = state.get("analyst_next_step")
    if next_step == "summarize":
        return "summary_plan"
    if next_step == "select_file":
        return "select_file"

    # 兜底：如果没有设置或值异常，默认继续选择文件
    return "select_file"


def build_analyst_graph() -> StateGraph:
    """
    构建 Analyst 子图：执行 → 选择文件 → 匹配服务 → 执行服务 → 反思 → 循环或完成。
    
    流程：
    1. node_analyst_execute: 入口，初始化
    2. node_analyst_select_file: 选择输入文件
    3. node_analyst_match_service: 匹配服务（根据文件类型筛选）
    4. node_analyst_execute_service: 执行服务
    5. node_analyst_reflect: 反思是否完成
    6. 如果未完成，回到步骤2；如果完成，结束
    """

    graph = StateGraph(GraphState)
    graph.add_node("analyst_execute", node_analyst_execute)
    graph.add_node("select_file", node_analyst_select_file)
    graph.add_node("match_service", node_analyst_match_service)
    graph.add_node("execute_service", node_analyst_execute_service)
    graph.add_node("reflect", node_analyst_reflect)
    graph.add_node("summary_plan", node_analyst_summary_plan)
    graph.add_node("summary_answer", node_analyst_summary_answer)
    
    graph.set_entry_point("analyst_execute")
    
    # 执行后进入选择文件
    graph.add_edge("analyst_execute", "select_file")
    
    # 选择文件后进入匹配服务
    graph.add_edge("select_file", "match_service")
    
    # 匹配服务后执行服务
    graph.add_edge("match_service", "execute_service")
    
    # 执行服务后反思
    graph.add_edge("execute_service", "reflect")
    
    # 反思后路由：继续选择文件或进入总结子流程
    graph.add_conditional_edges(
        "reflect",
        _analyst_reflection_router,
        {
            "select_file": "select_file",  # 继续循环（从选择文件开始）
            "summary_plan": "summary_plan",  # 进入总结子流程
        },
    )

    # 总结子流程：规划 -> 生成最终回答 -> 结束
    graph.add_edge("summary_plan", "summary_answer")
    graph.add_edge("summary_answer", END)
    
    return graph


analyst_node = node_analyst_execute


__all__ = [
    "build_analyst_graph",
]
