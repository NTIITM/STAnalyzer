from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from textmsa.logging_config import get_logger
from textmsa.services.agent.reranker_client import (
    RerankRequest,
    RerankerClient,
    get_reranker_client,
)
from textmsa.services.data.mongodb_models import Memory, MemoryCollection
from textmsa.services.data.user_data_manager_mongodb import (
    UserDataManagerMongoDB,
    get_user_data_manager,
)

from .bm25_retriever import MultiLanguageBM25Retriever
from .memory_summarizer import MemorySummarizer

logger = get_logger(__name__)


class MemoryService:
    """记忆管理服务，封装检索 / 摘要 / 存储逻辑。"""

    def __init__(
        self,
        *,
        user_data_manager: Optional[UserDataManagerMongoDB] = None,
        bm25_retriever: Optional[MultiLanguageBM25Retriever] = None,
        memory_summarizer: Optional[MemorySummarizer] = None,
        reranker_client: Optional[RerankerClient] = None,
    ) -> None:
        self.user_data_manager = user_data_manager or get_user_data_manager()
        self.bm25_retriever = bm25_retriever or MultiLanguageBM25Retriever()
        self.memory_summarizer = memory_summarizer or MemorySummarizer()
        self.reranker_client = reranker_client or get_reranker_client()

    async def retrieve_memories(
        self,
        *,
        query: str,
        project_id: str,
        top_k: int = 10,
        language: Optional[str] = None,
        use_reranker: bool = True,
    ) -> List[Dict[str, Any]]:
        """检索与 query 相关的记忆。"""
        collection = self.user_data_manager.get_memory_collection(project_id)
        if not collection or not collection.memory_list:
            return []

        bm25_results = self.bm25_retriever.retrieve(
            query=query,
            memories=collection.memory_list,
            top_k=max(top_k, 10),
            language=language,
        )
        if not use_reranker or len(bm25_results) <= top_k:
            return bm25_results[:top_k]

        try:
            reranked = await self._rerank_memories(
                query=query,
                bm25_results=bm25_results,
                top_k=top_k,
            )
            return reranked
        except Exception as exc:  # pragma: no cover - 兜底防止影响主流程
            logger.error("记忆 Reranker 失败，退回 BM25 排序: %s", exc, exc_info=True)
            return bm25_results[:top_k]

    async def summarize_memories(
        self,
        *,
        messages: List[Dict[str, str]],
        project_id: str,
        max_memories: int = 10,
    ) -> List[Memory]:
        """从对话历史中提取记忆。"""
        return await self.memory_summarizer.summarize(
            messages=messages,
            project_id=project_id,
            max_memories=max_memories,
        )

    async def add_memories(
        self,
        *,
        project_id: str,
        memories: List[Memory],
    ) -> MemoryCollection:
        """向项目追加记忆。"""
        return self.user_data_manager.add_memories(project_id, memories)

    async def _rerank_memories(
        self,
        *,
        query: str,
        bm25_results: List[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """使用 Reranker 对 BM25 结果进行精排。"""
        documents = [item.get("content", "") for item in bm25_results]
        request = RerankRequest(query=query, documents=documents, top_n=top_k)

        def _call_sync() -> Any:
            return self.reranker_client.rerank(request)

        response = await asyncio.to_thread(_call_sync)
        reranked: List[Dict[str, Any]] = []
        for r in response.results:
            idx = r.index
            if 0 <= idx < len(bm25_results):
                base = dict(bm25_results[idx])
                base["reranker_score"] = r.score
                reranked.append(base)

        # 按 reranker_score 降序排序
        reranked.sort(key=lambda x: float(x.get("reranker_score", 0.0)), reverse=True)
        return reranked[:top_k]


_MEMORY_SERVICE: Optional[MemoryService] = None


def get_memory_service() -> MemoryService:
    """获取记忆服务单例。"""
    global _MEMORY_SERVICE
    if _MEMORY_SERVICE is None:
        _MEMORY_SERVICE = MemoryService()
    return _MEMORY_SERVICE


