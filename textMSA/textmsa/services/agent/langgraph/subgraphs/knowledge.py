"""
Knowledge 子图：统一私有知识检索 + 多源公共检索（PubMed / arXiv / Scholar / Web）。

核心职责：
- 根据 Planner 给出的 `knowledge_queries` 或用户消息内容决定是否检索；
- 通过向量库检索私有文档；
- 通过 PubMed + 多源检索工具获取公共文献 / 网页；
- 将所有结果归一化为统一的 `KnowledgeRetrievalResult`，写入 LangGraph 状态。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional

import numpy as np
from langgraph.graph import END, StateGraph

from textmsa.logging_config import get_logger
from textmsa.services.agent.langgraph import jobs
from textmsa.services.agent.langgraph.state import GraphState, StateUpdate
from textmsa.knowledge.pubmed_api import PubMedAPI, get_pubmed_api
from textmsa.services.agent.vector_store import VectorStore, get_vector_store
from textmsa.services.agent.tools.multi_source_retrieval import (
    advanced_web_search_claude,
    extract_pdf_content,
    extract_url_content,
    fetch_supplementary_info_from_doi,
    normalize_arxiv_result,
    normalize_claude_result,
    normalize_crossref_results,
    normalize_google_result,
    normalize_private_doc,
    normalize_pubmed_article,
    normalize_scholar_result,
    normalize_semantic_scholar_results,
    query_arxiv,
    query_crossref,
    query_scholar,
    query_semantic_scholar,
    search_google,
    search_pubmed_structured,
    search_semantic_scholar_structured,
    search_crossref_structured,
    search_arxiv_structured,
    search_scholar_structured,
)
from textmsa.services.agent.llm_client import get_llm_client, LLMRequest
from textmsa.services.agent.qwen_embedding import get_qwen_embedding

logger = get_logger(__name__)


# === 配置常量 ===

ARXIV_RESULT_LIMIT = 10
SCHOLAR_RESULT_LIMIT = 10
GOOGLE_SEARCH_RESULT_LIMIT = 10
# 为避免单一来源过多结果，CrossRef / Semantic Scholar 与 PubMed 采用相近上限
CROSSREF_RESULT_LIMIT = 10
SEMANTIC_SCHOLAR_RESULT_LIMIT = 10
CLAUDE_WEB_SEARCH_MAX_SEARCHES = 2

DEFAULT_ACADEMIC_SOURCES = {
    "pubmed",
    "arxiv",
    # "scholar",
    "crossref",
    "semantic_scholar",
}
DEFAULT_GENERAL_SOURCES = {"google"}

# 精排和答案生成参数
RERANK_TOP_K = 15
MAX_DOCUMENTS_FOR_ANSWER = 10
MAX_TOKENS_PER_DOCUMENT = 500


# === 数据结构 ===


@dataclass
class KnowledgeDocument:
    """统一的知识文档结构，用于后续 RAG / 总结。"""

    source_id: str
    title: Optional[str]
    snippet: str
    source_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeRetrievalResult:
    """Knowledge 子图对外暴露的统一结果结构。"""

    sources: List[KnowledgeDocument]
    usage_metadata: Dict[str, Any] = field(default_factory=dict)


def to_state_update(result: KnowledgeRetrievalResult) -> StateUpdate:
    """将检索结果写入 LangGraph 状态结构。

    - 追加到 `knowledge_results`
    - 可在 Planner / Analyst 中用于后续推理
    """
    docs = [
        {
            "source_id": doc.source_id,
            "title": doc.title,
            "snippet": doc.snippet,
            "source_type": doc.source_type,
            "metadata": doc.metadata,
        }
        for doc in result.sources
    ]
    return {
        "knowledge_results": docs,
        "knowledge_usage": result.usage_metadata,
        "evidence_summary": result.usage_metadata.get("evidence_summary", ""),
    }


# === 辅助函数 ===


def _get_query_from_state(state: GraphState) -> str:
    """优先从 planner 写入的 `knowledge_queries` 中取查询，否则 fallback 用户消息。"""
    query = state.get("active_todo").get('goal')
    if not query:
        raise ValueError("No query found in state")
    return str(query)


def _extract_doi_from_query(query: str) -> Optional[str]:
    """简单 DOI 模式检测。"""
    import re

    pattern = r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b"
    match = re.search(pattern, query, flags=re.IGNORECASE)
    return match.group(0) if match else None


def _extract_urls_from_query(query: str) -> List[str]:
    import re

    url_pattern = r"https?://[^\s]+"
    return re.findall(url_pattern, query)


def _extract_query_params_with_llm(goal: str) -> Dict[str, Any]:
    """使用 LLM 从 goal 中提取实体、进行联想、生成查询参数。
    
    Args:
        goal: 用户的目标/查询文本
        
    Returns:
        包含查询参数的字典，包括：
        - title: 论文标题关键词
        - author: 作者名（列表）
        - keywords: 关键词（列表）
        - abstract_keywords: 摘要关键词（列表）
        - year: 发表年份
        - journal: 期刊名
        - related_concepts: 相关概念/联想词（列表）
    """
    import json
    
    system_prompt = """你是一个专业的文献检索助手。你的任务是从用户的研究目标中提取实体、进行概念联想，并生成结构化的文献检索参数。

请仔细分析用户的研究目标，提取以下信息：
1. **实体提取**：识别基因名、蛋白质名、疾病名、药物名、作者名、期刊名等
2. **概念联想**：基于提取的实体，联想相关的概念、同义词、相关术语
3. **查询参数生成**：将提取的信息组织成结构化的查询参数

请以 JSON 格式返回结果，格式如下：
{
    "title": "论文标题中的关键词（如果有明确的论文标题）",
    "author": ["作者1", "作者2"],
    "keywords": ["关键词1", "关键词2", "关键词3"],
    "abstract_keywords": ["摘要关键词1", "摘要关键词2"],
    "year": 2020,
    "journal": "期刊名（如果有）",
    "related_concepts": ["相关概念1", "相关概念2"]
}

注意：
- 如果某个字段没有相关信息，请设置为 null 或空列表 []
- keywords 应该包括主要的研究主题、方法、对象等
- abstract_keywords 应该包括在摘要中可能出现的更具体的关键词
- related_concepts 应该包括同义词、相关术语、扩展概念等
- year 应该是整数或 null
- 尽量提取所有可能相关的信息，但不要过度联想"""

    user_prompt = f"""请分析以下研究目标，提取实体、进行联想并生成查询参数：

研究目标：{goal}

请返回 JSON 格式的查询参数。"""

    try:
        llm = get_llm_client()
        request = LLMRequest(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=1000,
        )
        
        response = llm.chat(request)
        response_text = response.content.strip()
        
        # 尝试提取 JSON（可能包含 markdown 代码块）
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        params = json.loads(response_text)
        
        # 确保所有字段都有默认值
        result = {
            "title": params.get("title"),
            "author": params.get("author") or [],
            "keywords": params.get("keywords") or [],
            "abstract_keywords": params.get("abstract_keywords") or [],
            "year": params.get("year"),
            "journal": params.get("journal"),
            "related_concepts": params.get("related_concepts") or [],
        }
        
        logger.info(f"LLM 提取的查询参数: {result}")
        return result
        
    except Exception as e:
        logger.warning(f"LLM 提取查询参数失败: {e}，使用原始查询")
        # 失败时返回空参数，后续会使用原始查询
        return {
            "title": None,
            "author": [],
            "keywords": [],
            "abstract_keywords": [],
            "year": None,
            "journal": None,
            "related_concepts": [],
        }


def _determine_retrieval_strategy(
    query: str, state: GraphState
) -> Dict[str, Any]:
    """根据查询和 metadata 决定需要启用的检索源集合及附加信息。"""
    strategy: Dict[str, Any] = {
        "sources": set(),
        "doi": None,
        "urls": [],
    }

    doi = _extract_doi_from_query(query)
    urls = _extract_urls_from_query(query)
    sources = set()
    if doi:
        sources.add("doi")
    if urls:
        sources.add("url")
    sources.update(DEFAULT_ACADEMIC_SOURCES)
    strategy["sources"] = sources
    strategy["doi"] = doi
    strategy["urls"] = urls
    return strategy


def _deduplicate_results(
    docs: List[KnowledgeDocument],
) -> List[KnowledgeDocument]:
    """基于 (source_id, title) 进行简单去重。"""
    seen: set[tuple[str, str]] = set()
    deduped: List[KnowledgeDocument] = []
    for d in docs:
        key = (d.source_id, (d.title or "").strip())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(d)
    return deduped


def _convert_normalized_dicts_to_docs(
    items: List[Dict[str, Any]],
) -> List[KnowledgeDocument]:
    docs: List[KnowledgeDocument] = []
    for it in items:
        docs.append(
            KnowledgeDocument(
                source_id=str(it.get("source_id") or ""),
                title=it.get("title"),
                snippet=str(it.get("snippet") or ""),
                source_type=str(it.get("source_type") or "unknown"),
                metadata=dict(it.get("metadata") or {}),
            )
        )
    return docs


# === 私有检索 & PubMed 检索 ===


def _run_private_search(
    *,
    state: GraphState,
    vector_store: Optional[VectorStore] = None,
    top_k: int = 8,
) -> KnowledgeRetrievalResult:
    """使用向量库进行私有知识检索。"""
    vs = vector_store or get_vector_store()
    if vs is None:
        logger.info("Vector store not available, skipping private search")
        return KnowledgeRetrievalResult(sources=[], usage_metadata={"private_hits": 0})

    query = _get_query_from_state(state)
    # 当前 VectorStore.search 签名为 (query: str, top_k: int = 3)
    raw_docs = vs.search(query=query, top_k=top_k)

    normalized = [normalize_private_doc(doc) for doc in raw_docs]
    docs = _convert_normalized_dicts_to_docs(normalized)

    usage = {
        "query": query,
        "private_hits": len(docs),
    }

    return KnowledgeRetrievalResult(sources=docs, usage_metadata=usage)


def _run_pubmed_search(
    *,
    state: GraphState,
    query_params: Optional[Dict[str, Any]] = None,
    fallback_query: Optional[str] = None,
    pubmed_api: Optional[PubMedAPI] = None,
    max_results: int = 20,
) -> KnowledgeRetrievalResult:
    """使用 PubMed API 进行文献检索，优先使用结构化参数。"""
    api = pubmed_api or get_pubmed_api()

    if api is None:
        logger.info("PubMed API not available, skipping pubmed search")
        return KnowledgeRetrievalResult(sources=[], usage_metadata={"pubmed_hits": 0})

    # 优先使用结构化搜索
    normalized = []
    query = fallback_query or _get_query_from_state(state)
    pubmed_articles = []
    
    if query_params:
        try:
            normalized = search_pubmed_structured(
                title=query_params.get("title"),
                author=query_params.get("author") or None,
                keywords=query_params.get("keywords") or None,
                abstract_keywords=query_params.get("abstract_keywords") or None,
                year=query_params.get("year"),
                journal=query_params.get("journal"),
                max_results=max_results,
            )
            if normalized:
                # 从归一化结果中提取原始文章信息用于 evidence extractor
                # 归一化结果已经包含了 title, snippet (abstract), source_id (pmid) 等信息
                for item in normalized:
                    article_dict = {
                        "title": item.get("title", ""),
                        "abstract": item.get("snippet", ""),
                        "pmid": item.get("source_id", ""),
                    }
                    pubmed_articles.append(article_dict)
        except Exception as e:
            logger.warning(f"PubMed 结构化搜索失败: {e}，使用 fallback 查询")
            normalized = []
    
    # 如果结构化搜索没有结果，使用原始查询方式
    if not normalized:
        from textmsa.services.agent.tools.multi_source_retrieval import query_pubmed_api
        raw_articles = query_pubmed_api(query=query, max_results=max_results)
        normalized = [normalize_pubmed_article(a) for a in raw_articles]
        pubmed_articles = raw_articles  # 原始文章信息用于 evidence extractor
    
    docs = _convert_normalized_dicts_to_docs(normalized)

    # 生成简要摘要以便写入 state
    evidence_summary_parts: List[str] = []
    for doc in docs[:3]:
        title = (doc.title or doc.snippet[:80]).strip()
        label = f"literature:{doc.source_id}"
        if title:
            label = f"{label}-{title}"
        evidence_summary_parts.append(label[:160])
    evidence_summary = " | ".join(evidence_summary_parts) if evidence_summary_parts else "literature:0"

    usage = {
        "query": query,
        "query_params": query_params,
        "pubmed_hits": len(docs),
        "evidence_summary": evidence_summary,
        "selected_pmids": [d.source_id for d in docs],
    }

    return KnowledgeRetrievalResult(sources=docs, usage_metadata=usage)


# === 多源公共检索 ===
def _run_arxiv_search(query_params: Dict[str, Any], fallback_query: str) -> List[KnowledgeDocument]:
    """使用结构化参数搜索 arXiv，如果参数不足则使用 fallback_query。"""
    try:
        # 尝试使用结构化搜索
        normalized = search_arxiv_structured(
            title=query_params.get("title"),
            author=query_params.get("author") or None,
            keywords=query_params.get("keywords") or None,
            abstract_keywords=query_params.get("abstract_keywords") or None,
            max_papers=ARXIV_RESULT_LIMIT,
        )
        if normalized:
            return _convert_normalized_dicts_to_docs(normalized)
    except Exception as e:
        logger.warning(f"arXiv 结构化搜索失败: {e}，使用 fallback 查询")
    
    # Fallback 到原始查询方式
    arxiv_text = query_arxiv(query=fallback_query, max_papers=ARXIV_RESULT_LIMIT)
    normalized = normalize_arxiv_result(arxiv_text, query=fallback_query)
    return _convert_normalized_dicts_to_docs(normalized)


def _run_scholar_search(query_params: Dict[str, Any], fallback_query: str) -> List[KnowledgeDocument]:
    """使用结构化参数搜索 Google Scholar，如果参数不足则使用 fallback_query。"""
    try:
        # 尝试使用结构化搜索
        normalized = search_scholar_structured(
            title=query_params.get("title"),
            author=query_params.get("author") or None,
            keywords=query_params.get("keywords") or None,
            abstract_keywords=query_params.get("abstract_keywords") or None,
            max_results=SCHOLAR_RESULT_LIMIT,
        )
        if normalized:
            return _convert_normalized_dicts_to_docs(normalized)
    except Exception as e:
        logger.warning(f"Google Scholar 结构化搜索失败: {e}，使用 fallback 查询")
    
    # Fallback 到原始查询方式
    scholar_text = query_scholar(query=fallback_query, max_results=SCHOLAR_RESULT_LIMIT)
    normalized = normalize_scholar_result(scholar_text, query=fallback_query)
    return _convert_normalized_dicts_to_docs(normalized)


def _run_google_search(query_params: Dict[str, Any], fallback_query: str) -> List[KnowledgeDocument]:
    """使用查询参数构建 Google 搜索查询。"""
    # Google 搜索使用自由文本查询，组合所有关键词
    search_terms = []
    if query_params.get("title"):
        search_terms.append(query_params["title"])
    if query_params.get("keywords"):
        search_terms.extend(query_params["keywords"])
    if query_params.get("related_concepts"):
        search_terms.extend(query_params["related_concepts"])
    
    query = " ".join(search_terms) if search_terms else fallback_query
    
    google_results = search_google(
        query=query,
        num_results=GOOGLE_SEARCH_RESULT_LIMIT,
        language="en",
    )
    normalized = normalize_google_result(google_results, query=query)
    return _convert_normalized_dicts_to_docs(normalized)


def _run_crossref_search(query_params: Dict[str, Any], fallback_query: str) -> List[KnowledgeDocument]:
    """使用结构化参数搜索 CrossRef，如果参数不足则使用 fallback_query。"""
    try:
        # 尝试使用结构化搜索
        normalized = search_crossref_structured(
            title=query_params.get("title"),
            author=query_params.get("author") or None,
            keywords=query_params.get("keywords") or None,
            abstract_keywords=query_params.get("abstract_keywords") or None,
            max_results=CROSSREF_RESULT_LIMIT,
        )
        if normalized:
            return _convert_normalized_dicts_to_docs(normalized)
    except Exception as e:
        logger.warning(f"CrossRef 结构化搜索失败: {e}，使用 fallback 查询")
    
    # Fallback 到原始查询方式
    items = query_crossref(query=fallback_query, max_results=CROSSREF_RESULT_LIMIT)
    normalized = normalize_crossref_results(items, query=fallback_query)
    return _convert_normalized_dicts_to_docs(normalized)


def _run_semantic_scholar_search(query_params: Dict[str, Any], fallback_query: str) -> List[KnowledgeDocument]:
    """使用结构化参数搜索 Semantic Scholar，如果参数不足则使用 fallback_query。"""
    try:
        # 尝试使用结构化搜索
        normalized = search_semantic_scholar_structured(
            title=query_params.get("title"),
            author=query_params.get("author") or None,
            keywords=query_params.get("keywords") or None,
            abstract_keywords=query_params.get("abstract_keywords") or None,
            max_results=SEMANTIC_SCHOLAR_RESULT_LIMIT,
        )
        if normalized:
            return _convert_normalized_dicts_to_docs(normalized)
    except Exception as e:
        logger.warning(f"Semantic Scholar 结构化搜索失败: {e}，使用 fallback 查询")
    
    # Fallback 到原始查询方式
    papers = query_semantic_scholar(
        query=fallback_query, max_results=SEMANTIC_SCHOLAR_RESULT_LIMIT
    )
    normalized = normalize_semantic_scholar_results(papers, query=fallback_query)
    return _convert_normalized_dicts_to_docs(normalized)


def _run_claude_web_search(query_params: Dict[str, Any], fallback_query: str) -> List[KnowledgeDocument]:
    """使用查询参数构建 Claude Web 搜索查询。"""
    # Claude Web 搜索使用自由文本查询，组合所有关键词
    search_terms = []
    if query_params.get("title"):
        search_terms.append(query_params["title"])
    if query_params.get("keywords"):
        search_terms.extend(query_params["keywords"])
    if query_params.get("related_concepts"):
        search_terms.extend(query_params["related_concepts"])
    
    query = " ".join(search_terms) if search_terms else fallback_query
    
    text, citations, errors = advanced_web_search_claude(
        query=query, max_searches=CLAUDE_WEB_SEARCH_MAX_SEARCHES
    )
    if errors:
        logger.info("Claude web search errors: %s", errors)
    normalized = normalize_claude_result(text, citations, query=query)
    return _convert_normalized_dicts_to_docs(normalized)


def _run_doi_supplementary_fetch(doi: str) -> List[KnowledgeDocument]:
    raw = fetch_supplementary_info_from_doi(doi)
    files = raw.get("files") or []
    docs: List[KnowledgeDocument] = []
    for idx, f in enumerate(files):
        docs.append(
            KnowledgeDocument(
                source_id=f"{doi}_supp_{idx}",
                title=str(f),
                snippet="Supplementary material link discovered from DOI page.",
                source_type="doi_supplementary",
                metadata={
                    "doi": doi,
                    "supplementary_link": f,
                    "log": raw.get("log"),
                },
            )
        )
    return docs


def _run_url_content_extraction(urls: List[str]) -> List[KnowledgeDocument]:
    docs: List[KnowledgeDocument] = []
    for url in urls:
        content = extract_url_content(url)
        if not content:
            continue
        docs.append(
            KnowledgeDocument(
                source_id=url,
                title=url,
                snippet=content[:1000],
                source_type="web_page",
                metadata={"access_url": url},
            )
        )
    return docs


def _run_pdf_content_extraction(urls: List[str]) -> List[KnowledgeDocument]:
    docs: List[KnowledgeDocument] = []
    for url in urls:
        if not url.lower().endswith(".pdf"):
            continue
        content = extract_pdf_content(url)
        if not content:
            continue
        docs.append(
            KnowledgeDocument(
                source_id=url,
                title=url,
                snippet=content[:1000],
                source_type="pdf",
                metadata={"access_url": url},
            )
        )
    return docs


def _run_multi_source_public_search(
    *, state: GraphState
) -> KnowledgeRetrievalResult:
    """根据策略执行多源公共检索（PubMed + arXiv + Scholar + Web）。
    
    使用 LLM 从 goal 中提取实体、进行联想、生成查询参数，然后调用结构化搜索接口。
    """
    goal = _get_query_from_state(state)
    
    # 使用 LLM 提取查询参数
    logger.info(f"使用 LLM 从 goal 中提取查询参数: {goal}")
    query_params = _extract_query_params_with_llm(goal)
    
    # 构建 fallback 查询（用于不支持结构化搜索的数据源或作为备用）
    fallback_terms = []
    if query_params.get("title"):
        fallback_terms.append(query_params["title"])
    if query_params.get("keywords"):
        fallback_terms.extend(query_params["keywords"])
    if query_params.get("related_concepts"):
        fallback_terms.extend(query_params["related_concepts"])
    fallback_query = " ".join(fallback_terms) if fallback_terms else goal
    
    # 确定检索策略
    strategy = _determine_retrieval_strategy(goal, state)
    sources = strategy["sources"]
    doi = strategy["doi"]
    urls = strategy["urls"]

    all_docs: List[KnowledgeDocument] = []

    # 使用结构化参数进行检索，每个来源独立处理，失败时跳过该来源
    if "pubmed" in sources:
        try:
            pubmed_result = _run_pubmed_search(
                state=state,
                query_params=query_params,
                fallback_query=fallback_query,
            )
            all_docs.extend(pubmed_result.sources)
        except Exception as e:
            logger.warning(f"PubMed 检索失败: {e}，跳过此来源")

    if "arxiv" in sources:
        try:
            all_docs.extend(_run_arxiv_search(query_params, fallback_query))
        except Exception as e:
            logger.warning(f"arXiv 检索失败: {e}，跳过此来源")

    if "scholar" in sources:
        try:
            all_docs.extend(_run_scholar_search(query_params, fallback_query))
        except Exception as e:
            logger.warning(f"Google Scholar 检索失败: {e}，跳过此来源")

    if "crossref" in sources:
        try:
            all_docs.extend(_run_crossref_search(query_params, fallback_query))
        except Exception as e:
            logger.warning(f"CrossRef 检索失败: {e}，跳过此来源")

    if "semantic_scholar" in sources:
        try:
            all_docs.extend(_run_semantic_scholar_search(query_params, fallback_query))
        except Exception as e:
            logger.warning(f"Semantic Scholar 检索失败: {e}，跳过此来源")

    if "google" in sources:
        try:
            all_docs.extend(_run_google_search(query_params, fallback_query))
        except Exception as e:
            logger.warning(f"Google 检索失败: {e}，跳过此来源")

    if "claude_web" in sources:
        try:
            all_docs.extend(_run_claude_web_search(query_params, fallback_query))
        except Exception as e:
            logger.warning(f"Claude Web 检索失败: {e}，跳过此来源")

    if "doi" in sources and doi:
        try:
            all_docs.extend(_run_doi_supplementary_fetch(doi))
        except Exception as e:
            logger.warning(f"DOI 补充信息获取失败: {e}，跳过此来源")

    if "url" in sources and urls:
        try:
            all_docs.extend(_run_url_content_extraction(urls))
        except Exception as e:
            logger.warning(f"URL 内容提取失败: {e}，跳过此来源")
        try:
            all_docs.extend(_run_pdf_content_extraction(urls))
        except Exception as e:
            logger.warning(f"PDF 内容提取失败: {e}，跳过此来源")

    all_docs = _deduplicate_results(all_docs)

    usage = {
        "goal": goal,
        "query_params": query_params,
        "fallback_query": fallback_query,
        "strategy_sources": sorted(list(sources)),
        "doi": doi,
        "urls": urls,
        "total_hits": len(all_docs),
    }

    # 将 strategy 中的 set 转换为可序列化类型，避免 Mongo 记录时报 BSON 错误
    strategy_for_log = {
        "sources": sorted(list(sources)),
        "doi": doi,
        "urls": urls,
    }
    return KnowledgeRetrievalResult(sources=all_docs, usage_metadata=usage)


# === LangGraph 节点 & 路由 ===


def knowledge_analysis_router(state: GraphState) -> str:
    """根据 `need_knowledge` / 查询内容判断是否执行 Knowledge 子图。"""
    if not state.get("need_knowledge", True):
        return "skip"
    query = _get_query_from_state(state)
    if not query.strip():
        return "skip"
    return "run"


def knowledge_node(state: GraphState) -> StateUpdate:
    """Knowledge 主节点：执行私有检索 + 多源公共检索，并写入统一结果。"""
    # private_result = _run_private_search(state=state)
    public_result = _run_multi_source_public_search(state=state)
    # all_docs = private_result.sources + public_result.sources
    all_docs = public_result.sources
    all_docs = _deduplicate_results(all_docs)
    usage = {
        # "private": private_result.usage_metadata,
        "public": public_result.usage_metadata,
        "total_hits": len(all_docs),
    }
    usage["evidence_summary"] = public_result.usage_metadata.get("evidence_summary", "")
    result = KnowledgeRetrievalResult(sources=all_docs, usage_metadata=usage)
    return to_state_update(result)


def knowledge_router(state: GraphState) -> str:
    """外层路由：决定是否进入 Knowledge 子图。"""
    return knowledge_analysis_router(state)


def knowledge_rerank_node(state: GraphState) -> StateUpdate:
    return None
    """精排节点：使用 Qwen embedding 对检索到的文档进行精排。

    1. 从 state.knowledge_results 获取检索到的文档
    2. 从 state.active_todo.goal 获取查询目标
    3. 使用 Qwen embedding 计算查询与每个文档的相似度
    4. 对文档按相关性排序
    5. 选择 top_k 个最相关的文档
    """
    knowledge_results = state.get("knowledge_results", [])
    if not knowledge_results:
        logger.info("精排节点：无检索结果，跳过精排")
        return {}

    query = _get_query_from_state(state)
    logger.info(f"精排节点：开始精排，查询: {query}，文档数量: {len(knowledge_results)}")

    # 获取 Qwen embedding 服务
    embedding_service = get_qwen_embedding()

    # 生成查询向量
    query_embedding = embedding_service.embed_text(query)
    query_embedding = query_embedding / np.linalg.norm(query_embedding)

    # 准备文档文本（标题 + 摘要）
    doc_texts = []
    for doc in knowledge_results:
        title = doc.get("title") or ""
        snippet = doc.get("snippet") or ""
        doc_text = f"{title}\n{snippet}".strip()
        doc_texts.append(doc_text)

    # 批量生成文档向量
    doc_embeddings = embedding_service.embed_batch(doc_texts)

    # 计算相似度分数
    scores = []
    for doc_emb in doc_embeddings:
        doc_emb_normalized = doc_emb / np.linalg.norm(doc_emb)
        similarity = np.dot(query_embedding, doc_emb_normalized)
        scores.append(float(similarity))

    # 将文档和分数配对并排序
    doc_score_pairs = list(zip(knowledge_results, scores))
    doc_score_pairs.sort(key=lambda x: x[1], reverse=True)

    # 选择 top_k 个文档
    top_k = min(RERANK_TOP_K, len(doc_score_pairs))
    reranked_docs = []
    reranked_scores = []

    for doc, score in doc_score_pairs[:top_k]:
        doc_with_score = doc.copy()
        doc_with_score["metadata"] = doc.get("metadata", {}).copy()
        doc_with_score["metadata"]["rerank_score"] = score
        reranked_docs.append(doc_with_score)
        reranked_scores.append(score)

    logger.info(
        f"精排节点：完成精排，保留 top {top_k} 个文档，分数范围: {min(reranked_scores):.4f} - {max(reranked_scores):.4f}"
    )
    return {
        "knowledge_results": reranked_docs,
    }


def knowledge_final_answer_node(state: GraphState) -> StateUpdate:
    """LLM 处理节点：使用 LLM + prompt 对精排结果进行处理并生成 knowledge_final_answer。

    1. 从状态获取精排后的文档
    2. 从 state.active_todo.goal 获取查询目标
    3. 格式化文档内容
    4. 使用 LLM + prompt 生成结构化答案
    5. 将结果写入 state.knowledge_final_answer
    """
    knowledge_results = state.get("knowledge_results", [])
    query = _get_query_from_state(state)

    if not knowledge_results:
        logger.info("LLM 处理节点：无文档，生成空答案")
        return {"knowledge_final_answer": "未找到相关文档。"}

    logger.info(f"LLM 处理节点：开始生成最终答案，查询: {query}，文档数量: {len(knowledge_results)}")

    # 格式化文档内容
    max_docs = min(MAX_DOCUMENTS_FOR_ANSWER, len(knowledge_results))
    formatted_docs = []

    for i, doc in enumerate(knowledge_results[:max_docs]):
        title = doc.get("title") or "无标题"
        snippet = doc.get("snippet") or ""
        source_type = doc.get("source_type") or "unknown"
        source_id = doc.get("source_id") or ""
        rerank_score = doc.get("metadata", {}).get("rerank_score", 0.0)

        # 截断过长的文档内容
        if len(snippet) > MAX_TOKENS_PER_DOCUMENT * 4:  # 粗略估算：1 token ≈ 4 字符
            snippet = snippet[: MAX_TOKENS_PER_DOCUMENT * 4] + "..."

        doc_text = f"""文档 {i + 1}:
标题：{title}
来源类型：{source_type}
来源ID：{source_id}
相关性分数：{rerank_score:.4f}
内容：
{snippet}
"""
        formatted_docs.append(doc_text)

    formatted_documents_text = "\n\n".join(formatted_docs)

    # 构建 prompt
    system_prompt = """你是一个专业的科研助手。基于以下检索到的文献和资料，回答用户的研究问题。

请确保回答：
- 准确引用来源
- 逻辑清晰
- 重点突出
- 便于理解"""

    user_prompt = f"""用户问题：{query}

检索到的相关文档：
{formatted_documents_text}

请基于这些文档，生成一个全面、准确、结构化的回答。回答应该包括：
1. 核心发现和结论
2. 关键证据和支持材料
3. 相关研究的总结

回答："""

    # 调用 LLM 生成答案
    llm = get_llm_client()
    request = LLMRequest(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=2000,
    )

    response = llm.chat(request)
    final_answer = response.content.strip()

    logger.info(f"LLM 处理节点：生成最终答案完成，答案长度: {len(final_answer)}")

    return {
        "knowledge_final_answer": final_answer,
    }


def build_knowledge_graph() -> StateGraph:
    """构建独立可测试的 Knowledge 子图。"""
    graph: StateGraph = StateGraph(GraphState)  # type: ignore[arg-type]

    graph.add_node("knowledge", knowledge_node)
    graph.add_node("rerank", knowledge_rerank_node)
    graph.add_node("final_answer", knowledge_final_answer_node)

    graph.set_entry_point("knowledge")
    graph.add_edge("knowledge", "rerank")
    graph.add_edge("rerank", "final_answer")
    graph.add_edge("final_answer", END)

    return graph


