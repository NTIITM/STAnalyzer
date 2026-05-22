"""
Files Deep Read Agent 节点实现
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

from dashscope import MultiModalConversation
from langchain_core.callbacks import file
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from textmsa.logging_config import get_logger
from textmsa.services.agent.agent_service import get_agent_service
from textmsa.services.agent.agent_utils import (
    extract_json_from_response,
    get_python_repl_tool_instance,
)
from textmsa.services.agent.tools.file_reader_tool import FileReaderTool
from textmsa.settings import (
    get_codegen_llm_config,
    get_llm_config,
    get_multimodal_llm_config,
)

from .prompts import (
    format_plan_decision_prompt,
    format_analysis_plan_prompt,
    format_read_plan_prompt,
    format_integration_prompt,
    format_read_prompt,
    format_failure_prompt,
)
from .state import FileTreeNode, FilesDeepReadAgentState, PlanHistory

logger = get_logger(__name__)

# ----------------------------------------------------------------------------- #
# LLM helpers (langchain-openai)
# ----------------------------------------------------------------------------- #


@lru_cache(maxsize=1)
def _base_llm_config() -> dict[str, Any]:
    return dict(get_llm_config())


@lru_cache(maxsize=1)
def _base_codegen_llm_config() -> dict[str, Any]:
    return dict(get_codegen_llm_config())


def _build_chat_llm(*, temperature: float, max_tokens: int, use_codegen: bool = False) -> ChatOpenAI:
    """Create a ChatOpenAI instance with config overrides."""
    base_config = _base_codegen_llm_config() if use_codegen else _base_llm_config()
    params: dict[str, Any] = {
        "model": base_config.get("model"),
        "api_key": base_config.get("api_key"),
        "base_url": base_config.get("base_url"),
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    # Optional fields only when provided to avoid passing unsupported kwargs.
    if base_config.get("timeout_seconds") is not None:
        params["timeout"] = base_config["timeout_seconds"]
    if base_config.get("max_retries") is not None:
        params["max_retries"] = base_config["max_retries"]
    return ChatOpenAI(**params)


def _run_llm(prompt: str, *, temperature: float, max_tokens: int, use_codegen: bool = False) -> str:
    """Execute a single-turn LLM call and return the text content."""
    llm = _build_chat_llm(temperature=temperature, max_tokens=max_tokens, use_codegen=use_codegen)
    response = llm.invoke([HumanMessage(content=prompt)])
    return getattr(response, "content", "") or ""


# ----------------------------------------------------------------------------- #
# helpers
# ----------------------------------------------------------------------------- #

def _find_file_info(
    file_tree_list: list[FileTreeNode] | FileTreeNode | dict, target_id: str
) -> FileTreeNode | dict | None:
    """DFS 查找 file_id 对应的节点，支持 list 或 dict 根节点"""
    if isinstance(file_tree_list, list):
        for item in file_tree_list:
            found = _find_file_info(item, target_id)
            if found:
                return found
        return None
    if not isinstance(file_tree_list, dict):
        return None
    if file_tree_list.get("file_id") == target_id:
        return file_tree_list
    for child in file_tree_list.get("children", []) or []:
        found = _find_file_info(child, target_id)
        if found:
            return found
    return None

# TODO：修改为多父节点
def _append_generated_file(
    generated_files: list[dict], file_tree_list: list[dict], parent_id: str | None, file_entry: dict
):
    generated_files.append(file_entry)

    # 更新 file_tree
    if parent_id is None:
        if isinstance(file_tree_list, list):
            file_tree_list.append(file_entry)
        return

    parent_node = _find_file_info(file_tree_list, parent_id) if file_tree_list else None
    if not parent_node:
        return
    if "children" not in parent_node or parent_node["children"] is None:
        parent_node["children"] = []
    parent_node["children"].append(file_entry)

    return file_tree_list, generated_files


def _is_image_file(path_str: str) -> bool:
    path = Path(path_str)
    return path.suffix.lower() in {
        ".png",
        ".jpg",
        ".jpeg",
        ".bmp",
        ".gif",
        ".tiff",
        ".webp",
    }


def _build_image_block(image_paths: list[str]) -> list[dict[str, str]]:
    """构造多模态 image 块（file:// 协议）"""
    content_payload: list[dict[str, str]] = [{"image": f"file://{path}"} for path in image_paths]
    return content_payload


def _strip_code_fence(text: str) -> str:
    """移除 ```lang ... ``` 样式代码块包裹"""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
        if cleaned.startswith("python"):
            cleaned = cleaned[len("python") :]
        if cleaned.startswith("\n"):
            cleaned = cleaned[1:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def _parse_integration_response(response_content: str) -> tuple[str, list[dict]]:
    """
    解析集成代码生成的响应，提取 code 和 expected_files。
    响应可能是 JSON 格式或纯代码格式（向后兼容）。
    
    Returns:
        tuple: (code, expected_files)
        - code: Python 代码字符串
        - expected_files: 字典列表，每个字典包含 file_name 和 description
    """
    import json
    
    cleaned = response_content.strip()
    
    # 尝试解析 JSON 格式
    try:
        # 先尝试提取 JSON（可能被 markdown 代码块包裹）
        parsed = extract_json_from_response(cleaned)
        if parsed:
            code = parsed.get("code", "")
            expected_files_raw = parsed.get("expected_files", [])
            
            # 将 expected_files 转换为标准格式（支持旧格式的字符串列表和新格式的字典列表）
            expected_files = []
            for item in expected_files_raw:
                if isinstance(item, dict):
                    # 新格式：字典，确保包含 file_name 和 description
                    expected_files.append({
                        "file_name": item.get("file_name", ""),
                        "description": item.get("description", "")
                    })
                elif isinstance(item, str):
                    # 旧格式：字符串，转换为字典格式（向后兼容）
                    expected_files.append({
                        "file_name": item,
                        "description": ""
                    })
            
            if code:
                return code, expected_files
    except (json.JSONDecodeError, KeyError, AttributeError):
        pass
    
    # 如果不是 JSON 格式，尝试作为纯代码处理（向后兼容）
    code = _strip_code_fence(cleaned)
    return code, []


# ----------------------------------------------------------------------------- #
# nodes
# ----------------------------------------------------------------------------- #


def decision_node(state: FilesDeepReadAgentState):
    user_query = state["user_query"]
    file_tree_list = state["file_tree_list"]
    generated_files = state.get("generated_files", [])    
    plan_count = state.get("plan_count", 0)
    language = state.get("language", "en")
    # 读取计划历史、在计划制定时再创建
    history_plans = state.get("history_plans", [])
    
    # 检查 plan_count 是否超过 3
    if plan_count > 3:
        if language == "zh":
            message = {"message": "超过最大规划次数，进入失败处理节点"}
        else:
            message = {"message": "Exceeded maximum planning attempts, entering failure node"}
        return {
            "next_route": "failure",
            "message": message,
            "plan_count": plan_count,
        }
    
    decision_prompt = format_plan_decision_prompt(
        user_query=user_query,
        file_tree_list=file_tree_list,
        generated_files=generated_files,
        plan_count=plan_count,
        history_plans=history_plans,
        language=language,
    )
    response_text = _run_llm(decision_prompt, temperature=0.1, max_tokens=2000)
    parsed = extract_json_from_response(response_text)

    decision = parsed.get("decision")
    reasoning = parsed.get("reasoning")


    message = get_agent_service().build_message(
        message=reasoning,
    )
    return {
        "next_route": decision,
        "message": message,
        "plan_count": plan_count + 1,
    }

    
def analysis_plan_node(state: FilesDeepReadAgentState):
    user_query = state["user_query"]
    file_tree_list = state["file_tree_list"]
    generated_files = state.get("generated_files", [])
    history_plans = state.get("history_plans", [])
    language = state.get("language", "en")
    

    analysis_prompt = format_analysis_plan_prompt(
        user_query=user_query,
        file_tree_list=file_tree_list,
        generated_files=generated_files,
        history_plans=history_plans,
        language=language,
    )
    response_text = _run_llm(analysis_prompt, temperature=0.1, max_tokens=32000)
    parsed = extract_json_from_response(response_text)
    analysis_plans = parsed.get("analysis_plans") or []
    reasoning = parsed.get("reasoning") or ""
    
    # 创建 history_plan 记录
    plan_history: PlanHistory = {
        "plan_type": "analysis_plans",
        "plan": analysis_plans,
        "reasoning": reasoning,
        "result": None,
    }
    history_plans.append(plan_history)
    
    message = {"message": reasoning}
    return {
        "history_plans": history_plans,
        "analysis_plans": analysis_plans,
        "message": message,
    }

    
def read_plan_node(state: FilesDeepReadAgentState):
    user_query = state["user_query"]
    file_tree_list = state["file_tree_list"]
    generated_files = state.get("generated_files", [])
    history_plans = state.get("history_plans", [])
    language = state.get("language", "en")

    read_plan_prompt = format_read_plan_prompt(
        user_query=user_query,
        file_tree_list=file_tree_list,
        generated_files=generated_files,
        history_plans=history_plans,
        language=language,
    )
    response_text = _run_llm(read_plan_prompt, temperature=0.1, max_tokens=32000)
    parsed = extract_json_from_response(response_text)
    read_plan = parsed.get("read_plan") or {}
    reasoning = parsed.get("reasoning") or ""
    message = {"message": reasoning}
    plan_history = PlanHistory(plan_type="read_plan", plan=read_plan, reasoning=reasoning)
    history_plans.append(plan_history)
    return {
        "read_plan": read_plan,
        "message": message,
        "history_plans": history_plans
    }

# def plan_node(state: FilesDeepReadAgentState):
#     user_query = state["user_query"]
#     file_tree_list = state["file_tree_list"]
#     analysis_plans = state.get("analysis_plans", [])
#     generated_files = state.get("generated_files", [])
#     plan_count = state.get("plan_count", 0)
#     read_plan = state.get("read_plan", {})
    
#     # 增加 plan 执行计数
#     plan_count = plan_count + 1

#     client = get_llm_client_instance()
#     # 先决策：生成分析计划还是阅读计划
#     decision_prompt = format_plan_decision_prompt(
#         user_query=user_query,
#         file_tree_list=file_tree_list,
#         generated_files=generated_files,
#         plan_count=plan_count,
#         read_plan=read_plan,
#     )
#     decision_request = LLMRequest(
#         messages=[{"role": "user", "content": decision_prompt}],
#         temperature=0.1,
#         max_tokens=32000,
#     )
#     decision_resp = client.chat(decision_request)
#     decision_parsed = extract_json_from_response(decision_resp.content)
#     decision = (decision_parsed.get("decision") or "").strip()
#     decision_reasoning = decision_parsed.get("reasoning") or ""

#     message: dict[str, Any] = {
#         "message": "plan_decision",
#         "extra": {"json": {"decision": decision, "reasoning": decision_reasoning}},
#     }

#     # 根据决策生成具体计划
#     if decision == "analysis":
#         analysis_prompt = format_analysis_plan_prompt(
#             user_query=user_query,
#             file_tree_list=file_tree_list,
#             generated_files=generated_files,
#         )
#         analysis_request = LLMRequest(
#             messages=[{"role": "user", "content": analysis_prompt}],
#             temperature=0.1,
#             max_tokens=32000,
#         )
#         analysis_resp = client.chat(analysis_request)
#         analysis_parsed = extract_json_from_response(analysis_resp.content)
#         new_plans = analysis_parsed.get("analysis_plans") or []

#         if new_plans:
#             analysis_plans = new_plans
#         message = {"message": "new_analysis_plans", "extra": {"json": analysis_plans}}
#         next_route = "analyze"
#     else:
#         read_prompt = format_read_plan_prompt(
#             user_query=user_query,
#             file_tree_list=file_tree_list,
#             generated_files=generated_files,
#         )
#         read_request = LLMRequest(
#             messages=[{"role": "user", "content": read_prompt}],
#             temperature=0.1,
#             max_tokens=32000,
#         )
#         read_resp = client.chat(read_request)
#         read_parsed = extract_json_from_response(read_resp.content)
#         new_read_plan = read_parsed.get("read_plan") or {}
#         if new_read_plan:
#             read_plan = new_read_plan
#         message = {"message": "read_plan", "extra": {"json": read_plan}}
#         next_route = "read"

#     return {
#         "plan_count": plan_count,
#         "analysis_plans": analysis_plans,
#         "read_plan": read_plan,
#         "message": message,
#         "next_route": next_route,
#     }


# def analyze_node(state: FilesDeepReadAgentState):
#     analysis_plans = state.get("analysis_plans", [])
#     generated_files_info = state.get("generated_files_info", [])
#     file_tree_list = state.get("file_tree_list", [])
#     user_query = state["user_query"]
#     work_dir_path = state["work_dir_path"]
    
#     new_file_infos = []
#     for plan_item in analysis_plans:
#         file_id = plan_item.get("file_id", "")

#         file_info = _find_file_info(file_tree_list, file_id) or {}
#         reader = FileReaderTool(max_text_bytes=2000)
#         file_path = file_info.get("file_path") or ""
#         preview_raw = (
#             reader.read_preview_by_path(
#                 file_path=file_path,
#                 filename=file_info.get("filename") or file_info.get("file_name") or "",
#             )
#             if file_path
#             else None
#         )
#         preview_text = ""
#         if preview_raw:
#             try:
#                 preview_text = reader.format_preview(preview_raw, style="compact")
#             except Exception:  # noqa: BLE001
#                 preview_text = str(preview_raw)

#         read_results = {
#             "file_id": file_id,
#             "file_name": file_info.get("filename") or file_info.get("file_name") or "",
#             "file_path": file_path,
#             "preview": preview_text or file_info.get("description") or "",
#         }
#         agent_result = run_file_analysis_agent(
#             user_query=plan_item.get("user_query", user_query),
#             read_results=read_results,
#             work_dir_path=work_dir_path,
#         )
#         plan_item["result"] = agent_result["final_answer"]
#         for file_info in agent_result["generated_files_info"]:
#             file_info["file_id"] = f"gen_{uuid.uuid4().hex}"
#             _append_generated_file(generated_files = generated_files_info, file_tree_list = file_tree_list, parent_id=file_id, file_entry=file_info)
#             new_file_infos.append(file_info)

#     message = {"message": "Sub Agent File Analysis Finshed", "extra": {"files": new_file_infos}}
#     return {
#         "file_tree_list": file_tree_list,
#         "analysis_plans": analysis_plans,
#         "generated_files_info": generated_files_info,
#         "message": message,
#     }


def analyze_node(state: FilesDeepReadAgentState):
    analysis_plans = state.get("analysis_plans")
    generated_files = state.get("generated_files", [])
    file_tree_list = state.get("file_tree_list", [])
    work_dir_path = state["work_dir_path"]
    language = state.get("language", "en")
    history_plans = state.get("history_plans", [])
    work_dir = Path(work_dir_path)
    work_dir.mkdir(parents=True, exist_ok=True)

    new_generated_file_info = list()
    repl = get_python_repl_tool_instance()
    # reader = FileReaderTool(max_text_bytes=2000)

    # 找到对应的 history_plan 记录（最后一个 analysis_plans 类型的记录）
    target_history_plan = None
    for plan_history in reversed(history_plans):
        if plan_history.get("plan_type") == "analysis_plans":
            target_history_plan = plan_history
            break
    
    # 存储所有 analysis_plan 的执行结果
    analysis_results = []

    for plan_idx, analysis_plan in enumerate(analysis_plans):
        file_ids = analysis_plan.get("file_ids", [])
        file_infos = []
        instruction = analysis_plan.get("instruction", "")
        
        for fid in file_ids:
            info = _find_file_info(file_tree_list, fid) or {}
            file_infos.append(
                {
                    "file_id": fid,
                    "file_name": info.get("filename") or info.get("file_name") or "",
                    "file_path": info.get("file_path") or "",
                    "description": info.get("description") or "",
                    # "preview": reader.read_preview_by_path(info.get("file_path"))
                }
            )
        
        # Try up to 3 times, stop early when new files appear.
        history_errors = list()
        new_files = set()
        execution_success = False
        
        for attempt in range(3):
            prompt = format_integration_prompt(
                instruction=instruction,
                file_infos=file_infos,
                history_errors=history_errors,
                work_dir_path=work_dir_path,
                language=language,
            )

            response_text = _run_llm(prompt, temperature=0.1, max_tokens=5000, use_codegen=True)
            code, expected_files = _parse_integration_response(response_text)

            before = {p.name for p in work_dir.iterdir() if p.is_file()}
            execution_result = repl.run_code(code=code)
            if not execution_result.success:
                history_errors.append(execution_result.stderr)
                continue
            
            execution_success = True
            after = {p.name for p in work_dir.iterdir() if p.is_file()}
            new_files = after - before
            
            if new_files:
                break

        # 处理生成的文件
        # 创建 expected_files 的查找字典，以 file_name 为键
        expected_files_dict = {
            item["file_name"]: item.get("description", "")
            for item in expected_files
        }
        
        for fname in new_files:
            fid = f"gen_{uuid.uuid4().hex}"
            path = str(work_dir / fname)
            # 从 expected_files 中获取对应的 description
            description = expected_files_dict.get(fname, "")
            entry = {
                "file_id": fid,
                "file_name": fname,
                "file_path": path,
                "description": description,
            }
            _append_generated_file(generated_files, file_tree_list, None, entry)
            new_generated_file_info.append(entry)
            
            # ========== 新增：注册生成的文件到数据库 ==========
            try:
                from textmsa.services.file.file_service import get_file_service
                from datetime import datetime
                
                file_service = get_file_service()
                
                # 获取 user_id 和 project_id
                # 方案A: 从 state 中获取（推荐）
                user_id = state.get("user_id")
                project_id = state.get("project_id")
                
                # 方案B: 从第一个父文件中获取（如果 state 中没有 user_id）
                # 注意：这需要先通过其他方式获取 user_id，因为 get_file_info 需要 user_id
                # 在大多数情况下，user_id 应该从 API 路由传入，所以方案B可能不会经常使用
                # 如果 state 中没有 user_id，我们跳过注册
                
                if user_id and file_ids:
                    # 注册文件
                    registered_file = file_service.register_generated_file(
                        file_path=path,
                        filename=fname,
                        parent_file_ids=file_ids,  # 使用当前 analysis_plan 的 file_ids
                        description=description,
                        metadata={
                            "from_agent": "files_deep_read_agent",
                            "generated_at": datetime.now().isoformat(),
                        },
                    )
                    
                    # 更新 entry 中的 file_id 为注册后的 ID
                    entry["file_id"] = registered_file["file_id"]
                    entry["registered"] = True
                    entry["project_id"] = registered_file.get("project_id")
                    logger.info(
                        f"成功注册生成的文件: {fname}, file_id={registered_file['file_id']}"
                    )
                else:
                    logger.warning(
                        f"无法获取 user_id 或 file_ids，跳过文件注册: {fname}. "
                        f"user_id={user_id}, file_ids={file_ids}"
                    )
                    entry["registered"] = False
                    entry["registration_error"] = "无法获取 user_id 或 file_ids"
            except Exception as e:
                logger.error(f"注册生成文件失败: {fname}, {e}", exc_info=True)
                entry["registered"] = False
                entry["registration_error"] = str(e)
            # ========== 文件注册逻辑结束 ==========
        
        # 构建单个 analysis_plan 的执行结果（格式化模板）
        plan_result = {
            "plan_index": plan_idx + 1,
            "instruction": instruction,
            "file_ids": file_ids,
            "file_names": [info.get("file_name", "") for info in file_infos],
            "execution_success": execution_success,
            "generated_files": list(new_files),
            "generated_files_count": len(new_files),
            "history_errors": history_errors,
            "error_count": len(history_errors),
        }
        analysis_results.append(plan_result)
    
    # 构建格式化的 result 字符串
    if language == "zh":
        result_lines = [f"共执行 {len(analysis_plans)} 个分析计划：\n"]
        for result in analysis_results:
            result_lines.append(f"\n【分析计划 {result['plan_index']}】")
            result_lines.append(f"指令: {result['instruction']}")
            result_lines.append(f"输入文件: {', '.join(result['file_names']) if result['file_names'] else '无'}")
            result_lines.append(f"执行状态: {'成功' if result['execution_success'] else '失败'}")
            result_lines.append(f"生成文件数量: {result['generated_files_count']}")
            if result['generated_files']:
                result_lines.append(f"生成文件列表: {', '.join(result['generated_files'])}")
            if result['error_count'] > 0:
                result_lines.append(f"错误次数: {result['error_count']}")
                result_lines.append("错误详情:")
                for err_idx, error in enumerate(result['history_errors'], 1):
                    result_lines.append(f"  错误 {err_idx}: {error[:200]}...")  # 限制错误信息长度
        result_summary = "\n".join(result_lines)
    else:
        result_lines = [f"Executed {len(analysis_plans)} analysis plans:\n"]
        for result in analysis_results:
            result_lines.append(f"\n[Analysis Plan {result['plan_index']}]")
            result_lines.append(f"Instruction: {result['instruction']}")
            result_lines.append(f"Input files: {', '.join(result['file_names']) if result['file_names'] else 'None'}")
            result_lines.append(f"Execution status: {'Success' if result['execution_success'] else 'Failed'}")
            result_lines.append(f"Generated files count: {result['generated_files_count']}")
            if result['generated_files']:
                result_lines.append(f"Generated files: {', '.join(result['generated_files'])}")
            if result['error_count'] > 0:
                result_lines.append(f"Error count: {result['error_count']}")
                result_lines.append("Error details:")
                for err_idx, error in enumerate(result['history_errors'], 1):
                    result_lines.append(f"  Error {err_idx}: {error[:200]}...")  # Limit error message length
        result_summary = "\n".join(result_lines)
    
    # 更新对应的 history_plan 的 result
    if target_history_plan:
        target_history_plan["result"] = result_summary
    
    message = {"message": "analyze finished", "extra": {"files": new_generated_file_info}}

    return {
        "generated_files": generated_files,
        "file_tree_list": file_tree_list,
        "history_plans": history_plans,
        "message": message,
    }

# def analyze_node(state: FilesDeepReadAgentState):
#     read_plan = state.get("read_plan", {})
#     file_tree_list = state.get("file_tree_list", [])
#     generated_files = state.get("generated_files", [])
#     integration_code = state.get("integration_code")
#     user_query = state["user_query"]
#     work_dir_path = state["work_dir_path"]
    
#     file_ids = read_plan.get("file_ids", [])
#     integration_plan = read_plan.get("integration_plan", "")

#     file_infos: list[dict[str, Any]] = []
#     for fid in file_ids:
#         info = _find_file_info(file_tree_list, fid) or {}
#         file_infos.append(
#             {
#                 "file_id": fid,
#                 "file_name": info.get("filename") or info.get("file_name") or "",
#                 "file_path": info.get("file_path") or "",
#                 "description": info.get("description") or "",
#             }
#         )

#     work_dir = Path(work_dir_path)
#     work_dir.mkdir(parents=True, exist_ok=True)

#     new_files: set[str] = set()
#     repl = get_python_repl_tool_instance()

#     # Try up to 3 times, stop early when new files appear.
#     for _ in range(3):
#         prompt = format_integration_prompt(
#             user_query=user_query,
#             integration_plan=integration_plan,
#             file_infos=file_infos,
#             integration_code=integration_code,
#             work_dir_path=work_dir_path,
#         )

#         client = get_codegen_llm_client_instance()
#         request = LLMRequest(
#             messages=[{"role": "user", "content": prompt}],
#             temperature=0.1,
#             max_tokens=5000,
#         )
#         response = client.chat(request)
#         code = _strip_code_fence(response.content)
#         integration_code = code

#         before = {p.name for p in work_dir.iterdir() if p.is_file()}
#         execution_result = repl.run_code(code=code)
#         if not execution_result.success:
#             continue
#         after = {p.name for p in work_dir.iterdir() if p.is_file()}
#         new_files = after - before

#         if new_files:
#             break

#     for fname in new_files:
#         fid = f"gen_{uuid.uuid4().hex}"
#         path = str(work_dir / fname)
#         entry = {
#             "file_id": fid,
#             "file_name": fname,
#             "file_path": path,
#             "description": f"integration output {fname}",
#             "from_agent": "integration",
#         }
#         _append_generated_file(generated_files, file_tree_list, None, entry)
#         read_plan["file_ids"].append(fid)
#     message = {"message": "integration_success", "extra": {"json": {"code": integration_code, "new_files": new_files}}}

#     return {
#         "read_plan": read_plan,
#         "integration_code": integration_code,
#         "generated_files": generated_files,
#         "file_tree_list": file_tree_list,
#         "message": message,
#     }


def read_node(state: FilesDeepReadAgentState):
    read_plan = state.get("read_plan", {})
    file_tree_list = state.get("file_tree_list", [])
    user_query = state["user_query"]
    language = state.get("language", "en")
    history_plans = state.get("history_plans", [])

    # 优先使用计划中的 file_ids；若无则回退为所有有路径的节点
    file_ids: list[str] = read_plan.get("file_ids") or []
    report_plan = read_plan.get("report_plan")
    has_images = False
    image_paths: list[str] = []
    content_blocks: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    reader = FileReaderTool(max_text_bytes=2000)

    for fid in file_ids:
        info = _find_file_info(file_tree_list, fid) or {}
        path = info.get("file_path") or ""
        filename = info.get("filename") or info.get("file_name") or ""

        if not path or not filename:
            continue

        if _is_image_file(path):
            has_images = True
            image_paths.append(path)
            text_block = {
                "type": "text",
                "text": f"文件: {filename}\n路径: {path}\n类型: 图像文件",
            }
            content_blocks.append(text_block)
            continue

        try:
            full_raw = reader.read_full_by_path(file_path=path, filename=filename)
            text_content = f"文件: {filename}\n路径: {path}\n内容:\n{full_raw}"
            content_blocks.append({"type": "text", "text": text_content})
            summaries.append(
                {
                    "file_name": filename,
                    "file_id": fid,
                    "file_path": path,
                    "content": full_raw,
                    "description": info.get("description") or "",
                }
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"读取文件失败 {path}: {e}")
            text_content = f"文件: {filename}\n路径: {path}\n[读取失败: {str(e)}]"
            content_blocks.append({"type": "text", "text": text_content})

    prompt = format_read_prompt(
        user_query=user_query,
        report_plan=report_plan,
        file_summaries=summaries,
        language=language,
    )

    if has_images:
        text_blocks = [prompt] + [
            block["text"] for block in content_blocks if block.get("type") == "text"
        ]
        merged_text = "\n\n".join(text_blocks)
        content_payload: list[dict[str, str]] = _build_image_block(image_paths)
        content_payload.append({"text": merged_text})
        messages = [{"role": "user", "content": content_payload}]
        response = MultiModalConversation.call(
            api_key=get_multimodal_llm_config()["api_key"],
            model=get_multimodal_llm_config()["model"],
            messages=messages,
        )
        final_answer = (
            response.output.choices[0].message.content[0].get("text", "")
            if response.output and response.output.choices
            else ""
        )
    else:
        file_contents_text = "\n\n".join(
            [block["text"] for block in content_blocks if block.get("type") == "text"]
        )
        final_prompt = f"{prompt}\n\n{file_contents_text}" if file_contents_text else prompt
        response_text = _run_llm(final_prompt, temperature=0.1, max_tokens=32000)
        final_answer = extract_json_from_response(response_text).get("final_answer", "")

    # 更新对应的 history_plan 的 result（更新最后一个 read_plan 类型的记录）
    for plan_history in reversed(history_plans):
        if plan_history.get("plan_type") == "read_plan":
            plan_history["result"] = final_answer
            break

    message = {"message": final_answer}
    return {
        "final_answer": final_answer,
        "history_plans": history_plans,
        "message": message,
    }


def failure_node(state: FilesDeepReadAgentState):
    """Failure node: generates final answer explaining why the task failed after exceeding plan_count limit."""
    user_query = state["user_query"]
    file_tree_list = state["file_tree_list"]
    history_plans = state.get("history_plans", [])
    language = state.get("language", "en")
    
    prompt = format_failure_prompt(
        user_query=user_query,
        file_tree_list=file_tree_list,
        history_plans=history_plans,
        language=language,
    )
    
    response_text = _run_llm(prompt, temperature=0.1, max_tokens=32000)
    parsed = extract_json_from_response(response_text)
    final_answer = parsed.get("final_answer", "")
    
    if not final_answer:
        # Fallback message
        if language == "zh":
            final_answer = "抱歉，任务执行失败。已超过最大规划尝试次数，无法完成您的请求。请尝试简化您的问题或提供更具体的文件信息。"
        else:
            final_answer = "Sorry, the task execution failed. The maximum number of planning attempts has been exceeded, and your request could not be completed. Please try simplifying your question or providing more specific file information."
    
    message = {"message": final_answer}
    return {
        "final_answer": final_answer,
        "message": message,
    }

