"""
Report Agent Prompts

用于生成结构化执行报告的提示词模板。
"""

from typing import Any


def build_report_generation_prompt(
    report_data: dict[str, Any],
    language: str = "zh",
) -> str:
    """
    构建生成结构化报告的提示词
    
    Args:
        report_data: 报告数据，包含：
            - user_query: 用户查询
            - total_executions: 总执行数
            - successful_count: 成功数
            - failed_count: 失败数
            - executions: 执行列表，每个包含：
                - execution_id: 执行ID
                - service_id: 服务ID
                - service_name: 服务名称
                - status: 状态
                - input_file_ids: 输入文件ID列表
                - output_file_ids: 输出文件ID列表
                - parameters: 参数
                - error_message: 错误信息（如果有）
                - analysis: 分析结果（成功的执行）
                - error: 错误原因（失败的执行）
        language: 语言（默认中文）
    
    Returns:
        提示词字符串
    """
    lang = language.lower() if language else "zh"
    
    if lang == "zh":
        prompt = f"""你是一个专业的执行分析和报告生成助手。请根据以下执行信息生成一份结构化的分析报告。

## 用户查询
{report_data.get("user_query", "")}

## 执行详情

"""
        
        for idx, execution in enumerate(report_data.get("executions", []), 1):
            service_name = execution.get("service_name", "未知服务")
            status = execution.get("status", "unknown")
            parameters = execution.get("parameters", {})
            analysis = execution.get("analysis")
            error = execution.get("error")
            error_message = execution.get("error_message", "")
            
            prompt += f"""### 执行 {idx}: {service_name}

**状态**: {status}

"""
            
            if status.lower() == "completed" and analysis:
                prompt += f"""**执行结果分析**:
{analysis}

"""
            elif error or error_message:
                failure_reason = error or error_message or "未知错误"
                prompt += f"""**失败原因**:
{failure_reason}

"""
        
        prompt += """## 报告要求

请生成一份结构化的分析报告，包含以下部分：

1. **执行过程概述**
   - 简要总结整个执行过程
   - 说明执行的主要步骤和目标

2. **总结报告**
   - 整体执行情况总结，回答用户问题

请使用清晰的结构和专业的语言生成报告。"""
    else:
        prompt = f"""You are a professional execution analysis and report generation assistant. Please generate a structured analysis report based on the following execution information.

## User Query
{report_data.get("user_query", "")}

## Execution Details

"""
        
        for idx, execution in enumerate(report_data.get("executions", []), 1):
            service_name = execution.get("service_name", "Unknown Service")
            status = execution.get("status", "unknown")
            analysis = execution.get("analysis")
            error = execution.get("error")
            error_message = execution.get("error_message", "")
            
            prompt += f"""### Execution {idx}: {service_name}

**Status**: {status}

"""
            
            if status.lower() == "completed" and analysis:
                prompt += f"""**Execution Result Analysis**:
{analysis}

"""
            elif error or error_message:
                failure_reason = error or error_message or "Unknown error"
                prompt += f"""**Failure Reason**:
{failure_reason}

"""
        
        prompt += """## Report Requirements

Please generate a structured analysis report with the following sections:

1. **Execution Process Overview**
   - Briefly summarize the entire execution process
   - Explain the main steps and objectives

2. **Summary Report**
   - Provide an overall execution summary that answers the user's question

Please use clear structure and professional language to generate the report."""
    
    return prompt

