from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Dict, List, Optional

from textmsa.logging_config import get_logger
from textmsa.services.agent.llm_client import LLMClient, LLMRequest, get_llm_client
from textmsa.services.data.mongodb_models import Memory

logger = get_logger(__name__)


class MemorySummarizer:
    """使用 LLM 从对话历史中提取记忆。"""

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        self._llm_client = llm_client or get_llm_client()

    async def summarize(
        self,
        *,
        messages: List[Dict[str, str]],
        max_memories: int = 10,
    ) -> List[Memory]:
        """从对话历史中提取记忆。"""
        if not messages:
            return []

        formatted = self._format_messages(messages)
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(formatted, max_memories)

        request = LLMRequest(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        def _call_sync() -> str:
            resp = self._llm_client.chat(request)
            return (resp.content or "").strip()

        try:
            content = await asyncio.to_thread(_call_sync)
        except Exception as exc:  # pragma: no cover - 上层统一处理
            logger.error("调用 LLM 生成记忆摘要失败: %s", exc, exc_info=True)
            return []

        return self._parse_response(content)

    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        lines: List[str] = []
        for msg in messages:
            try:
                role = msg.get("role", "unknown")
                # TODO：将消息转换为 JSON 格式, 可能错误
                content = json.dumps(msg, ensure_ascii=False, indent=2)
                lines.append(f"{role}: {content}")
            except Exception:
                continue
        return "\n".join(lines)

    def _build_system_prompt(self) -> str:
        return (
            "你是一个专业的记忆提取助手。你的任务是从对话历史中提取关键信息，"
            "并将其转化为结构化的记忆。\n\n"
            "提取原则：\n"
            "1. 关注用户的偏好、习惯、重要决策\n"
            "2. 关注项目相关的关键信息\n"
            "3. 关注需要长期记住的事实\n"
            "4. 忽略临时性的对话内容\n\n"
            "重要性评分规则：\n"
            "- 0.9-1.0：关键决策、核心偏好、重要结论\n"
            "- 0.7-0.9：重要信息、用户偏好、项目配置\n"
            "- 0.5-0.7：一般信息、上下文信息\n"
            "- 0.0-0.5：次要信息、临时信息\n\n"
            "请以 JSON 格式返回，结构如下：\n"
            '{\n'
            '  "memories": [\n'
            '    {\n'
            '      "content": "记忆内容（简洁明了，不超过100字）",\n'
            '      "importance": 0.85\n'
            "    }\n"
            "  ]\n"
            "}\n"
        )

    def _build_user_prompt(self, formatted_messages: str, max_memories: int) -> str:
        return (
            "请从以下对话历史中提取关键记忆：\n\n"
            "【对话历史】\n"
            f"{formatted_messages}\n\n"
            f"请提取 3-{max_memories} 条关键记忆，并按重要性评分排序。"
        )

    def _parse_response(self, content: str) -> List[Memory]:
        """解析 LLM JSON 响应为 Memory 对象列表。"""
        try:
            data = json.loads(content or "{}")
        except json.JSONDecodeError:
            logger.error("解析记忆摘要 JSON 失败，返回原始内容截断: %s", content[:200])
            return []

        memories_raw = data.get("memories") or []
        results: List[Memory] = []
        for item in memories_raw:
            if not isinstance(item, dict):
                continue
            text = str(item.get("content", "")).strip()
            if not text:
                continue
            try:
                importance = float(item.get("importance", 0.5))
            except Exception:
                importance = 0.5
            try:
                mem = Memory(
                    memory_id=str(uuid.uuid4()),
                    content=text,
                    importance=max(0.0, min(1.0, importance)),
                )
                results.append(mem)
            except Exception as exc:
                logger.warning("构建 Memory 对象失败: %s", exc)
                continue
        return results


