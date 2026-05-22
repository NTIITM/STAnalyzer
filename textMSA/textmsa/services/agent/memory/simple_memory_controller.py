"""
Simple memory controller implementation using sliding window truncation.

This implementation uses a simple strategy:
- Keep the most recent N messages (max_history_messages)
- If total length exceeds max_context_length, further truncate from the beginning
"""

from __future__ import annotations

from typing import Any

from textmsa.services.agent.memory.memory_controller import MemoryController


class SimpleMemoryController(MemoryController):
    """
    Simple memory controller using sliding window truncation.

    This controller:
    1. Truncates conversation history to the most recent N messages
    2. Further truncates if total length exceeds max_context_length
    3. Does not perform any long-term memory updates
    """

    def __init__(
        self,
        max_history_messages: int = 10,
        max_context_length: int = 4000,
    ) -> None:
        """
        Initialize the simple memory controller.

        Args:
            max_history_messages: Maximum number of messages to keep
            max_context_length: Maximum total context length (rough token estimate)
        """
        self.max_history_messages = max_history_messages
        self.max_context_length = max_context_length

    async def prepare_context(
        self,
        user_id: str,
        project_id: str,
        user_query: str,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Prepare context by truncating conversation history.

        Args:
            user_id: User identifier (unused in simple implementation)
            project_id: Project identifier (unused in simple implementation)
            user_query: Current user query (unused in simple implementation)
            conversation_history: Optional list of previous messages

        Returns:
            Dictionary with:
            - conversation_history: List of processed messages
            - context_summary: None (simple implementation doesn't summarize)
            - total_tokens: Estimated token count
        """
        # Handle empty or None history
        if not conversation_history:
            return {
                "conversation_history": [],
                "context_summary": None,
                "total_tokens": 0,
            }

        # Step 1: Truncate to most recent N messages
        truncated_history = conversation_history[-self.max_history_messages :]

        # Step 2: Estimate token count (rough: 1 token ≈ 4 characters)
        def estimate_tokens(text: str) -> int:
            """Rough token estimation: 1 token ≈ 4 characters."""
            return len(text) // 4

        def get_message_length(msg: dict[str, Any]) -> int:
            """Get estimated token length of a message."""
            content = msg.get("content", "")
            if isinstance(content, str):
                return estimate_tokens(content)
            return 0

        # Step 3: If total length exceeds max_context_length, truncate from beginning
        total_tokens = sum(get_message_length(msg) for msg in truncated_history)

        if total_tokens > self.max_context_length:
            # Truncate from the beginning until we're under the limit
            final_history: list[dict[str, Any]] = []
            current_tokens = 0

            # Process messages from end to beginning
            for msg in reversed(truncated_history):
                msg_tokens = get_message_length(msg)
                if current_tokens + msg_tokens <= self.max_context_length:
                    final_history.insert(0, msg)
                    current_tokens += msg_tokens
                else:
                    # If this is the first (most recent) message and it exceeds the limit,
                    # we still keep it (can't truncate a single message)
                    if not final_history:
                        final_history.insert(0, msg)
                        current_tokens = msg_tokens
                    # Otherwise, stop truncating
                    break

            truncated_history = final_history
            total_tokens = current_tokens

        return {
            "conversation_history": truncated_history,
            "context_summary": None,
            "total_tokens": total_tokens,
        }

    async def update_memory(
        self,
        user_id: str,
        project_id: str,
        conversation_id: str,
        user_message: str,
        assistant_response: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Update memory (no-op for simple implementation).

        Simple memory controller doesn't maintain long-term memory,
        so this method does nothing.
        """
        # Simple implementation doesn't update memory
        pass
