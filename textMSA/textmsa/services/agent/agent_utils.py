"""
Agent 共用工具函数

提供所有 Agent 节点共用的工具函数：
- get_llm_client: 获取 LLMClient 实例（单例）
- get_python_repl_tool: 获取 PythonREPLTool 实例（单例）
- extract_json_from_response: 从 LLM 响应中提取 JSON 对象
- format_file_tree: 将文件树结构格式化为便于展示的文本
"""

import json
import re
from typing import Any

from textmsa.logging_config import get_logger
from textmsa.services.agent.llm_client import LLMClient, get_llm_client
from textmsa.services.agent.tools.python_repl_tool import PythonREPLTool
from textmsa.services.file.file_service import get_file_service
from textmsa.settings import (
    get_codegen_llm_config,
    get_multimodal_llm_config,
)

logger = get_logger(__name__)

# 文件树格式化语言配置
LANG_CONFIG = {
    "zh": {
        "unknown": "unknown",
        "desc_label": "描述",
        "ellipsis": "...",
    },
    "en": {
        "unknown": "unknown",
        "desc_label": "Description",
        "ellipsis": "...",
    },
}

# 全局 LLMClient 和 PythonREPLTool 实例（延迟初始化）
_llm_client: LLMClient | None = None
_codegen_llm_client: LLMClient | None = None
_multimodal_llm_client: LLMClient | None = None
_python_repl_tool: PythonREPLTool | None = None


def get_llm_client_instance() -> LLMClient:
    """获取 LLMClient 实例（单例）"""
    global _llm_client
    if _llm_client is None:
        logger.info("Initializing LLMClient")
        _llm_client = get_llm_client()
        logger.info("LLMClient initialized")
    return _llm_client


def get_codegen_llm_client_instance() -> LLMClient:
    """获取代码生成专用的 LLMClient（单例，使用 codegen_llm 配置）"""
    global _codegen_llm_client
    if _codegen_llm_client is None:
        logger.info("Initializing codegen LLMClient")
        _codegen_llm_client = LLMClient(config=get_codegen_llm_config())
        logger.info("Codegen LLMClient initialized")
    return _codegen_llm_client


def get_multimodal_llm_client_instance() -> LLMClient:
    """获取多模态专用的 LLMClient（单例，使用 multimodal_llm 配置）"""
    global _multimodal_llm_client
    if _multimodal_llm_client is None:
        logger.info("Initializing multimodal LLMClient")
        _multimodal_llm_client = LLMClient(config=get_multimodal_llm_config())
        logger.info("Multimodal LLMClient initialized")
    return _multimodal_llm_client


def get_python_repl_tool_instance() -> PythonREPLTool:
    """获取 PythonREPLTool 实例（单例）"""
    global _python_repl_tool
    if _python_repl_tool is None:
        logger.info("Initializing PythonREPLTool")
        _python_repl_tool = PythonREPLTool(llm_client=None)  # 不需要 LLM，只用于执行代码
        logger.info("PythonREPLTool initialized")
    return _python_repl_tool


def extract_json_from_response(response: str) -> dict[str, Any]:
    """
    从 LLM 响应中提取 JSON 对象
    
    Args:
        response: LLM 响应文本
    
    Returns:
        解析后的 JSON 字典
    
    Raises:
        ValueError: 如果无法提取有效的 JSON
    """
    if not response:
        raise ValueError("响应为空")
    
    # 清理响应
    text = response.strip()
    
    # 移除 markdown 代码块标记
    text = re.sub(r'^```json\s*\n', '', text, flags=re.MULTILINE)
    text = re.sub(r'^```\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'```\s*$', '', text, flags=re.MULTILINE)
    text = text.strip()
    
    def remove_json_comments(json_str: str) -> str:
        """
        移除 JSON 字符串中的注释（支持 // 和 /* */）
        
        Args:
            json_str: 可能包含注释的 JSON 字符串
        
        Returns:
            移除注释后的 JSON 字符串
        """
        # 移除多行注释 /* ... */
        json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
        
        # 移除单行注释 // ...（但要注意字符串中的 // 不应该被移除）
        # 逐行处理，对于每一行，找到不在字符串中的 // 并移除后面的内容
        lines = []
        for line in json_str.split('\n'):
            cleaned_line = []
            in_string = False
            escape_next = False
            i = 0
            
            while i < len(line):
                char = line[i]
                
                if escape_next:
                    cleaned_line.append(char)
                    escape_next = False
                    i += 1
                    continue
                
                if char == '\\':
                    escape_next = True
                    cleaned_line.append(char)
                    i += 1
                    continue
                
                if char == '"':
                    in_string = not in_string
                    cleaned_line.append(char)
                    i += 1
                    continue
                
                # 如果不在字符串中，检查是否是注释
                if not in_string and i < len(line) - 1 and line[i:i+2] == '//':
                    # 找到注释开始，跳过这一行的剩余部分
                    break
                
                cleaned_line.append(char)
                i += 1
            
            cleaned_line_str = ''.join(cleaned_line).rstrip()
            if cleaned_line_str:  # 只添加非空行
                lines.append(cleaned_line_str)
        
        return '\n'.join(lines)
    
    # 尝试解析完整的 JSON 对象（先移除注释）
    try:
        cleaned_text = remove_json_comments(text)
        data = json.loads(cleaned_text)
        if isinstance(data, dict):
            logger.debug("Extracted JSON from full response")
            return data
    except json.JSONDecodeError:
        pass
    
    # 尝试提取 JSON 对象（可能包含在其他文本中）
    brace_count = 0
    start_idx = -1
    for i, char in enumerate(text):
        if char == '{':
            if start_idx == -1:
                start_idx = i
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0 and start_idx != -1:
                json_str = text[start_idx:i+1]
                try:
                    # 移除注释后再解析
                    cleaned_json_str = remove_json_comments(json_str)
                    data = json.loads(cleaned_json_str)
                    if isinstance(data, dict):
                        logger.debug("Extracted JSON from pattern match")
                        return data
                except json.JSONDecodeError:
                    pass
                start_idx = -1
    
    # 如果无法提取，抛出异常
    logger.error(
        "Failed to extract JSON from response",
        extra={"response_preview": text[:500]},
    )
    raise ValueError(f"无法从响应中提取有效的 JSON。响应预览: {text[:500]}")


def format_file_tree(
    files_tree_list: list[dict[str, Any]],
    language: str = "zh",
) -> str:
    """
    将文件树结构「拍平」并格式化为带 parent_file_id 的文件列表字符串，支持中英文。

    Args:
        files_tree_list: 文件树列表，每个节点可能有 children 字段
        language: 语言，支持 "zh" 或 "en"
    
    Returns:
        扁平化后的文件列表字符串
    """
    lang = "en" if str(language).lower().startswith("en") else "zh"
    config = LANG_CONFIG.get(lang, LANG_CONFIG["zh"])
    lines: list[str] = []

    desc_label = config["desc_label"]
    ellipsis = config["ellipsis"]

    def traverse(node: dict[str, Any], parent_id: str | None = None) -> None:
        """递归拍平节点，输出文件列表行"""
        filename = node.get("file_name") or config["unknown"]
        file_type = node.get("file_type_id") or config["unknown"]
        description = node.get("description") or ""
        file_path = node.get("file_path") or ""
        file_id = node.get("file_id") or ""
        parent_file_id = parent_id or ""

        # 主行：文件名 + 类型 + file_id + parent_file_id + 路径
        line = f"- {filename} [{file_type}]"
        if file_id or parent_file_id:
            parent_display = parent_file_id or "-"
            line += f" (file_id: {file_id or '-'}, parent_file_id: {parent_display})"
        if file_path:
            line += f" - {file_path}"
        lines.append(line)

        # 描述行（可选）
        if description:
            desc_text = (
                description[:180] + ellipsis if len(description) > 180 else description
            )
            lines.append(f"    {desc_label}: {desc_text}")

        # 递归子节点
        children = node.get("children") or []
        for child in children:
            traverse(child, file_id or parent_file_id)

    for root_node in files_tree_list:
        traverse(root_node, None)

    return "\n".join(lines)


def get_context_files_tree_list(
    user_id: str,
    project_id: str,
    context_file_ids: list[str] | None = None,
    recursive: bool = True,
    phase: str | None = None,
) -> list[dict[str, Any]]:
    """
    根据 context_file_ids 获取项目文件树列表的通用工具函数。

    Args:
        user_id: 用户 ID
        project_id: 项目 ID
        context_file_ids: 上下文文件 ID 列表
        recursive: 是否递归获取子节点
        phase: 日志中标注的阶段名称（例如 "answer"），可选

    Returns:
        文件树列表（获取失败时返回空列表）
    """
    if not user_id or not project_id:
        return []

    try:
        file_service = get_file_service()
        files_tree_list = file_service.get_project_files_tree_list(
            project_id=project_id,
            user_id=user_id,
            context_files=context_file_ids or None,
            recursive=recursive,
        )
        return files_tree_list or []
    except Exception as e:
        # 保持与原有日志尽量一致的文案
        if phase == "answer":
            msg = "获取项目文件树失败（answer 阶段），使用空列表"
        else:
            msg = "获取项目文件树失败，使用空列表"
        logger.warning(
            msg,
            extra={
                "user_id": user_id,
                "project_id": project_id,
                "context_file_ids": context_file_ids,
                "error": str(e),
            },
        )
        return []

