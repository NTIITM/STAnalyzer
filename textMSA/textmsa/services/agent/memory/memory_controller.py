"""
Memory controller interface for managing conversation context and history.

This module defines the abstract base class for memory controllers, which
handle conversation history management, context preparation, and optional
memory updates.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class MemoryController(ABC):
    """
    Abstract base class for memory controllers.

    Memory controllers are responsible for:
    1. Preparing context from conversation history (truncation, summarization, etc.)
    2. Optionally updating memory after conversations (for long-term memory)

    Different implementations can use different strategies:
    - SimpleMemoryController: Sliding window truncation
    - AdvancedMemoryController: Summarization + vector retrieval
    """

    @abstractmethod
    async def prepare_context(
        self,
        user_id: str,
        project_id: str,
        user_query: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Prepare context from conversation history and query.

        This method processes the conversation history (truncation, summarization,
        etc.) and returns a formatted context dictionary that will be passed to
        the workflow.

        Args:
            user_id: User identifier
            project_id: Project identifier
            user_query: Current user query
            conversation_history: Optional list of previous conversation messages.
                Each message is a dict with at least "role" and "content" keys.

        Returns:
            Dictionary containing:
            - conversation_history: List[Dict[str, Any]] - Processed conversation history
            - context_summary: Optional[str] - Optional summary of older context
            - total_tokens: int - Estimated total token count
            - Additional implementation-specific fields
        """
        ...

    async def update_memory(
        self,
        user_id: str,
        project_id: str,
        conversation_id: str,
        user_message: str,
        assistant_response: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Update memory after a conversation (optional).

        This method can be used to store conversation data for long-term memory
        management. Simple implementations may leave this as a no-op.

        Args:
            user_id: User identifier
            project_id: Project identifier
            conversation_id: Conversation identifier
            user_message: User's message
            assistant_response: Assistant's response
            metadata: Optional additional metadata
        """
        # Default implementation is a no-op
        pass
