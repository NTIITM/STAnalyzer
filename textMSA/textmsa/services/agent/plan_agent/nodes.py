"""
Plan Agent 节点实现

实现所有工作流节点和辅助函数。
"""

import json
import time
import uuid
from pathlib import Path
from typing import Any

from textmsa.logging_config import get_logger
from textmsa.services.agent.agent_service import get_agent_service
from textmsa.services.agent.agent_utils import (
    get_llm_client_instance,
    get_codegen_llm_client_instance,
    get_python_repl_tool_instance,
    extract_json_from_response,
)
from textmsa.services.agent.read_agent.nodes import _fix_main_block
from textmsa.services.agent.read_agent.prompts import (
    format_data_preview_analysis_prompt,
)
from textmsa.services.agent.llm_client import LLMRequest
from textmsa.services.agent.tools import ServiceDispatchClient
from textmsa.services.agent.plan_agent.state import PlanAgentState

logger = get_logger(__name__)
from textmsa.services.agent.plan_agent.prompts import (
    format_plan_prompt,
    format_report_prompt,
    format_service_info_for_planning,
    format_context_files_info,
    format_execution_history,
    format_code_generation_prompt,
    format_code_retry_prompt,
    format_failure_loop_detection_prompt,
)
from textmsa.services.data.mongodb_models import FileInfo, file_info_from_dict
from textmsa.services.project.project_service import get_project_service
from textmsa.services.user.user_service import get_user_service
from textmsa.services.file.file_service import get_file_service


def _get_language(state: PlanAgentState) -> str:
    """从状态中获取语言，默认中文。"""
    lang = str(state.get("language", "zh")).lower()
    return "en" if lang.startswith("en") else "zh"


# ============================================================================
# 辅助函数
# ============================================================================


def _get_file_infos_from_ids(
    file_ids: list[str],
    user_id: str,
) -> list[FileInfo]:
    """
    从数据库获取文件信息
    
    Args:
        file_ids: 文件ID列表
        user_id: 用户ID
    
    Returns:
        文件信息列表
    """
    file_service = get_file_service()
    file_infos = []
    
    for file_id in file_ids:
        try:
            file_dict = file_service.get_file_info(file_id, user_id)
            # 转换为FileInfo对象
            file_info = file_info_from_dict(file_dict)
            file_infos.append(file_info)
        except Exception as e:
            logger.warning(
                f"Failed to get file info for file_id={file_id}",
                extra={"file_id": file_id, "error": str(e)},
            )
    
    return file_infos


def _get_file_descriptions_from_ids(
    file_ids: list[str],
    user_id: str,
) -> list[dict[str, Any]]:
    """
    从数据库获取文件描述信息（description）。

    Args:
        file_ids: 文件ID列表
        user_id: 用户ID

    Returns:
        文件描述信息列表，每个元素包含 file_id, file_name, description。
    """
    file_service = get_file_service()
    file_descriptions: list[dict[str, Any]] = []

    for file_id in file_ids:
        try:
            file_info_dict = file_service.get_file_info(file_id, user_id)
            file_name = file_info_dict.get("filename", file_id)
            description = (file_info_dict.get("description") or "").strip()
            file_descriptions.append(
                {
                    "file_id": file_id,
                    "file_name": file_name,
                    "description": description,
                }
            )
        except Exception as e:
            logger.warning(
                f"Failed to get file description for file_id={file_id}",
                extra={"file_id": file_id, "error": str(e)},
            )

    return file_descriptions


def _get_service_graph_by_context_files(
    context_file_ids: list[str],
    user_id: str,
    project_id: str | None = None,
) -> dict[str, Any]:
    """
    根据 context_file_ids 获取服务图谱
    
    Args:
        context_file_ids: 上下文文件ID列表
        user_id: 用户ID
        project_id: 项目ID（可选）
    
    Returns:
        服务图谱字典
    """
    project_service = get_project_service()
    
    # 从数据库获取文件信息
    context_files = _get_file_infos_from_ids(context_file_ids, user_id)
    
    # 从上下文文件中提取文件类型ID（去重）
    file_type_ids = list(set(
        f.file_type_id
        for f in context_files
        if hasattr(f, "file_type_id") and f.file_type_id
    ))
    
    depth = 3
    # 如果只有一个文件类型，使用它作为根节点
    if len(file_type_ids) == 1:
        file_type_id = file_type_ids[0]
        service_graph = project_service.get_service_file_type_graph(
            project_id=project_id,
            user_id=user_id,
            file_type_id=file_type_id,
            depth=depth,  # 不限制深度
        )
    else:
        # 多个文件类型，使用默认根文件类型列表
        service_graph = project_service.get_service_file_type_graph(
            project_id=project_id,
            user_id=user_id,
            file_type_id=None,
            depth=depth,
            root_file_type_list=file_type_ids if file_type_ids else None,
    )
    
    return service_graph


def _extract_service_ids_from_graph(graph: dict[str, Any]) -> list[str]:
    """
    从服务图谱中递归提取所有服务ID
    
    Args:
        graph: 服务图谱字典
    
    Returns:
        服务ID列表
    """
    service_ids = []
    
    def traverse(node: dict[str, Any]) -> None:
        node_type = node.get("node_type")
        if node_type == "service":
            service_id = node.get("service_id") or node.get("id")
            if service_id:
                service_ids.append(service_id)
        
        # 递归遍历子节点
        children = node.get("children", [])
        for child in children:
            traverse(child)
    
    roots = graph.get("roots", [])
    for root in roots:
        traverse(root)
    
    # 去重
    return list(set(service_ids))


def _extract_service_info_for_planning(
    service_ids: list[str],
    user_id: str,
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    """
    从服务ID列表中提取服务信息（用于规划）
    
    Args:
        service_ids: 服务ID列表
        user_id: 用户ID
        project_id: 项目ID（可选）
    
    Returns:
        服务信息列表，每个元素包含：
            - service_id: 服务ID
            - name: 服务名称
            - description: 服务描述
            - input_file_types: 输入文件类型列表
            - output_file_types: 输出文件类型列表
    """
    service_client = ServiceDispatchClient()
    service_info_list = []
    
    for service_id in service_ids:
        try:
            metadata = service_client.fetch_service_metadata(
                service_id=service_id,
                user_id=user_id,
                project_id=project_id,
            )
            
            # 提取服务基本信息
            service_id_value = metadata.get("service_id") or service_id
            name = metadata.get("name", "")
            description = metadata.get("description", "") or ""
            
            # 提取输入文件类型（保留详细配置）
            accepted_files_config = {}
            accepted_files = metadata.get("accepted_files")
            if accepted_files and isinstance(accepted_files, dict):
                for filename, file_config in accepted_files.items():
                    if isinstance(file_config, dict):
                        file_type_ids = file_config.get("file_type_ids", [])
                        description = file_config.get("description", "")
                        if isinstance(file_type_ids, list):
                            accepted_files_config[filename] = {
                                "file_type_ids": file_type_ids,
                                "description": description,
                            }
            
            # 提取所有输入文件类型ID（用于兼容性）
            input_file_types = []
            for file_config in accepted_files_config.values():
                input_file_types.extend(file_config.get("file_type_ids", []))
            input_file_types = list(set(input_file_types))
            
            # 提取输出文件类型
            output_file_types = []
            output_config = metadata.get("output_config")
            if output_config and isinstance(output_config, dict):
                items = output_config.get("items", [])
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict) and item.get("type") == "file":
                            file_type_id = item.get("file_type_id")
                            if file_type_id:
                                output_file_types.append(file_type_id)
            
            # 去重
            output_file_types = list(set(output_file_types))
            
            service_info_list.append({
                "service_id": service_id_value,
                "name": name,
                "description": description,
                "input_file_types": input_file_types,
                "accepted_files": accepted_files_config,  # 详细的输入文件配置
                "output_file_types": output_file_types,
            })
            
        except Exception as exc:
            # 继续处理其他服务
            continue
    
    return service_info_list


def _generate_service_parameters_with_llm(
    service_metadata: dict[str, Any],
    expect_output: str,
    execution_history: list[dict[str, Any]],
    user_query: str,
    input_file_ids: list[str], # 新增参数
    user_id: str, # 新增参数
    language: str = "zh",
) -> tuple[dict[str, Any], str]:
    """
    使用 LLM 根据服务元信息和任务目标生成参数，支持中英文。
    """
    lang = "en" if str(language).lower().startswith("en") else "zh"
    llm = get_llm_client_instance()
    
    parameter_template = service_metadata.get("parameter_template") or {}
    parameter_schema = service_metadata.get("parameter_schema") or {}
    service_name = service_metadata.get("name", "")
    service_description = service_metadata.get("description", "") or ""
    
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
    
    execution_history_string = format_execution_history(execution_history, language=lang)
    
    # 获取文件描述信息
    file_descriptions = _get_file_descriptions_from_ids(input_file_ids, user_id)
    file_description_string = json.dumps(file_descriptions, ensure_ascii=False, indent=2)
    
    if lang == "zh":
        prompt = f"""你是一个智能参数生成助手。根据用户任务、服务的参数定义和文件描述信息，生成合适的参数值。

用户问题：{user_query}
期望输出：{expect_output}

服务名称: {service_name}
服务描述: {service_description}

执行历史：
{execution_history_string}

文件描述信息：
{file_description_string}

参数定义（约束和类型）:
{json.dumps(param_definitions, ensure_ascii=False, indent=2)}

请根据任务需求和期望输出，为所有参数生成合适的值。规则：
1. 必须遵循参数类型和约束（如 enum 值、数值范围、字符串长度等）
2. 必填参数（required=true）必须提供值
3. 可选参数如果任务中没有明确要求，可以使用默认值或合理的值
4. 参数值必须符合参数定义中的类型和约束
5. 必须显式对比历史执行中的参数配置，避免在**同一服务、相同输入文件**的前提下，重复返回与最近一次成功执行完全相同的参数组合；如果参数定义中不存在能够改变输出行为的额外字段，导致无法构造“有本质差异的新配置”，应在 reasoning 中明确说明“当前参数体系无法解决该问题”，并提示上游逻辑不要再次执行该服务
6. 无论用户问题或需求如何变化，所有超参数和数值型参数都必须严格落在参数定义给出的取值范围内；即使用户显式要求超出范围，也必须在限定范围内选择最合适的值

请以 JSON 格式返回结果，格式如下：
{{
  "parameters": {{
    "参数名1": "参数值1",
    "参数名2": 参数值2,
    ...
  }}
  "reasoning": "推理过程描述"
}}

只返回 JSON，不要包含其他文字说明。"""
        system_content = "你是一个专业的参数生成助手，擅长根据任务需求生成符合参数定义的服务调用参数。"
    else:
        prompt = f"""You are a smart parameter generation assistant. Based on the user task, service parameter definitions, and file description information, generate suitable parameter values.

User question: {user_query}
Expected output: {expect_output}

Service name: {service_name}
Service description: {service_description}

Execution history:
{execution_history_string}

File description information:
{file_description_string}

Parameter definitions (constraints and types):
{json.dumps(param_definitions, ensure_ascii=False, indent=2)}

Rules:
1. Follow parameter types and constraints (enum values, numeric ranges, string lengths, etc.)
2. Required parameters must be provided
3. Optional parameters may use defaults or reasonable values when not specified
4. Parameter values must satisfy the definitions and constraints
5. Consider execution history to avoid repeating the same configuration
6. Regardless of how the user question or task is phrased, all hyperparameters and numeric values must strictly stay within the allowed ranges specified in the parameter definitions; even if the user explicitly asks for out-of-range values, you must still choose the most appropriate values within the allowed ranges

Return JSON in the format:
{{
  "parameters": {{
    "param1": "value1",
    "param2": value2
  }},
  "reasoning": "Reasoning process"
}}

Return JSON only, no extra text."""
        system_content = "You are a professional parameter generation assistant, skilled at producing service call parameters that match the definitions."
    
    request = LLMRequest(
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
    )
    response = llm.chat(request)
    
    # 解析响应
    content = response.content.strip() if response.content else ""
    result = extract_json_from_response(content)
    reasoning = result.get("reasoning", "")
    parameters = result.get("parameters", {})
    
    return parameters, reasoning


# ============================================================================
# 节点函数
# ============================================================================


def _detect_repeated_failure_loop_with_llm(
    execution_history: list[dict[str, Any]],
    language: str,
    plan_loop_count: int,
    user_id: str,
    project_id: str,
) -> dict[str, Any] | None:
    """
    使用 LLM 判断是否存在“相同或类似原因”的重复失败循环。
    
    Returns:
        若检测到循环，返回包含停止信息的状态字典；否则返回 None。
    """
    if not execution_history:
        return None

    llm = get_llm_client_instance()

    # 仅提取失败记录，避免无关信息干扰
    failed_records: list[dict[str, Any]] = []
    for record in execution_history:
        status = str(record.get("status", "")).lower()
        if status not in ("success", "completed", "succeeded"):
            failed_records.append(
                {
                    "service_id": record.get("service_id", ""),
                    "status": status,
                    "feedback": str(record.get("feedback", "")).strip(),
                }
            )

    if not failed_records:
        return None

    prompt = format_failure_loop_detection_prompt(
        failed_records=failed_records,
        language=language,
    )
    request = LLMRequest(
        messages=[
            {
                "role": "system",
                "content": (
                    "你是一个负责检测服务执行循环的助手，擅长根据执行历史识别相同或类似原因的重复失败。"
                    if language == "zh"
                    else "You are an assistant that detects execution loops, good at identifying repeated failures due to the same or similar reasons."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
    )
    response = llm.chat(request)
    content = response.content.strip() if response.content else ""
    result = extract_json_from_response(content)

    is_loop_detected = bool(result.get("is_loop_detected"))
    loop_service_id = str(result.get("service_id") or "")
    loop_reason_summary = str(result.get("reason_summary") or "")

    if not is_loop_detected:
        return None

    if language == "zh":
        stop_reason = (
            "检测到同一服务因相同或类似原因多次失败，为避免无限循环，停止继续执行并生成总结报告。"
        )
        if loop_service_id:
            stop_reason += f" 相关服务：{loop_service_id}。"
        if loop_reason_summary:
            stop_reason += f" 失败原因概述：{loop_reason_summary}"
    else:
        stop_reason = (
            "Detected repeated failures of the same service due to the same or similar reasons; "
            "stopping further execution to avoid infinite loops and generating the final report."
        )
        if loop_service_id:
            stop_reason += f" Related service: {loop_service_id}."
        if loop_reason_summary:
            stop_reason += f" Failure reason summary: {loop_reason_summary}"

    message = get_agent_service().build_message(
        message=stop_reason,
    )
    logger.info(
        "plan_node: LLM-detected repeated failure loop, force routing to report",
        extra={
            "loop_service_id": loop_service_id,
            "loop_reason_summary": loop_reason_summary,
            "user_id": user_id,
            "project_id": project_id,
        },
    )
    return {
        "next_plan": None,
        "plan_loop_count": plan_loop_count,
        "stop_reason_code": "repeated_failure_loop_detected",
        "stop_reason": stop_reason,
        "message": message,
    }


def _check_max_plan_loops_exceeded(
    plan_loop_count: int,
    max_plan_loops: int,
    language: str,
    user_id: str,
    project_id: str | None,
) -> dict[str, Any] | None:
    """
    若达到规划轮数上限，返回停止执行的状态；否则返回 None。
    """
    if max_plan_loops <= 0 or plan_loop_count <= max_plan_loops:
        return None

    if language == "zh":
        stop_reason = (
            f"已达到允许的最大规划轮数上限（{max_plan_loops}），不再继续调用服务，直接生成总结报告。"
        )
    else:
        stop_reason = (
            f"Reached the maximum allowed planning loop count ({max_plan_loops}); "
            f"stopping further service execution and generating the final report."
        )

    message = get_agent_service().build_message(
        message=stop_reason,
    )
    logger.info(
        "plan_node: max_plan_loops exceeded, force routing to report",
        extra={
            "plan_loop_count": plan_loop_count,
            "max_plan_loops": max_plan_loops,
            "user_id": user_id,
            "project_id": project_id,
        },
    )
    return {
        # 不再给出下一步计划，强制让 check_plan_route 进入 report
        "next_plan": None,
        "plan_loop_count": plan_loop_count,
        "stop_reason_code": "max_plan_loops_exceeded",
        "stop_reason": stop_reason,
        "message": message,
    }


def plan_node(state: PlanAgentState) -> PlanAgentState:
    """
    规划节点：根据用户查询和服务图谱生成执行计划
    
    Args:
        state: 当前状态
    
    Returns:
        更新后的状态
    """
    user_query = state["user_query"]
    user_id = state["user_id"]
    project_id = state.get("project_id")
    context_file_ids = state["context_files"]
    execution_history = state.get("execution_history", [])
    execute_feedback = state.get("execute_feedback", "")
    language = _get_language(state)

    # 规划循环计数，用于防止无限循环
    plan_loop_count = int(state.get("plan_loop_count", 0) or 0) + 1
    max_plan_loops = int(state.get("max_plan_loops", 0) or 0)

    # 方案2（改造版）：使用 LLM 判断是否属于“相同或类似原因”的重复失败
    loop_detection_result = _detect_repeated_failure_loop_with_llm(
        execution_history=execution_history,
        language=language,
        plan_loop_count=plan_loop_count,
        user_id=user_id,
        project_id=project_id,
    )
    if loop_detection_result:
        return loop_detection_result

    # 如果配置了最大规划轮数且已经达到或超过上限，则不再继续规划，直接进入报告阶段
    max_loop_result = _check_max_plan_loops_exceeded(
        plan_loop_count=plan_loop_count,
        max_plan_loops=max_plan_loops,
        language=language,
        user_id=user_id,
        project_id=project_id,
    )
    if max_loop_result:
        return max_loop_result

    # 1. 获取服务图谱
    service_graph = _get_service_graph_by_context_files(
        context_file_ids=context_file_ids,
        user_id=user_id,
        project_id=project_id,
    )
    
    # 2. 提取服务ID
    service_ids = _extract_service_ids_from_graph(service_graph)
    
    # 3. 提取服务信息
    service_info_list = _extract_service_info_for_planning(
        service_ids=service_ids,
        user_id=user_id,
        project_id=project_id,
    )
    
    # 4. 从数据库获取文件信息并格式化
    context_files = _get_file_infos_from_ids(context_file_ids, user_id)
    service_info_string = format_service_info_for_planning(service_info_list, language=language)
    context_files_info_string = format_context_files_info(context_files, language=language)
    execution_history_string = format_execution_history(execution_history, language=language)
    
    # 5. 调用 LLM 生成计划
    llm = get_llm_client_instance()
    prompt = format_plan_prompt(
        user_query=user_query,
        service_info_string=service_info_string,
        context_files_info_string=context_files_info_string,
        execution_history_string=execution_history_string,
        execution_feedback_string=execute_feedback,
        language=language,
    )
    
    request = LLMRequest(
        messages=[
            {
                "role": "system",
                "content": (
                    "你是一个智能规划助手，擅长根据用户查询和可用服务生成执行计划。"
                    if language == "zh"
                    else "You are an intelligent planning assistant, skilled at generating execution plans based on user queries and available services."
                ),
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
    )
    response = llm.chat(request)
    
    # 6. 解析响应
    content = response.content.strip() if response.content else ""
    result = extract_json_from_response(content)
    
    next_plan = result.get("next_plan")
    reasoning = result.get("reasoning", "")
    
    # 如果 next_plan 类型不正确、为空或缺少 service_id，设置为 None
    if not isinstance(next_plan, dict):
        next_plan = None
    elif not next_plan or not next_plan.get("service_id"):
        next_plan = None
    
    
    # message = get_agent_service().build_message(
    #     message=reasoning or "",
    # )
    
    return {
        "next_plan": next_plan,
        "current_service_graph": json.dumps(service_graph, ensure_ascii=False),
        # "message": message,
        "message": None,
        "plan_loop_count": plan_loop_count,
        # 如果之前存在停止原因，在正常规划成功时清空，避免污染后续判断
        "stop_reason_code": "",
        "stop_reason": "",
    }


def execute_node(state: PlanAgentState) -> PlanAgentState:
    """
    执行节点（阶段1）：生成参数并发起服务执行
    
    Args:
        state: 当前状态
    
    Returns:
        更新后的状态，只包含待等待的执行信息
    """
    user_id = state["user_id"]
    project_id = state.get("project_id")
    next_plan = state.get("next_plan")
    execution_history = state.get("execution_history", [])
    user_query = state["user_query"]
    context_files = state.get("context_files", [])
    language = _get_language(state)
    
    if not next_plan:
        return {}
    
    service_id = next_plan.get("service_id")
    input_file_ids = next_plan.get("input_file_ids", [])
    expect_output = next_plan.get("expect_output", "")
    
    service_client = ServiceDispatchClient()
    
    try:
        # 1. 获取服务元信息
        service_metadata = service_client.fetch_service_metadata(
            service_id=service_id,
            user_id=user_id,
            project_id=project_id,
        )
        
        service_name = service_metadata.get("name", "")
        
        # 2. 使用 LLM 生成服务参数
        parameters, reasoning = _generate_service_parameters_with_llm(
            service_metadata=service_metadata,
            expect_output=expect_output,
            execution_history=execution_history,
            user_query=user_query,
            input_file_ids=input_file_ids, # 新增参数
            user_id=user_id, # 新增参数
            language=language,
        )
        # 3. 调用服务
        service_result = service_client.invoke_service(
            service_id=service_id,
            input_files=input_file_ids,
            parameters=parameters,
            user_id=user_id,
            project_id=project_id,
        )
        
        execution_id = service_result.metadata.get("execution_id")
        status = str(service_result.metadata.get("status") or "").lower()
        output_file_ids = service_result.metadata.get("output_file_ids") or []
        
        # 保存 pending_execution 供 wait_execution_node 使用，并携带参数生成阶段的 reasoning，便于后续规划节点参考
        pending_execution = {
            "service_id": service_id,
            "service_name": service_name or service_id,
            "service_description": service_metadata.get("description", "") or "",
            "input_file_ids": input_file_ids,
            "parameters": parameters,
            "execution_id": execution_id,
            "initial_status": status,
            "output_file_ids": output_file_ids,
            "parameter_reasoning": reasoning,
        }
        
        message = get_agent_service().build_execution_message(
            message=reasoning,
            execution_id=execution_id,
        )
        logger.info(f"execute_node: {message}")

        return {
            "pending_execution_id": execution_id,
            "pending_execution": pending_execution,
            "message": message,
        }
    
    except Exception as exc:
        # 捕获所有异常，确保即使服务调用失败也能返回状态并继续到下一节点
        logger.error(
            f"执行服务时出错: {exc}",
            extra={"service_id": service_id, "input_file_ids": input_file_ids},
            exc_info=True,
        )
        
        # 生成错误反馈
        service_name = service_id or "未知服务"
        feedback = f"服务执行异常: {str(exc)}" if language == "zh" else f"Service execution error: {exc}"
        final_status_value = "failed"
        
        # 记录执行历史
        execution_record = {
            "service_id": service_id,
            "service_name": service_name,
            "service_description": "",
            "input_file_ids": input_file_ids,
            "parameters": {},
            "output_file_ids": [],
            "status": final_status_value,
            "feedback": feedback,
        }
        
        updated_execution_history = execution_history + [execution_record]
        
        # 添加执行消息
        execute_message = (
            f"执行服务 {service_name} ({service_id})：{feedback}"
            if language == "zh"
            else f"Execute service {service_name} ({service_id}): {feedback}"
        )
        
        message = get_agent_service().build_message(
            message=execute_message,
        )
        
        return {
            "execution_history": updated_execution_history,
            "execute_feedback": feedback,
            "message": message,
            "context_files": context_files,
            "pending_execution": None,
        }


def wait_execution_node(state: PlanAgentState) -> PlanAgentState:
    """
    执行节点（阶段2）：等待服务执行完成并生成反馈
    
    Args:
        state: 当前状态
    
    Returns:
        更新后的状态（包含执行历史、反馈、上下文文件等）
    """
    pending_execution = state.get("pending_execution")
    user_id = state.get("user_id")
    language = _get_language(state)
    
    execution_history = state.get("execution_history", [])
    context_files = list(state.get("context_files", []))

    # 如果没有待执行的服务（例如 execute_node 已在异常分支中处理完并将 pending_execution 置为 None），
    # 则直接返回当前状态，避免中断整个工作流。
    if not pending_execution:
        logger.warning("wait_execution_node called but 'pending_execution' is None; skipping wait.")
        # 尝试从最近一次执行历史中提取反馈，便于后续节点总结
        feedback = ""
        if execution_history:
            last_record = execution_history[-1]
            feedback = str(last_record.get("feedback") or "")
        if not feedback:
            feedback = (
                "上一个服务执行已结束（可能失败），无待等待的执行。"
                if language == "zh"
                else "Previous service execution already handled (possibly failed); no pending execution to wait for."
            )
        message = get_agent_service().build_message(
            message=feedback,
        )
        logger.info(f"wait_execution_node (no pending_execution): {message}")
        return {
            "execution_history": execution_history,
            "execute_feedback": feedback,
            "message": message,
            "context_files": context_files,
            "pending_execution": None,
            "pending_execution_id": None,
        }
    
    service_id = pending_execution.get("service_id")
    service_name = pending_execution.get("service_name") or service_id or "未知服务"
    service_description = pending_execution.get("service_description", "")
    input_file_ids = pending_execution.get("input_file_ids", [])
    parameters = pending_execution.get("parameters", {})
    execution_id = pending_execution.get("execution_id")
    initial_status = str(pending_execution.get("initial_status", "") or "").lower()
    output_file_ids = pending_execution.get("output_file_ids", []) or []
    
    service_client = ServiceDispatchClient()
    
    feedback = ""
    parameter_reasoning = pending_execution.get("parameter_reasoning", "")
    final_status_value = initial_status or "unknown"
    
    # 如果服务是异步执行且处于运行状态，等待完成
    if initial_status == "running" and execution_id:
        try:
            completed_execution = service_client.wait_for_execution(
                execution_id=execution_id,
                max_wait_seconds=3000.0,  # 50分钟
                poll_interval_seconds=10.0,
                timeout_error=True,
            )
            
            final_status_value = completed_execution.get("status", "").lower()
            final_output_file_ids = completed_execution.get("output_file_ids", [])
            if final_output_file_ids:
                output_file_ids = [str(fid) for fid in final_output_file_ids if fid]
                context_files.extend(output_file_ids)
        except Exception as wait_exc:
            logger.error(
                f"等待服务执行完成时出错: {wait_exc}",
                extra={"execution_id": execution_id, "service_id": service_id},
                exc_info=True,
            )
            final_status_value = "failed"
            feedback = (
                f"服务执行等待超时或出错: {str(wait_exc)}"
                if language == "zh"
                else f"Service execution timed out or failed while waiting: {wait_exc}"
            )
    else:
        output_file_ids = [str(fid) for fid in output_file_ids if fid]
        if output_file_ids:
            context_files.extend(output_file_ids)
    
    # 生成反馈信息
    if not feedback:
        if final_status_value == "completed":
            feedback = (
                f"服务执行成功。输出文件: {', '.join(output_file_ids) if output_file_ids else '无'}"
                if language == "zh"
                else f"Service executed successfully. Output files: {', '.join(output_file_ids) if output_file_ids else 'None'}"
            )
        else:
            feedback = (
                f"服务执行失败。状态: {final_status_value}"
                if language == "zh"
                else f"Service execution failed. Status: {final_status_value}"
            )
    
    # 记录执行历史，附带参数生成阶段的 reasoning，便于后续规划节点参考
    execution_record = {
        "execution_id": execution_id,  # 添加 execution_id 以便后续查询详细信息
        "service_id": service_id,
        "service_name": service_name,
        "service_description": service_description,
        "input_file_ids": input_file_ids,
        "parameters": parameters,
        "output_file_ids": output_file_ids,
        "status": final_status_value,
        "feedback": feedback,
        "parameter_reasoning": parameter_reasoning,
    }
    
    updated_execution_history = execution_history + [execution_record]
    
    # 添加执行消息
    execute_message = (
        f"执行 {service_name} ({service_id}) 完成，状态 {final_status_value}。"
        if language == "zh"
        else f"Execution {execution_id} of {service_name} ({service_id}) completed with status {final_status_value}."
    )
    message = get_agent_service().build_files_message(
        message=execute_message,
        file_ids=output_file_ids,
        user_id=user_id,
    )
    logger.info(f"wait_execution_node: {message}")
    
    return {
        "execution_history": updated_execution_history,
        "execute_feedback": feedback,
        "message": message,
        "context_files": context_files,
        "pending_execution": None,
        "pending_execution_id": None,
    }


def check_plan_route(state: PlanAgentState) -> str:
    """
    检查计划节点：检查 next_plan 是否为空，决定路由
    
    Args:
        state: 当前状态
    
    Returns:
        "execute" - 如果 next_plan 存在且 service_id 不是 "codegen"
        "codegen" - 如果 next_plan 存在且 service_id 是 "codegen"
        "report" - 如果 next_plan 为空或不存在
    """
    next_plan = state.get("next_plan")

    # 如果存在显式的停止原因代码，则强制路由到报告节点
    stop_reason_code = str(state.get("stop_reason_code", "") or "").strip()
    if stop_reason_code:
        return "report"
    
    if not next_plan:
        return "report"
    
    # 检查是否为空字典或缺少关键字段
    if isinstance(next_plan, dict):
        service_id = next_plan.get("service_id")
        if not service_id:
            return "report"
        
        # 如果 service_id 是 "codegen"，路由到代码生成节点
        if service_id == "codegen":
            return "codegen"
    
    return "execute"


def _strip_code_fence(text: str) -> str:
    """
    移除 ```lang ... ``` 样式代码块包裹
    
    Args:
        text: 原始文本
    
    Returns:
        清理后的代码
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
        if cleaned.startswith("python"):
            cleaned = cleaned[len("python"):]
        if cleaned.startswith("\n"):
            cleaned = cleaned[1:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def _parse_code_response(response_content: str) -> tuple[str, str]:
    """
    解析代码生成的响应，提取 code 和 expected_output。
    
    Args:
        response_content: LLM 响应内容
    
    Returns:
        tuple: (code, expected_output)
        - code: Python 代码字符串
        - expected_output: 预期输出描述
    """
    cleaned = response_content.strip()
    
    # 尝试解析 JSON 格式
    try:
        parsed = extract_json_from_response(cleaned)
        if parsed:
            code = parsed.get("code", "")
            expected_output = parsed.get("expected_output", "")
            if code:
                return code, expected_output
    except (KeyError, AttributeError, ValueError):
        pass
    
    # 如果不是 JSON 格式，尝试作为纯代码处理（向后兼容）
    code = _strip_code_fence(cleaned)
    return code, ""


def _find_file_by_id(file_id: str, user_id: str) -> FileInfo | None:
    """
    从数据库根据 file_id 查找文件信息
    
    Args:
        file_id: 文件ID
        user_id: 用户ID
    
    Returns:
        文件信息，如果未找到则返回 None
    """
    try:
        file_service = get_file_service()
        file_dict = file_service.get_file_info(file_id, user_id)
        file_info = file_info_from_dict(file_dict)
        return file_info
    except Exception as e:
        logger.warning(
            f"Failed to get file info for file_id={file_id}",
            extra={"file_id": file_id, "error": str(e)},
        )
        return None


def codegen_node(state: PlanAgentState) -> PlanAgentState:
    """
    代码生成节点：使用自生成代码执行生信分析或数据处理任务
    
    Args:
        state: 当前状态
    
    Returns:
        更新后的状态
    """
    user_id = state["user_id"]
    next_plan = state.get("next_plan")
    execution_history = state.get("execution_history", [])
    context_files = state.get("context_files", [])
    language = _get_language(state)
    if not next_plan:
        return {}
    
    service_id = next_plan.get("service_id")
    if service_id != "codegen":
        return {}
    
    input_file_ids = next_plan.get("input_file_ids", [])
    expect_output = next_plan.get("expect_output", "")
    
    # 1. 构建文件信息
    file_info_list = []
    for file_id in input_file_ids:
        file_info = _find_file_by_id(file_id, user_id)
        if file_info:
            file_info_list.append({
                "file_id": file_info.file_id,
                "file_name": file_info.filename,
                "file_path": file_info.file_path or "",
                "description": file_info.description or "",
            })
    
    # 2. 准备工作目录
    work_dir_path = get_user_service().get_user_work_dir_path(user_id)
    work_dir = Path(work_dir_path)
    work_dir.mkdir(parents=True, exist_ok=True)
    
    # 3. 在代码生成前，对输入文件做一次预览分析，用于指导后续代码生成
    execution_history_string = format_execution_history(execution_history, language=language)
    analysis_guidance = ""
    try:
        user_query = state.get("user_query", "")
        # 这里只处理单文件或少量文件的概要信息，因此只取第一个文件做预览
        preview_target = file_info_list[0] if file_info_list else None
        if preview_target:
            preview_analysis_prompt = format_data_preview_analysis_prompt(
                user_query=user_query,
                file_info={
                    "file_id": preview_target["file_id"],
                    "file_name": preview_target["file_name"],
                    "file_path": preview_target.get("file_path", ""),
                    "preview": "",  # Plan Agent 当前没有预览内容，这里只传基础元信息
                    "description": preview_target.get("description", ""),
                },
                previous_results=execution_history_string,
                language=language,
            )
            # 预览分析走普通对话模型（非 codegen 模型），与 Read Agent 行为保持一致
            llm = get_llm_client_instance()
            request = LLMRequest(
                messages=[
                    {
                        "role": "user",
                        "content": preview_analysis_prompt,
                    }
                ]
            )
            logger.info(
                "[LLM Input] PlanAgent Preview",
                extra={
                    "node": "plan_agent_codegen_preview",
                    "temperature": 0.1,
                    "max_tokens": 2000,
                    "prompt_length": len(preview_analysis_prompt),
                    "prompt_preview": preview_analysis_prompt[:500] + "..."
                    if len(preview_analysis_prompt) > 500
                    else preview_analysis_prompt,
                },
            )
            response = llm.chat(request)
            guidance_response = getattr(response, "content", "") or ""
            logger.info(
                "[LLM Output] PlanAgent Preview",
                extra={
                    "node": "plan_agent_codegen_preview",
                    "response_length": len(guidance_response),
                    "response_preview": guidance_response[:500] + "..."
                    if len(guidance_response) > 500
                    else guidance_response,
                },
            )
            # 解析指导信息
            try:
                parsed = extract_json_from_response(guidance_response)
                if parsed and "guidance" in parsed:
                    analysis_guidance = parsed["guidance"]
                else:
                    analysis_guidance = guidance_response.strip()
            except Exception:
                analysis_guidance = guidance_response.strip()
            logger.info(
                "Plan Agent - 代码生成前数据预览分析完成",
                extra={
                    "first_file_name": preview_target["file_name"],
                    "guidance_length": len(analysis_guidance),
                    "guidance_preview": analysis_guidance[:200] + "..."
                    if len(analysis_guidance) > 200
                    else analysis_guidance,
                },
            )
    except Exception as e:
        logger.warning(
            f"Plan Agent - 代码生成前数据预览分析失败: {e}",
            exc_info=True,
        )
        # 如果分析失败，继续执行，但不使用指导信息
    
    # 4. 使用 Python REPL 执行代码（最多3次重试）
    repl = get_python_repl_tool_instance()
    code = ""
    expected_output = ""  # 初始化 expected_output，避免未赋值错误
    execution_result = None
    execution_success = False
    result = ""
    new_files = set()
    
    for attempt in range(3):
        try:
            if attempt == 0:
                # 第一次：生成代码（包含执行历史和预览分析指导）
                prompt = format_code_generation_prompt(
                    instruction=expect_output,
                    file_info={"files": file_info_list},
                    execution_history_string=execution_history_string,
                    work_dir_path=work_dir_path,
                    analysis_guidance=analysis_guidance,
                    language=language,
                )
            else:
                # 重试：基于错误信息生成新代码
                if execution_result is None:
                    break  # 如果之前没有执行结果，无法重试
                prompt = format_code_retry_prompt(
                    instruction=expect_output,
                    file_info={"files": file_info_list},
                    previous_code=code,
                    error_message=execution_result.stderr or "",
                    execution_history_string=execution_history_string,
                    work_dir_path=work_dir_path,
                    analysis_guidance=analysis_guidance,
                    language=language,
                )
            
            # 使用代码生成专用的 LLM
            llm = get_codegen_llm_client_instance()
            request = LLMRequest(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是一个专业的代码生成助手，擅长生成生信分析和数据处理的 Python 代码。\n\n"
                            "**关键 - 错误处理规则：**\n"
                            "- **绝对禁止**使用会静默吞掉异常而不重新抛出或打印详细错误信息的 try-except 代码块\n"
                            "- 如果使用 try-except，你必须：\n"
                            "  (1) 在记录/打印后重新抛出异常，或者\n"
                            "  (2) 使用 `traceback.print_exc()` 或 `sys.stderr.write()` 将完整错误详情（包括堆栈跟踪）打印到 stderr\n"
                            "- **不要**捕获异常后只打印简单错误信息而不包含完整堆栈跟踪\n"
                            "- **不要**捕获异常后静默继续执行 - 这会使调试变得不可能\n"
                            "- 如果需要错误处理，优先让异常自然传播，或使用能保留错误信息的正确错误处理方式\n\n"
                            if language == "zh"
                            else "You are a professional code generation assistant, skilled at producing Python code for bioinformatics and data processing.\n\n"
                            "**CRITICAL - Error Handling Rules:**\n"
                            "- **NEVER** use try-except blocks that silently swallow exceptions without re-raising them or printing detailed error information\n"
                            "- If you use try-except, you MUST either:\n"
                            "  (1) Re-raise the exception after logging/printing it, OR\n"
                            "  (2) Print the full error details (including traceback) to stderr using `traceback.print_exc()` or `sys.stderr.write()`\n"
                            "- **DO NOT** catch exceptions and only print a simple error message without the full traceback\n"
                            "- **DO NOT** catch exceptions and continue execution silently - this makes debugging impossible\n"
                            "- If error handling is needed, prefer letting exceptions propagate naturally, or use proper error handling that preserves error information\n\n"
                           ),
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
            )
            response = llm.chat(request)
            
            response_content = response.content.strip() if response.content else ""
            code, expected_output = _parse_code_response(response_content)
            
            if not code:
                result = "[错误] 代码生成失败"
                break
            
            # 修复 if __name__ == "__main__": 块，确保代码能在 REPL 环境中执行
            code = _fix_main_block(code)
            
            # 在代码前添加 work_dir_path 变量定义
            code_with_context = f"""import os
work_dir_path = r"{work_dir_path}"
os.makedirs(work_dir_path, exist_ok=True)

{code}
"""
            
            # 记录执行前的文件列表
            files_before = set()
            if work_dir.exists():
                files_before = {f.name for f in work_dir.iterdir() if f.is_file()}
            
            # 执行代码
            execution_result = repl.run_code(code=code_with_context)
            
            if execution_result.success:
                # 成功：从 stdout 读取结果
                if execution_result.stdout:
                    result = execution_result.stdout
                else:
                    result = "[成功] 代码执行完成，但无输出" if language == "zh" else "[Success] Code executed without output"
                execution_success = True
                
                # 检查是否有新文件生成
                files_after = set()
                if work_dir.exists():
                    files_after = {f.name for f in work_dir.iterdir() if f.is_file()}
                new_files = files_after - files_before
                
                break
            else:
                # 失败：记录错误，准备重试
                if attempt < 2:  # 不是最后一次尝试
                    logger.warning(
                        f"代码执行失败（尝试 {attempt + 1}/3）",
                        extra={"stderr": execution_result.stderr},
                    )
                else:
                    # 最后一次尝试也失败
                    last_err = execution_result.stderr or ("无错误信息" if language == "zh" else "no error message")
                    if language == "zh":
                        result = f"[错误] 代码执行失败（已重试3次）\n最后错误信息:\n{last_err}"
                    else:
                        result = f"[Error] Code execution failed after 3 attempts.\nLast error:\n{last_err}"
        
        except Exception as e:
            logger.error(f"代码生成或执行异常: {e}", exc_info=True)
            if attempt == 2:  # 最后一次尝试
                result = (
                    f"[错误] 代码生成或执行异常: {str(e)}"
                    if language == "zh"
                    else f"[Error] Code generation or execution exception: {e}"
                )
            continue
    
    if not execution_success and not result:
        result = "[错误] 代码执行失败，已重试3次" if language == "zh" else "[Error] Code execution failed after 3 attempts"
    
    # 3. 生成反馈信息
    if execution_success:
        if language == "zh":
            feedback = f"代码执行成功。输出: {result[:200]}..." if len(result) > 200 else f"代码执行成功。输出: {result}"
        else:
            feedback = f"Code executed successfully. Output: {result[:200]}..." if len(result) > 200 else f"Code executed successfully. Output: {result}"
        status = "completed"
    else:
        feedback = result
        status = "failed"
    
    # 4. 处理生成的文件（如果执行成功）
    output_file_ids = []
    generated_files_info = []
    updated_context_file_ids = list(context_files)  # 创建副本，避免直接修改
    
    if execution_success and new_files:
        try:
            from textmsa.services.file.file_service import get_file_service
            from datetime import datetime
            
            file_service = get_file_service()
            
            for fname in new_files:
                try:
                    file_path = str(work_dir / fname)
                    
                    # 注册生成的文件到数据库
                    registered_file = file_service.register_generated_file(
                        file_path=file_path,
                        filename=fname,
                        parent_file_ids=input_file_ids,
                        description=(
                            f"代码生成输出: {expect_output[:100] if expect_output else '无描述'}"
                            if language == "zh"
                            else f"Codegen output: {expect_output[:100] if expect_output else 'No description'}"
                        ),
                        metadata={
                            "from_agent": "plan_agent_codegen",
                            "generated_at": datetime.now().isoformat(),
                        },
                    )
                    
                    file_id = registered_file["file_id"]
                    output_file_ids.append(file_id)
                    
                    # 添加到 context_files（用于后续步骤）
                    updated_context_file_ids.append(file_id)
                    
                    generated_files_info.append({
                        "file_id": file_id,
                        "file_name": fname,
                        "file_path": file_path,
                        "description": registered_file.get("description", ""),
                    })
                    
                    logger.info(
                        f"成功注册生成的文件: {fname}, file_id={file_id}"
                    )
                except Exception as e:
                    logger.error(f"注册生成文件失败: {fname}, {e}", exc_info=True)
        except Exception as e:
            logger.error(f"处理生成文件时出错: {e}", exc_info=True)
    
    # 5. 记录执行历史
    execution_record = {
        "service_id": "codegen",
        "input_file_ids": input_file_ids,
        "parameters": {"code": code, "expected_output": expected_output},
        "output_file_ids": output_file_ids,
        "status": status,
        "feedback": feedback,
    }
    
    updated_execution_history = execution_history + [execution_record]
    
    # 6. 添加执行消息
    execute_message = f"执行自生成代码：{feedback}" if language == "zh" else f"Run self-generated code: {feedback}"
    
    message = get_agent_service().build_files_message(
        message=execute_message,
        file_ids=output_file_ids,
        user_id=user_id,
    )
    return {
        "execution_history": updated_execution_history,
        "execute_feedback": feedback,
        "context_files": updated_context_file_ids,
        "message": message,
    }


def report_node(state: PlanAgentState) -> PlanAgentState:
    """
    报告节点：根据执行历史生成最终报告
    
    Args:
        state: 当前状态
    
    Returns:
        更新后的状态
    """
    user_query = state["user_query"]
    execution_history = state.get("execution_history", [])
    language = _get_language(state)
    stop_reason = str(state.get("stop_reason", "") or "")

    # 1. 计算最终状态与错误/中止原因
    final_status = "unknown"
    final_error_or_stop_reason = ""
    if execution_history:
        last_record = execution_history[-1]
        final_status = str(last_record.get("status", "unknown") or "unknown")
        last_feedback = str(last_record.get("feedback", "") or "")
        # 如果有显式停止原因，则优先展示停止原因；否则使用最后一次执行反馈
        if stop_reason:
            final_error_or_stop_reason = stop_reason
        else:
            final_error_or_stop_reason = last_feedback
    else:
        # 没有执行历史，只能依赖 stop_reason
        if stop_reason:
            final_error_or_stop_reason = stop_reason
    
    # 2. 格式化执行历史
    execution_history_string = format_execution_history(execution_history, language=language)
    
    # 3. 调用 LLM 生成报告
    llm = get_llm_client_instance()
    prompt = format_report_prompt(
        user_query=user_query,
        execution_history_string=execution_history_string,
        final_status=final_status,
        final_error_or_stop_reason=final_error_or_stop_reason,
        language=language,
    )
    
    request = LLMRequest(
        messages=[
            {
                "role": "system",
                "content": (
                    "你是一个专业的报告生成助手，擅长根据执行历史生成清晰的总结报告。"
                    if language == "zh"
                    else "You are a professional report generation assistant, skilled at producing clear summaries based on execution history."
                ),
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
    )
    response = llm.chat(request)
    
    # 4. 解析响应
    content = response.content.strip() if response.content else ""
    result = extract_json_from_response(content)
    
    execution_summary = result.get("execution_summary", "")
    
    # 5. 添加最终报告消息
    # 构建消息对象（类似 read_agent 的格式）


    message = get_agent_service().build_message(
        message=execution_summary
    )

    
    return {
        "final_answer": execution_summary,
        "message": message,
    }
