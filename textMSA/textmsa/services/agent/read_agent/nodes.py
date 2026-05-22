"""
Files Deep Read Agent 节点实现
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from dashscope import MultiModalConversation
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from textmsa.logging_config import get_logger
from textmsa.services.agent.agent_service import get_agent_service
from textmsa.services.agent.agent_utils import (
    extract_json_from_response,
    format_file_tree,
    get_python_repl_tool_instance,
)
from textmsa.services.agent.tools.file_reader_tool import FileReaderTool
from textmsa.settings import (
    get_codegen_llm_config,
    get_llm_config,
    get_multimodal_llm_config,
)

from .prompts import (
    format_answer_prompt,
    format_code_generation_prompt,
    format_code_retry_prompt,
    format_data_preview_analysis_prompt,
    format_plan_prompt,
    format_text_summary_prompt,
)
from .state import ReadAgentState, PlanHistory

logger = get_logger(__name__)

# ----------------------------------------------------------------------------- #
# Localization helpers
# ----------------------------------------------------------------------------- #


def _normalize_language(language: str | None) -> str:
    """Normalize language input; default to English."""
    if not language:
        return "en"
    lower = language.lower()
    if lower.startswith("zh"):
        return "zh"
    if lower.startswith("en"):
        return "en"
    return "en"


def _get_localized_message(messages: dict[str, str], language: str | None) -> str:
    """Get localized message by language with English fallback."""
    lang = _normalize_language(language)
    return messages.get(lang, messages.get("en", ""))


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


def _run_llm(prompt: str, *, temperature: float, max_tokens: int, use_codegen: bool = False, node_name: str = "unknown") -> str:
    """Execute a single-turn LLM call and return the text content."""
    base_config = _base_codegen_llm_config() if use_codegen else _base_llm_config()
    model_name = base_config.get("model", "unknown")
    
    # 记录输入
    logger.info(
        f"[LLM Input] Node: {node_name} | Model: {model_name} | UseCodegen: {use_codegen}",
        extra={
            "node": node_name,
            "model": model_name,
            "use_codegen": use_codegen,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "prompt_length": len(prompt),
            "prompt_preview": prompt[:500] + "..." if len(prompt) > 500 else prompt,
        },
    )
    logger.info(f"[LLM Input Full] Node: {node_name}\n{prompt}")
    
    llm = _build_chat_llm(temperature=temperature, max_tokens=max_tokens, use_codegen=use_codegen)
    response = llm.invoke([HumanMessage(content=prompt)])
    response_content = getattr(response, "content", "") or ""
    
    # 记录输出
    logger.info(
        f"[LLM Output] Node: {node_name} | Model: {model_name}",
    )
    logger.info(f"[LLM Output Full] Node: {node_name}\n{response_content}")
    
    return response_content


# ----------------------------------------------------------------------------- #
# helpers
# ----------------------------------------------------------------------------- #

def _find_file_info(
    file_tree_list: list[dict] | dict, target_id: str
) -> dict | None:
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


def _parse_code_response(response_content: str) -> str:
    """
    解析代码生成的响应，提取 code。
    
    Returns:
        str: Python 代码字符串
    """
    cleaned = response_content.strip()
    
    # 尝试解析 JSON 格式
    try:
        parsed = extract_json_from_response(cleaned)
        if parsed:
            code = parsed.get("code", "")
            if code:
                return code
    except (KeyError, AttributeError):
        pass
    
    # 如果不是 JSON 格式，尝试作为纯代码处理（向后兼容）
    code = _strip_code_fence(cleaned)
    return code


def _fix_main_block(code: str) -> str:
    """
    修复代码中的 if __name__ == "__main__": 块
    
    在 REPL 环境中，__name__ 可能不是 "__main__"，导致代码不执行。
    此函数将 if __name__ == "__main__": 块中的内容提取出来，直接执行。
    """
    import re
    
    # 检查是否包含 if __name__ == "__main__": 模式
    pattern = r'if\s+__name__\s*==\s*["\']__main__["\']\s*:'
    
    if not re.search(pattern, code):
        return code  # 没有 main 块，直接返回
    
    lines = code.split('\n')
    result_lines = []
    non_main_lines = []
    main_content_lines = []
    in_main_block = False
    main_block_indent = None
    
    for line in lines:
        # 检查是否是 if __name__ == "__main__": 行
        if re.match(r'\s*if\s+__name__\s*==\s*["\']__main__["\']\s*:', line):
            in_main_block = True
            main_block_indent = len(line) - len(line.lstrip())
            continue
        
        if in_main_block:
            # 在 main 块中
            if not line.strip():  # 空行
                main_content_lines.append('')
                continue
            
            current_indent = len(line) - len(line.lstrip())
            
            # 如果缩进小于等于 main_block_indent，说明 main 块结束了
            if current_indent <= main_block_indent:
                in_main_block = False
                # 这一行不属于 main 块，添加到非 main 块
                non_main_lines.append(line)
                continue
            
            # 提取 main 块中的内容，去除缩进（main_block_indent + 4）
            indent_to_remove = main_block_indent + 4
            if len(line) >= indent_to_remove:
                main_content_lines.append(line[indent_to_remove:])
            else:
                # 如果缩进不够，可能是使用了 tab 或其他缩进方式，直接去除所有前导空白
                main_content_lines.append(line.lstrip())
        else:
            # 不在 main 块中，保留原行
            non_main_lines.append(line)
    
    # 组合代码：非 main 块 + main 块内容
    fixed_code = '\n'.join(non_main_lines)
    if main_content_lines:
        if fixed_code and not fixed_code.endswith('\n'):
            fixed_code += '\n'
        fixed_code += '\n'.join(main_content_lines)
    
    if main_content_lines:
        logger.info(
            "Read Agent - 修复了 if __name__ == '__main__': 块",
            extra={
                "original_code_length": len(code),
                "fixed_code_length": len(fixed_code),
                "main_block_lines": len(main_content_lines),
            },
        )
    
    return fixed_code


def _is_data_file(filename: str) -> bool:
    """判断是否为数据文件（需要代码分析）"""
    data_extensions = {
        ".csv", ".h5ad", ".json", ".parquet", ".xlsx", ".xls",
        ".h5", ".hdf5", ".feather", ".pkl", ".pickle",
    }
    return Path(filename).suffix.lower() in data_extensions


# ----------------------------------------------------------------------------- #
# nodes
# ----------------------------------------------------------------------------- #

def plan_node(state: ReadAgentState):
    """生成执行计划（顺序规划）"""
    user_query = state["user_query"]
    file_tree_list = state["file_tree_list"]
    language = state.get("language", "en")

    file_tree_format_string = format_file_tree(file_tree_list, language=language)    
    plan_prompt = format_plan_prompt(
        user_query=user_query,
        file_tree_format_string=file_tree_format_string,
        language=language,
    )
    response_text = _run_llm(plan_prompt, temperature=0.1, max_tokens=32000, node_name="plan_node")
    parsed = extract_json_from_response(response_text)
    plans = parsed.get("plans", [])
    reasoning = parsed.get("reasoning", "")
    
    if not plans:
        warning_msg = _get_localized_message(
            {
                "zh": "计划生成失败，返回空计划列表",
                "en": "Plan generation failed, returning empty plan list",
            },
            language,
        )
        logger.warning(warning_msg)
        plans = []
    
    history_plans: list[PlanHistory] = []
    for plan in plans:
        plan_history: PlanHistory = {
            "file_id": plan.get("file_id", ""),
            "file_name": plan.get("file_name", ""),
            "file_path": plan.get("file_path", ""),
            "plan_detail": plan.get("plan_detail", ""),
            "result": None,
        }
        # 保存每个文件的顺序理由（如果存在）
        order_reasoning = plan.get("order_reasoning", "")
        if order_reasoning:
            plan_history["order_reasoning"] = order_reasoning
        history_plans.append(plan_history)
    
    logger.info(
        "Plan node completed",
        extra={
            "plan_count": len(history_plans),
            "reasoning": reasoning[:200] + "..." if len(reasoning) > 200 else reasoning,
        },
    )
    
    plan_message = _get_localized_message(
        {
            "zh": f"已生成 {len(history_plans)} 个阅读计划（顺序执行）",
            "en": f"{len(history_plans)} reading plans generated (sequential order)",
        },
        language,
    )
    # message = get_agent_service().build_message(
    #     message=plan_message,
    #     extra={
    #         "plans": history_plans,
    #         "reasoning": reasoning,
    #     },
    # )
    
    return {
        "current_plan_index": 0,
        "history_plans": history_plans,
        "plan_reasoning": reasoning,
        # "message": message,
        "message": None,
    }

def execute_plan_node(state: ReadAgentState):
    """路由节点：判断是否还有计划需要执行"""
    current_plan_index = state.get("current_plan_index", 0)
    history_plans = state.get("history_plans", [])
    
    if current_plan_index >= len(history_plans):
        next_route = "answer"
    else:
        next_route = "read"
    return {
        "next_route": next_route,
        "message": None,
    }

def read_node(state: ReadAgentState):
    """执行单个计划项：读取文件或执行代码分析（可以看到之前读取的结果）"""
    file_tree_list = state["file_tree_list"]
    history_plans = state.get("history_plans", [])
    current_plan_index = state.get("current_plan_index", 0)
    language = state.get("language", "en")
    
    if current_plan_index >= len(history_plans):
        warning_msg = _get_localized_message(
            {
                "zh": "current_plan_index 超出范围",
                "en": "current_plan_index out of range",
            },
            language,
        )
        logger.warning(warning_msg)
        return {}
    
    # 收集之前已读取的结果
    previous_results_list = []
    for i in range(current_plan_index):
        prev_plan = history_plans[i]
        prev_result = prev_plan.get("result")
        if prev_result:
            previous_results_list.append({
                "file_id": prev_plan.get("file_id", ""),
                "file_name": prev_plan.get("file_name", ""),
                "file_path": prev_plan.get("file_path", ""),
                "plan_detail": prev_plan.get("plan_detail", ""),
                "result": prev_result,
            })
    
    # 格式化之前的读取结果
    if previous_results_list:
        previous_results_str = json.dumps(previous_results_list, ensure_ascii=False, indent=2)
        prefix = _get_localized_message(
            {
                "zh": "以下是之前已读取的文件结果：\n\n",
                "en": "The following are results from previously read files:\n\n",
            },
            language,
        )
        suffix = _get_localized_message(
            {
                "zh": "\n\n请参考这些结果来更好地理解上下文。",
                "en": "\n\nPlease refer to these results to better understand the context.",
            },
            language,
        )
        previous_results_str = f"{prefix}{previous_results_str}{suffix}"
    else:
        previous_results_str = _get_localized_message(
            {
                "zh": "尚未读取任何文件。",
                "en": "No previous files have been read yet.",
            },
            language,
        )
    
    current_plan = history_plans[current_plan_index]
    file_id = current_plan.get("file_id", "")
    file_name = current_plan.get("file_name", "")
    file_path = current_plan.get("file_path", "")
    plan_detail = current_plan.get("plan_detail", "")

    # 查找文件信息
    file_info = _find_file_info(file_tree_list, file_id) or {}
    if not file_info:
        warning_msg = _get_localized_message(
            {
                "zh": f"文件信息不存在: file_id={file_id}",
                "en": f"File info not found: file_id={file_id}",
            },
            language,
        )
        logger.warning(warning_msg)
        error_msg = _get_localized_message(
            {
                "zh": f"[错误] 文件信息不存在: file_id={file_id}",
                "en": f"[Error] File info not found: file_id={file_id}",
            },
            language,
        )
        result = error_msg
        history_plans[current_plan_index]["result"] = result
        return {
            "history_plans": history_plans,
            "current_plan_index": current_plan_index + 1,
        }
    
    # 使用文件信息中的路径和名称（如果可用）
    if not file_path:
        file_path = file_info.get("file_path", "")
    if not file_name:
        file_name = file_info.get("file_name") or file_info.get("filename", "")
    
    result = ""
    
    # 判断文件类型并处理
    if _is_image_file(file_path):
        # 图像文件：使用多模态模型分析
        try:
            # 构建图像分析的 prompt，包含结果回答要求
            if language == "zh":
                answer_requirements = """
**回答要求：**
- 你的回答必须严格忠于指令，只报告图像内容中发现的内容
- 使用自然的叙述性文字，不要使用列表或结构化格式
- 不包含任何建议、推荐或超出执行结果范围的建议
- 不要提供任何超出执行结果范围的推荐或建议
"""
            else:
                answer_requirements = """
**Answer Requirements:**
- Your answer must strictly adhere to the instruction and only report what is found in the image content
- Use natural narrative text, not lists or structured formats
- Do NOT include any suggestions, recommendations, or advice beyond what is in the execution results
- Do NOT provide any recommendations or suggestions that go beyond the scope of the execution results
"""
            
            if language == "zh":
                text_content = f"文件: {file_name}\n路径: {file_path}\n类型: 图像文件\n\n请分析图像内容并回答: {plan_detail}\n\n{answer_requirements}"
            else:
                text_content = f"File: {file_name}\nPath: {file_path}\nType: Image file\n\nPlease analyze the image content and answer: {plan_detail}\n\n{answer_requirements}"
            
            content_payload: list[dict[str, str]] = _build_image_block([file_path])
            content_payload.append({"text": text_content})
            messages = [{"role": "user", "content": content_payload}]
            
            multimodal_config = get_multimodal_llm_config()
            model_name = multimodal_config.get("model", "unknown")
            
            # 记录多模态模型输入
            logger.info(
                "[Multimodal LLM Input] Node: read_node | Type: image_analysis",
                extra={
                    "node": "read_node",
                    "model": model_name,
                    "file_name": file_name,
                    "file_path": file_path,
                    "text_content": text_content,
                },
            )
            logger.info(f"[Multimodal LLM Input Full] Node: read_node\nText: {text_content}\nImage: [base64 encoded]")
            
            response = MultiModalConversation.call(
                api_key=multimodal_config["api_key"],
                model=model_name,
                messages=messages,
            )
            
            # 记录多模态模型输出
            empty_response_msg = _get_localized_message(
                {
                    "zh": "[错误] 多模态模型响应为空",
                    "en": "[Error] Multimodal model response is empty",
                },
                language,
            )
            response_text_content = (
                response.output.choices[0].message.content[0].get("text", "")
                if response.output and response.output.choices
                else empty_response_msg
            )
            logger.info(
                "[Multimodal LLM Output] Node: read_node | Type: image_analysis",
                extra={
                    "node": "read_node",
                    "model": model_name,
                    "file_name": file_name,
                    "response_length": len(response_text_content),
                    "response_preview": response_text_content[:500] + "..." if len(response_text_content) > 500 else response_text_content,
                },
            )
            logger.info(f"[Multimodal LLM Output Full] Node: read_node\n{response_text_content}")
            result = response_text_content
        except Exception as e:  # noqa: BLE001
            error_log_msg = _get_localized_message(
                {
                    "zh": f"图像分析失败: {e}",
                    "en": f"Image analysis failed: {e}",
                },
                language,
            )
            logger.error(error_log_msg, exc_info=True)
            error_result_msg = _get_localized_message(
                {
                    "zh": f"[错误] 图像分析失败: {str(e)}",
                    "en": f"[Error] Image analysis failed: {str(e)}",
                },
                language,
            )
            result = error_result_msg
    
    elif _is_data_file(file_name):
        # 数据文件：执行代码分析（最多3次重试）
        repl = get_python_repl_tool_instance()
        code = ""
        execution_result = None
        execution_success = False
        analysis_guidance = ""  # 存储分析指导信息
        
        # 在第一次代码生成前，先进行数据预览分析
        try:
            user_query = state.get("user_query", "")
            preview_analysis_prompt = format_data_preview_analysis_prompt(
                user_query=user_query,
                file_info={
                    "file_id": file_id,
                    "file_name": file_name,
                    "file_path": file_path,
                    "preview": file_info.get("preview", ""),
                    "description": file_info.get("description", ""),
                },
                previous_results=previous_results_str,
                language=language,
            )
            
            guidance_response = _run_llm(
                preview_analysis_prompt,
                temperature=0.1,
                max_tokens=2000,
                use_codegen=False,  # 使用普通 LLM，不是代码生成模型
                node_name="read_node_preview_analysis",
            )
            
            # 解析指导信息
            try:
                parsed = extract_json_from_response(guidance_response)
                if parsed and "guidance" in parsed:
                    analysis_guidance = parsed["guidance"]
                else:
                    analysis_guidance = guidance_response.strip()  # fallback
            except Exception:
                analysis_guidance = guidance_response.strip()  # fallback
            
            logger.info(
                "Read Agent - 数据预览分析完成",
                extra={
                    "file_name": file_name,
                    "guidance_length": len(analysis_guidance),
                    "guidance_preview": analysis_guidance[:200] + "..." if len(analysis_guidance) > 200 else analysis_guidance,
                },
            )
        except Exception as e:
            logger.warning(
                f"数据预览分析失败: {e}",
                exc_info=True,
            )
            # 如果分析失败，继续执行，但不使用指导信息
        
        for attempt in range(3):
            try:
                if attempt == 0:
                    # 第一次：生成代码（包含之前读取的结果和分析指导）
                    prompt = format_code_generation_prompt(
                        instruction=plan_detail,
                        file_info={
                            "file_id": file_id,
                            "file_name": file_name,
                            "file_path": file_path,
                            "preview": file_info.get("preview", ""),
                            "description": file_info.get("description", ""),
                        },
                        previous_results=previous_results_str,
                        analysis_guidance=analysis_guidance,  # 传递分析指导信息
                        language=language,
                    )
                else:
                    # 重试：基于错误信息生成新代码（包含之前读取的结果）
                    if execution_result is None:
                        break  # 如果之前没有执行结果，无法重试
                    prompt = format_code_retry_prompt(
                        instruction=plan_detail,
                        file_info={
                            "file_id": file_id,
                            "file_name": file_name,
                            "file_path": file_path,
                            "preview": file_info.get("preview", ""),
                            "description": file_info.get("description", ""),
                        },
                        previous_code=code,
                        error_message=execution_result.stderr or "",
                        previous_results=previous_results_str,
                        language=language,
                    )
                
                response_text = _run_llm(
                    prompt, 
                    temperature=0.1, 
                    max_tokens=5000, 
                    use_codegen=True,
                    node_name=f"read_node_codegen_attempt_{attempt + 1}",
                )
                code = _parse_code_response(response_text)
                
                if not code:
                    result = _get_localized_message(
                        {
                            "zh": "[错误] 代码生成失败",
                            "en": "[Error] Code generation failed",
                        },
                        language,
                    )
                    break
                
                # 修复 if __name__ == "__main__": 块，确保代码能在 REPL 环境中执行
                code = _fix_main_block(code)
                
                # 执行代码
                execution_result = repl.run_code(code=code)
                
                # 记录执行结果用于调试
                logger.info(
                    "Read Agent - 代码执行结果",
                    extra={
                        "attempt": attempt + 1,
                        "success": execution_result.success,
                        "stdout_length": len(execution_result.stdout) if execution_result.stdout else 0,
                        "stderr_length": len(execution_result.stderr) if execution_result.stderr else 0,
                        "stdout_preview": execution_result.stdout[:200] if execution_result.stdout else None,
                        "stderr_preview": execution_result.stderr[:200] if execution_result.stderr else None,
                    },
                )
                
                # 检查是否有错误（即使 success=True，stderr 或 stdout 中也可能有错误信息）
                # 注意：某些代码可能将错误信息打印到 stdout 而不是 stderr
                has_error = False
                error_keywords = [
                    "Error", "Exception", "Traceback",
                    "AttributeError", "TypeError", "ValueError", "NameError",
                    "KeyError", "IndexError", "FileNotFoundError",
                ]
                
                # 1. 检查 stderr 中的错误关键词
                if execution_result.stderr and execution_result.stderr.strip():
                    stderr_lower = execution_result.stderr.lower()
                    has_error = any(keyword.lower() in stderr_lower for keyword in error_keywords)
                
                # 2. 如果 stderr 中没有错误，检查 stdout 中的错误关键词
                # （某些代码可能使用 print() 将错误信息输出到 stdout）
                if not has_error and execution_result.stdout and execution_result.stdout.strip():
                    stdout_lower = execution_result.stdout.lower()
                    has_error = any(keyword.lower() in stdout_lower for keyword in error_keywords)
                    if has_error:
                        logger.warning(
                            "Read Agent - 在 stdout 中发现错误关键词",
                            extra={
                                "stdout_preview": execution_result.stdout[:500],
                            },
                        )
                
                if execution_result.success and not has_error:
                    # 成功：从 stdout 读取结果
                    success_msg = _get_localized_message(
                        {
                            "zh": "[成功] 代码执行完成，但无输出",
                            "en": "[Success] Code execution completed, but no output",
                        },
                        language,
                    )
                    result = execution_result.stdout or success_msg
                    execution_success = True
                    break
                else:
                    # 失败：记录错误，准备重试
                    # 错误可能在 stderr 或 stdout 中
                    error_sources = []
                    if execution_result.stderr and execution_result.stderr.strip():
                        error_sources.append(f"stderr: {execution_result.stderr}")
                    if execution_result.stdout and execution_result.stdout.strip() and has_error:
                        # 如果 stdout 中包含错误关键词，也将其包含在错误信息中
                        error_sources.append(f"stdout: {execution_result.stdout}")
                    
                    if attempt < 2:  # 不是最后一次尝试
                        warning_msg = _get_localized_message(
                            {
                                "zh": f"代码执行失败（尝试 {attempt + 1}/3）",
                                "en": f"Code execution failed (attempt {attempt + 1}/3)",
                            },
                            language,
                        )
                        logger.warning(
                            warning_msg,
                            extra={
                                "stderr": execution_result.stderr,
                                "stdout": execution_result.stdout if has_error else None,
                            },
                        )
                    else:
                        # 最后一次尝试也失败
                        error_detail = _get_localized_message(
                            {
                                "zh": "无错误信息",
                                "en": "No error message",
                            },
                            language,
                        )
                        # 组合所有错误来源
                        combined_error = "\n".join(error_sources) if error_sources else error_detail
                        error_msg = _get_localized_message(
                            {
                                "zh": f"[错误] 代码执行失败（已重试3次）\n最后错误信息:\n{combined_error}",
                                "en": f"[Error] Code execution failed (retried 3 times)\nLast error:\n{combined_error}",
                            },
                            language,
                        )
                        result = error_msg
            
            except Exception as e:  # noqa: BLE001
                error_log_msg = _get_localized_message(
                    {
                        "zh": f"代码生成或执行异常: {e}",
                        "en": f"Code generation or execution exception: {e}",
                    },
                    language,
                )
                logger.error(error_log_msg, exc_info=True)
                if attempt == 2:  # 最后一次尝试
                    error_result_msg = _get_localized_message(
                        {
                            "zh": f"[错误] 代码生成或执行异常: {str(e)}",
                            "en": f"[Error] Code generation or execution exception: {str(e)}",
                        },
                        language,
                    )
                    result = error_result_msg
                continue
        
        if not execution_success and not result:
            result = _get_localized_message(
                {
                    "zh": "[错误] 代码执行失败，已重试3次",
                    "en": "[Error] Code execution failed, retried 3 times",
                },
                language,
            )
    
    else:
        # 文本文件：直接读取（考虑之前读取的结果）
        try:
            reader = FileReaderTool(max_text_bytes=2000)
            full_raw = reader.read_full_by_path(file_path=file_path, filename=file_name)
            
            # 使用 LLM 总结内容（如果需要，包含之前读取的结果）
            if plan_detail and plan_detail.strip():
                summary_prompt = format_text_summary_prompt(
                    instruction=plan_detail,
                    file_content=full_raw,
                    previous_results=previous_results_str,
                    language=language,
                )
                summary_result = _run_llm(summary_prompt, temperature=0.1, max_tokens=4000, node_name="read_node_text_summary")
                result = summary_result
            else:
                # Fallback: 直接返回文件内容（带格式）
                file_label = _get_localized_message(
                    {
                        "zh": "文件",
                        "en": "File",
                    },
                    language,
                )
                path_label = _get_localized_message(
                    {
                        "zh": "路径",
                        "en": "Path",
                    },
                    language,
                )
                content_label = _get_localized_message(
                    {
                        "zh": "内容",
                        "en": "Content",
                    },
                    language,
                )
                text_content = f"{file_label}: {file_name}\n{path_label}: {file_path}\n{content_label}:\n{full_raw}"
                result = text_content
        except Exception as e:  # noqa: BLE001
            warning_msg = _get_localized_message(
                {
                    "zh": f"读取文件失败 {file_path}: {e}",
                    "en": f"Failed to read file {file_path}: {e}",
                },
                language,
            )
            logger.warning(warning_msg)
            error_result_msg = _get_localized_message(
                {
                    "zh": f"[错误] 读取文件失败: {str(e)}",
                    "en": f"[Error] Failed to read file: {str(e)}",
                },
                language,
            )
            result = error_result_msg
    
    # 更新结果
    history_plans[current_plan_index]["result"] = result

    # Check if result indicates an error (supports both Chinese and English error prefixes)
    is_error = result.startswith("[错误]") or result.startswith("[Error]")
    logger.info(
        "Read node completed",
        extra={
            "file_id": file_id,
            "file_name": file_name,
            "success": not is_error,
        },
    )

    message = get_agent_service().build_message(
        message=result,
    )
    
    return {
        "history_plans": history_plans,
        "current_plan_index": current_plan_index + 1,
        "message": message,
    }

def answer_node(state: ReadAgentState):
    """汇总所有计划结果，生成最终答案"""
    user_query = state["user_query"]
    history_plans = state.get("history_plans", [])
    language = state.get("language", "en")
    
    # 构建执行结果列表
    execution_results = []
    for plan in history_plans:
        result_str = plan.get("result", "")
        # Check if result indicates an error (supports both Chinese and English error prefixes)
        is_error = result_str.startswith("[错误]") or result_str.startswith("[Error]") if result_str else False
        execution_results.append({
            "file_id": plan.get("file_id", ""),
            "file_name": plan.get("file_name", ""),
            "file_path": plan.get("file_path", ""),
            "plan_detail": plan.get("plan_detail", ""),
            "result": result_str,
            "success": not is_error,
        })
    
    # 生成最终答案
    answer_prompt = format_answer_prompt(
        user_query=user_query,
        execution_results=execution_results,
        language=language,
    )
    response_text = _run_llm(answer_prompt, temperature=0.1, max_tokens=8000, node_name="answer_node")
    parsed = extract_json_from_response(response_text)
    final_answer = parsed.get("final_answer", "")
    
    if not final_answer:
        # Fallback: 简单汇总
        completion_msg = _get_localized_message(
            {
                "zh": "执行完成。\n\n",
                "en": "Execution completed.\n\n",
            },
            language,
        )
        success_status = _get_localized_message(
            {
                "zh": "成功",
                "en": "Success",
            },
            language,
        )
        failed_status = _get_localized_message(
            {
                "zh": "失败",
                "en": "Failed",
            },
            language,
        )
        file_prefix = _get_localized_message(
            {
                "zh": "- 文件",
                "en": "- File",
            },
            language,
        )
        final_answer = completion_msg
        for plan in history_plans:
            file_name = plan.get("file_name", "")
            file_id = plan.get("file_id", "")
            result = plan.get("result", "")
            is_error = result.startswith("[错误]") or result.startswith("[Error]") if result else False
            status = success_status if result and not is_error else failed_status
            final_answer += f"{file_prefix} [{file_id}]: {file_name} - {status}\n"
    
    message = get_agent_service().build_message(
        message=final_answer,
    )
    return {
        "final_answer": final_answer,
        "message": message,
    }