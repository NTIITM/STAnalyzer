"""
OpenAI 风格的文档精排（rerank）客户端。

设计目标：
- 与 `llm_client.LLMClient` 风格统一：集中处理超时、重试和遥测
- 使用 OpenAI / Cohere 类似的精排接口风格：
  请求体:
    {
      "model": "reranker-model",
      "query": "user question",
      "documents": ["doc1 text", "doc2 text", ...]
    }
  响应体（示例，兼容多种实现）:
    {
      "results": [
        {"index": 0, "score": 0.98},
        {"index": 1, "score": 0.76},
        ...
      ]
    }
"""

from __future__ import annotations

from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any, Dict, List, Optional, Protocol, Sequence

import httpx

from textmsa.logging_config import get_logger
from textmsa.services.agent.llm_client import (
    RetryConfig,
    LLMClientError,
    LLMAuthError,
    LLMRateLimitError,
    LLMProviderError,
)
from textmsa.settings import get_reranker_llm_config

logger = get_logger(__name__)


@dataclass
class RerankRequest:
    """标准化的精排请求结构。"""

    query: str
    documents: Sequence[str]
    model: Optional[str] = None
    top_n: Optional[int] = None
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RerankedDocument:
    """单个文档的精排结果。"""

    index: int
    score: float


@dataclass
class RerankResponse:
    """精排响应（归一化格式）。"""

    results: List[RerankedDocument]
    raw: Dict[str, Any]


class RerankTelemetryHook(Protocol):
    """可选的遥测 hook。"""

    def on_rerank(
        self,
        *,
        provider: str,
        model: str,
        duration_ms: float,
        success: bool,
        status_code: Optional[int],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None: ...


class BaseRerankProvider:
    """负责构造不同 provider 的 payload / endpoint。"""

    name: str = "openai-compatible-rerank"

    def __init__(self, config: Dict[str, Any], base_url: str = "") -> None:
        self.config = config
        self.base_url = base_url.rstrip("/") if base_url else ""

    def endpoint(self) -> str:
        # 允许通过配置覆盖 endpoint
        if "endpoint" in self.config:
            return self.config["endpoint"]

        # 默认认为 base_url 已经带 /v1
        # 常见实现：/v1/rerank 或 /v1/rerankings
        default_endpoint = "/rerank"
        return default_endpoint

    def build_payload(self, request: RerankRequest) -> Dict[str, Any]:
        documents = list(request.documents)
        if not documents:
            raise LLMClientError("RerankRequest.documents 不能为空")

        payload: Dict[str, Any] = {
            "model": request.model or self.config.get("model"),
            "query": request.query,
            "documents": documents,
        }
        if not payload["model"]:
            raise LLMClientError("reranker_llm.model 未配置")

        if request.top_n is not None:
            payload["top_n"] = request.top_n

        if request.extra_params:
            payload.update(request.extra_params)
        return payload

    def parse_response(self, raw: Dict[str, Any]) -> RerankResponse:
        """从不同实现中抽取统一的结果格式。"""
        results_field = raw.get("results") or raw.get("data") or []
        if not isinstance(results_field, list):
            raise LLMProviderError("rerank 响应缺少 results / data 字段")

        normalized: List[RerankedDocument] = []
        for item in results_field:
            # 尝试兼容多种字段命名
            idx = item.get("index")
            score = item.get("score") or item.get("relevance_score")
            if idx is None or score is None:
                continue
            try:
                normalized.append(RerankedDocument(index=int(idx), score=float(score)))
            except Exception:
                continue

        if not normalized:
            raise LLMProviderError("rerank 响应中未能解析出有效结果")

        return RerankResponse(results=normalized, raw=raw)


class DashScopeRerankProvider(BaseRerankProvider):
    """DashScope 风格的文档精排 provider。
    
    请求格式：
    {
      "model": "qwen3-rerank",
      "input": {
        "query": "...",
        "documents": [...]
      },
      "parameters": {
        "return_documents": true,
        "top_n": 2,
        "instruct": "..."
      }
    }
    
    响应格式：
    {
      "output": {
        "results": [
          {
            "document": {"text": "..."},
            "index": 0,
            "relevance_score": 0.93
          }
        ]
      }
    }
    """

    name: str = "dashscope-rerank"

    def endpoint(self) -> str:
        # 允许通过配置覆盖 endpoint
        if "endpoint" in self.config:
            return self.config["endpoint"]
        # DashScope 默认 endpoint
        return "/api/v1/services/rerank/text-rerank/text-rerank"

    def build_payload(self, request: RerankRequest) -> Dict[str, Any]:
        documents = list(request.documents)
        if not documents:
            raise LLMClientError("RerankRequest.documents 不能为空")

        model = request.model or self.config.get("model")
        if not model:
            raise LLMClientError("reranker_llm.model 未配置")

        # DashScope 格式
        payload: Dict[str, Any] = {
            "model": model,
            "input": {
                "query": request.query,
                "documents": documents,
            },
            "parameters": {
                "return_documents": True,
            },
        }

        # 设置 top_n
        if request.top_n is not None:
            payload["parameters"]["top_n"] = request.top_n
        elif "top_n" in self.config:
            payload["parameters"]["top_n"] = self.config["top_n"]

        # 设置 instruct（如果有配置）
        if "instruct" in self.config:
            payload["parameters"]["instruct"] = self.config["instruct"]

        # 允许通过 extra_params 覆盖参数
        if request.extra_params:
            if "parameters" in request.extra_params:
                payload["parameters"].update(request.extra_params["parameters"])
            else:
                # 如果 extra_params 中的键不是 "parameters"，则直接更新到 parameters 中
                payload["parameters"].update(request.extra_params)

        return payload

    def parse_response(self, raw: Dict[str, Any]) -> RerankResponse:
        """解析 DashScope 格式的响应。"""
        # DashScope 响应格式：{"output": {"results": [...]}}
        output = raw.get("output") or {}
        results_field = output.get("results") or []
        
        if not isinstance(results_field, list):
            raise LLMProviderError("DashScope rerank 响应缺少 output.results 字段")

        normalized: List[RerankedDocument] = []
        for item in results_field:
            # DashScope 格式：{"document": {"text": "..."}, "index": 0, "relevance_score": 0.93}
            idx = item.get("index")
            score = item.get("relevance_score")
            if idx is None or score is None:
                continue
            try:
                normalized.append(RerankedDocument(index=int(idx), score=float(score)))
            except Exception:
                continue

        if not normalized:
            raise LLMProviderError("DashScope rerank 响应中未能解析出有效结果")

        return RerankResponse(results=normalized, raw=raw)


class RerankerClient:
    """高层精排客户端，封装 HTTP / 重试 / 遥测。"""

    def __init__(
        self,
        *,
        config: Optional[Dict[str, Any]] = None,
        telemetry_hook: Optional[RerankTelemetryHook] = None,
    ) -> None:
        cfg = dict(config or get_reranker_llm_config())
        self.provider_name = (cfg.get("provider") or "openai").lower()

        self.base_url = cfg.get("base_url", "").rstrip("/")
        if not self.base_url:
            raise LLMClientError("reranker_llm.base_url 未配置")

        self.api_key = cfg.get("api_key") or ""
        if not self.api_key:
            raise LLMClientError("reranker_llm.api_key 未配置")

        timeout_seconds = float(cfg.get("timeout_seconds", 60))
        self.timeout = httpx.Timeout(
            timeout=timeout_seconds,
            connect=float(cfg.get("connect_timeout_seconds", 10)),
            read=timeout_seconds,
            write=float(cfg.get("write_timeout_seconds", 30)),
        )

        self.retry_cfg = RetryConfig(
            max_attempts=int(cfg.get("max_retries", 3)),
            backoff_seconds=float(cfg.get("retry_backoff_seconds", 1.5)),
        )
        self.telemetry_hook = telemetry_hook
        
        # 根据 provider 类型选择 provider
        provider_type = (cfg.get("provider") or "dashscope").lower()
        if provider_type == "dashscope":
            self.provider = DashScopeRerankProvider(cfg, base_url=self.base_url)
        else:
            self.provider = BaseRerankProvider(cfg, base_url=self.base_url)

        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

    def rerank(self, request: RerankRequest) -> RerankResponse:
        payload = self.provider.build_payload(request)
        raw = self._send_with_retry(payload)
        return self.provider.parse_response(raw)

    # ------------------------------------------------------------------ #
    # 内部实现
    # ------------------------------------------------------------------ #

    def _send_with_retry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        import time

        endpoint = self.provider.endpoint()
        attempts = max(self.retry_cfg.max_attempts, 1)
        delay = self.retry_cfg.backoff_seconds
        last_error: Optional[Exception] = None

        for attempt in range(1, attempts + 1):
            start = time.perf_counter()
            status: Optional[int] = None
            try:
                resp = self._client.post(endpoint, json=payload)
                status = resp.status_code
                resp.raise_for_status()
                data = resp.json()
                self._emit_telemetry(
                    duration_ms=(time.perf_counter() - start) * 1000,
                    success=True,
                    status_code=status,
                    metadata={"attempt": attempt},
                )
                return data
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                last_error = self._map_http_error(exc)
                should_retry = self._should_retry(status, attempt, attempts)
                logger.error(
                    "Reranker 请求失败 | 状态码: %s | 尝试次数: %d/%d | 是否重试: %s | 详情: %s",
                    status,
                    attempt,
                    attempts,
                    should_retry,
                    self._safe_json(exc.response),
                )
                self._emit_telemetry(
                    duration_ms=(time.perf_counter() - start) * 1000,
                    success=False,
                    status_code=status,
                    metadata={"attempt": attempt, "retrying": should_retry},
                )
                if not should_retry:
                    raise last_error
                time.sleep(delay)
                delay *= 2
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = LLMProviderError(str(exc))
                should_retry = self._should_retry(None, attempt, attempts, transport_error=True)
                logger.error(
                    "Reranker 传输错误 | 类型: %s | 尝试次数: %d/%d | 是否重试: %s | 错误: %s",
                    type(exc).__name__,
                    attempt,
                    attempts,
                    should_retry,
                    str(exc),
                )
                self._emit_telemetry(
                    duration_ms=(time.perf_counter() - start) * 1000,
                    success=False,
                    status_code=status,
                    metadata={"attempt": attempt, "retrying": should_retry},
                )
                if not should_retry:
                    raise last_error
                time.sleep(delay)
                delay *= 2

        raise last_error or LLMProviderError("Reranker 请求失败且未返回详细错误")

    def _map_http_error(self, exc: httpx.HTTPStatusError) -> Exception:
        status_code = exc.response.status_code
        if status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
            return LLMAuthError("Reranker 认证失败，请检查配置的 API Key")
        if status_code == HTTPStatus.TOO_MANY_REQUESTS:
            return LLMRateLimitError("Reranker 请求过于频繁，请稍后再试")
        detail = self._safe_json(exc.response)
        message = (
            detail.get("error", {}).get("message")
            if isinstance(detail, dict)
            else None
        )
        return LLMProviderError(message or f"Reranker 返回错误状态码 {status_code}")

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
            self.telemetry_hook.on_rerank(
                provider=self.provider_name,
                model=model,
                duration_ms=duration_ms,
                success=success,
                status_code=status_code,
                metadata=metadata,
            )
        except Exception:
            # 遥测失败不应影响主流程
            logger.debug("Rerank telemetry hook error", exc_info=True)

    def close(self) -> None:
        self._client.close()

    def __del__(self) -> None:  # pragma: no cover - best-effort cleanup
        try:
            self.close()
        except Exception:
            pass


_RERANKER_CLIENT: Optional[RerankerClient] = None


def get_reranker_client() -> RerankerClient:
    """懒加载单例 RerankerClient。"""
    global _RERANKER_CLIENT
    if _RERANKER_CLIENT is None:
        _RERANKER_CLIENT = RerankerClient()
    return _RERANKER_CLIENT


