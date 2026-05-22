"""
Knowledge service package.
Provides helper to access the singleton KnowledgeService.
"""
from .knowledge_service import get_knowledge_service, KnowledgeService

__all__ = ["get_knowledge_service", "KnowledgeService"]
