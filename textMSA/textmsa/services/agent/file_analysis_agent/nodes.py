"""
File Analysis Agent 节点函数实现

实现所有节点函数：
- generate_sub_agent_info_node: 生成子Agent信息
- generate_and_execute_sub_agent_node: 生成并执行子Agent代码（合并节点，最多循环3次）
- return_result_node: 返回最终结果
"""

import os
from pathlib import Path

from textmsa.services.agent.agent_utils import (
    extract_json_from_response,
    get_llm_client_instance,
    get_python_repl_tool_instance,
    get_codegen_llm_client_instance,
)
from textmsa.services.agent.llm_client import LLMRequest

from .state import FileAnalysisAgentState
from .prompts import (
    format_generate_sub_agent_info_prompt,
    format_generate_sub_agent_code_prompt,
    format_return_result_prompt,
)




# ============================================================================
# 节点函数
# ============================================================================

def generate_sub_agent_info_node(state: FileAnalysisAgentState):
    """
    生成子Agent信息节点
    
    根据已读取的文件预览信息、用户查询，生成子Agent的信息。
    如果任务已完成或可以直接返回结果，则返回空集合。
    
    Args:
        state: File Analysis Agent 状态
    
    Returns:
        更新后的状态（包含路由决策字段 `route_decision`）
        路由决策：`"generate_code"` 或 `"return_result"`
    """
    user_query = state["user_query"]
    read_results = state["read_results"]
    work_dir_path = state["work_dir_path"]
    route_decision = state.get("route_decision")
    sub_agent_info = state.get("sub_agent_info")
    
    # 格式化 Prompt
    prompt = format_generate_sub_agent_info_prompt(
        user_query=user_query,
        read_results=read_results,
        work_dir_path=work_dir_path,
    )
    
    # 调用 LLM
    llm_client = get_llm_client_instance()
    request = LLMRequest(
        messages=[
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=8192,  # API限制最大值为8192
    )
    
    response = llm_client.chat(request)
    
    # 解析 JSON 响应
    parsed_data = extract_json_from_response(response.content)
    sub_agent_info = parsed_data.get("sub_agent_info")
    
    # 路由决策
    if sub_agent_info is None:
        route_decision = "return_result"
        return {
            "route_decision": route_decision,
        }
    else:
        route_decision = "generate_code"
        return {
            "sub_agent_info": sub_agent_info,
            "route_decision": route_decision,
        }


def generate_and_execute_sub_agent_node(state: FileAnalysisAgentState):
    """
    生成并执行子Agent代码节点（合并节点）
    
    根据子Agent prompt和期望输出，生成Python代码并执行，最多循环3次。
    参考 files_deep_read_agent 的 integrate_node 逻辑。
    
    Args:
        state: File Analysis Agent 状态
    
    Returns:
        更新后的状态（无论成功失败都会前往 return_result 节点）
    """
    sub_agent_info = state.get("sub_agent_info")
    read_results = state["read_results"]
    work_dir_path = state["work_dir_path"]
    sub_agent_execution_history = state.get("sub_agent_execution_history", [])
    sub_agent_code = state.get("sub_agent_code")
    sub_agent_feedback = state.get("sub_agent_feedback")
    generated_files_info = state.get("generated_files_info", [])
    sub_agent_info_execution_history = state.get("sub_agent_info_execution_history", [])
    
    # 确保工作目录存在
    work_dir = Path(work_dir_path)
    work_dir.mkdir(parents=True, exist_ok=True)
    
    # 获取代码生成和执行工具
    llm_client = get_codegen_llm_client_instance()
    python_repl_tool = get_python_repl_tool_instance()
    
    # 最多循环3次，参考 integrate_node 的逻辑
    max_attempts = 3
    generated_files = set()
    execution_success = False
    
    for attempt in range(max_attempts):
        # 记录执行前的文件列表
        files_before = set()
        if work_dir.exists():
            files_before = {f.name for f in work_dir.iterdir() if f.is_file()}
        
        # 1. 生成代码
        prompt = format_generate_sub_agent_code_prompt(
            sub_agent_info=sub_agent_info,
            read_results=read_results,
            sub_agent_execution_history=sub_agent_execution_history,
            work_dir_path=work_dir_path,
        )
        
        request = LLMRequest(
            messages=[
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=5000,
        )
        
        response = llm_client.chat(request)
    
        # 提取代码（去除代码块标记）
        generated_code = llm_client.extract_code_from_response(response)
        
        if not generated_code:
            # 继续下一次尝试
            continue
        
        # 更新代码
        sub_agent_code = generated_code

        
        # 2. 执行代码
        execution_result = python_repl_tool.run_code(code=generated_code)

        # 3. 检查生成的文件
        files_after = set()
        if work_dir.exists():
            files_after = {f.name for f in work_dir.iterdir() if f.is_file()}
        
        generated_files = files_after - files_before
        
        # 4. 判断是否成功
        if execution_result.success:
            execution_success = True
            # 如果生成了文件，提前退出循环
            if generated_files:
                break
            else:
                # 如果执行成功但未生成文件，继续尝试（最多3次）
                if attempt < max_attempts - 1:
                    continue
        else:
            # 执行失败：添加到执行历史
            error_reason = execution_result.stderr or "执行失败"
            sub_agent_execution_history.append({
                "error": error_reason,
            })
            # 继续下一次尝试
    
    # 处理最终结果
    if execution_success and generated_files:
        # 执行成功：清空执行历史
        sub_agent_execution_history = []
        
        # 生成反馈
        file_names = ", ".join(generated_files)
        sub_agent_feedback = f"按照预期生成文件: {file_names}"
        
        # 更新生成的文件信息
        expected_files = sub_agent_info.get("expected_files", []) if sub_agent_info else []
        
        for file_name in generated_files:
            # 从期望文件中查找描述
            description = f"由子Agent {sub_agent_info.get('name', '') if sub_agent_info else ''} 生成的文件"
            for expected_file in expected_files:
                if expected_file.get("file_name") == file_name:
                    description = expected_file.get("description", description)
                    break
            
            generated_files_info.append({
                "file_name": file_name,
                "description": description,
                "file_path": os.path.join(work_dir_path, file_name),
            })
        
        # 将子Agent信息和反馈添加到执行历史
        sub_agent_info_execution_history.append({
            "sub_agent_info": sub_agent_info,
            "feedback": sub_agent_feedback,
        })
        
    else:
        # 执行失败或未生成文件
        if execution_success:
            error_reason = "代码执行成功，但未检测到新生成的文件"
            sub_agent_feedback = error_reason
        else:
            error_reason = sub_agent_execution_history[-1].get("error", "执行失败") if sub_agent_execution_history else "执行失败"
            sub_agent_feedback = f"代码执行失败: {error_reason}"
    
    return {
        "sub_agent_code": sub_agent_code,
        "sub_agent_feedback": sub_agent_feedback,
        "generated_files_info": generated_files_info,
        "sub_agent_execution_history": sub_agent_execution_history,
        "sub_agent_info_execution_history": sub_agent_info_execution_history,
    }


def return_result_node(state: FileAnalysisAgentState):
    """
    返回结果节点
    
    根据执行历史和子Agent执行结果，生成最终分析报告。
    
    Args:
        state: File Analysis Agent 状态
    
    Returns:
        更新后的状态（包含 final_answer）
    """
    user_query = state["user_query"]
    sub_agent_info_execution_history = state.get("sub_agent_info_execution_history", [])
    generated_files_info = state.get("generated_files_info", [])
    read_results = state["read_results"]
    
    # 格式化 Prompt
    prompt = format_return_result_prompt(
        user_query=user_query,
        sub_agent_info_execution_history=sub_agent_info_execution_history,
        generated_files_info=generated_files_info,
        read_results=read_results,
    )
    
    # 调用 LLM
    llm_client = get_llm_client_instance()
    request = LLMRequest(
        messages=[
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=3000,
    )
    
    response = llm_client.chat(request)

    # 解析 JSON 响应
    parsed_data = extract_json_from_response(response.content)
    final_answer = parsed_data.get("final_answer", "")
    
    if not final_answer:
        final_answer = "无法生成最终分析报告"
    
    return {
        "final_answer": final_answer,
    }

