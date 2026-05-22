"""
共享工具函数
用于 analyst、planner 和 knowledge 子图的通用功能。
"""

from __future__ import annotations

import json
from typing import Any, Mapping, NoReturn

from textmsa.logging_config import get_logger
from textmsa.services.agent.langgraph import jobs
from textmsa.services.data.mongodb_models import AgentJobStatus


logger = get_logger(__name__)


def format_log_extra(extra: dict[str, Any] | None) -> dict[str, Any] | None:
    """
    格式化日志 extra 参数，将复杂对象转换为美观的 JSON 字符串。
    
    这样可以避免日志中出现转义字符，使日志更易读。
    
    Args:
        extra: 原始 extra 字典，可以为 None
        
    Returns:
        格式化后的 extra 字典，复杂对象已转换为 JSON 字符串，如果输入为 None 则返回 None
    """
    if extra is None:
        return None
    
    formatted: dict[str, Any] = {}
    for key, value in extra.items():
        # 对于复杂对象（字典、列表等），格式化为 JSON 字符串
        if isinstance(value, (dict, list, tuple)):
            try:
                formatted[key] = json.dumps(
                    value,
                    ensure_ascii=False,
                    indent=2,
                    default=str,  # 对于无法序列化的对象，使用 str() 转换
                )
            except (TypeError, ValueError):
                # 如果无法序列化，使用字符串表示
                formatted[key] = str(value)
        elif isinstance(value, (str, int, float, bool, type(None))):
            # 简单类型保持原样
            formatted[key] = value
        else:
            # 其他类型转换为字符串
            try:
                formatted[key] = json.dumps(
                    value,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            except (TypeError, ValueError):
                formatted[key] = str(value)
    return formatted


def parse_json_from_llm_response(content: str | None, default: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    从 LLM 响应中安全解析 JSON 字符串。
    
    支持从 markdown 代码块中提取 JSON（如 ```json ... ```）。
    如果解析失败，返回默认值或空字典。
    
    Args:
        content: LLM 响应内容，可能包含 markdown 代码块
        default: 解析失败时返回的默认值，如果为 None 则返回空字典
        
    Returns:
        解析后的 JSON 字典，如果解析失败则返回 default 或空字典
    """
    if not content:
        return default or {}
    
    # 清理内容
    content = content.strip()
    
    # 尝试提取 JSON（可能包含 markdown 代码块）
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return default or {}


class SubgraphExecutionError(RuntimeError):
    """
    Raised when a LangGraph subgraph encounters an unrecoverable state.
    """

    def __init__(
        self,
        message: str,
        *,
        role: jobs.RoleLiteral,
        code: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.role = role
        self.code = code
        self.details = dict(details or {})


def fail_job_and_raise(
    *,
    job_id: str,
    role: jobs.RoleLiteral,
    message: str,
    code: str = "unexpected_state",
    details: Mapping[str, Any] | None = None,
    log_extra: Mapping[str, Any] | None = None,
) -> NoReturn:
    """
    Helper to log, mark the job as failed, and raise a structured error.
    """

    formatted_extra = format_log_extra({"job_id": job_id, **(log_extra or {})})
    logger.error(
        f"{role} subgraph failed: {message}",
        extra=formatted_extra,
    )

    error_payload: dict[str, Any] = {
        "role": role,
        "code": code,
        "message": message,
    }
    if details:
        error_payload["details"] = dict(details)

    jobs.mark_progress(
        jobs.JobStatusPayload(
            job_id=job_id,
            status=AgentJobStatus.FAILED,
            message=message,
            error=error_payload,
        )
    )

    raise SubgraphExecutionError(
        message,
        role=role,
        code=code,
        details=details,
    )


__all__ = (
    "SubgraphExecutionError",
    "fail_job_and_raise",
    "format_log_extra",
    "parse_json_from_llm_response",
)

