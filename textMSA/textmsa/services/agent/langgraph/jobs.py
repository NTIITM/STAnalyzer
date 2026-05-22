from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, MutableMapping, Sequence

from textmsa.logging_config import get_logger
from textmsa.services.agent.exceptions import JobCancelled
from textmsa.services.agent.repositories.job_repository import (
    AgentJobRepository,
    AgentJobNotFoundError as RepoJobNotFoundError,
    get_agent_job_repository,
)
from textmsa.services.data.mongodb_models import (
    AgentJobStatus,
    AgentJobStepStatus,
    AgentJobStep as MongoAgentJobStep,
)

logger = get_logger(__name__)

RoleLiteral = Literal["planner", "knowledge", "analyst", "system"]

_JOB_REPOSITORY: AgentJobRepository | None = None


def get_job_repo() -> AgentJobRepository:
    """
    Lazily resolve the agent job repository so LangGraph modules can reuse it.
    """

    global _JOB_REPOSITORY
    if _JOB_REPOSITORY is None:
        _JOB_REPOSITORY = get_agent_job_repository()
    return _JOB_REPOSITORY


@dataclass(slots=True)
class JobUpdatePayload:
    """
    Reusable payload describing a single job step update (no job metadata).
    """

    name: str
    message: str | None = None
    output: str | None = None
    status: AgentJobStepStatus = AgentJobStepStatus.RUNNING
    metadata: MutableMapping[str, Any] = field(default_factory=dict)
    artifacts: Sequence[str] = field(default_factory=tuple)

    def to_step(self, *, job_id: str, role: RoleLiteral) -> "JobStepPayload":
        """
        Materialize a full JobStepPayload using the provided job context.
        """

        return JobStepPayload(
            job_id=job_id,
            role=role,
            name=self.name,
            message=self.message,
            output=self.output,
            status=self.status,
            metadata=dict(self.metadata),
            artifacts=list(self.artifacts),
        )


@dataclass(slots=True)
class JobStepPayload:
    """
    Fully-qualified job step payload including job + role metadata.
    """

    job_id: str
    role: RoleLiteral
    name: str
    message: str | None = None
    output: str | None = None
    status: AgentJobStepStatus = AgentJobStepStatus.RUNNING
    metadata: MutableMapping[str, Any] = field(default_factory=dict)
    artifacts: Sequence[str] = field(default_factory=tuple)


@dataclass(slots=True)
class JobStatusPayload:
    """
    Wrapper for job status transitions (running/completed/failed/etc).
    """

    job_id: str
    status: AgentJobStatus
    message: str | None = None
    result: Mapping[str, Any] | None = None
    error: Mapping[str, Any] | None = None


def append_step(
    payload: JobStepPayload,
    *,
    repo: AgentJobRepository | None = None,
) -> MongoAgentJobStep | None:
    """
    Append a job step backed by AgentJobRepository.append_step.
    """

    repo = repo or get_job_repo()
    metadata = dict(payload.metadata or {})
    metadata.setdefault("role", payload.role)
    if payload.artifacts:
        metadata["artifacts"] = list(payload.artifacts)
    step = MongoAgentJobStep(
        name=payload.name,
        status=payload.status,
        message=payload.message,
        output=payload.output,
        metadata=metadata,
    )
    try:
        repo.append_step(job_id=payload.job_id, step=step)
        return step
    except RepoJobNotFoundError:
        logger.warning(
            "job %s not found when appending step %s",
            payload.job_id,
            payload.name,
        )
        return None
    except Exception as exc:  # pragma: no cover - logged before raising
        logger.error(
            "failed to append job step",
            extra={"job_id": payload.job_id, "step": payload.name},
            exc_info=True,
        )
        raise exc


def mark_progress(
    payload: JobStatusPayload,
    *,
    repo: AgentJobRepository | None = None,
) -> None:
    """
    Update the job status/result fields via the repository.
    """

    repo = repo or get_job_repo()
    try:
        repo.update_status(
            job_id=payload.job_id,
            status=payload.status,
            message=payload.message,
            result=dict(payload.result) if payload.result is not None else None,
            error=dict(payload.error) if payload.error is not None else None,
        )
    except RepoJobNotFoundError:
        logger.warning(
            "job %s not found when updating status to %s",
            payload.job_id,
            payload.status.value,
        )
    except Exception as exc:  # pragma: no cover - logged before raising
        logger.error(
            "failed to update job status",
            extra={"job_id": payload.job_id, "status": payload.status.value},
            exc_info=True,
        )
        raise exc


def record_llm_step(
    *,
    job_id: str,
    role: RoleLiteral,
    name: str,
    prompt: str,
    response: str,
    usage: Mapping[str, Any] | None = None,
    message: str | None = None,
    status: AgentJobStepStatus = AgentJobStepStatus.COMPLETED,
    metadata: Mapping[str, Any] | None = None,
    repo: AgentJobRepository | None = None,
) -> None:
    """
    Helper for logging LLM invocations with a consistent metadata schema.
    """

    llm_metadata: dict[str, Any] = {
        "type": "llm",
        "inputs": {"prompt": prompt},
        "outputs": {"response": response},
    }
    if usage:
        llm_metadata["usage"] = dict(usage)
    if metadata:
        llm_metadata.update(metadata)

    append_step(
        JobStepPayload(
            job_id=job_id,
            role=role,
            name=name,
            message=message,
            output=response,
            status=status,
            metadata=llm_metadata,
        ),
        repo=repo,
    )


def record_tool_step(
    *,
    job_id: str,
    role: RoleLiteral,
    name: str,
    tool: str,
    inputs: Mapping[str, Any],
    outputs: Mapping[str, Any] | None = None,
    message: str | None = None,
    artifacts: Sequence[str] | None = None,
    status: AgentJobStepStatus = AgentJobStepStatus.RUNNING,
    metadata: Mapping[str, Any] | None = None,
    repo: AgentJobRepository | None = None,
) -> None:
    """
    Helper for recording tool/service/sandbox invocations.
    """

    tool_metadata: dict[str, Any] = {
        "tool": tool,
        "inputs": dict(inputs),
    }
    if outputs is not None:
        tool_metadata["outputs"] = dict(outputs)
    if metadata:
        tool_metadata.update(metadata)

    append_step(
        JobStepPayload(
            job_id=job_id,
            role=role,
            name=name,
            message=message,
            output=None,
            status=status,
            metadata=tool_metadata,
            artifacts=list(artifacts) if artifacts else (),
        ),
        repo=repo,
    )


def check_job_cancelled(job_id: str, *, repo: AgentJobRepository | None = None) -> None:
    """
    Check if a job has been cancelled and raise JobCancelled if so.
    
    This function should be called periodically in LangGraph nodes to support
    cancellation. If the job has been cancelled, it will raise JobCancelled
    which should be caught and handled appropriately.
    
    Args:
        job_id: Job ID to check
        repo: Optional job repository (defaults to global singleton)
        
    Raises:
        JobCancelled: If the job has been cancelled
    """
    repo = repo or get_job_repo()
    try:
        job = repo.get_job(job_id=job_id, user_id=None)
        if job.cancel_requested or job.status == AgentJobStatus.CANCELLING:
            logger.info(f"Job {job_id} cancellation detected in LangGraph node")
            raise JobCancelled(job_id, "Job was cancelled by user")
    except JobCancelled:
        raise
    except RepoJobNotFoundError:
        # Job not found - might have been deleted, allow execution to continue
        logger.debug(f"Job {job_id} not found when checking cancellation status")
    except Exception as exc:
        logger.warning(f"Failed to check job cancellation status: {exc}")
        # Don't raise - allow execution to continue if check fails


__all__ = [
    "JobUpdatePayload",
    "JobStepPayload",
    "JobStatusPayload",
    "append_step",
    "mark_progress",
    "record_llm_step",
    "record_tool_step",
    "get_job_repo",
    "check_job_cancelled",
]


