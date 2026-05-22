"""
多源数据检索工具模块
支持 arXiv、Google Scholar、Google 搜索、Claude 网络搜索、DOI 补充材料、URL/PDF 内容提取

统一查询构建器：
    本模块提供了统一的查询构建接口，支持结构化输入（title, author, keywords等），
    自动为不同数据源构建合适的查询字符串。

    使用示例：
        # 方式1: 使用查询构建器 + 原始查询函数
        from textmsa.services.agent.tools.multi_source_retrieval import (
            build_pubmed_query,
            query_pubmed_api,
            normalize_pubmed_article,
        )
        
        query = build_pubmed_query(
            title="TP53",
            author=["Smith", "Jones"],
            keywords="cancer",
            year=2020
        )
        articles = query_pubmed_api(query, max_results=10)
        normalized = [normalize_pubmed_article(a) for a in articles]
        
        # 方式2: 使用结构化搜索函数（推荐，一步到位）
        from textmsa.services.agent.tools.multi_source_retrieval import (
            search_pubmed_structured,
            search_semantic_scholar_structured,
            search_crossref_structured,
        )
        
        # PubMed 结构化搜索
        results = search_pubmed_structured(
            title="TP53",
            author="Smith",
            keywords="tumor suppressor",
            abstract_keywords="apoptosis",
            year=2020,
            max_results=10
        )
        
        # Semantic Scholar 结构化搜索（支持摘要查询）
        results = search_semantic_scholar_structured(
            title="machine learning",
            keywords=["neural networks", "deep learning"],
            abstract_keywords="backpropagation",
            max_results=10
        )
        
        # CrossRef 结构化搜索（支持摘要查询）
        results = search_crossref_structured(
            title="TP53",
            author=["Smith", "Jones"],
            keywords="cancer",
            abstract_keywords="tumor suppressor",
            max_results=10
        )

数据源支持：
    - PubMed: 支持字段查询（Title, Author, Abstract, Journal, Publication Date）
        摘要查询使用 abstract_keywords 参数，会使用 [Abstract] 字段查询
    - Semantic Scholar: 自由文本查询，支持摘要关键词（abstract_keywords）
    - CrossRef: 自由文本查询，支持摘要关键词（abstract_keywords）
    - arXiv: 支持作者字段查询（au:"author"），支持摘要关键词（abstract_keywords）
    - Google Scholar: 支持标题和作者精确匹配，支持摘要关键词（abstract_keywords）
"""

from __future__ import annotations

import os
import re
import time
from datetime import datetime, timezone
from typing import Any

from textmsa.logging_config import get_logger

try:
    # PubMed API 封装（已经在 knowledge 层使用），这里作为工具复用
    from textmsa.knowledge.pubmed_api import get_pubmed_api, PubMedAPI
except Exception:  # 避免循环/环境问题导致导入失败
    get_pubmed_api = None  # type: ignore[assignment]
    PubMedAPI = None  # type: ignore[assignment]

logger = get_logger(__name__)


# ============= 统一查询构建器 =============


def build_pubmed_query(
    title: str | None = None,
    author: str | list[str] | None = None,
    keywords: str | list[str] | None = None,
    year: int | str | None = None,
    journal: str | None = None,
    abstract_keywords: str | list[str] | None = None,
) -> str:
    """
    构建 PubMed 查询字符串。
    
    PubMed 支持字段查询语法：
    - title: [Title]
    - author: [Author]
    - keywords: 自由文本，会搜索标题和摘要
    - year: [Publication Date]
    - journal: [Journal]
    - abstract_keywords: [Abstract]
    
    Args:
        title: 论文标题
        author: 作者名（字符串或列表）
        keywords: 关键词（字符串或列表）
        year: 发表年份
        journal: 期刊名
        abstract_keywords: 摘要中的关键词
        
    Returns:
        构建好的 PubMed 查询字符串
    """
    parts: list[str] = []
    
    if title:
        # 清理标题中的特殊字符，并用引号包裹以提高精确度
        title_clean = title.strip().replace('"', '')
        parts.append(f'"{title_clean}"[Title]')
    
    if author:
        if isinstance(author, list):
            # 多个作者用 OR 连接
            author_parts = [f'"{a.strip()}"[Author]' for a in author if a.strip()]
            if author_parts:
                parts.append("(" + " OR ".join(author_parts) + ")")
        else:
            parts.append(f'"{author.strip()}"[Author]')
    
    if keywords:
        if isinstance(keywords, list):
            # 多个关键词用 OR 连接（同义词或相关概念，只要匹配任何一个即可）
            keyword_parts = [kw.strip() for kw in keywords if kw.strip()]
            if keyword_parts:
                parts.append("(" + " OR ".join(keyword_parts) + ")")
        else:
            parts.append(keywords.strip())
    
    if abstract_keywords:
        if isinstance(abstract_keywords, list):
            abstract_parts = [f'"{kw.strip()}"[Abstract]' for kw in abstract_keywords if kw.strip()]
            if abstract_parts:
                parts.append("(" + " OR ".join(abstract_parts) + ")")
        else:
            parts.append(f'"{abstract_keywords.strip()}"[Abstract]')
    
    if year:
        year_str = str(year).strip()
        # PubMed 支持年份范围，这里简化为单年
        parts.append(f'{year_str}[Publication Date]')
    
    if journal:
        journal_clean = journal.strip().replace('"', '')
        parts.append(f'"{journal_clean}"[Journal]')
    
    if not parts:
        return ""
    
    # 主要搜索字段（title, keywords, abstract_keywords）之间用 OR 连接，更灵活
    # 精确过滤字段（author, year, journal）用 AND 连接（必须满足）
    main_parts = []  # title, keywords, abstract_keywords
    exact_parts = []  # author, year, journal
    
    for part in parts:
        if '[Author]' in part or '[Publication Date]' in part or '[Journal]' in part:
            exact_parts.append(part)
        else:
            main_parts.append(part)
    
    query_parts = []
    if main_parts:
        # 主要字段用 OR 连接，只要匹配任何一个即可
        if len(main_parts) > 1:
            query_parts.append("(" + " OR ".join(main_parts) + ")")
        else:
            query_parts.append(main_parts[0])
    
    if exact_parts:
        # 精确字段用 AND 连接（必须满足）
        query_parts.extend(exact_parts)
    
    if len(query_parts) > 1:
        query = " AND ".join(query_parts)
    else:
        query = query_parts[0] if query_parts else ""
    logger.debug(f"Built PubMed query: {query}")
    return query


def build_semantic_scholar_query(
    title: str | None = None,
    author: str | list[str] | None = None,
    keywords: str | list[str] | None = None,
    abstract_keywords: str | list[str] | None = None,
) -> str:
    """
    构建 Semantic Scholar 查询字符串。
    
    Semantic Scholar 使用自由文本查询，支持标题、作者、关键词、摘要关键词的组合。
    摘要关键词会被添加到查询中，Semantic Scholar 会自动在摘要中搜索。
    
    Args:
        title: 论文标题
        author: 作者名（字符串或列表）
        keywords: 关键词（字符串或列表）
        abstract_keywords: 摘要中的关键词（字符串或列表）
        
    Returns:
        构建好的查询字符串
    """
    parts: list[str] = []
    
    if title:
        parts.append(title.strip())
    
    if author:
        if isinstance(author, list):
            parts.extend([a.strip() for a in author if a.strip()])
        else:
            parts.append(author.strip())
    
    if keywords:
        if isinstance(keywords, list):
            parts.extend([kw.strip() for kw in keywords if kw.strip()])
        else:
            parts.append(keywords.strip())
    
    if abstract_keywords:
        if isinstance(abstract_keywords, list):
            parts.extend([kw.strip() for kw in abstract_keywords if kw.strip()])
        else:
            parts.append(abstract_keywords.strip())
    
    if not parts:
        return ""
    
    query = " ".join(parts)
    logger.debug(f"Built Semantic Scholar query: {query}")
    return query


def build_crossref_query(
    title: str | None = None,
    author: str | list[str] | None = None,
    keywords: str | list[str] | None = None,
    abstract_keywords: str | list[str] | None = None,
) -> str:
    """
    构建 CrossRef 查询字符串。
    
    CrossRef 使用自由文本查询，支持标题、作者、关键词、摘要关键词的组合。
    摘要关键词会被添加到查询中，CrossRef 会自动在摘要中搜索。
    
    Args:
        title: 论文标题
        author: 作者名（字符串或列表）
        keywords: 关键词（字符串或列表）
        abstract_keywords: 摘要中的关键词（字符串或列表）
        
    Returns:
        构建好的查询字符串
    """
    parts: list[str] = []
    
    if title:
        parts.append(title.strip())
    
    if author:
        if isinstance(author, list):
            parts.extend([a.strip() for a in author if a.strip()])
        else:
            parts.append(author.strip())
    
    if keywords:
        if isinstance(keywords, list):
            parts.extend([kw.strip() for kw in keywords if kw.strip()])
        else:
            parts.append(keywords.strip())
    
    if abstract_keywords:
        if isinstance(abstract_keywords, list):
            parts.extend([kw.strip() for kw in abstract_keywords if kw.strip()])
        else:
            parts.append(abstract_keywords.strip())
    
    if not parts:
        return ""
    
    query = " ".join(parts)
    logger.debug(f"Built CrossRef query: {query}")
    return query


def build_arxiv_query(
    title: str | None = None,
    author: str | list[str] | None = None,
    keywords: str | list[str] | None = None,
    abstract_keywords: str | list[str] | None = None,
) -> str:
    """
    构建 arXiv 查询字符串。
    
    arXiv 使用自由文本查询，支持标题、作者、关键词、摘要关键词的组合。
    摘要关键词会被添加到查询中，arXiv 会自动在摘要中搜索。
    
    Args:
        title: 论文标题
        author: 作者名（字符串或列表）
        keywords: 关键词（字符串或列表）
        abstract_keywords: 摘要中的关键词（字符串或列表）
        
    Returns:
        构建好的查询字符串
    """
    parts: list[str] = []
    
    if title:
        parts.append(title.strip())
    
    if author:
        if isinstance(author, list):
            parts.extend([f'au:"{a.strip()}"' for a in author if a.strip()])
        else:
            parts.append(f'au:"{author.strip()}"')
    
    if keywords:
        if isinstance(keywords, list):
            parts.extend([kw.strip() for kw in keywords if kw.strip()])
        else:
            parts.append(keywords.strip())
    
    if abstract_keywords:
        if isinstance(abstract_keywords, list):
            parts.extend([kw.strip() for kw in abstract_keywords if kw.strip()])
        else:
            parts.append(abstract_keywords.strip())
    
    if not parts:
        return ""
    
    query = " ".join(parts)
    logger.debug(f"Built arXiv query: {query}")
    return query


def build_scholar_query(
    title: str | None = None,
    author: str | list[str] | None = None,
    keywords: str | list[str] | None = None,
    abstract_keywords: str | list[str] | None = None,
) -> str:
    """
    构建 Google Scholar 查询字符串。
    
    Google Scholar 使用自由文本查询，支持标题、作者、关键词、摘要关键词的组合。
    摘要关键词会被添加到查询中，Google Scholar 会自动在摘要中搜索。
    
    Args:
        title: 论文标题
        author: 作者名（字符串或列表）
        keywords: 关键词（字符串或列表）
        abstract_keywords: 摘要中的关键词（字符串或列表）
        
    Returns:
        构建好的查询字符串
    """
    parts: list[str] = []
    
    if title:
        # 用引号包裹标题以提高精确度
        parts.append(f'"{title.strip()}"')
    
    if author:
        if isinstance(author, list):
            parts.extend([f'author:"{a.strip()}"' for a in author if a.strip()])
        else:
            parts.append(f'author:"{author.strip()}"')
    
    if keywords:
        if isinstance(keywords, list):
            parts.extend([kw.strip() for kw in keywords if kw.strip()])
        else:
            parts.append(keywords.strip())
    
    if abstract_keywords:
        if isinstance(abstract_keywords, list):
            parts.extend([kw.strip() for kw in abstract_keywords if kw.strip()])
        else:
            parts.append(abstract_keywords.strip())
    
    if not parts:
        return ""
    
    query = " ".join(parts)
    logger.debug(f"Built Google Scholar query: {query}")
    return query


# ============= 结构化查询封装函数 =============


def search_pubmed_structured(
    title: str | None = None,
    author: str | list[str] | None = None,
    keywords: str | list[str] | None = None,
    year: int | str | None = None,
    journal: str | None = None,
    abstract_keywords: str | list[str] | None = None,
    max_results: int = 10,
) -> list[dict[str, Any]]:
    """
    使用结构化输入搜索 PubMed。
    
    Args:
        title: 论文标题
        author: 作者名（字符串或列表）
        keywords: 关键词（字符串或列表）
        year: 发表年份
        journal: 期刊名
        abstract_keywords: 摘要中的关键词
        max_results: 最大返回结果数
        
    Returns:
        文章信息列表（已归一化）
    """
    query = build_pubmed_query(
        title=title,
        author=author,
        keywords=keywords,
        year=year,
        journal=journal,
        abstract_keywords=abstract_keywords,
    )
    
    if not query:
        logger.warning("Empty PubMed query, returning empty results")
        return []
    
    articles = query_pubmed_api(query, max_results=max_results)
    # 归一化结果
    normalized = [normalize_pubmed_article(a) for a in articles]
    return normalized


def search_semantic_scholar_structured(
    title: str | None = None,
    author: str | list[str] | None = None,
    keywords: str | list[str] | None = None,
    abstract_keywords: str | list[str] | None = None,
    max_results: int = 10,
) -> list[dict[str, Any]]:
    """
    使用结构化输入搜索 Semantic Scholar。
    
    Args:
        title: 论文标题
        author: 作者名（字符串或列表）
        keywords: 关键词（字符串或列表）
        abstract_keywords: 摘要中的关键词（字符串或列表）
        max_results: 最大返回结果数
        
    Returns:
        归一化的结果列表
    """
    query = build_semantic_scholar_query(
        title=title,
        author=author,
        keywords=keywords,
        abstract_keywords=abstract_keywords,
    )
    
    if not query:
        logger.warning("Empty Semantic Scholar query, returning empty results")
        return []
    
    papers = query_semantic_scholar(query, max_results=max_results)
    normalized = normalize_semantic_scholar_results(papers, query=query)
    return normalized


def search_crossref_structured(
    title: str | None = None,
    author: str | list[str] | None = None,
    keywords: str | list[str] | None = None,
    abstract_keywords: str | list[str] | None = None,
    max_results: int = 10,
) -> list[dict[str, Any]]:
    """
    使用结构化输入搜索 CrossRef。
    
    Args:
        title: 论文标题
        author: 作者名（字符串或列表）
        keywords: 关键词（字符串或列表）
        abstract_keywords: 摘要中的关键词（字符串或列表）
        max_results: 最大返回结果数
        
    Returns:
        归一化的结果列表
    """
    query = build_crossref_query(
        title=title,
        author=author,
        keywords=keywords,
        abstract_keywords=abstract_keywords,
    )
    
    if not query:
        logger.warning("Empty CrossRef query, returning empty results")
        return []
    
    items = query_crossref(query, max_results=max_results)
    normalized = normalize_crossref_results(items, query=query)
    return normalized


def search_arxiv_structured(
    title: str | None = None,
    author: str | list[str] | None = None,
    keywords: str | list[str] | None = None,
    abstract_keywords: str | list[str] | None = None,
    max_papers: int = 10,
) -> list[dict[str, Any]]:
    """
    使用结构化输入搜索 arXiv。
    
    Args:
        title: 论文标题
        author: 作者名（字符串或列表）
        keywords: 关键词（字符串或列表）
        abstract_keywords: 摘要中的关键词（字符串或列表）
        max_papers: 最大返回论文数
        
    Returns:
        归一化的结果列表
    """
    query = build_arxiv_query(
        title=title,
        author=author,
        keywords=keywords,
        abstract_keywords=abstract_keywords,
    )
    
    if not query:
        logger.warning("Empty arXiv query, returning empty results")
        return []
    
    arxiv_text = query_arxiv(query, max_papers=max_papers)
    normalized = normalize_arxiv_result(arxiv_text, query=query)
    return normalized


def search_scholar_structured(
    title: str | None = None,
    author: str | list[str] | None = None,
    keywords: str | list[str] | None = None,
    abstract_keywords: str | list[str] | None = None,
    max_results: int = 10,
) -> list[dict[str, Any]]:
    """
    使用结构化输入搜索 Google Scholar。
    
    Args:
        title: 论文标题
        author: 作者名（字符串或列表）
        keywords: 关键词（字符串或列表）
        abstract_keywords: 摘要中的关键词（字符串或列表）
        max_results: 最大返回结果数
        
    Returns:
        归一化的结果列表
    """
    query = build_scholar_query(
        title=title,
        author=author,
        keywords=keywords,
        abstract_keywords=abstract_keywords,
    )
    
    if not query:
        logger.warning("Empty Google Scholar query, returning empty results")
        return []
    
    scholar_text = query_scholar(query, max_results=max_results)
    normalized = normalize_scholar_result(scholar_text, query=query)
    return normalized


# 可选依赖处理
try:
    import arxiv
except ImportError:
    arxiv = None
    logger.warning("arxiv package not available, arXiv search will be disabled")

try:
    from scholarly import scholarly
except ImportError:
    scholarly = None
    logger.warning("scholarly package not available, Google Scholar search will be disabled")

try:
    from googlesearch import search as google_search_func
except ImportError:
    google_search_func = None
    logger.warning("googlesearch-python package not available, Google search will be disabled")

try:
    import anthropic
except ImportError:
    anthropic = None
    logger.warning("anthropic package not available, Claude web search will be disabled")

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    requests = None
    BeautifulSoup = None
    logger.warning("requests/beautifulsoup4 not available, web content extraction will be disabled")

try:
    import PyPDF2
    from io import BytesIO
except ImportError:
    PyPDF2 = None
    BytesIO = None
    logger.warning("PyPDF2 not available, PDF extraction will be disabled")


def fetch_supplementary_info_from_doi(doi: str, output_dir: str = "/tmp") -> dict[str, Any]:
    """
    从 DOI 获取补充材料信息
    
    Args:
        doi: DOI 标识符
        output_dir: 输出目录
        
    Returns:
        包含文件路径和日志的字典
    """
    if not requests:
        logger.error("requests not available for DOI supplementary fetch")
        return {"error": "requests package not available", "files": [], "log": []}
    
    try:
        # 构建 DOI URL
        doi_url = f"https://doi.org/{doi}"
        logger.debug(f"Fetching supplementary info from DOI: {doi_url}")
        
        # 获取 DOI 页面
        response = requests.get(doi_url, timeout=30, allow_redirects=True)
        response.raise_for_status()
        
        # 解析页面查找补充材料链接
        if BeautifulSoup:
            soup = BeautifulSoup(response.text, "html.parser")
            supplementary_links = []
            
            # 查找常见的补充材料链接模式
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                text = link.get_text().lower()
                if any(keyword in text for keyword in ["supplementary", "supplement", "additional", "data"]):
                    supplementary_links.append(href)
            
            log = [f"Found {len(supplementary_links)} potential supplementary material links"]
            
            return {
                "doi": doi,
                "doi_url": doi_url,
                "files": supplementary_links,
                "log": log,
            }
        else:
            return {
                "doi": doi,
                "doi_url": doi_url,
                "files": [],
                "log": ["BeautifulSoup not available for parsing"],
            }
    except Exception as exc:
        logger.error(f"Failed to fetch supplementary info from DOI {doi}", exc_info=True)
        return {
            "error": str(exc),
            "doi": doi,
            "files": [],
            "log": [f"Error: {str(exc)}"],
        }


def query_arxiv(query: str, max_papers: int = 10) -> str:
    """
    查询 arXiv 论文
    
    Args:
        query: 搜索查询
        max_papers: 最大返回论文数
        
    Returns:
        格式化的论文信息字符串
    """
    if not arxiv:
        logger.warning("arxiv package not available")
        return ""
    
    try:
        logger.debug(f"Searching arXiv with query: {query}")
        search = arxiv.Search(query=query, max_results=max_papers, sort_by=arxiv.SortCriterion.Relevance)
        
        results = []
        for paper in search.results():
            result = f"Title: {paper.title}\n"
            result += f"Authors: {', '.join([author.name for author in paper.authors])}\n"
            result += f"Published: {paper.published.strftime('%Y-%m-%d')}\n"
            result += f"Summary: {paper.summary[:500]}...\n"
            result += f"URL: {paper.entry_id}\n"
            result += f"arXiv ID: {paper.entry_id.split('/')[-1]}\n"
            result += "-" * 80 + "\n"
            results.append(result)
        
        output = "\n".join(results)
        logger.debug(f"Found {len(results)} arXiv papers")
        return output
    except Exception as exc:
        logger.error(f"arXiv search failed for query: {query}", exc_info=True)
        return f"Error searching arXiv: {str(exc)}"


def query_scholar(query: str, max_results: int = 5) -> str:
    """
    查询 Google Scholar
    
    Args:
        query: 搜索查询
        max_results: 最大返回结果数
        
    Returns:
        格式化的论文信息字符串
    """
    if not scholarly:
        logger.warning("scholarly package not available")
        return ""
    
    try:
        logger.debug(f"Searching Google Scholar with query: {query}")
        search_query = scholarly.search_pubs(query)
        
        results = []
        count = 0
        for pub in search_query:
            if count >= max_results:
                break
            
            result = f"Title: {pub.get('bib', {}).get('title', 'N/A')}\n"
            result += f"Authors: {', '.join(pub.get('bib', {}).get('author', []))}\n"
            result += f"Year: {pub.get('bib', {}).get('pub_year', 'N/A')}\n"
            result += f"Venue: {pub.get('bib', {}).get('venue', 'N/A')}\n"
            if pub.get('bib', {}).get('abstract'):
                result += f"Abstract: {pub['bib']['abstract'][:500]}...\n"
            if pub.get('eprint_url'):
                result += f"URL: {pub['eprint_url']}\n"
            result += "-" * 80 + "\n"
            results.append(result)
            count += 1
        
        output = "\n".join(results)
        logger.debug(f"Found {len(results)} Scholar results")
        return output
    except Exception as exc:
        logger.error(f"Google Scholar search failed for query: {query}", exc_info=True)
        return f"Error searching Google Scholar: {str(exc)}"


def search_google(query: str, num_results: int = 3, language: str = "en") -> list[dict[str, Any]]:
    """
    Google 搜索
    
    Args:
        query: 搜索查询
        num_results: 返回结果数
        language: 语言代码
        
    Returns:
        搜索结果列表
    """
    if not google_search_func:
        logger.warning("googlesearch-python package not available")
        return []
    
    try:
        logger.debug(f"Searching Google with query: {query}")
        results = []
        # 兼容不同版本的 googlesearch / googlesearch-python
        try:
            # 常见签名：search(query, num_results=..., lang=...)
            iterator = google_search_func(
                query, num_results=num_results, lang=language
            )
        except TypeError:
            # 旧版签名：search(query, num=..., stop=..., pause=..., lang=...)
            iterator = google_search_func(
                query, num=num_results, stop=num_results, pause=2, lang=language
            )

        for url in iterator:
            results.append({
                "url": url,
                "title": "",  # googlesearch-python 不返回标题，需要额外提取
                "snippet": "",
            })
        
        logger.debug(f"Found {len(results)} Google results")
        return results
    except Exception as exc:
        logger.error(f"Google search failed for query: {query}", exc_info=True)
        return []


def advanced_web_search_claude(
    query: str, max_searches: int = 2, max_retries: int = 3
) -> tuple[str, list[dict[str, Any]], list[str]]:
    """
    使用 Claude API 进行高级网络搜索
    
    Args:
        query: 搜索查询
        max_searches: 最大搜索次数
        max_retries: 最大重试次数
        
    Returns:
        (搜索结果文本, 引用列表, 错误列表)
    """
    if not anthropic:
        logger.warning("anthropic package not available")
        return "", [], ["anthropic package not available"]
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set")
        return "", [], ["ANTHROPIC_API_KEY not set"]
    
    try:
        client = anthropic.Anthropic(api_key=api_key)
        logger.debug(f"Performing Claude web search with query: {query}")
        
        # 使用 Claude 的 web search 工具
        # 注意：这需要 Claude API 支持 web search 功能
        # 如果 API 不支持，可以降级到普通对话模式
        
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            tools=[{
                "name": "web_search",
                "description": "Search the web for current information",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"}
                    },
                    "required": ["query"]
                }
            }],
            messages=[{
                "role": "user",
                "content": f"Please search the web for: {query}"
            }]
        )
        
        # 提取搜索结果
        search_results = []
        citations = []
        errors = []
        
        # 解析 Claude 响应
        # 这里需要根据实际的 API 响应格式进行调整
        if hasattr(message, "content") and message.content:
            for block in message.content:
                if hasattr(block, "text"):
                    search_results.append(block.text)
                if hasattr(block, "citations"):
                    citations.extend(block.citations)
        
        result_text = "\n".join(search_results) if search_results else ""
        logger.debug(f"Claude web search completed, found {len(citations)} citations")
        
        return result_text, citations, errors
    except Exception as exc:
        logger.error(f"Claude web search failed for query: {query}", exc_info=True)
        return "", [], [str(exc)]


def extract_url_content(url: str, timeout: int = 30) -> str:
    """
    提取 URL 内容
    
    Args:
        url: 目标 URL
        timeout: 超时时间（秒）
        
    Returns:
        提取的文本内容
    """
    if not requests or not BeautifulSoup:
        logger.warning("requests/BeautifulSoup not available for URL content extraction")
        return ""
    
    try:
        logger.debug(f"Extracting content from URL: {url}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, timeout=timeout, headers=headers, allow_redirects=True)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # 移除脚本和样式
        for script in soup(["script", "style"]):
            script.decompose()
        
        # 提取文本
        text = soup.get_text()
        # 清理文本
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = " ".join(chunk for chunk in chunks if chunk)
        
        logger.debug(f"Extracted {len(text)} characters from URL")
        return text[:10000]  # 限制长度
    except Exception as exc:
        logger.error(f"Failed to extract content from URL: {url}", exc_info=True)
        return f"Error extracting content: {str(exc)}"


def extract_pdf_content(url: str, timeout: int = 30) -> str:
    """
    提取 PDF 内容
    
    Args:
        url: PDF URL
        timeout: 超时时间（秒）
        
    Returns:
        提取的文本内容
    """
    if not requests or not PyPDF2 or not BytesIO:
        logger.warning("requests/PyPDF2 not available for PDF extraction")
        return ""
    
    try:
        logger.debug(f"Extracting content from PDF: {url}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, timeout=timeout, headers=headers, allow_redirects=True)
        response.raise_for_status()
        
        pdf_file = BytesIO(response.content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        text_parts = []
        for page_num, page in enumerate(pdf_reader.pages):
            if page_num >= 10:  # 限制页数
                break
            text = page.extract_text()
            if text:
                text_parts.append(text)
        
        content = "\n".join(text_parts)
        logger.debug(f"Extracted {len(content)} characters from PDF ({len(text_parts)} pages)")
        return content[:10000]  # 限制长度
    except Exception as exc:
        logger.error(f"Failed to extract content from PDF: {url}", exc_info=True)
        return f"Error extracting PDF content: {str(exc)}"


# ============= Normalize functions =============

def normalize_private_doc(raw_doc: dict[str, Any]) -> dict[str, Any]:
    """
    归一化私有文档
    """
    metadata = dict(raw_doc.get("metadata") or {})
    if raw_doc.get("score") is not None and "score" not in metadata:
        metadata["score"] = raw_doc["score"]

    snippet = raw_doc.get("snippet") or raw_doc.get("text") or ""
    title = raw_doc.get("title") or metadata.get("title")
    source_id = raw_doc.get("doc_id") or raw_doc.get("id") or metadata.get("doc_id")

    return {
        "source_id": str(source_id or ""),
        "title": title,
        "snippet": snippet,
        "source_type": "private",
        "metadata": metadata,
    }


def normalize_pubmed_article(article: dict[str, Any]) -> dict[str, Any]:
    """
    归一化 PubMed 文章，包含完整溯源信息。
    
    溯源信息包括：
    - source_name: 检索源名称
    - source_url: 原始检索URL/API端点
    - access_url: 可访问的文档URL
    - retrieval_timestamp: 检索时间戳
    - retrieval_method: 检索方法
    - citation: 引用信息（如果可用）
    """
    pmid = str(
        article.get("pmid")
        or article.get("pubmed_id")
        or article.get("id")
        or article.get("uid")
        or ""
    )
    
    year = article.get("year") or article.get("pubdate")
    journal = article.get("journal")
    title = article.get("title")
    abstract = article.get("abstract") or article.get("summary", "")
    doi = article.get("doi")
    authors = article.get("authors", [])
    
    metadata: dict[str, Any] = {}
    if year:
        metadata["year"] = year
    if journal:
        metadata["journal"] = journal
    
    # 添加溯源信息
    metadata["source_name"] = "PubMed"
    metadata["source_url"] = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    if pmid:
        metadata["access_url"] = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}"
    metadata["retrieval_timestamp"] = datetime.now(timezone.utc).isoformat()
    metadata["retrieval_method"] = "api"
    
    # 添加引用信息（如果可用）
    if authors and year and title and journal:
        authors_str = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
        citation = f"{authors_str} ({year}). {title}. {journal}."
        if doi:
            citation += f" doi:{doi}"
        metadata["citation"] = citation
    
    if doi:
        metadata["doi"] = doi
    if authors:
        metadata["authors"] = authors if isinstance(authors, list) else [authors]

    return {
        "source_id": pmid,
        "title": title,
        "snippet": abstract,
        "source_type": "literature",
        "metadata": metadata,
    }


def normalize_arxiv_result(arxiv_text: str, query: str) -> list[dict[str, Any]]:
    """
    归一化 arXiv 检索结果
    
    Args:
        arxiv_text: query_arxiv 返回的文本
        query: 原始查询
        
    Returns:
        归一化的结果列表
    """
    if not arxiv_text or "Error" in arxiv_text:
        return []
    
    results = []
    current_result: dict[str, Any] = {}
    lines = arxiv_text.split("\n")
    
    for line in lines:
        line = line.strip()
        if line.startswith("Title:"):
            if current_result:
                results.append(current_result)
            current_result = {
                "title": line.replace("Title:", "").strip(),
                "metadata": {
                    "source_name": "arXiv",
                    "source_url": "https://arxiv.org/search",
                    "retrieval_timestamp": datetime.now(timezone.utc).isoformat(),
                    "retrieval_method": "api",
                },
            }
        elif line.startswith("Authors:"):
            if current_result:
                authors = line.replace("Authors:", "").strip()
                current_result["metadata"]["authors"] = [a.strip() for a in authors.split(",")]
        elif line.startswith("Published:"):
            if current_result:
                current_result["metadata"]["year"] = line.replace("Published:", "").strip()[:4]
        elif line.startswith("Summary:"):
            if current_result:
                current_result["snippet"] = line.replace("Summary:", "").strip()
        elif line.startswith("URL:"):
            if current_result:
                url = line.replace("URL:", "").strip()
                current_result["metadata"]["access_url"] = url
                arxiv_id = url.split("/")[-1] if "/" in url else ""
                current_result["source_id"] = arxiv_id
        elif line.startswith("arXiv ID:"):
            if current_result:
                arxiv_id = line.replace("arXiv ID:", "").strip()
                current_result["source_id"] = arxiv_id
                if "access_url" not in current_result.get("metadata", {}):
                    current_result["metadata"]["access_url"] = f"https://arxiv.org/abs/{arxiv_id}"
    
    if current_result:
        results.append(current_result)
    
    # 添加完整的归一化字段
    normalized = []
    for r in results:
        normalized.append({
            "source_id": r.get("source_id", ""),
            "title": r.get("title", ""),
            "snippet": r.get("snippet", ""),
            "source_type": "literature",
            "metadata": r.get("metadata", {}),
        })
    
    return normalized


def normalize_scholar_result(scholar_text: str, query: str) -> list[dict[str, Any]]:
    """
    归一化 Google Scholar 检索结果
    
    Args:
        scholar_text: query_scholar 返回的文本
        query: 原始查询
        
    Returns:
        归一化的结果列表
    """
    if not scholar_text or "Error" in scholar_text:
        return []
    
    results = []
    current_result: dict[str, Any] = {}
    lines = scholar_text.split("\n")
    
    for line in lines:
        line = line.strip()
        if line.startswith("Title:"):
            if current_result:
                results.append(current_result)
            current_result = {
                "title": line.replace("Title:", "").strip(),
                "metadata": {
                    "source_name": "Google Scholar",
                    "source_url": "https://scholar.google.com",
                    "retrieval_timestamp": datetime.now(timezone.utc).isoformat(),
                    "retrieval_method": "api",
                },
            }
        elif line.startswith("Authors:"):
            if current_result:
                authors = line.replace("Authors:", "").strip()
                current_result["metadata"]["authors"] = [a.strip() for a in authors.split(",")]
        elif line.startswith("Year:"):
            if current_result:
                year = line.replace("Year:", "").strip()
                current_result["metadata"]["year"] = year
        elif line.startswith("Venue:"):
            if current_result:
                current_result["metadata"]["venue"] = line.replace("Venue:", "").strip()
        elif line.startswith("Abstract:"):
            if current_result:
                current_result["snippet"] = line.replace("Abstract:", "").strip()
        elif line.startswith("URL:"):
            if current_result:
                url = line.replace("URL:", "").strip()
                current_result["metadata"]["access_url"] = url
                current_result["source_id"] = url  # 使用 URL 作为 ID
    
    if current_result:
        results.append(current_result)
    
    # 添加完整的归一化字段
    normalized = []
    for r in results:
        normalized.append({
            "source_id": r.get("source_id", ""),
            "title": r.get("title", ""),
            "snippet": r.get("snippet", ""),
            "source_type": "literature",
            "metadata": r.get("metadata", {}),
        })
    
    return normalized


def normalize_google_result(google_results: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    """
    归一化 Google 搜索结果
    
    Args:
        google_results: search_google 返回的结果列表
        query: 原始查询
        
    Returns:
        归一化的结果列表
    """
    normalized = []
    for result in google_results:
        url = result.get("url", "")
        title = result.get("title", "")
        snippet = result.get("snippet", "")
        
        normalized.append({
            "source_id": url,
            "title": title or url,
            "snippet": snippet,
            "source_type": "web",
            "metadata": {
                "source_name": "Google Search",
                "source_url": "https://www.google.com/search",
                "access_url": url,
                "retrieval_timestamp": datetime.now(timezone.utc).isoformat(),
                "retrieval_method": "api",
            },
        })
    
    return normalized


def normalize_claude_result(
    claude_text: str, citations: list[dict[str, Any]], query: str
) -> list[dict[str, Any]]:
    """
    归一化 Claude 网络搜索结果
    
    Args:
        claude_text: advanced_web_search_claude 返回的文本
        citations: 引用列表
        query: 原始查询
        
    Returns:
        归一化的结果列表
    """
    normalized = []
    
    # 从 citations 创建结果
    for citation in citations:
        url = citation.get("url", "")
        title = citation.get("title", "")
        
        normalized.append({
            "source_id": url or f"claude_citation_{len(normalized)}",
            "title": title or url,
            "snippet": claude_text[:500] if claude_text else "",
            "source_type": "web",
            "metadata": {
                "source_name": "Claude Web Search",
                "source_url": "https://api.anthropic.com",
                "access_url": url,
                "retrieval_timestamp": datetime.now(timezone.utc).isoformat(),
                "retrieval_method": "api",
            },
        })
    
    # 如果没有 citations，创建一个基于文本的结果
    if not normalized and claude_text:
        normalized.append({
            "source_id": f"claude_search_{query[:20]}",
            "title": f"Claude Search Results for: {query}",
            "snippet": claude_text[:1000],
            "source_type": "web",
            "metadata": {
                "source_name": "Claude Web Search",
                "source_url": "https://api.anthropic.com",
                "retrieval_timestamp": datetime.now(timezone.utc).isoformat(),
                "retrieval_method": "api",
            },
        })
    
    return normalized


# ============= PubMed / CrossRef / Semantic Scholar =============


def query_pubmed_api(query: str, max_results: int = 10) -> list[dict[str, Any]]:
    """
    使用项目内封装好的 PubMedAPI 进行检索，并返回结构化结果列表。
    
    注意：这是对 `textmsa.knowledge.pubmed_api` 的轻量封装，便于在 tools 层复用。
    """
    if not get_pubmed_api or not PubMedAPI:
        logger.warning("PubMedAPI not available (get_pubmed_api import failed)")
        return []
    
    try:
        api: PubMedAPI = get_pubmed_api()  # type: ignore[assignment]
        logger.debug(f"Searching PubMed API with query: {query}, max_results={max_results}")
        articles = api.search_articles(query, max_results=max_results)
        # 返回原始结构，由上层调用 `normalize_pubmed_article` 进行归一化
        logger.debug("PubMed API returned %d articles", len(articles))
        return articles
    except Exception as exc:
        logger.error("PubMed API search failed for query: %s", query, exc_info=True)
        return []


def query_crossref(query: str, max_results: int = 10) -> list[dict[str, Any]]:
    """
    使用 CrossRef API 检索文献。
    
    Docs: https://api.crossref.org/swagger-ui/index.html#/Works/get_works
    
    Returns:
        CrossRef `items` 的子集列表（每个元素是一个 dict），由上层进行归一化。
    """
    if not requests:
        logger.warning("requests not available, CrossRef search disabled")
        return []
    
    url = "https://api.crossref.org/works"
    params = {
        "query": query,
        "rows": max_results,
    }
    
    try:
        logger.debug("Searching CrossRef with query: %s", query)
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        items = (data.get("message") or {}).get("items") or []
        logger.debug("CrossRef returned %d items", len(items))
        return items[:max_results]
    except Exception as exc:
        logger.error("CrossRef search failed for query: %s", query, exc_info=True)
        return []


def normalize_crossref_results(
    items: list[dict[str, Any]], query: str
) -> list[dict[str, Any]]:
    """
    归一化 CrossRef 检索结果。
    """
    normalized: list[dict[str, Any]] = []
    for it in items:
        doi = (it.get("DOI") or "") if isinstance(it.get("DOI"), str) else ""
        titles = it.get("title") or []
        title = titles[0] if titles else ""
        abstract = it.get("abstract") or ""
        container_title = it.get("container-title") or []
        journal = container_title[0] if container_title else ""
        year = None
        issued = it.get("issued") or {}
        date_parts = (issued.get("date-parts") or [[]])
        if date_parts and date_parts[0]:
            year = date_parts[0][0]
        
        authors_raw = it.get("author") or []
        authors: list[str] = []
        for a in authors_raw:
            given = a.get("given") or ""
            family = a.get("family") or ""
            full = " ".join([given, family]).strip()
            if full:
                authors.append(full)
        
        metadata: dict[str, Any] = {
            "source_name": "CrossRef",
            "source_url": "https://api.crossref.org/works",
            "retrieval_timestamp": datetime.now(timezone.utc).isoformat(),
            "retrieval_method": "api",
        }
        if journal:
            metadata["journal"] = journal
        if year:
            metadata["year"] = year
        if doi:
            metadata["doi"] = doi
        if authors:
            metadata["authors"] = authors
        
        # 生成简单 citation
        if authors and year and title and journal:
            authors_str = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
            citation = f"{authors_str} ({year}). {title}. {journal}."
            if doi:
                citation += f" doi:{doi}"
            metadata["citation"] = citation
        
        normalized.append(
            {
                "source_id": doi or it.get("URL") or "",
                "title": title or query,
                "snippet": abstract,
                "source_type": "literature",
                "metadata": metadata,
            }
        )
    
    return normalized


def query_semantic_scholar(query: str, max_results: int = 10) -> list[dict[str, Any]]:
    """
    使用 Semantic Scholar Graph API 检索论文。
    
    Docs: https://api.semanticscholar.org/api-docs/graph
    
    环境变量:
        SEMANTIC_SCHOLAR_API_KEY (可选): 若提供则通过 header 发送。
    """
    if not requests:
        logger.warning("requests not available, Semantic Scholar search disabled")
        return []
    
    base_url = "https://api.semanticscholar.org/graph/v1/paper/search"
    fields = [
        "title",
        "abstract",
        "year",
        "venue",
        "authors",
        "url",
        "externalIds",
        "isOpenAccess",
    ]
    params = {
        "query": query,
        "limit": max_results,
        "fields": ",".join(fields),
    }
    
    headers: dict[str, str] = {}
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    
    try:
        logger.debug("Searching Semantic Scholar with query: %s", query)
        resp = requests.get(base_url, params=params, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        papers = data.get("data") or []
        logger.debug("Semantic Scholar returned %d papers", len(papers))
        return papers[:max_results]
    except Exception as exc:
        logger.error(
            "Semantic Scholar search failed for query: %s", query, exc_info=True
        )
        return []


def normalize_semantic_scholar_results(
    papers: list[dict[str, Any]], query: str
) -> list[dict[str, Any]]:
    """
    归一化 Semantic Scholar 检索结果。
    """
    normalized: list[dict[str, Any]] = []
    for p in papers:
        title = p.get("title") or ""
        abstract = p.get("abstract") or ""
        year = p.get("year")
        venue = p.get("venue")
        url = p.get("url") or ""
        external_ids = p.get("externalIds") or {}
        doi = external_ids.get("DOI") or ""
        paper_id = p.get("paperId") or ""
        
        authors_raw = p.get("authors") or []
        authors: list[str] = []
        for a in authors_raw:
            name = a.get("name") or ""
            if name:
                authors.append(name)
        
        metadata: dict[str, Any] = {
            "source_name": "Semantic Scholar",
            "source_url": "https://api.semanticscholar.org",
            "retrieval_timestamp": datetime.now(timezone.utc).isoformat(),
            "retrieval_method": "api",
        }
        if venue:
            metadata["venue"] = venue
        if year:
            metadata["year"] = year
        if doi:
            metadata["doi"] = doi
        if url:
            metadata["access_url"] = url
        if authors:
            metadata["authors"] = authors
        
        if authors and year and title and venue:
            authors_str = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
            citation = f"{authors_str} ({year}). {title}. {venue}."
            if doi:
                citation += f" doi:{doi}"
            metadata["citation"] = citation
        
        source_id = doi or paper_id or url
        normalized.append(
            {
                "source_id": source_id,
                "title": title or query,
                "snippet": abstract,
                "source_type": "literature",
                "metadata": metadata,
            }
        )
    
    return normalized

