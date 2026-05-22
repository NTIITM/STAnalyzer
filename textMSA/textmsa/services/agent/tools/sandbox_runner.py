from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from textmsa.logging_config import get_logger
from textmsa.services.agent.experiment_tools import (
    ExperimentTools,
    ToolCallContext,
    get_experiment_tools,
)

logger = get_logger(__name__)

ArtifactUploader = Callable[[Mapping[str, Any]], str | None]


class SandboxExecutionError(RuntimeError):
    """Raised when sandbox execution fails."""


@dataclass(slots=True)
class SandboxRunResult:
    """
    Structured return type for sandbox executions.
    """

    output: str
    metadata: dict[str, Any]
    artifacts: tuple[str, ...] = ()


class SandboxRunner:
    """
    Thin wrapper around ExperimentTools that handles artifact uploads.
    """

    def __init__(
        self,
        *,
        tools: ExperimentTools | None = None,
        artifact_uploader: ArtifactUploader | None = None,
    ) -> None:
        self._tools = tools or get_experiment_tools()
        self._artifact_uploader = artifact_uploader

    def run(
        self,
        task: Mapping[str, Any],
        state: Mapping[str, Any] | None = None,
    ) -> SandboxRunResult:
        if state is None:
            raise SandboxExecutionError("sandbox task 缺少执行状态（state）")
        job_id = state.get("job_id", "unknown")
        task_id = task.get("task_id", "unknown")
        metadata = dict(task.get("metadata") or {})
        tool_name = _resolve_tool_name(task, metadata)
        params = dict(metadata.get("params") or {})

        logger.info(
            "Running sandbox tool",
            extra={
                "job_id": job_id,
                "task_id": task_id,
                "tool_name": tool_name,
                "params_keys": list(params.keys()),
            },
        )

        try:
            logger.debug(
                "Calling sandbox tool",
                extra={"job_id": job_id, "task_id": task_id, "tool_name": tool_name},
            )
            context = self._tools.build_context(
                task,
                state,
                default_task_id=str(task.get("task_id") or tool_name),
            )
            result = self._tools.execute_tool(
                tool_name,
                params,
                context=context,
            )
            logger.info(
                "Sandbox tool completed",
                extra={
                    "job_id": job_id,
                    "task_id": task_id,
                    "tool_name": tool_name,
                    "output_length": len(str(result.output)),
                },
            )
        except Exception as exc:
            logger.error(
                "sandbox tool failed",
                extra={
                    "job_id": job_id,
                    "task_id": task_id,
                    "tool": tool_name,
                },
                exc_info=True,
            )
            raise SandboxExecutionError(str(exc)) from exc

        artifacts = self._store_artifacts(metadata.get("artifacts") or ())
        run_metadata = dict(result.metadata)
        run_metadata.update(
            {
                "tool_name": tool_name,
                "params": params,
                "context": _summarize_context(context),
            }
        )
        if state and state.get("selected_file_id"):
            run_metadata.setdefault("selected_file_id", state["selected_file_id"])

        return SandboxRunResult(
            output=result.output,
            metadata=run_metadata,
            artifacts=result.artifacts or artifacts,
        )

    def _store_artifacts(self, artifacts: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
        if not artifacts or not self._artifact_uploader:
            return ()
        artifact_ids: list[str] = []
        for artifact in artifacts:
            try:
                artifact_id = self._artifact_uploader(artifact)
            except Exception as exc:  # pragma: no cover - surfaced to logs
                logger.warning("artifact upload failed: %s", exc, exc_info=True)
                continue
            if artifact_id:
                artifact_ids.append(str(artifact_id))
        return tuple(artifact_ids)


def _resolve_tool_name(task: Mapping[str, Any], metadata: Mapping[str, Any]) -> str:
    tool_name = (
        task.get("type")
        if str(task.get("type", "")).startswith("sandbox:")
        else metadata.get("tool_name")
        or metadata.get("experiment_tool")
        or metadata.get("service_id")
    )
    if isinstance(tool_name, str) and tool_name.startswith("sandbox:"):
        tool_name = tool_name.split(":", 1)[1]
    if not tool_name:
        raise SandboxExecutionError("sandbox task 缺少 tool_name")
    return str(tool_name)


def _summarize_context(context: ToolCallContext) -> dict[str, Any]:
    summary = context.summary()
    summary.setdefault("selected_file_id", context.selected_file_id)
    if context.metadata:
        summary.setdefault("metadata_keys", list(context.metadata.keys()))
    return summary


__all__ = ["SandboxRunner", "SandboxRunResult", "SandboxExecutionError"]

