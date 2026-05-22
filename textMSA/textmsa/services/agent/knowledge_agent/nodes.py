"""
Knowledge Agent 节点实现
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any

import requests
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from textmsa.logging_config import get_logger
from textmsa.services.agent.agent_service import get_agent_service
from textmsa.services.agent.agent_utils import extract_json_from_response
from textmsa.services.knowledge_service import get_knowledge_search_service
from textmsa.settings import get_llm_config, get_gene_relation_api_config

from .prompts import (
    format_intent_prompt,
    format_answer_prompt,
    format_plan_prompt,
    format_read_prompt,
)
from .state import KnowledgeAgentState, ReadingPlan

logger = get_logger(__name__)

# ----------------------------------------------------------------------------- #
# LLM helpers
# ----------------------------------------------------------------------------- #


@lru_cache(maxsize=1)
def _base_llm_config() -> dict[str, Any]:
    return dict(get_llm_config())


def _build_chat_llm(*, temperature: float, max_tokens: int) -> ChatOpenAI:
    """Create a ChatOpenAI instance with config overrides."""
    base_config = _base_llm_config()
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


def _run_llm(prompt: str, *, temperature: float, max_tokens: int, node_name: str = "unknown") -> str:
    """Execute a single-turn LLM call and return the text content."""
    base_config = _base_llm_config()
    model_name = base_config.get("model", "unknown")
    
    # 记录输入
    logger.info(
        f"[LLM Input] Node: {node_name} | Model: {model_name}",
        extra={
            "node": node_name,
            "model": model_name,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "prompt_length": len(prompt),
            "prompt_preview": prompt[:500] + "..." if len(prompt) > 500 else prompt,
        },
    )
    logger.info(f"[LLM Input Full] Node: {node_name}\n{prompt}")
    
    llm = _build_chat_llm(temperature=temperature, max_tokens=max_tokens)
    response = llm.invoke([HumanMessage(content=prompt)])
    response_content = getattr(response, "content", "") or ""
    
    # 记录输出
    logger.info(
        f"[LLM Output] Node: {node_name} | Model: {model_name}",
    )
    logger.info(f"[LLM Output Full] Node: {node_name}\n{response_content}")
    
    return response_content


# ----------------------------------------------------------------------------- #
# nodes
# ----------------------------------------------------------------------------- #


def intent_node(state: KnowledgeAgentState):
    """意图识别节点：识别用户意图，并生成用于检索的重写查询"""
    user_query = state["user_query"]
    language = state.get("language", "zh")
    
    intent_prompt = format_intent_prompt(
        user_query=user_query,
        language=language,
    )
    response_text = _run_llm(intent_prompt, temperature=0, max_tokens=2000, node_name="intent_node")
    parsed = extract_json_from_response(response_text)
    # 兼容不同返回结构，优先 intent 字段，其次直接解析 JSON 根
    intent_payload = parsed.get("intent") or parsed or {}
    rewritten_query = intent_payload.get("rewritten_query") or user_query
    intent_summary = intent_payload.get("intent_summary") or ""
    
    logger.info(
        "Intent node completed " + intent_summary + " " + rewritten_query
    )
    
    message = get_agent_service().build_message(
        message="识别到检索意图：" if language.startswith("zh") else "Search intent identified: " + intent_summary,
    )
    
    return {
        "search_query": rewritten_query,
        "message": message,
    }

# TODO：代码逻辑待优化
def gene_relation_node(state: KnowledgeAgentState):
    """基因关系查询节点：调用基因关系API进行查询"""
    try:
        # 获取配置
        api_config = get_gene_relation_api_config()
        
        # 检查是否启用
        if not api_config.get("enabled", True):
            logger.info("Gene relation API is disabled, skipping")
            return {}
        
        base_url = api_config.get("base_url", "http://localhost:8001")
        timeout_seconds = api_config.get("timeout_seconds", 300)
        connect_timeout_seconds = api_config.get("connect_timeout_seconds", 5)
        
        # 健康检查：ping /health 端点
        health_url = f"{base_url}/health"
        try:
            logger.info(f"Checking gene relation API health at {health_url}")
            health_response = requests.get(
                health_url,
                timeout=connect_timeout_seconds
            )
            if health_response.status_code != 200:
                logger.warning(
                    f"Gene relation API health check failed with status {health_response.status_code}, skipping"
                )
                return {}
        except requests.exceptions.RequestException as e:
            logger.warning(
                f"Gene relation API health check failed: {e}, skipping",
                exc_info=True
            )
            return {}
        
        # API 可用，进行查询
        user_query = state["user_query"]
        question_url = f"{base_url}/api/question"
        
        logger.info(f"Querying gene relation API: {user_query[:100]}...")
        
        try:
            response = requests.post(
                question_url,
                json={
                    "question": user_query,
                    "include_trace": False
                },
                timeout=timeout_seconds
            )
            response.raise_for_status()
            
            result_data = response.json()
            if result_data.get("success") and result_data.get("answer"):
                answer = result_data.get("answer", "")
                logger.info(f"Gene relation API query successful, answer length: {len(answer)}")
                
                # 构建 message 并返回
                message = get_agent_service().build_message(
                    message=answer
                )
                
                logger.info(
                    f"Gene relation node returning message to frontend | "
                    f"message_text={answer} | "
                )
                
                return {
                    "gene_relation_result": answer,
                    "message": message,
                }
            else:
                logger.warning(f"Gene relation API returned unsuccessful result: {result_data}")
                return {}
                
        except requests.exceptions.RequestException as e:
            logger.warning(
                f"Gene relation API query failed: {e}, continuing without result",
                exc_info=True
            )
            return {}
            
    except Exception as e:
        logger.error(
            f"Unexpected error in gene_relation_node: {e}, continuing without result",
            exc_info=True
        )
        return {}


def search_node(state: KnowledgeAgentState):
    """搜索文献节点：在意图识别后调用知识搜索服务，过滤掉没有 snippet 的文献"""
    user_query = state["user_query"]
    # 优先使用意图节点生成的 search_query，否则回退到原始 user_query
    search_query = state.get("search_query") or user_query
    project_id = state["project_id"]
    language = state.get("language", "zh")
    
    knowledge_service = get_knowledge_search_service()
    
    # 调用知识搜索服务，获取文献（异步调用）
    # 在同步节点中调用异步函数，使用 asyncio.run() 创建新的事件循环
    search_result = asyncio.run(
        knowledge_service.run(
            query=search_query,
            project_id=project_id,
            top_k=50,
            rewrite=True,
            # sources=["pubmed"],
            language=language,
            trace=False,
        )
    )
    
    # 过滤掉没有 snippet 或 snippet 为空的文档
    filtered_documents = [
        doc for doc in search_result.documents
        if doc.snippet and doc.snippet.strip()
    ]
    
    # 更新 search_result 的 documents
    search_result.documents = filtered_documents
    
    logger.info(
        "Search node completed",
        extra={
            "total_documents": len(search_result.documents),
            "datasources_used": search_result.datasources_used,
            "original_query": user_query,
            "used_query": search_query,
        },
    )
    
    # message = get_agent_service().build_message(
    #     message=f"Found {len(filtered_documents)} relevant documents",
    #     extra={
    #         "total_documents": len(filtered_documents),
    #         "datasources_used": search_result.datasources_used,
    #         "used_query": search_query,
    #     },
    # )
    
    return {
        "search_result": search_result,
        "message": None,
    }


def plan_node(state: KnowledgeAgentState):
    """生成阅读计划节点：基于 query 和文献列表生成读取计划"""
    user_query = state["user_query"]
    search_result = state.get("search_result")
    language = state.get("language", "zh")
    
    if not search_result or not search_result.documents:
        logger.warning("No documents found in search result")
        return {
            "reading_plans": [],
            "current_plan_index": 0,
        }
    
    # 构建文档列表（用于 prompt）
    documents_list = []
    for doc in search_result.documents:
        documents_list.append({
            "title": doc.title,
            "snippet": doc.snippet,
            "url": doc.url,
            "doi": doc.doi,
            "source": doc.source,
        })
    
    plan_prompt = format_plan_prompt(
        user_query=user_query,
        documents_list=documents_list,
        language=language,
    )
    response_text = _run_llm(plan_prompt, temperature=0.1, max_tokens=32000, node_name="plan_node")
    parsed = extract_json_from_response(response_text)
    plans = parsed.get("plans", [])
    
    if not plans:
        logger.warning("计划生成失败，返回空计划列表")
        plans = []
    
    # 构建 reading_plans，匹配 search_result 中的文档
    reading_plans: list[ReadingPlan] = []
    for plan in plans:
        # 根据 document_id 或 title 匹配文档
        document_id = plan.get("document_id", "")
        title = plan.get("title", "")
        snippet = plan.get("snippet", "")
        plan_detail = plan.get("plan_detail", "")
        
        # 查找匹配的文档
        matched_doc = None
        for doc in search_result.documents:
            if doc.title == title or doc.doi == document_id or doc.title == document_id:
                matched_doc = doc
                break
        
        if matched_doc:
            reading_plan: ReadingPlan = {
                "document_id": document_id or title,
                "title": matched_doc.title,
                "snippet": matched_doc.snippet,
                "url": matched_doc.url,
                "doi": matched_doc.doi,
                "plan_detail": plan_detail,
                "result": None,
            }
            reading_plans.append(reading_plan)
        else:
            # 如果找不到匹配的文档，使用 plan 中的数据
            reading_plan: ReadingPlan = {
                "document_id": document_id or title,
                "title": title,
                "snippet": snippet,
                "url": None,
                "doi": None,
                "plan_detail": plan_detail,
                "result": None,
            }
            reading_plans.append(reading_plan)
    
    logger.info(
        "Plan node completed",
        extra={
            "plan_count": len(reading_plans),
        },
    )
    
    # message = get_agent_service().build_message(
    #     message=f"{len(reading_plans)} reading plans generated",
    #     extra={
    #         "plans": reading_plans,
    #     },
    # )
    
    return {
        "reading_plans": reading_plans,
        "current_plan_index": 0,
        "message": None,
    }


def execute_plan_node(state: KnowledgeAgentState):
    """路由节点：判断是否还有计划需要执行"""
    current_plan_index = state.get("current_plan_index", 0)
    reading_plans = state.get("reading_plans", [])
    
    if current_plan_index >= len(reading_plans):
        next_route = "answer"
    else:
        next_route = "read"
    return {
        "next_route": next_route,
        "message": None,
    }


def read_node(state: KnowledgeAgentState):
    """执行单个计划项：读取一篇文献"""
    user_query = state["user_query"]
    reading_plans = state.get("reading_plans", [])
    current_plan_index = state.get("current_plan_index", 0)
    language = state.get("language", "zh")
    
    if current_plan_index >= len(reading_plans):
        logger.warning("current_plan_index 超出范围")
        return {}
    
    current_plan = reading_plans[current_plan_index]
    title = current_plan.get("title", "")
    snippet = current_plan.get("snippet", "")
    url = current_plan.get("url")
    doi = current_plan.get("doi")
    plan_detail = current_plan.get("plan_detail", "")
    
    # 使用 LLM 分析文档片段
    read_prompt = format_read_prompt(
        user_query=user_query,
        plan_detail=plan_detail,
        title=title,
        snippet=snippet,
        url=url,
        doi=doi,
        language=language,
    )
    result = _run_llm(read_prompt, temperature=0.1, max_tokens=4000, node_name="read_node")
    
    # 更新结果
    reading_plans[current_plan_index]["result"] = result
    
    logger.info(
        "Read node completed",
        extra={
            "title": title,
            "plan_index": current_plan_index,
        },
    )
    
    # 构建文献信息，包含当前阅读的文献
    current_plan_with_result = reading_plans[current_plan_index].copy()
    literatures = [current_plan_with_result]
    
    message = get_agent_service().build_literature_message(
        message=result,
        literatures=literatures,
    )
    
    return {
        "reading_plans": reading_plans,
        "current_plan_index": current_plan_index + 1,
        "message": message,
    }


def _format_reading_results_for_answer(
    reading_results: list[dict[str, Any]],
) -> str:
    """格式化阅读结果，使其包含 DOI 超链接，并以 Markdown 形式返回。"""
    formatted_results = []
    for res in reading_results:
        title = res.get("title", "")
        doi = res.get("doi")
        result_content = res.get("result", "")
        
        if doi:
            # 构建 Markdown 格式的 DOI 超链接
            formatted_title = f"[{title}](https://doi.org/{doi})"
        else:
            formatted_title = title
            
        formatted_results.append(f"### {formatted_title}\n{result_content}\n")
    return "\n".join(formatted_results)


def answer_node(state: KnowledgeAgentState):
    """汇总所有计划结果，生成最终答案"""
    user_query = state["user_query"]
    reading_plans = state.get("reading_plans", [])
    language = state.get("language", "zh")
    gene_relation_result = state.get("gene_relation_result")
    
    # 记录 gene_relation_result 状态
    if gene_relation_result:
        logger.info(
            f"Answer node received gene_relation_result | "
            f"result_length={len(gene_relation_result)} | "
            f"preview={gene_relation_result[:200]}..."
        )
    else:
        logger.info("Answer node: no gene_relation_result found in state")
    
    # 构建阅读结果列表
    reading_results = []
    for plan in reading_plans:
        reading_results.append({
            "title": plan.get("title", ""),
            "plan_detail": plan.get("plan_detail", ""),
            "result": plan.get("result", ""),
            "doi": plan.get("doi"),
        })
    
    formatted_reading_results = _format_reading_results_for_answer(reading_results)

    # 生成最终答案
    answer_prompt = format_answer_prompt(
        user_query=user_query,
        reading_results=formatted_reading_results,
        language=language,
        gene_relation_result=gene_relation_result,
    )
    response_text = _run_llm(answer_prompt, temperature=0.1, max_tokens=8000, node_name="answer_node")
    parsed = extract_json_from_response(response_text)
    final_answer = parsed.get("final_answer", "")
    
    logger.info(
        f"Answer node generated final_answer | "
        f"answer_length={len(final_answer)} | "
        f"used_gene_relation={bool(gene_relation_result)}"
    )
    
    if not final_answer:
        # Fallback: 简单汇总
        if language == "zh":
            final_answer = "阅读完成。\n\n"
            for plan in reading_plans:
                title = plan.get("title", "")
                result = plan.get("result", "")
                status = "成功" if result and not result.startswith("[错误]") else "失败"
                final_answer += f"- {title} - {status}\n"
        else:
            final_answer = "Reading completed.\n\n"
            for plan in reading_plans:
                title = plan.get("title", "")
                result = plan.get("result", "")
                status = "Success" if result and not result.startswith("[错误]") else "Failed"
                final_answer += f"- {title} - {status}\n"
    
    message = get_agent_service().build_message(
        message=final_answer,
    )
    return {
        "final_answer": final_answer,
        "message": message,
    }

