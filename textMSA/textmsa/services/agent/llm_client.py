"""
Pluggable LLM client with provider-agnostic interface.

The client wraps HTTP requests with retries, timeout control, and telemetry
hooks so higher-level agent components can invoke LLMs in a consistent way.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence

import httpx

from textmsa.logging_config import get_logger
from textmsa.settings import get_llm_config
from textmsa.services.agent.langgraph.subgraphs.utils import format_log_extra

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Dataclasses / protocols
# ---------------------------------------------------------------------------


@dataclass
class LLMRequest:
    """Normalized chat-style request."""

    messages: Sequence[Dict[str, str]]
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    response_format: Optional[Dict[str, Any]] = None
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """Normalized response returned to callers."""

    content: str
    model: str
    usage: Optional[Dict[str, Any]]
    raw: Dict[str, Any]


@dataclass
class RetryConfig:
    """Retry configuration for transient failures."""

    max_attempts: int = 3
    backoff_seconds: float = 1.5
    retry_statuses: Sequence[int] = (
        HTTPStatus.TOO_MANY_REQUESTS,
        HTTPStatus.INTERNAL_SERVER_ERROR,
        HTTPStatus.BAD_GATEWAY,
        HTTPStatus.SERVICE_UNAVAILABLE,
        HTTPStatus.GATEWAY_TIMEOUT,
    )


class LLMTelemetryHook(Protocol):
    """Optional hook for tracing/tracking LLM usage."""

    def on_completion(
        self,
        *,
        provider: str,
        model: str,
        duration_ms: float,
        success: bool,
        status_code: Optional[int],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None: ...


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class LLMClientError(RuntimeError):
    """Base error for LLM client issues."""


class LLMAuthError(LLMClientError):
    """Authentication/authorization problems."""


class LLMRateLimitError(LLMClientError):
    """429/Too many requests errors."""


class LLMProviderError(LLMClientError):
    """Provider returned an unexpected error."""


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


class BaseLLMProvider:
    """Base helper that knows how to construct payloads for a provider."""

    name: str = "openai-compatible"

    def __init__(self, config: Dict[str, Any], base_url: str = "") -> None:
        self.config = config
        self.base_url = base_url.rstrip("/") if base_url else ""

    def endpoint(self) -> str:
        # 如果配置中明确指定了 endpoint，直接使用
        if "endpoint" in self.config:
            return self.config["endpoint"]

        # httpx 在 base_url 包含路径时，如果 endpoint 以 "/" 开头会丢失已有路径，
        # 因此这里返回的路径一律不加前导斜杠。
        if self.base_url.endswith("/v1"):
            return "chat/completions"

        # 默认走标准的 v1 路径
        return "v1/chat/completions"

    def build_payload(self, request: LLMRequest) -> Dict[str, Any]:
        """Translate LLMRequest into provider-specific payload."""
        payload: Dict[str, Any] = {
            "model": request.model or self.config.get("model"),
            "messages": list(request.messages),
        }
        if not payload["model"]:
            raise LLMClientError("LLM模型未配置，请在 config.llm.model 中设置默认模型")
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        if request.response_format:
            payload["response_format"] = request.response_format
        if request.extra_params:
            payload.update(request.extra_params)
        return payload

    def parse_response(self, raw: Dict[str, Any]) -> LLMResponse:
        """Extract normalized response data."""
        choices = raw.get("choices") or []
        if not choices:
            raise LLMProviderError("LLM响应缺少choices字段")
        message = choices[0].get("message") or {}
        content = message.get("content") or ""
        return LLMResponse(
            content=content,
            model=raw.get("model") or self.config.get("model", ""),
            usage=raw.get("usage"),
            raw=raw,
        )


# ---------------------------------------------------------------------------
# Client implementation
# ---------------------------------------------------------------------------


class LLMClient:
    """High-level client that orchestrates requests/retries/telemetry."""

    def __init__(
        self,
        *,
        config: Optional[Dict[str, Any]] = None,
        telemetry_hook: Optional[LLMTelemetryHook] = None,
    ) -> None:
        cfg = dict(config or get_llm_config())
        self.provider_name = (cfg.get("provider") or "openai").lower()
        # 不提供默认 base_url，必须显式配置，避免落到错误的兼容端点
        self.base_url = (cfg.get("base_url") or "").rstrip("/")
        if not self.base_url:
            raise LLMClientError("llm.base_url 未配置")
        self.api_key = cfg.get("api_key") or ""
        if not self.api_key:
            raise LLMClientError("llm.api_key 未配置")
        # 默认超时时间从 30 秒增加到 180 秒（3分钟），以适应长文本生成
        timeout_seconds = float(cfg.get("timeout_seconds", 180))
        # 使用细粒度的超时配置：
        # - connect: 连接超时（10秒，连接应该很快）
        # - read: 读取超时（主要超时时间，等待LLM响应可能需要较长时间）
        # - write: 写入超时（30秒，发送请求应该很快）
        # - pool: 连接池超时（使用默认值）
        self.timeout = httpx.Timeout(
            timeout=timeout_seconds,  # 总超时时间
            connect=float(cfg.get("connect_timeout_seconds", 10)),
            read=timeout_seconds,  # 读取超时使用总超时时间
            write=float(cfg.get("write_timeout_seconds", 30)),
        )
        self.retry_cfg = RetryConfig(
            max_attempts=int(cfg.get("max_retries", 3)),
            backoff_seconds=float(cfg.get("retry_backoff_seconds", 1.5)),
        )
        self.telemetry_hook = telemetry_hook
        self.provider = BaseLLMProvider(cfg, base_url=self.base_url)
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

    def chat(self, request: LLMRequest) -> LLMResponse:
        """Invoke chat completion API and parse structured response."""
        payload = self.provider.build_payload(request)

        # 记录请求详情
        messages = payload.get("messages", [])
        logger.info(
            "LLM请求开始 | 模型: %s | Provider: %s | Messages数量: %d",
            payload.get("model", "deepseek-chat"),
            self.provider_name,
            len(messages),
        )
        
        # 记录完整的对话内容
        logger.info(
            "LLM完整对话内容 | Messages: %s",
            json.dumps(
                messages,
                ensure_ascii=False,
                indent=2,
            ),
        )
        
        logger.debug(
            "LLM请求详情 | Payload: %s",
            json.dumps(
                self._sanitize_payload_for_logging(payload),
                ensure_ascii=False,
                indent=2,
            ),
        )

        raw = self._send_with_retry(payload)
        response = self.provider.parse_response(raw)

        # 记录响应详情
        usage_info = response.usage or {}
        logger.info(
            "LLM响应成功 | 模型: %s | 响应长度: %d字符 | Token使用: prompt_tokens=%s, completion_tokens=%s, total_tokens=%s",
            response.model,
            len(response.content),
            usage_info.get("prompt_tokens", "N/A"),
            usage_info.get("completion_tokens", "N/A"),
            usage_info.get("total_tokens", "N/A"),
        )
        logger.info(
            "LLM完整响应内容 | Content: %s",
            response.content,
        )
        logger.debug(
            "LLM响应内容预览 | Content preview: %s",
            response.content[:1000] + ("..." if len(response.content) > 1000 else ""),
        )
        logger.debug(
            "LLM完整响应 | Raw response: %s",
            json.dumps(
                self._sanitize_response_for_logging(raw), ensure_ascii=False, indent=2
            ),
        )

        return response

    def _send_with_retry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        endpoint = self.provider.endpoint()
        attempts = max(self.retry_cfg.max_attempts, 1)
        delay = self.retry_cfg.backoff_seconds
        last_error: Optional[Exception] = None

        for attempt in range(1, attempts + 1):
            start = time.perf_counter()
            response_status: Optional[int] = None
            try:
                response = self._client.post(endpoint, json=payload)
                response_status = response.status_code
                response.raise_for_status()
                data = response.json()
                self._emit_telemetry(
                    duration_ms=(time.perf_counter() - start) * 1000,
                    success=True,
                    status_code=response_status,
                    metadata={"attempt": attempt},
                )
                return data
            except httpx.HTTPStatusError as exc:
                response_status = exc.response.status_code
                last_error = self._map_http_error(exc)
                should_retry = self._should_retry(response_status, attempt, attempts)
                error_detail = self._safe_json(exc.response)
                logger.error(
                    "LLM请求失败 | 状态码: %d | 尝试次数: %d/%d | 是否重试: %s | 错误详情: %s",
                    response_status,
                    attempt,
                    attempts,
                    should_retry,
                    error_detail,
                )
                self._emit_telemetry(
                    duration_ms=(time.perf_counter() - start) * 1000,
                    success=False,
                    status_code=response_status,
                    metadata={"attempt": attempt, "retrying": should_retry},
                )
                if not should_retry:
                    raise last_error
                time.sleep(delay)
                delay *= 2
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = LLMProviderError(str(exc))
                should_retry = self._should_retry(
                    None, attempt, attempts, transport_error=True
                )
                logger.error(
                    "LLM请求传输错误 | 错误类型: %s | 尝试次数: %d/%d | 是否重试: %s | 错误信息: %s",
                    type(exc).__name__,
                    attempt,
                    attempts,
                    should_retry,
                    str(exc),
                )
                self._emit_telemetry(
                    duration_ms=(time.perf_counter() - start) * 1000,
                    success=False,
                    status_code=response_status,
                    metadata={"attempt": attempt, "retrying": should_retry},
                )
                if not should_retry:
                    raise last_error
                time.sleep(delay)
                delay *= 2

        # Exhausted retries
        raise last_error or LLMProviderError("LLM请求失败且未返回详细错误")

    def _map_http_error(self, exc: httpx.HTTPStatusError) -> Exception:
        status_code = exc.response.status_code
        if (
            status_code == HTTPStatus.UNAUTHORIZED
            or status_code == HTTPStatus.FORBIDDEN
        ):
            return LLMAuthError("LLM认证失败，请检查配置的API Key")
        if status_code == HTTPStatus.TOO_MANY_REQUESTS:
            return LLMRateLimitError("LLM请求过于频繁，请稍后再试")
        detail = self._safe_json(exc.response)
        message = (
            detail.get("error", {}).get("message") if isinstance(detail, dict) else None
        )
        return LLMProviderError(message or f"LLM返回错误状态码 {status_code}")

    def _should_retry(
        self,
        status_code: Optional[int],
        attempt: int,
        max_attempts: int,
        *,
        transport_error: bool = False,
    ) -> bool:
        if attempt >= max_attempts:
            return False
        if transport_error:
            return True
        if status_code is None:
            return False
        return status_code in self.retry_cfg.retry_statuses

    def _safe_json(self, response: httpx.Response) -> Any:
        try:
            return response.json()
        except Exception:
            return None

    def _sanitize_payload_for_logging(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """清理payload中的敏感信息用于日志记录"""
        sanitized = payload.copy()
        # 保留messages但限制长度
        if "messages" in sanitized:
            messages = sanitized["messages"]
            sanitized_messages = []
            for msg in messages:
                sanitized_msg = msg.copy()
                content = sanitized_msg.get("content", "")
                # 如果内容太长，截断
                if len(content) > 2000:
                    sanitized_msg["content"] = (
                        content[:2000] + f"... (截断，总长度: {len(content)})"
                    )
                sanitized_messages.append(sanitized_msg)
            sanitized["messages"] = sanitized_messages
        return sanitized

    def _sanitize_response_for_logging(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """清理响应中的敏感信息用于日志记录"""
        sanitized = raw.copy()
        # 处理choices中的content
        if "choices" in sanitized:
            choices = sanitized["choices"]
            sanitized_choices = []
            for choice in choices:
                sanitized_choice = choice.copy()
                if "message" in sanitized_choice:
                    msg = sanitized_choice["message"].copy()
                    content = msg.get("content", "")
                    if len(content) > 2000:
                        msg["content"] = (
                            content[:2000] + f"... (截断，总长度: {len(content)})"
                        )
                    sanitized_choice["message"] = msg
                sanitized_choices.append(sanitized_choice)
            sanitized["choices"] = sanitized_choices
        return sanitized

    def _emit_telemetry(
        self,
        *,
        duration_ms: float,
        success: bool,
        status_code: Optional[int],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.telemetry_hook:
            return
        try:
            model = self.provider.config.get("model", "")
            self.telemetry_hook.on_completion(
                provider=self.provider_name,
                model=model,
                duration_ms=duration_ms,
                success=success,
                status_code=status_code,
                metadata=metadata,
            )
        except (
            Exception
        ) as exc:  # pragma: no cover - telemetry failures must not break flow
            logger.debug("Telemetry hook error: %s", exc)

    def extract_code_from_response(self, response: LLMResponse) -> str:
        """
        从 LLM 响应中提取代码，去除代码块标记（如 ```python 和 ```）。
        
        Args:
            response: LLMResponse 对象，包含 LLM 返回的内容
        
        Returns:
            提取后的代码字符串（去除代码块标记和首尾空白）
        """
        generated_code = response.content.strip()
        if generated_code.startswith("```python"):
            generated_code = generated_code[9:]
        elif generated_code.startswith("```"):
            generated_code = generated_code[3:]
        if generated_code.endswith("```"):
            generated_code = generated_code[:-3]
        return generated_code.strip()

    def close(self) -> None:
        """Close underlying HTTP client."""
        self._client.close()

    def __del__(self) -> None:  # pragma: no cover - best-effort cleanup
        try:
            self.close()
        except Exception:
            pass


def get_llm_client() -> LLMClient:
    """Factory for lazy singleton usage."""
    global _LLM_CLIENT
    if _LLM_CLIENT is None:
        _LLM_CLIENT = LLMClient()
    return _LLM_CLIENT


_LLM_CLIENT: Optional[LLMClient] = None
