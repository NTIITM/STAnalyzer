"""Datasource implementations for knowledge search."""
from __future__ import annotations

import asyncio
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

import httpx

from textmsa.logging_config import get_logger
from textmsa.services.knowledge_service.models import KnowledgeDocument

logger = get_logger(__name__)


class DataSource:
    name: str

    async def fetch(self, query: str, top_k: int) -> List[KnowledgeDocument]:  # pragma: no cover - interface
        raise NotImplementedError


class PubMedDataSource(DataSource):
    name = "pubmed"
    _ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    _ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    _EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

    async def fetch(self, query: str, top_k: int) -> List[KnowledgeDocument]:
        if not query:
            return []
        async with httpx.AsyncClient(timeout=10.0) as client:
            search_resp = await client.get(
                self._ESEARCH_URL,
                params={"db": "pubmed", "term": query, "retmode": "json", "retmax": top_k},
            )
            search_resp.raise_for_status()
            search_data = search_resp.json()
            id_list = search_data.get("esearchresult", {}).get("idlist", [])
            if not id_list:
                return []

            summary_resp = await client.get(
                self._ESUMMARY_URL,
                params={"db": "pubmed", "id": ",".join(id_list), "retmode": "json"},
            )
            summary_resp.raise_for_status()
            summary_data = summary_resp.json().get("result", {})

            # 使用 efetch 获取摘要
            abstracts_dict: Dict[str, str] = {}
            try:
                fetch_resp = await client.get(
                    self._EFETCH_URL,
                    params={"db": "pubmed", "id": ",".join(id_list), "retmode": "xml"},
                )
                fetch_resp.raise_for_status()
                fetch_xml = fetch_resp.text
                abstracts_dict = self._extract_abstracts_from_xml(fetch_xml, id_list)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to fetch abstracts from PubMed efetch API: %s", exc)

        documents: List[KnowledgeDocument] = []
        for uid in id_list:
            doc = summary_data.get(uid) or {}
            title = doc.get("title") or ""
            pubdate = doc.get("pubdate") or doc.get("epubdate") or ""
            article_ids = doc.get("articleids") or []
            doi = None
            for item in article_ids:
                if item.get("idtype") == "doi":
                    doi = item.get("value")
                    break
            authors = [a.get("name") for a in doc.get("authors") or [] if a.get("name")]
            # 使用从 efetch 获取的摘要，如果没有则使用空字符串
            snippet = abstracts_dict.get(uid, "")
            documents.append(
                KnowledgeDocument(
                    source=self.name,
                    title=title,
                    snippet=snippet,
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
                    doi=doi,
                    published_at=pubdate,
                    authors=authors,
                    journal=doc.get("fulljournalname"),
                    source_type=doc.get("pubtype", ["article"])[0] if doc.get("pubtype") else None,
                    metadata={"uid": uid},
                )
            )
        return documents

    def _extract_abstracts_from_xml(self, xml_content: str, id_list: List[str]) -> Dict[str, str]:
        """从 PubMed efetch XML 响应中提取摘要"""
        abstracts: Dict[str, str] = {}
        try:
            root = ET.fromstring(xml_content)
            # PubMed XML 命名空间
            ns = {"pubmed": "http://www.ncbi.nlm.nih.gov"}
            
            # 查找所有 PubmedArticle 元素
            articles = root.findall(".//PubmedArticle", ns) or root.findall(".//PubmedArticle")
            
            for article in articles:
                # 提取 PMID
                pmid_elem = article.find(".//PMID", ns) or article.find(".//PMID")
                if pmid_elem is None or pmid_elem.text is None:
                    continue
                pmid = pmid_elem.text.strip()
                
                # 提取摘要
                abstract_elem = article.find(".//AbstractText", ns) or article.find(".//AbstractText")
                if abstract_elem is not None:
                    # 收集所有文本内容（包括子元素的文本）
                    abstract_parts = []
                    if abstract_elem.text:
                        abstract_parts.append(abstract_elem.text.strip())
                    
                    # 处理子元素（AbstractText 可能包含多个段落）
                    for child in abstract_elem:
                        if child.text:
                            abstract_parts.append(child.text.strip())
                        if child.tail:
                            abstract_parts.append(child.tail.strip())
                    
                    abstract_text = " ".join([p for p in abstract_parts if p])
                    if abstract_text:
                        abstracts[pmid] = abstract_text
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to parse PubMed XML for abstracts: %s", exc)
        
        return abstracts


class CrossRefDataSource(DataSource):
    name = "crossref"
    _URL = "https://api.crossref.org/works"

    async def fetch(self, query: str, top_k: int) -> List[KnowledgeDocument]:
        if not query:
            return []
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(self._URL, params={"query": query, "rows": top_k})
            resp.raise_for_status()
            data = resp.json().get("message", {})

        items = data.get("items") or []
        documents: List[KnowledgeDocument] = []
        for item in items:
            doi = item.get("DOI")
            title_list = item.get("title") or []
            title = title_list[0] if title_list else ""
            authors = []
            for author in item.get("author") or []:
                name_parts = [author.get("given"), author.get("family")]
                authors.append(" ".join([p for p in name_parts if p]))
            published = item.get("published-print") or item.get("published-online") or {}
            date_parts = published.get("date-parts") or []
            published_at = None
            if date_parts and isinstance(date_parts[0], list):
                published_at = "-".join(str(p) for p in date_parts[0] if p is not None)
            # 提取摘要：abstract 字段可能包含 HTML，需要清理
            abstract = item.get("abstract")
            snippet = ""
            if abstract:
                # 如果 abstract 是字符串，直接使用
                if isinstance(abstract, str):
                    snippet = abstract
                # 如果 abstract 是字典，可能包含其他格式
                elif isinstance(abstract, dict):
                    snippet = abstract.get("text", "") or abstract.get("value", "")
                # 移除 HTML 标签（简单处理）
                if snippet:
                    snippet = re.sub(r"<[^>]+>", "", snippet).strip()
            
            documents.append(
                KnowledgeDocument(
                    source=self.name,
                    title=title,
                    snippet=snippet,
                    url=item.get("URL"),
                    doi=doi,
                    published_at=published_at,
                    authors=[a for a in authors if a],
                    journal=(item.get("container-title") or [""])[0],
                    source_type=item.get("type"),
                    score=item.get("score"),
                    metadata={"publisher": item.get("publisher")},
                )
            )
        return documents


class ArxivDataSource(DataSource):
    name = "arxiv"
    _URL = "http://export.arxiv.org/api/query"
    _WHITESPACE_RE = re.compile(r"\s+")

    async def fetch(self, query: str, top_k: int) -> List[KnowledgeDocument]:
        if not query:
            return []
        params = {"search_query": query, "start": 0, "max_results": top_k}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(self._URL, params=params)
            resp.raise_for_status()
            content = resp.text

        documents: List[KnowledgeDocument] = []
        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            logger.warning("Failed to parse arXiv response")
            return documents

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("atom:entry", ns):
            title = _text(entry.find("atom:title", ns))
            summary = _text(entry.find("atom:summary", ns))
            link_el = entry.find("atom:link[@type='text/html']", ns)
            link = link_el.get("href") if link_el is not None else None
            doi_el = entry.find("atom:doi", ns)
            doi = doi_el.text.strip() if doi_el is not None and doi_el.text else None
            published = _text(entry.find("atom:published", ns))
            authors = [_text(a.find("atom:name", ns)) for a in entry.findall("atom:author", ns)]
            documents.append(
                KnowledgeDocument(
                    source=self.name,
                    title=title,
                    snippet=self._clean_whitespace(summary),
                    url=link,
                    doi=doi,
                    published_at=published,
                    authors=[a for a in authors if a],
                    journal="arXiv",
                    source_type="preprint",
                )
            )
        return documents

    def _clean_whitespace(self, text: Optional[str]) -> str:
        if not text:
            return ""
        return self._WHITESPACE_RE.sub(" ", text).strip()


def _text(element: Optional[ET.Element]) -> str:
    if element is None or element.text is None:
        return ""
    return element.text.strip()

