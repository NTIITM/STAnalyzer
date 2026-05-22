"""Prompts for knowledge search query rewriting/extraction."""
from __future__ import annotations

from typing import List, Dict, Optional


def get_project_info(project_id: str) -> Optional[Dict[str, str]]:
    """
    获取项目信息（暂时只留接口，后续实现）。
    
    Args:
        project_id: 项目ID
        
    Returns:
        项目信息字典，包含 name 和 description 字段，如果不存在则返回 None
    """
    # TODO: 后续实现从数据库获取项目信息
    # from textmsa.services.project.project_service import get_project_service
    # project_service = get_project_service()
    # project_dict = project_service.get_project(project_id, user_id)
    # if project_dict:
    #     return {
    #         "name": project_dict.get("name", ""),
    #         "description": project_dict.get("description", ""),
    #     }
    return None


def build_rewrite_messages(
    query: str,
    project_id: str,
    datasources: List[str],
    language: str = "zh",
) -> List[Dict[str, str]]:
    """
    构建查询重写的消息列表。
    
    Args:
        query: 用户查询语句
        project_id: 项目ID
        datasources: 数据源列表，如 ["pubmed", "arxiv", "crossref"]
        language: 语言，目前支持 "zh"，后续计划支持 "en"
        
    Returns:
        消息列表
    """
    # 获取项目信息
    project_info = get_project_info(project_id)
    project_description = project_info.get("description", "") if project_info else ""
    project_name = project_info.get("name", "") if project_info else ""
    
    # 根据语言选择提示词
    if language == "zh":
        system_prompt = (
            "你是科研文献检索助手。"
            "请根据用户查询和项目背景信息，提取关键词并联想相关实体，为每个数据源生成适合的查询语句。"
            "\n\n严格输出要求："
            "1) 只能返回 JSON 对象（不要 markdown 代码块、前后缀、解释）。"
            "2) 键仅限于当前请求的数据源列表；未包含的数据源不要返回。"
            "3) 每个值是一条可直接用于该数据源的查询语句。"
            "4) 如用户提供 DOI/URL/英文查询，保持原样放入对应数据源。"
            "\n\n示例："
            '{"pubmed": "PDCD1[Title/Abstract] AND tumor microenvironment", "arxiv": "PD-1 T cell exhaustion", "crossref": "PDCD1 tumor microenvironment"}'
            "\n\n只返回 JSON 对象本身。"
        )
        
        user_content_parts = [f"用户查询：{query}"]
        if project_name:
            user_content_parts.append(f"项目名称：{project_name}")
        if project_description:
            user_content_parts.append(f"项目描述：{project_description}")
        else:
            user_content_parts.append("项目描述：无")
        user_content_parts.append(f"需要生成查询的数据源：{', '.join(datasources)}")
        
        user_content = "\n".join(user_content_parts)
    else:
        # 英文提示词（后续实现）
        system_prompt = (
            "You are a research literature search assistant. "
            "Please extract keywords and related entities from the user query and project background, "
            "then generate optimized query statements for each datasource."
            "\n\nStrict output requirements:"
            "1) Only return a JSON object (no markdown fences, no prefix/suffix, no explanation). The word 'json' must appear in your response rules."
            "2) Keys must be limited to the requested datasources only; do not include others."
            "3) Each value is a directly usable query string for that datasource."
            "4) If the user provides DOI/URL/English query, keep it as-is in the corresponding datasource."
            "\n\nExample:"
            '{"pubmed": "PDCD1[Title/Abstract] AND tumor microenvironment", "arxiv": "PD-1 T cell exhaustion", "crossref": "PDCD1 tumor microenvironment"}'
            "\n\nReturn the JSON object only."
        )
        user_content = (
            f"User query: {query}\n"
            f"Datasources: {', '.join(datasources)}\n"
            "Return strictly as json object only (no markdown)."
        )
    
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

