from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from fastapi import HTTPException

from textmsa.logging_config import get_logger
from textmsa.services.service import ServiceService, get_service_service

logger = get_logger(__name__)


class ServiceDispatchError(RuntimeError):
    """
    Raised when a planner-defined service task cannot be executed.
    """


@dataclass(slots=True)
class ServiceDispatchResult:
    """
    Normalized container for service execution outputs.
    """

    output: str
    metadata: dict[str, Any]
    artifacts: tuple[str, ...] = ()


class ServiceDispatchClient:
    """
    Thin wrapper around ServiceService for Analyst/Planner use.

    This client is intentionally synchronous and stateless so it can be
    constructed inside LangGraph nodes or injected from tests.
    """

    def __init__(self, *, service_service: ServiceService | None = None) -> None:
        self._service_service = service_service or get_service_service()

    # ------------------------------------------------------------------
    # Metadata helpers
    # ------------------------------------------------------------------

    def fetch_service_metadata(
        self,
        service_id: str,
        *,
        user_id: str,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Fetch a single service's metadata for tool selection / logging.
        """

        try:
            metadata = self._service_service.get_service(service_id, user_id=user_id)
        except HTTPException as exc:  # pragma: no cover - HTTP path is integration tested at API layer
            logger.error(
                "failed to fetch service metadata",
                extra={"service_id": service_id, "status_code": exc.status_code},
                exc_info=True,
            )
            raise ServiceDispatchError(str(exc.detail)) from exc
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(
                "unexpected error while fetching service metadata",
                extra={"service_id": service_id},
                exc_info=True,
            )
            raise ServiceDispatchError(str(exc)) from exc

        return metadata

    def list_available_services(
        self,
        *,
        user_id: str,
        project_id: str | None = None,
        file_type_id: str | None = None,
        visibility: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """
        List services visible to the current user / project, optionally
        filtered by input file type.
        """

        try:
            return self._service_service.list_services(
                visibility_filter=visibility,
                user_id=user_id,
                project_id=project_id,
                input_file_type_id=file_type_id,
                skip=0,
                limit=limit,
            )
        except HTTPException as exc:  # pragma: no cover - propagated upwards
            logger.error(
                "failed to list services",
                extra={"status_code": exc.status_code, "detail": exc.detail},
                exc_info=True,
            )
            raise ServiceDispatchError(str(exc.detail)) from exc
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("unexpected error while listing services", exc_info=True)
            raise ServiceDispatchError(str(exc)) from exc

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def invoke_service(
        self,
        service_id: str,
        *,
        input_files: Sequence[str],
        parameters: Mapping[str, Any] | None,
        user_id: str,
        project_id: str | None = None,
    ) -> ServiceDispatchResult:
        """
        Execute a service via ServiceService.execute_service.
        """

        logger.info(
            "Invoking service",
            extra={
                "service_id": service_id,
                "user_id": user_id,
                "project_id": project_id,
                "input_files_count": len(input_files),
            },
        )

        if not input_files:
            logger.error("Service task missing input files", extra={"service_id": service_id})
            raise ServiceDispatchError("service task 缺少输入文件 input_files")

        input_ids = [str(fid) for fid in input_files if fid]
        try:
            logger.debug(
                "Executing service",
                extra={
                    "service_id": service_id,
                    "input_file_ids": input_ids,
                    "parameters_keys": list((parameters or {}).keys()),
                },
            )
            result = self._service_service.execute_service(
                service_id=service_id,
                input_file_ids=input_ids,
                user_id=user_id,
                parameters=dict(parameters or {}),
                project_id=project_id,
                validate_input_types=False,
            )
            logger.info(
                "Service execution completed",
                extra={
                    "service_id": service_id,
                    "execution_id": result.get("execution_id"),
                    "status": result.get("status"),
                },
            )
        except HTTPException as exc:
            logger.error(
                "service execution failed",
                extra={
                    "service_id": service_id,
                    "status_code": exc.status_code,
                    "detail": exc.detail,
                },
                exc_info=True,
            )
            # Let Analyst mark the step as FAILED and stop the pipeline.
            raise ServiceDispatchError(str(exc.detail)) from exc
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(
                "unexpected error during service execution",
                extra={"service_id": service_id},
                exc_info=True,
            )
            raise ServiceDispatchError(str(exc)) from exc

        execution_id = str(result.get("execution_id") or "")
        output_file_ids = tuple(str(fid) for fid in result.get("output_file_ids") or ())
        status = str(result.get("status") or "")

        output_text = (
            result.get("summary")
            or f"Service '{service_id}' 已触发执行（execution_id={execution_id or 'N/A'}，status={status or 'unknown'}）。"
        )

        metadata = {
            "service_id": service_id,
            "execution_id": execution_id,
            "status": status,
            "input_file_ids": input_ids,
            "output_file_ids": list(output_file_ids),
            "raw_result": result,
        }

        return ServiceDispatchResult(
            output=str(output_text),
            metadata=metadata,
            artifacts=output_file_ids,
        )

    def wait_for_execution(
        self,
        execution_id: str,
        *,
        max_wait_seconds: float = 3000.0,
        poll_interval_seconds: float = 3.0,
        timeout_error: bool = True,
    ) -> dict[str, Any]:
        """
        等待服务执行完成（基于 Event 通知，非轮询）。
        
        内部委托给 ServiceService.wait_for_execution()，使用 threading.Event.wait()
        挂起线程，不消耗 CPU，不反复查询数据库。任务完成时立即被唤醒。
        
        Args:
            execution_id: 执行ID
            max_wait_seconds: 最大等待时间（秒），默认3000秒（50分钟）
            poll_interval_seconds: 已废弃，保留参数以兼容旧调用
            timeout_error: 如果超时是否抛出异常，默认True
        
        Returns:
            执行记录（包含 status, output_file_ids 等）
        
        Raises:
            ServiceDispatchError: 如果执行失败或超时
        """
        logger.info(
            "Waiting for service execution to complete (event-based)",
            extra={
                "execution_id": execution_id,
                "max_wait_seconds": max_wait_seconds,
            },
        )
        
        try:
            execution = self._service_service.wait_for_execution(
                execution_id, timeout=max_wait_seconds
            )
        except TimeoutError as exc:
            if timeout_error:
                logger.error(
                    "Service execution timeout",
                    extra={
                        "execution_id": execution_id,
                        "max_wait_seconds": max_wait_seconds,
                    },
                )
                raise ServiceDispatchError(str(exc)) from exc
            else:
                logger.warning(
                    "Service execution timeout (non-fatal)",
                    extra={
                        "execution_id": execution_id,
                        "max_wait_seconds": max_wait_seconds,
                    },
                )
                try:
                    return self._service_service.get_execution(execution_id)
                except Exception as e:
                    raise ServiceDispatchError(
                        f"服务执行超时且无法获取状态（execution_id={execution_id}）"
                    ) from e
        
        status = execution.get("status", "").lower()
        
        logger.info(
            "Service execution finished",
            extra={
                "execution_id": execution_id,
                "status": status,
            },
        )
        
        if status == "failed":
            error_msg = execution.get("error_message") or "服务执行失败"
            logger.error(
                "Service execution failed",
                extra={
                    "execution_id": execution_id,
                    "error_message": error_msg,
                },
            )
            raise ServiceDispatchError(
                f"服务执行失败（execution_id={execution_id}）：{error_msg}"
            )
        
        return execution

    # ------------------------------------------------------------------
    # High-level task helper used by Analyst
    # ------------------------------------------------------------------

    def run_task(
        self,
        task: Mapping[str, Any],
        state: Mapping[str, Any],
    ) -> ServiceDispatchResult:
        """
        Execute a planner-defined service task against the current state.

        This helper resolves service_id / parameters / input_files from
        the planner task and GraphState, then delegates to invoke_service.
        """

        job_id = state.get("job_id", "unknown")
        task_id = task.get("task_id", "unknown")
        logger.debug(
            "Running service task",
            extra={"job_id": job_id, "task_id": task_id},
        )

        metadata = dict(task.get("metadata") or {})
        service_id = _resolve_service_id(task, metadata)

        user_id = str(state.get("user_id") or "")
        project_id = str(state.get("project_id") or "")

        # Resolve input files: prefer explicit task metadata, then selected_file,
        # finally fall back to any context_files file_id.
        input_files = _resolve_input_files(task, state)
        parameters = metadata.get("parameters") or metadata.get("workflow_params") or {}

        logger.debug(
            "Service task resolved",
            extra={
                "job_id": job_id,
                "task_id": task_id,
                "service_id": service_id,
                "input_files_count": len(input_files),
                "parameters_count": len(parameters),
            },
        )

        # Enrich with static service metadata
        service_meta = self.fetch_service_metadata(
            service_id, user_id=user_id, project_id=project_id
        )

        exec_result = self.invoke_service(
            service_id,
            input_files=input_files,
            parameters=parameters,
            user_id=user_id,
            project_id=project_id,
        )

        merged_metadata = {
            "service_id": service_id,
            "service_name": service_meta.get("name"),
            "service_description": service_meta.get("description"),
            "accepted_files": service_meta.get("accepted_files"),
            "request_config": service_meta.get("request_config"),
            "parameter_template": service_meta.get("parameter_template"),
        }
        # Preserve execution-level metadata (execution_id, status, etc.)
        merged_metadata.update(exec_result.metadata)

        return ServiceDispatchResult(
            output=exec_result.output,
            metadata=merged_metadata,
            artifacts=exec_result.artifacts,
        )


def _resolve_service_id(task: Mapping[str, Any], metadata: Mapping[str, Any]) -> str:
    service_id = (
        metadata.get("service_id")
        or task.get("tool_id")
        or task.get("service_id")
        or task.get("task_id")
    )
    if not service_id:
        raise ServiceDispatchError("service task 缺少 service_id/tool_id")
    return str(service_id)


def _resolve_input_files(
    task: Mapping[str, Any],
    state: Mapping[str, Any],
) -> list[str]:
    """
    Decide which file_ids to send to ServiceService.

    Priority:
    1. task.metadata.input_file_ids
    2. state.selected_file_id
    3. all state.context_files[*].file_id
    """

    metadata = task.get("metadata") or {}
    meta_files = metadata.get("input_file_ids")
    if isinstance(meta_files, Sequence) and not isinstance(meta_files, (str, bytes)):
        return [str(fid) for fid in meta_files if fid]

    selected_file_id = state.get("selected_file_id")
    if selected_file_id:
        return [str(selected_file_id)]

    context_files = state.get("context_files") or []
    collected: list[str] = []
    for item in context_files:
        if isinstance(item, Mapping) and item.get("file_id"):
            collected.append(str(item["file_id"]))
    return collected


def dispatch_service(
    task: Mapping[str, Any],
    state: Mapping[str, Any],
    *,
    client: ServiceDispatchClient | None = None,
) -> ServiceDispatchResult:
    """
    Backwards-compatible helper used by Analyst subgraph.

    Existing code expects a simple function; this adapter delegates to
    ServiceDispatchClient so call sites do not need to change.
    """

    service_client = client or ServiceDispatchClient()
    return service_client.run_task(task, state)


__all__ = [
    "ServiceDispatchError",
    "ServiceDispatchResult",
    "ServiceDispatchClient",
    "dispatch_service",
]
