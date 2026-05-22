"""
Knowledge search service public entrypoints.
"""
from __future__ import annotations

from functools import lru_cache

from textmsa.services.knowledge_service.service import KnowledgeSearchService


@lru_cache(maxsize=1)
def get_knowledge_search_service() -> KnowledgeSearchService:
    """Return a singleton instance for reuse across requests."""
    return KnowledgeSearchService()


__all__ = ["KnowledgeSearchService", "get_knowledge_search_service"]

