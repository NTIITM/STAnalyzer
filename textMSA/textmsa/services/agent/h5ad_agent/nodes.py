"""
H5AD Agent 节点函数实现

实现所有 5 个节点函数：
- parse_query_node: 解析用户查询
- generate_code_node: 生成 Python 代码
- execute_code_node: 执行代码
- check_result_node: 检查执行结果
- synthesize_result_node: 合成最终答案
"""

import time

from textmsa.logging_config import get_logger
from textmsa.services.agent.agent_utils import (
    extract_json_from_response,
    get_llm_client_instance,
    get_python_repl_tool_instance,
)
from textmsa.services.agent.llm_client import LLMRequest

from .state import H5ADAgentState
from .prompts import (
    format_query_parse_prompt,
    format_code_generation_prompt,
    format_result_synthesis_prompt,
)

logger = get_logger(__name__)


# ============================================================================
# 节点函数
# ============================================================================

def parse_query_node(state: H5ADAgentState) -> H5ADAgentState:
    """
    解析用户查询节点
    
    解析用户查询，提取查询意图和关键参数。
    
    Args:
        state: H5AD Agent 状态
    
    Returns:
        更新后的状态（包含 parsed_intent 和 parsed_params）
    """
    start_time = time.perf_counter()
    
    logger.info(
        "H5AD Agent - parse_query_node 开始",
        extra={
            "node": "parse_query",
            "user_query": state["user_query"],
            "user_query_length": len(state["user_query"]),
            "h5ad_file_path": state["h5ad_file_path"],
        },
    )
    
    # 格式化 Prompt
    prompt = format_query_parse_prompt(
        user_query=state["user_query"],
        h5ad_file_path=state["h5ad_file_path"],
        file_preview=state.get("file_preview"),
    )
    
    logger.debug(
        "H5AD Agent - parse_query_node Prompt 已格式化",
        extra={
            "node": "parse_query",
            "prompt_length": len(prompt),
        },
    )
    
    # 调用 LLM
    llm_client = get_llm_client_instance()
    request = LLMRequest(
        messages=[
            {
                "role": "system",
                "content": "你是一个 H5AD 数据分析专家，专门解析用户查询并提取关键信息。请严格按照 JSON 格式返回结果。",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=1000,
    )
    
    logger.info(
        "H5AD Agent - parse_query_node 调用 LLM",
        extra={"node": "parse_query"},
    )
    
    response = llm_client.chat(request)
    
    logger.info(
        "H5AD Agent - parse_query_node LLM 响应接收",
        extra={
            "node": "parse_query",
            "response_length": len(response.content),
        },
    )
    
    # 解析 JSON 响应
    parsed_data = extract_json_from_response(response.content)
    
    parsed_intent = parsed_data.get("intent", "")
    parsed_params = parsed_data.get("params", {})
    
    logger.info(
        "H5AD Agent - parse_query_node 解析完成",
        extra={
            "node": "parse_query",
            "parsed_intent": parsed_intent,
            "parsed_params_keys": list(parsed_params.keys()) if parsed_params else [],
        },
    )
    
    logger.debug(
        "H5AD Agent - parse_query_node 详细解析结果",
        extra={
            "node": "parse_query",
            "parsed_intent": parsed_intent,
            "parsed_params": parsed_params,
        },
    )
    
    # 更新状态
    state["parsed_intent"] = parsed_intent
    state["parsed_params"] = parsed_params
    
    elapsed_time = time.perf_counter() - start_time
    
    logger.info(
        "H5AD Agent - parse_query_node 完成",
        extra={
            "node": "parse_query",
            "elapsed_time": elapsed_time,
            "parsed_intent": parsed_intent,
        },
    )
    
    return state


def generate_code_node(state: H5ADAgentState) -> H5ADAgentState:
    """
    生成 Python 代码节点
    
    根据解析结果生成用于查询 H5AD 数据的 Python 代码。
    
    Args:
        state: H5AD Agent 状态
    
    Returns:
        更新后的状态（包含 generated_code 和递增的 execution_attempts）
    """
    start_time = time.perf_counter()
    
    execution_attempts = state.get("execution_attempts", 0)
    is_retry = execution_attempts > 0
    
    logger.info(
        "H5AD Agent - generate_code_node 开始",
        extra={
            "node": "generate_code",
            "parsed_intent": state.get("parsed_intent"),
            "parsed_params": state.get("parsed_params"),
            "h5ad_file_path": state["h5ad_file_path"],
            "execution_attempts": execution_attempts,
            "is_retry": is_retry,
        },
    )
    
    # 构建重试上下文（如果有）
    retry_context = ""
    if is_retry:
        last_error = state.get("error_message", "")
        last_stderr = ""
        if state.get("code_execution_result"):
            last_stderr = state["code_execution_result"].get("stderr", "")
        retry_context = f"上次执行错误：{last_error}\n上次执行 stderr：{last_stderr}"
        
        logger.info(
            "H5AD Agent - generate_code_node 重试模式",
            extra={
                "node": "generate_code",
                "retry_context": retry_context,
            },
        )
    
    # 格式化 Prompt
    prompt = format_code_generation_prompt(
        user_query=state["user_query"],
        parsed_intent=state.get("parsed_intent", ""),
        parsed_params=state.get("parsed_params", {}),
        h5ad_file_path=state["h5ad_file_path"],
        retry_context=retry_context,
        file_preview=state.get("file_preview"),
    )
    
    logger.debug(
        "H5AD Agent - generate_code_node Prompt 已格式化",
        extra={
            "node": "generate_code",
            "prompt_length": len(prompt),
        },
    )
    
    # 调用 LLM
    llm_client = get_llm_client_instance()
    request = LLMRequest(
        messages=[
            {
                "role": "system",
                "content": (
                    "你是一个 H5AD 数据查询专家，专门生成用于查询 AnnData 对象的 Python 代码。"
                    "请严格按照 JSON 格式返回代码，格式为：{\"code\": \"你的 Python 代码\"}。"
                    "只返回 JSON，不要其他内容。"
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=2000,
    )
    
    logger.info(
        "H5AD Agent - generate_code_node 调用 LLM",
        extra={"node": "generate_code"},
    )
    
    response = llm_client.chat(request)
    
    logger.info(
        "H5AD Agent - generate_code_node LLM 响应接收",
        extra={
            "node": "generate_code",
            "response_length": len(response.content),
        },
    )
    
    # 解析 JSON 响应，提取代码
    parsed_data = extract_json_from_response(response.content)
    generated_code = parsed_data.get("code", "")
    
    if not generated_code:
        logger.error(
            "H5AD Agent - generate_code_node 代码为空",
            extra={"node": "generate_code", "parsed_data": parsed_data},
        )
        state["error_message"] = "LLM 未生成有效代码"
        return state
    
    logger.info(
        "H5AD Agent - generate_code_node 代码生成完成",
        extra={
            "node": "generate_code",
            "code_length": len(generated_code),
            "code_preview": generated_code[:500],
        },
    )
    
    logger.debug(
        "H5AD Agent - generate_code_node 完整代码",
        extra={
            "node": "generate_code",
            "code": generated_code,
        },
    )
    
    # 更新状态
    state["generated_code"] = generated_code
    state["execution_attempts"] = execution_attempts + 1
    
    elapsed_time = time.perf_counter() - start_time
    
    logger.info(
        "H5AD Agent - generate_code_node 完成",
        extra={
            "node": "generate_code",
            "elapsed_time": elapsed_time,
            "code_length": len(generated_code),
            "execution_attempts": state["execution_attempts"],
        },
    )
    
    return state


def execute_code_node(state: H5ADAgentState) -> H5ADAgentState:
    """
    执行 Python 代码节点
    
    执行生成的 Python 代码，加载 H5AD 文件并执行查询。
    
    Args:
        state: H5AD Agent 状态
    
    Returns:
        更新后的状态（包含 code_execution_result 和 raw_result）
    """
    start_time = time.perf_counter()
    
    generated_code = state.get("generated_code", "")
    h5ad_file_path = state["h5ad_file_path"]
    
    logger.info(
        "H5AD Agent - execute_code_node 开始",
        extra={
            "node": "execute_code",
            "code_length": len(generated_code),
            "h5ad_file_path": h5ad_file_path,
            "code_preview": generated_code[:200] if generated_code else "",
        },
    )
    
    if not generated_code:
        logger.error(
            "H5AD Agent - execute_code_node 代码为空",
            extra={"node": "execute_code"},
        )
        state["error_message"] = "没有可执行的代码"
        state["code_execution_result"] = {
            "stdout": "",
            "stderr": "没有可执行的代码",
        }
        state["raw_result"] = ""
        return state
    
    # 构建完整的执行代码
    # 1. 导入必要库
    # 2. 加载 H5AD 文件
    # 3. 追加生成的代码
    full_code = f"""import anndata
import scanpy as sc
import numpy as np
import pandas as pd

# 加载 H5AD 文件
adata = anndata.read_h5ad('{h5ad_file_path}')

# 用户查询代码
{generated_code}
"""
    
    logger.debug(
        "H5AD Agent - execute_code_node 完整执行代码",
        extra={
            "node": "execute_code",
            "full_code": full_code,
        },
    )
    
    # 使用 PythonREPLTool 执行代码
    python_repl_tool = get_python_repl_tool_instance()
    
    logger.info(
        "H5AD Agent - execute_code_node 开始执行代码",
        extra={"node": "execute_code"},
    )
    
    execution_result = python_repl_tool.run_code(code=full_code)
    
    logger.info(
        "H5AD Agent - execute_code_node 代码执行完成",
        extra={
            "node": "execute_code",
            "success": execution_result.success,
            "execution_time": execution_result.execution_time,
            "stdout_length": len(execution_result.stdout),
            "stderr_length": len(execution_result.stderr),
        },
    )
    
    if execution_result.stdout:
        logger.info(
            "H5AD Agent - execute_code_node 标准输出",
            extra={
                "node": "execute_code",
                "stdout": execution_result.stdout,
            },
        )
    
    if execution_result.stderr:
        logger.warning(
            "H5AD Agent - execute_code_node 标准错误",
            extra={
                "node": "execute_code",
                "stderr": execution_result.stderr,
            },
        )
    
    # 更新状态
    state["code_execution_result"] = {
        "stdout": execution_result.stdout,
        "stderr": execution_result.stderr,
        "success": execution_result.success,  # 添加 success 字段
    }
    state["raw_result"] = execution_result.stdout
    
    if not execution_result.success:
        state["error_message"] = execution_result.stderr or "代码执行失败"
    
    elapsed_time = time.perf_counter() - start_time
    
    logger.info(
        "H5AD Agent - execute_code_node 完成",
        extra={
            "node": "execute_code",
            "elapsed_time": elapsed_time,
            "success": execution_result.success,
            "stdout_length": len(execution_result.stdout),
            "stderr_length": len(execution_result.stderr),
        },
    )
    
    return state


def check_result_node(state: H5ADAgentState) -> H5ADAgentState:
    """
    检查执行结果节点
    
    检查代码执行结果，决定是否需要重试或继续。
    
    Args:
        state: H5AD Agent 状态
    
    Returns:
        更新后的状态（包含 should_retry, is_complete, error_message）
    """
    start_time = time.perf_counter()
    
    execution_result = state.get("code_execution_result", {})
    execution_attempts = state.get("execution_attempts", 0)
    stderr = execution_result.get("stderr", "") if execution_result else ""
    stdout = execution_result.get("stdout", "") if execution_result else ""
    success = execution_result.get("success", True)  # 默认为 True 以保持向后兼容
    
    logger.info(
        "H5AD Agent - check_result_node 开始",
        extra={
            "node": "check_result",
            "execution_attempts": execution_attempts,
            "success": success,
            "has_stderr": bool(stderr),
            "has_stdout": bool(stdout),
            "stderr_length": len(stderr),
            "stdout_length": len(stdout),
        },
    )
    
    # 检查是否有错误（多种方式）
    # 1. 检查 success 字段（最可靠）
    has_success_error = not success
    
    # 2. 检查 stderr 是否有内容
    has_stderr_error = bool(stderr and stderr.strip())
    
    # 3. 检查 stdout 中是否包含错误关键词（可能代码打印了错误信息到 stdout）
    error_keywords = [
        "Error", "Exception", "Traceback", "错误", "异常",
        "NameError", "TypeError", "ValueError", "AttributeError",
        "KeyError", "IndexError", "FileNotFoundError",
    ]
    stdout_has_error = False
    if stdout:
        stdout_lower = stdout.lower()
        for keyword in error_keywords:
            if keyword.lower() in stdout_lower:
                stdout_has_error = True
                logger.warning(
                    "H5AD Agent - check_result_node 在 stdout 中发现错误关键词",
                    extra={
                        "node": "check_result",
                        "keyword": keyword,
                        "stdout_preview": stdout[:500],
                    },
                )
                break
    
    # 4. 检查 stdout 是否为空（如果应该产生输出但没有输出，可能是错误）
    # 注意：某些查询可能确实没有输出，所以这个检查要谨慎
    # 这里我们只作为辅助判断，不单独作为错误条件
    
    # 综合判断：如果有任何错误迹象，则认为有错误
    has_error = has_success_error or has_stderr_error or stdout_has_error
    
    # 检查是否超过最大重试次数
    max_attempts = 3
    can_retry = execution_attempts < max_attempts
    
    # 决定下一步
    if not has_error:
        # 执行成功
        logger.info(
            "H5AD Agent - check_result_node 执行成功",
            extra={
                "node": "check_result",
                "stdout_length": len(stdout),
            },
        )
        state["should_retry"] = False
        state["is_complete"] = True
        state["error_message"] = None
    elif can_retry:
        # 执行失败但可以重试
        error_details = []
        if has_success_error:
            error_details.append("execution_result.success=False")
        if has_stderr_error:
            error_details.append(f"stderr: {stderr[:200]}")
        if stdout_has_error:
            error_details.append("stdout contains error keywords")
        
        error_summary = "; ".join(error_details)
        
        logger.warning(
            "H5AD Agent - check_result_node 执行失败，将重试",
            extra={
                "node": "check_result",
                "execution_attempts": execution_attempts,
                "max_attempts": max_attempts,
                "error_summary": error_summary,
                "stderr": stderr[:500] if stderr else "",
                "stdout_preview": stdout[:500] if stdout else "",
            },
        )
        state["should_retry"] = True
        state["is_complete"] = False
        # 组合错误信息
        error_message = stderr if stderr else "代码执行失败"
        if stdout_has_error:
            error_message += f"\n输出中包含错误信息: {stdout[:500]}"
        state["error_message"] = error_message
    else:
        # 执行失败且超过重试次数
        error_details = []
        if has_success_error:
            error_details.append("execution_result.success=False")
        if has_stderr_error:
            error_details.append(f"stderr: {stderr[:200]}")
        if stdout_has_error:
            error_details.append("stdout contains error keywords")
        
        error_summary = "; ".join(error_details)
        
        logger.error(
            "H5AD Agent - check_result_node 执行失败且超过重试次数",
            extra={
                "node": "check_result",
                "execution_attempts": execution_attempts,
                "max_attempts": max_attempts,
                "error_summary": error_summary,
                "stderr": stderr[:500] if stderr else "",
                "stdout_preview": stdout[:500] if stdout else "",
            },
        )
        state["should_retry"] = False
        state["is_complete"] = True
        # 组合错误信息
        error_message = f"代码执行失败，已重试 {execution_attempts} 次。"
        if stderr:
            error_message += f"\n错误信息：{stderr}"
        if stdout_has_error:
            error_message += f"\n输出中的错误：{stdout[:500]}"
        state["error_message"] = error_message
    
    elapsed_time = time.perf_counter() - start_time
    
    logger.info(
        "H5AD Agent - check_result_node 完成",
        extra={
            "node": "check_result",
            "elapsed_time": elapsed_time,
            "should_retry": state.get("should_retry"),
            "is_complete": state.get("is_complete"),
            "has_error": has_error,
            "has_success_error": has_success_error,
            "has_stderr_error": has_stderr_error,
            "stdout_has_error": stdout_has_error,
        },
    )
    
    return state


def synthesize_result_node(state: H5ADAgentState) -> H5ADAgentState:
    """
    合成最终答案节点
    
    将代码执行结果转化为清晰、结构化的答案。
    
    Args:
        state: H5AD Agent 状态
    
    Returns:
        更新后的状态（包含 structured_result, final_answer, is_complete=True）
    """
    start_time = time.perf_counter()
    
    raw_result = state.get("raw_result", "")
    user_query = state["user_query"]
    parsed_intent = state.get("parsed_intent", "")
    
    logger.info(
        "H5AD Agent - synthesize_result_node 开始",
        extra={
            "node": "synthesize_result",
            "user_query": user_query,
            "parsed_intent": parsed_intent,
            "raw_result_length": len(raw_result),
            "raw_result_preview": raw_result[:500] if raw_result else "",
        },
    )
    
    if not raw_result:
        logger.warning(
            "H5AD Agent - synthesize_result_node 原始结果为空",
            extra={"node": "synthesize_result"},
        )
        state["final_answer"] = "执行完成，但未产生输出结果。"
        state["structured_result"] = {}
        state["is_complete"] = True
        return state
    
    # 格式化 Prompt
    prompt = format_result_synthesis_prompt(
        user_query=user_query,
        parsed_intent=parsed_intent,
        raw_result=raw_result,
    )
    
    logger.debug(
        "H5AD Agent - synthesize_result_node Prompt 已格式化",
        extra={
            "node": "synthesize_result",
            "prompt_length": len(prompt),
        },
    )
    
    # 调用 LLM
    llm_client = get_llm_client_instance()
    request = LLMRequest(
        messages=[
            {
                "role": "system",
                "content": (
                    "你是一个数据分析结果总结专家，专门将代码执行结果转化为清晰、结构化的答案。"
                    "请严格按照 JSON 格式返回结果，格式为："
                    '{"summary": "简洁的文字总结", "structured_data": {...}, "formatted_answer": "格式化后的完整答案（Markdown 格式）"}。'
                    "只返回 JSON，不要其他内容。"
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=2000,
    )
    
    logger.info(
        "H5AD Agent - synthesize_result_node 调用 LLM",
        extra={"node": "synthesize_result"},
    )
    
    response = llm_client.chat(request)
    
    logger.info(
        "H5AD Agent - synthesize_result_node LLM 响应接收",
        extra={
            "node": "synthesize_result",
            "response_length": len(response.content),
        },
    )
    
    # 解析 JSON 响应
    parsed_data = extract_json_from_response(response.content)
    
    summary = parsed_data.get("summary", "")
    structured_data = parsed_data.get("structured_data", {})
    formatted_answer = parsed_data.get("formatted_answer", summary)
    
    logger.info(
        "H5AD Agent - synthesize_result_node 结果解析完成",
        extra={
            "node": "synthesize_result",
            "summary_length": len(summary),
            "formatted_answer_length": len(formatted_answer),
            "has_structured_data": bool(structured_data),
        },
    )
    
    logger.debug(
        "H5AD Agent - synthesize_result_node 详细结果",
        extra={
            "node": "synthesize_result",
            "summary": summary,
            "structured_data": structured_data,
            "formatted_answer": formatted_answer,
        },
    )
    
    # 更新状态
    state["structured_result"] = {
        "summary": summary,
        "structured_data": structured_data,
    }
    state["final_answer"] = formatted_answer
    state["is_complete"] = True
    
    elapsed_time = time.perf_counter() - start_time
    
    logger.info(
        "H5AD Agent - synthesize_result_node 完成",
        extra={
            "node": "synthesize_result",
            "elapsed_time": elapsed_time,
            "final_answer_length": len(formatted_answer),
        },
    )
    
    return state

