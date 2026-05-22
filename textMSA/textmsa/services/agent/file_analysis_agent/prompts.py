"""
File Read Agent Prompt 模板和格式化函数

定义所有 Prompt 模板字符串和格式化函数。
"""

import json
from typing import Any

from textmsa.logging_config import get_logger

logger = get_logger(__name__)


# ============================================================================
# Prompt 模板
# ============================================================================

GENERATE_SUB_AGENT_INFO_PROMPT = """
根据用户查询和已读取的文件预览信息，判断需要生成代码对于文件进行分析，如果需要则生成知道性代码的prompt和期望输出。

用户查询：{user_query}

已读取的文件预览信息：
文件名：{file_name}
预览内容：{preview}

如果需要生成子Agent，请生成以下信息：
1. 子Agent名称（一个描述性的名称，用于标识这个子Agent的任务，如 "数据清洗子Agent"、"统计分析子Agent" 等）
2. 任务描述（基于文件预览信息，调用这个子agent是希望其产生什么文件，以及这些文件应该包含什么内容）
3. **期望生成的文件列表**（**重要：必须明确列出期望生成的所有文件，包括每个文件的文件名和描述**）：
   - 文件名：应该生成的文件名（如 "cleaned_data.csv", "analysis_result.json" 等）
   - 描述：每个文件应该包含什么内容、用途是什么（如 "清洗后的数据，包含去重和缺失值处理后的结果"）
4. 子agent需要完成的任务重点是产生数据文件、图标文件等，而不是分析性的报告信息。

工作目录路径：{work_dir_path}

请以 JSON 格式返回：
- **如果需要生成子Agent**：
{{
  "sub_agent_info": {{
    "name": "子Agent名称",
    "prompt": "完整的子Agent prompt，包含任务描述、文件信息、期望输出等",
    "expected_output": "期望的输出结果描述（格式、内容、示例等，强调输出应该是文件）",
    "expected_files": [
      {{
        "file_name": "文件名（如 cleaned_data.csv）",
        "description": "文件描述（说明文件来源，包含什么内容、用途等）"
      }}
    ]
  }}
}}

- **如果不需要生成子Agent（任务已完成或可以直接返回结果）**：
{{
  "sub_agent_info": null
}}
"""


GENERATE_SUB_AGENT_CODE_PROMPT = """
根据子Agent信息和期望输出，生成Python代码。

子Agent信息：
{sub_agent_info}

期望输出：
{expected_output}

期望生成的文件列表：
{expected_files_string}

已读取的文件信息：
文件名：{file_name}
文件路径：{file_path}
预览内容：{preview}

过往代码执行历史（如果存在，包含之前的错误）：
{sub_agent_execution_history_string}

请生成Python代码，代码应该：
2. **将结果保存到文件（保存到 work_dir_path 目录下），而不是通过stdout返回**
3. **必须生成期望的文件列表中的所有文件，文件名和内容必须符合描述**
4. 输入文件可能不在工作目录中，读取数据时必须使用提供的 file_path（不要假设在 work_dir_path 下）

工作目录路径：{work_dir_path}

**重要代码规范（必须严格遵守）：**

   - **禁止画图**：代码生成过程中**绝对禁止**使用任何可视化库（如 matplotlib、seaborn、plotly 等）进行画图操作，**禁止**生成任何图表、图像文件或可视化输出。如果分析需要可视化，请使用 print() 输出数值结果、统计摘要等文本信息。
   - 生成代码不应该创建示例数据，而是直接读取实际的文件数据
   - 必须导入必要的库（如 `import sys` 用于 stderr 输出）
   - 代码必须将结果保存到文件，文件路径使用 file_path
   - 代码必须生成期望的文件列表中的所有文件，文件名必须与期望的文件名一致

**关键 - 错误处理规则：**
   - **绝对禁止**使用会静默吞掉异常而不重新抛出或打印详细错误信息的 try-except 代码块
   - 如果使用 try-except，你必须：
     (1) 在记录/打印后重新抛出异常，或者
     (2) 使用 `traceback.print_exc()` 或 `sys.stderr.write()` 将完整错误详情（包括堆栈跟踪）打印到 stderr
   - **不要**捕获异常后只打印简单错误信息而不包含完整堆栈跟踪
   - **不要**捕获异常后静默继续执行 - 这会使调试变得不可能
   - 如果需要错误处理，优先让异常自然传播，或使用能保留错误信息的正确错误处理方式

请直接返回Python代码字符串（不需要JSON格式，只需要代码本身）。
"""


RETURN_RESULT_PROMPT = """
根据用户查询和子Agent生成记录，判断任务是否完成。

用户查询：{user_query}

子Agent生成记录（包含子Agent的执行反馈）：
{sub_agent_info_execution_history_string}

已生成的文件信息：
{generated_files_info_string}
请生成最终分析报告：
1. 评估当前执行结果是否满足用户查询
2. 总结已生成的文件信息
3. 如果未完成向用户报告原因

请以 JSON 格式返回：
{{
  "final_answer": "最终分析报告（总结性的回答，包含生成的文件信息等）"
}}
"""


# ============================================================================
# 格式化函数
# ============================================================================

def format_sub_agent_info_execution_history(
    sub_agent_info_execution_history: list[dict],
) -> str:
    """
    格式化子Agent信息执行历史
    
    Args:
        sub_agent_info_execution_history: 子Agent信息执行历史列表
    
    Returns:
        格式化后的字符串
    """
    if not sub_agent_info_execution_history:
        return "无过往执行反馈"
    
    history_lines = []
    for idx, item in enumerate(sub_agent_info_execution_history, 1):
        sub_agent_info = item.get("sub_agent_info", {})
        feedback = item.get("feedback", "")
        
        history_lines.append(f"第 {idx} 次执行：")
        history_lines.append(f"  子Agent名称：{sub_agent_info.get('name', '未知')}")
        history_lines.append(f"  任务描述：{sub_agent_info.get('prompt', '')[:200]}...")
        history_lines.append(f"  执行反馈：{feedback}")
        history_lines.append("")
    
    return "\n".join(history_lines)


def format_sub_agent_execution_history(
    sub_agent_execution_history: list[dict],
) -> str:
    """
    格式化子Agent代码执行历史
    
    Args:
        sub_agent_execution_history: 子Agent代码执行历史列表
    
    Returns:
        格式化后的字符串
    """
    if not sub_agent_execution_history:
        return "无过往执行历史"
    
    history_lines = []
    for idx, item in enumerate(sub_agent_execution_history, 1):
        code = item.get("code", "")
        error = item.get("error")
        
        history_lines.append(f"第 {idx} 次执行：")
        history_lines.append(f"  代码：{code[:500]}...")
        if error:
            history_lines.append(f"  错误：{error}")
        history_lines.append("")
    
    return "\n".join(history_lines)


def format_expected_files(
    expected_files: list[dict],
) -> str:
    """
    格式化期望生成的文件列表
    
    Args:
        expected_files: 期望生成的文件列表
    
    Returns:
        格式化后的字符串
    """
    if not expected_files:
        return "无期望生成的文件"
    
    files_lines = []
    for idx, file_info in enumerate(expected_files, 1):
        file_name = file_info.get("file_name", "")
        description = file_info.get("description", "")
        files_lines.append(f"{idx}. 文件名：{file_name}")
        files_lines.append(f"   描述：{description}")
        files_lines.append("")
    
    return "\n".join(files_lines)


def format_generated_files_info(
    generated_files_info: list[dict],
) -> str:
    """
    格式化已生成的文件信息列表
    
    Args:
        generated_files_info: 已生成的文件信息列表
    
    Returns:
        格式化后的字符串
    """
    if not generated_files_info:
        return "无已生成的文件"
    
    files_lines = []
    for idx, file_info in enumerate(generated_files_info, 1):
        file_name = file_info.get("file_name", "")
        description = file_info.get("description", "")
        files_lines.append(f"{idx}. 文件名：{file_name}")
        files_lines.append(f"   描述：{description}")
        files_lines.append("")
    
    return "\n".join(files_lines)


def format_generate_sub_agent_info_prompt(
    user_query: str,
    read_results: dict,
    work_dir_path: str,
) -> str:
    """
    格式化生成子Agent信息的 Prompt
    
    Args:
        user_query: 用户查询
        read_results: 已读取的文件预览结果（单个元素）
        work_dir_path: 工作目录路径
    
    Returns:
        格式化后的 Prompt 字符串
    """
    
    # 格式化执行历史
    
    # 格式化预览内容
    preview = read_results.get("preview", "")
    if isinstance(preview, dict):
        preview = json.dumps(preview, ensure_ascii=False, indent=2)
    elif not isinstance(preview, str):
        preview = str(preview)
    
    prompt = GENERATE_SUB_AGENT_INFO_PROMPT.format(
        user_query=user_query,
        file_id=read_results.get("file_id", ""),
        file_name=read_results.get("file_name", ""),
        preview=preview,
        work_dir_path=work_dir_path,
    )
    
    logger.debug(
        "Generate_sub_agent_info prompt formatted",
        extra={"prompt_length": len(prompt)},
    )
    
    return prompt


def format_generate_sub_agent_code_prompt(
    sub_agent_info: dict,
    read_results: dict,
    sub_agent_execution_history: list[dict],
    work_dir_path: str,
) -> str:
    """
    格式化生成子Agent代码的 Prompt
    
    Args:
        sub_agent_info: 子Agent信息
        read_results: 已读取的文件预览结果（单个元素）
        sub_agent_execution_history: 子Agent代码执行历史
        work_dir_path: 工作目录路径
    
    Returns:
        格式化后的 Prompt 字符串
    """
    logger.debug(
        "Formatting generate_sub_agent_code prompt",
        extra={
            "sub_agent_name": sub_agent_info.get("name", ""),
            "file_id": read_results.get("file_id"),
            "file_name": read_results.get("file_name"),
            "work_dir_path": work_dir_path,
            "execution_history_length": len(sub_agent_execution_history),
        },
    )
    
    # 格式化子Agent信息
    sub_agent_info_string = json.dumps(sub_agent_info, ensure_ascii=False, indent=2)
    
    # 格式化期望文件列表
    expected_files = sub_agent_info.get("expected_files", [])
    expected_files_string = format_expected_files(expected_files)
    
    # 格式化执行历史
    execution_history_string = format_sub_agent_execution_history(sub_agent_execution_history)
    
    # 格式化预览内容
    preview = read_results.get("preview", "")
    if isinstance(preview, dict):
        preview = json.dumps(preview, ensure_ascii=False, indent=2)
    elif not isinstance(preview, str):
        preview = str(preview)
    
    prompt = GENERATE_SUB_AGENT_CODE_PROMPT.format(
        sub_agent_info=sub_agent_info_string,
        expected_output=sub_agent_info.get("expected_output", ""),
        expected_files_string=expected_files_string,
        file_path=read_results.get("file_path", ""),
        file_name=read_results.get("file_name", ""),
        preview=preview,
        sub_agent_execution_history_string=execution_history_string,
        work_dir_path=work_dir_path,
    )
    
    logger.debug(
        "Generate_sub_agent_code prompt formatted",
        extra={"prompt_length": len(prompt)},
    )
    
    return prompt


def format_return_result_prompt(
    user_query: str,
    sub_agent_info_execution_history: list[dict],
    generated_files_info: list[dict],
    read_results: dict,
) -> str:
    """
    格式化返回结果的 Prompt
    
    Args:
        user_query: 用户查询
        sub_agent_info_execution_history: 子Agent信息执行历史
        generated_files_info: 已生成的文件信息列表
        read_results: 已读取的文件预览结果（单个元素）
    
    Returns:
        格式化后的 Prompt 字符串
    """

    # 格式化执行历史
    history_string = format_sub_agent_info_execution_history(sub_agent_info_execution_history)
    
    # 格式化已生成的文件信息
    generated_files_string = format_generated_files_info(generated_files_info)
    
    # 格式化预览内容
    preview = read_results.get("preview", "")
    if isinstance(preview, dict):
        preview = json.dumps(preview, ensure_ascii=False, indent=2)
    elif not isinstance(preview, str):
        preview = str(preview)
    
    prompt = RETURN_RESULT_PROMPT.format(
        user_query=user_query,
        sub_agent_info_execution_history_string=history_string,
        generated_files_info_string=generated_files_string,
        file_id=read_results.get("file_id", ""),
        file_name=read_results.get("file_name", ""),
        preview=preview,
    )
    
    logger.debug(
        "Return_result prompt formatted",
        extra={"prompt_length": len(prompt)},
    )
    
    return prompt

