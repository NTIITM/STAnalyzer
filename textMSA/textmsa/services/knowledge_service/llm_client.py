"""Thin wrappers over the shared LLM client."""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional, Tuple

from textmsa.services.agent.langgraph.subgraphs.utils import parse_json_from_llm_response
from textmsa.services.agent.llm_client import LLMRequest, LLMResponse, get_llm_client
from textmsa.services.knowledge_service.prompts import build_rewrite_messages


async def rewrite_query_with_llm(
    query: str,
    project_id: str,
    datasources: List[str],
    *,
    language: str = "zh",
    llm_client=None,
    temperature: float = 0.2,
) -> Tuple[Dict[str, str], Dict[str, Any]]:
    """
    使用LLM为每个数据源重写查询语句。
    
    Args:
        query: 用户查询语句
        project_id: 项目ID
        datasources: 数据源列表
        language: 语言，目前支持 "zh"，后续计划支持 "en"
        llm_client: LLM客户端，如果为None则使用默认客户端
        temperature: 温度参数
        
    Returns:
        (queries_dict, usage_info) 元组
        queries_dict: 字典，键为数据源名称，值为重写后的查询语句
        usage_info: 使用情况信息
    """
    client = llm_client or get_llm_client()
    messages = build_rewrite_messages(query, project_id, datasources, language)
    # 通过 response_format 请求模型严格返回 JSON 对象，减少 markdown 包装
    request = LLMRequest(
        messages=messages,
        temperature=temperature,
        response_format={"type": "json_object"},
    )

    def _call() -> LLMResponse:
        return client.chat(request)

    response = await asyncio.to_thread(_call)
    content = (response.content or "").strip()
    
    # 解析JSON响应（优先使用严格 JSON，其次容错解析 markdown 代码块）
    queries_dict: Dict[str, str] = {}
    parsed = parse_json_from_llm_response(content, default={})
    if isinstance(parsed, dict):
        for source in datasources:
            if source in parsed:
                queries_dict[source] = str(parsed[source]).strip()
    else:
        parsed = {}
    
    # 确保所有数据源都有查询语句
    for source in datasources:
        if source not in queries_dict or not queries_dict[source]:
            queries_dict[source] = query
    
    usage = {
        "model": response.model,
        "llm_usage": response.usage,
    }
    return queries_dict, usage
