"""Knowledge search orchestration."""
from __future__ import annotations

import asyncio
import re
from typing import Dict, Iterable, List, Optional

from textmsa.logging_config import get_logger
from textmsa.services.agent.reranker_client import (
    RerankRequest,
    get_reranker_client,
)
from textmsa.services.knowledge_service.config import get_project_sources
from textmsa.services.knowledge_service.datasources import (
    ArxivDataSource,
    CrossRefDataSource,
    DataSource,
    PubMedDataSource,
)
from textmsa.services.knowledge_service.llm_client import rewrite_query_with_llm
from textmsa.services.knowledge_service.models import (
    KnowledgeDocument,
    KnowledgeSearchResult,
)

logger = get_logger(__name__)


class KnowledgeSearchService:
    def __init__(self) -> None:
        self._datasources: Dict[str, DataSource] = {
            "pubmed": PubMedDataSource(),
            "arxiv": ArxivDataSource(),
            "crossref": CrossRefDataSource(),
        }

    async def run(
        self,
        query: str,
        project_id: str,
        *,
        top_k: int = 20,
        rewrite: bool = True,
        sources: Optional[List[str]] = None,
        language: str = "zh",
        trace: bool = False,
    ) -> KnowledgeSearchResult:
        if not query:
            raise ValueError("query is required")

        # 先获取选择的数据源
        chosen_sources = self._resolve_sources(project_id, sources)
        
        # 为每个数据源生成查询语句
        queries_dict: Dict[str, str] = {}
        usage: Optional[Dict[str, object]] = None
        
        if rewrite:
            try:
                queries_dict, usage = await rewrite_query_with_llm(
                    query, project_id, chosen_sources, language=language
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("LLM rewrite failed, fallback to raw query: %s", exc)
                # 如果重写失败，为所有数据源使用原始查询
                queries_dict = {source: query for source in chosen_sources}
        else:
            # 如果不重写，为所有数据源使用原始查询
            queries_dict = {source: query for source in chosen_sources}

        # 为每个数据源使用对应的查询语句进行检索
        tasks = [
            self._fetch_source(name, queries_dict.get(name, query), top_k)
            for name in chosen_sources
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        documents: List[KnowledgeDocument] = []
        errors: List[Dict[str, object]] = []
        for name, result in zip(chosen_sources, results):
            if isinstance(result, Exception):
                errors.append({"source": name, "error": str(result)})
                logger.warning("Datasource %s failed: %s", name, result)
                continue
            documents.extend(result)
        
        # 过滤掉图片等非文本内容
        documents = self._filter_non_text_content(documents)
        
        # 先去重，避免对重复文档进行 rerank
        deduped = self._deduplicate(documents)
        
        # 使用 Reranker 对去重后的数据进行重排
        if deduped:
            try:
                deduped = await self._rerank_documents(query, deduped, top_k)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Reranker failed, using original order: %s", exc)
                # 如果 rerank 失败，继续使用原始顺序
        
        # 限制返回数量
        limited = deduped[:top_k]

        # 将查询字典转换为字符串用于返回（兼容原有接口）
        rewrite_query = str(queries_dict) if queries_dict else query

        return KnowledgeSearchResult(
            rewrite_query=rewrite_query,
            datasources_used=chosen_sources,
            documents=limited,
            usage=usage if trace else None,
            errors=errors,
        )

    def _resolve_sources(self, project_id: str, requested: Optional[Iterable[str]]) -> List[str]:
        allowed = {s.lower(): s for s in get_project_sources(project_id)}
        if requested:
            selected = []
            for s in requested:
                key = s.lower()
                if key in allowed:
                    selected.append(allowed[key])
            return selected or list(allowed.values())
        return list(allowed.values())

    async def _fetch_source(self, name: str, query: str, top_k: int) -> List[KnowledgeDocument]:
        datasource = self._datasources.get(name)
        if not datasource:
            raise ValueError(f"Unknown datasource: {name}")
        return await datasource.fetch(query, top_k)

    async def _rerank_documents(
        self,
        query: str,
        documents: List[KnowledgeDocument],
        top_k: int,
    ) -> List[KnowledgeDocument]:
        """使用 Reranker 对文档进行重排。
        
        Args:
            query: 用户查询
            documents: 待重排的文档列表
            top_k: 返回的文档数量上限
            
        Returns:
            重排后的文档列表
        """
        if not documents:
            return documents
        
        # 将文档转换为文本格式（标题 + 摘要）
        # 过滤掉空文档，并维护索引映射
        doc_texts = []
        valid_indices = []  # 记录有效文档在原始列表中的索引
        for idx, doc in enumerate(documents):
            text_parts = []
            if doc.title:
                text_parts.append(str(doc.title))
            if doc.snippet:
                text_parts.append(str(doc.snippet))
            doc_text = "\n".join(text_parts).strip()
            
            # 只添加非空文档
            if doc_text:
                doc_texts.append(doc_text)
                valid_indices.append(idx)
            else:
                # 输出空文档的详细信息以便排查
                doc_info = {
                    "index": idx,
                    "source": doc.source,
                    "title": doc.title,
                    "snippet": doc.snippet,
                    "url": doc.url,
                    "doi": doc.doi,
                    "authors": doc.authors,
                    "journal": doc.journal,
                    "published_at": doc.published_at,
                    "source_type": doc.source_type,
                }
                logger.warning(
                    "文档索引 %d 的 title 和 snippet 都为空，跳过 rerank。文档信息: %s",
                    idx,
                    doc_info,
                )
        
        # 如果所有文档文本都为空，跳过 rerank
        if not doc_texts:
            logger.warning("所有文档文本为空，跳过 rerank")
            return documents
        
        # 如果有效文档数量少于原始文档数量，记录警告
        if len(valid_indices) < len(documents):
            logger.info(
                "过滤了 %d 个空文档，剩余 %d 个有效文档进行 rerank",
                len(documents) - len(valid_indices),
                len(valid_indices)
            )
        
        try:
            reranker = get_reranker_client()
            request = RerankRequest(
                query=query,
                documents=doc_texts,
                top_n=min(top_k, len(doc_texts)),  # 确保 top_n 不超过有效文档数
            )
            
            # 在线程中运行同步的 rerank 方法
            def _call() -> List[KnowledgeDocument]:
                response = reranker.rerank(request)
                # 根据 rerank 结果重新排序文档
                reranked_docs = []
                for result in response.results:
                    # result.index 是 doc_texts 中的索引，需要映射回原始 documents 的索引
                    valid_idx = result.index
                    if 0 <= valid_idx < len(valid_indices):
                        original_idx = valid_indices[valid_idx]
                        if 0 <= original_idx < len(documents):
                            doc = documents[original_idx]
                            # 更新文档的 score 字段
                            doc.score = result.score
                            reranked_docs.append(doc)
                return reranked_docs
            
            reranked_docs = await asyncio.to_thread(_call)
            logger.info(
                "Reranker completed: %d documents reranked, top %d returned",
                len(documents),
                len(reranked_docs),
            )
            return reranked_docs
        except Exception as exc:  # noqa: BLE001
            logger.error("Reranker error: %s", exc, exc_info=True)
            raise

    def _filter_non_text_content(self, documents: List[KnowledgeDocument]) -> List[KnowledgeDocument]:
        """过滤掉图片等非文本内容。
        
        Args:
            documents: 待过滤的文档列表
            
        Returns:
            过滤后的文档列表
        """
        # 图片文件扩展名列表
        image_extensions = {
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif',
            '.webp', '.svg', '.ico', '.heic', '.heif', '.raw', '.cr2',
            '.nef', '.orf', '.sr2', '.psd', '.ai', '.eps'
        }
        
        # 图片相关的source_type关键词
        image_source_types = {'image', 'figure', 'picture', 'photo', 'illustration', 'graphic'}
        
        filtered_docs: List[KnowledgeDocument] = []
        filtered_count = 0
        
        for doc in documents:
            should_filter = False
            filter_reason = None
            
            # 1. 检查URL是否是图片文件
            if doc.url:
                url_lower = doc.url.lower()
                # 检查URL路径中是否包含图片扩展名
                for ext in image_extensions:
                    if ext in url_lower:
                        # 确保是文件扩展名，而不是URL路径的一部分
                        # 使用正则表达式匹配文件扩展名模式
                        pattern = rf'{re.escape(ext)}(?:[?#]|$)'
                        if re.search(pattern, url_lower):
                            should_filter = True
                            filter_reason = f"URL包含图片扩展名: {ext}"
                            break
            
            # 2. 检查source_type是否是图片类型
            if not should_filter and doc.source_type:
                source_type_lower = doc.source_type.lower()
                if any(keyword in source_type_lower for keyword in image_source_types):
                    should_filter = True
                    filter_reason = f"source_type为图片类型: {doc.source_type}"
            
            # 3. 检查metadata中是否包含图片标识
            if not should_filter and doc.metadata:
                metadata_str = str(doc.metadata).lower()
                # 检查metadata中是否包含图片相关的关键词
                image_keywords = ['image', 'figure', 'picture', 'photo', 'illustration', 'graphic', 'img']
                if any(keyword in metadata_str for keyword in image_keywords):
                    # 进一步检查是否是明确的图片类型标识
                    if any(f'"{keyword}"' in metadata_str or f"'{keyword}'" in metadata_str 
                           for keyword in image_keywords):
                        should_filter = True
                        filter_reason = "metadata中包含图片标识"
            
            if should_filter:
                filtered_count += 1
                logger.debug(
                    "过滤掉非文本内容文档: source=%s, title=%s, reason=%s",
                    doc.source,
                    doc.title[:50] if doc.title else "N/A",
                    filter_reason
                )
            else:
                filtered_docs.append(doc)
        
        if filtered_count > 0:
            logger.info(
                "过滤了 %d 个图片/非文本内容文档，剩余 %d 个文档",
                filtered_count,
                len(filtered_docs)
            )
        
        return filtered_docs

    def _deduplicate(self, documents: List[KnowledgeDocument]) -> List[KnowledgeDocument]:
        seen_keys: set[str] = set()
        unique_docs: List[KnowledgeDocument] = []
        for doc in documents:
            key = (doc.doi or "").lower().strip()
            if not key:
                key = doc.title.lower().strip()
            if key in seen_keys:
                continue
            seen_keys.add(key)
            unique_docs.append(doc)
        return unique_docs

