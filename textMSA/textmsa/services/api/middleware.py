"""
Custom middleware for the textMSA API service.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from textmsa.logging_config import get_logger


def _safe_decode_body(body: bytes) -> str:
    """
    Decode request body for logging purposes.

    Ensures that binary or excessively large payloads do not flood logs.
    """
    if not body:
        return ""

    # Limit the logged payload size to avoid flooding logs
    max_length = 4096
    truncated = False
    if len(body) > max_length:
        body = body[:max_length]
        truncated = True

    try:
        decoded = body.decode("utf-8")
    except UnicodeDecodeError:
        decoded = body.decode("latin-1", errors="ignore")

    if truncated:
        decoded += "... [truncated]"
    return decoded


def _extract_json_if_possible(body_str: str) -> Any:
    """
    Attempt to parse the body as JSON to improve readability in logs.
    """
    if not body_str:
        return body_str

    try:
        return json.loads(body_str)
    except json.JSONDecodeError:
        return body_str


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs inbound request details and processing time.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.logger: logging.Logger = get_logger(__name__)

    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        body_bytes = await request.body()
        # Ensure downstream handlers can re-read the body
        request._body = body_bytes  # type: ignore[attr-defined]

        body_str = _safe_decode_body(body_bytes)
        body_data = _extract_json_if_possible(body_str)

        request_info: Dict[str, Any] = {
            "method": request.method,
            "path": request.url.path,
            "query": dict(request.query_params),
            "client": request.client.host if request.client else None,
            "headers": dict(request.headers),
            "body": body_data,
        }

        self.logger.info("Incoming request: %s", request_info)

        response = await call_next(request)
        process_time_ms = (time.perf_counter() - start_time) * 1000

        self.logger.info(
            "Request handled: method=%s path=%s status=%s duration=%.2fms",
            request.method,
            request.url.path,
            response.status_code,
            process_time_ms,
        )

        return response


