"""
Agent job service.

Encapsulates job lifecycle management: create, poll, cancel, and step updates.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from textmsa.services.api.schemas import (
        AgentJobResponse,
        AgentJobStep,
        AgentMessageRequest,
    )

from textmsa.logging_config import get_logger
from textmsa.services.agent.exceptions import (
    ActiveJobExistsError,
    AgentServiceError,
    JobAccessDeniedError,
    JobCancelled,
    JobNotFoundError,
)
from textmsa.services.agent.repositories.job_repository import (
    AgentJobRepository,
    AgentJobNotFoundError as RepoJobNotFoundError,
    get_agent_job_repository,
)
from textmsa.services.agent.langgraph import run_agent_graph
from textmsa.services.agent.memory import MemoryController, SimpleMemoryController
from textmsa.services.data.mongodb_models import (
    AgentJob,
    AgentJobStatus,
    AgentJobStep as MongoAgentJobStep,
    AgentJobStepStatus,
)


logger = get_logger(__name__)


class AgentJobService:
    """
    Service for managing agent job lifecycle.

    Handles job creation, status polling, cancellation, and orchestrator callbacks.
    """

    def __init__(
        self,
        *,
        job_repository: Optional[AgentJobRepository] = None,
        memory_controller: Optional[MemoryController] = None,
    ) -> None:
        """
        Initialize the job service.

        Args:
            job_repository: Job repository instance (defaults to global singleton)
            user_data_manager: User data manager instance (defaults to global singleton)
            memory_controller: Memory controller for preparing workflow context
        """
        self._job_repository = job_repository or get_agent_job_repository()
        self._memory_controller = memory_controller or SimpleMemoryController()

    def start_job(
        self, *, request: "AgentMessageRequest", user_id: str
    ) -> "AgentJobResponse":
        """
        Start a new agent job.

        Args:
            request: Message request containing project_id, message, etc.
            user_id: User ID

        Returns:
            Created job response

        Raises:
            ActiveJobExistsError: If an active job already exists for this user/project
            AgentServiceError: If job creation fails
        """
        project_id = request.project_id

        # 1. Guard: ensure no active job for (user_id, project_id)
        active_job = self._job_repository.get_active_job(
            user_id=user_id, project_id=project_id
        )
        if active_job:
            raise ActiveJobExistsError(
                active_job.job_id,
                f"An active job ({active_job.job_id}) already exists for project {project_id}",
            )

        # 2. Build job payload
        payload: Dict[str, Any] = {
            "message": request.message,
            "workflow_name": "rag",  # Default workflow, can be extended
        }
        if request.context_files:
            payload["context_files"] = request.context_files
        if request.metadata:
            payload["metadata"] = request.metadata

        # 3. Create job
        try:
            job = self._job_repository.create_job(
                user_id=user_id,
                project_id=project_id,
                payload=payload,
                status=AgentJobStatus.PENDING,
            )
        except Exception as exc:
            logger.error(f"Failed to create job: {exc}", exc_info=True)
            raise AgentServiceError("Failed to create job") from exc

        # 4. Dispatch orchestrator task (async, non-blocking)
        # Prepare context and dispatch workflow execution in background
        asyncio.create_task(
            self._prepare_and_dispatch_workflow(
                job=job,
                user_id=user_id,
                project_id=project_id,
            )
        )

        # 6. Convert to response
        return self._job_to_response(job)

    async def _prepare_and_dispatch_workflow(
        self,
        *,
        job: AgentJob,
        user_id: str,
        project_id: str,
    ) -> None:
        """
        Prepare workflow context and dispatch workflow execution.

        This method runs asynchronously in the background to:
        1. Get conversation history
        2. Prepare context using MemoryController
        3. Execute LangGraph workflow directly

        Args:
            job: The job to execute
            user_id: User ID
            project_id: Project ID
        """
        job_id = job.job_id
        user_query = job.payload.get("message", "")

        try:
            # 1. Update job status to RUNNING
            try:
                self._job_repository.update_status(
                    job_id=job_id, status=AgentJobStatus.RUNNING
                )
            except Exception as exc:
                logger.error(f"Failed to update job status to RUNNING: {exc}", exc_info=True)
                # Continue anyway - job might already be running

            # 2. Prepare context using MemoryController (conversation history removed)
            conversation_history: list[dict[str, Any]] = []
            context = await self._memory_controller.prepare_context(
                user_id=user_id,
                project_id=project_id,
                user_query=user_query,
                conversation_history=conversation_history,
            )
            context = dict(context or {})

            # Add workflow params if present
            workflow_params = job.payload.get("workflow_params")
            if workflow_params:
                context["workflow_params"] = workflow_params

            # 3. Build LangGraph payload
            context_files = job.payload.get("metadata", {}).get("context_files") or []
            lg_context: Dict[str, Any] = {}
            if context_files:
                lg_context["context_files"] = context_files
            if context:
                lg_context.update(context)

            langgraph_payload: Dict[str, Any] = {
                "job_id": job_id,
                "user_id": user_id,
                "project_id": project_id,
                "message": user_query,
                "conversation_history": conversation_history,
            }
            if lg_context:
                langgraph_payload["context"] = lg_context

            # 5. Create cancellation token and monitoring task
            cancel_token = asyncio.Event()
            monitoring_task = asyncio.create_task(
                self._monitor_cancellation(job_id, cancel_token)
            )

            # 4. Execute LangGraph pipeline in background
            try:
                # Run LangGraph in executor to avoid blocking
                loop = asyncio.get_event_loop()
                start_time = time.perf_counter()
                result = await loop.run_in_executor(
                    None,
                    self._run_langgraph_sync,
                    langgraph_payload,
                    job_id,
                    cancel_token,
                )
                execution_time = time.perf_counter() - start_time

                # Cancel monitoring task
                monitoring_task.cancel()
                try:
                    await monitoring_task
                except asyncio.CancelledError:
                    pass

                # 5. Handle successful completion
                final_answer = str(result.get("final_answer") or "")
                # If LangGraph didn't write execution_time, fall back to wall-clock.
                execution_time = float(result.get("execution_time", execution_time))

                # Mark job as completed
                self.complete_job(
                    job_id=job_id,
                    result={
                        "final_answer": final_answer,
                        "execution_time": execution_time,
                        "workflow_name": "langgraph",
                    },
                    message="LangGraph execution completed successfully",
                )

                logger.info(
                    f"LangGraph execution completed | job_id={job_id} | "
                    f"execution_time={execution_time:.2f}s"
                )

            except JobCancelled:
                # Handle cancellation
                logger.info(f"LangGraph execution cancelled | job_id={job_id}")
                try:
                    self._job_repository.update_status(
                        job_id=job_id,
                        status=AgentJobStatus.CANCELLED,
                        message="Job was cancelled by user",
                    )
                except Exception as exc:
                    logger.error(
                        f"Failed to update job status to CANCELLED: {exc}",
                        exc_info=True,
                    )

            except Exception as exc:
                # Handle failure
                error_msg = str(exc)
                logger.error(
                    f"LangGraph execution failed | job_id={job_id} | error={error_msg}",
                    exc_info=True,
                )

                # Mark job as failed
                self.fail_job(
                    job_id=job_id,
                    error={
                        "error_type": type(exc).__name__,
                        "error_message": error_msg,
                    },
                    message=f"LangGraph execution failed: {error_msg}",
                )

        except Exception as exc:
            logger.error(
                f"Failed to prepare and dispatch workflow for job {job_id}: {exc}",
                exc_info=True,
            )
            # Mark job as failed
            self.fail_job(
                job_id=job_id,
                error={
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
                message=f"Failed to prepare workflow context: {str(exc)}",
            )

    def get_active_job_with_steps(
        self, *, user_id: str, project_id: str
    ) -> Optional["AgentJobResponse"]:
        """
        Get active job with full step telemetry for polling endpoint.

        Args:
            user_id: User ID
            project_id: Project ID

        Returns:
            Job response with steps, or None if no active job
        """
        job = self._job_repository.get_active_job(
            user_id=user_id, project_id=project_id
        )
        if not job:
            return None
        return self._job_to_response(job)

    def request_stop(self, *, job_id: str, user_id: str) -> "AgentJobResponse":
        """
        Request that a running job be stopped.

        Args:
            job_id: Job ID
            user_id: User ID (for ownership verification)

        Returns:
            Updated job response

        Raises:
            JobNotFoundError: If job doesn't exist
            JobAccessDeniedError: If user doesn't own the job
        """
        # 1. Fetch job and verify ownership
        try:
            job = self._job_repository.get_job(job_id=job_id, user_id=user_id)
        except RepoJobNotFoundError as exc:
            raise JobNotFoundError(job_id) from exc

        if job.user_id != user_id:
            raise JobAccessDeniedError(job_id, user_id)

        # 2. Mark as cancel requested
        try:
            updated_job = self._job_repository.mark_cancel_requested(
                job_id=job_id, reason="User requested cancellation"
            )
        except RepoJobNotFoundError as exc:
            raise JobNotFoundError(job_id) from exc

        # 3. Update status to CANCELLING if still active
        if updated_job.status in (
            AgentJobStatus.PENDING,
            AgentJobStatus.RUNNING,
        ):
            try:
                updated_job = self._job_repository.update_status(
                    job_id=job_id, status=AgentJobStatus.CANCELLING
                )
            except RepoJobNotFoundError as exc:
                raise JobNotFoundError(job_id) from exc

        # Cancellation is handled by _monitor_cancellation task
        # which checks job.cancel_requested and job.status == CANCELLING
        logger.info(f"Stop requested for job {job_id} by user {user_id}")
        return self._job_to_response(updated_job)

    def request_stop_by_project(
        self, *, project_id: str, user_id: str
    ) -> "AgentJobResponse":
        """
        Request that the active job for a project be stopped.

        Args:
            project_id: Project ID
            user_id: User ID (for ownership verification)

        Returns:
            Updated job response

        Raises:
            JobNotFoundError: If no active job exists for the project
            JobAccessDeniedError: If user doesn't own the job
        """
        # 1. Get active job for the project
        active_job = self._job_repository.get_active_job(
            user_id=user_id, project_id=project_id
        )
        if not active_job:
            raise JobNotFoundError(f"No active job found for project {project_id}")

        # 2. Use the existing request_stop method
        return self.request_stop(job_id=active_job.job_id, user_id=user_id)

    # ---------------------------------------------------------------------
    # Job lifecycle methods (called internally during workflow execution)
    # ---------------------------------------------------------------------

    def record_step(
        self,
        *,
        job_id: str,
        step_name: str,
        status: str = "running",
        message: Optional[str] = None,
        output: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record a step update (called by orchestrator).

        Args:
            job_id: Job ID
            step_name: Step name
            status: Step status (pending, running, completed, failed, skipped)
            message: Optional step message
            output: Optional step output
            metadata: Optional step metadata
        """
        try:
            step_status = AgentJobStepStatus(status)
        except ValueError:
            logger.warning(f"Invalid step status: {status}, defaulting to running")
            step_status = AgentJobStepStatus.RUNNING

        now = datetime.utcnow()
        step = MongoAgentJobStep(
            name=step_name,
            status=step_status,
            started_at=now if status == "running" else None,
            finished_at=now
            if status in ("completed", "failed", "skipped")
            else None,
            output=output,
            metadata=metadata or {},
            message=message,
        )

        try:
            self._job_repository.append_step(job_id=job_id, step=step)
            logger.debug(f"Recorded step {step_name} for job {job_id}")
        except RepoJobNotFoundError:
            logger.warning(f"Job {job_id} not found when recording step {step_name}")
        except Exception as exc:
            logger.error(
                f"Failed to record step {step_name} for job {job_id}: {exc}",
                exc_info=True,
            )

    def complete_job(
        self,
        *,
        job_id: str,
        result: Dict[str, Any],
        message: Optional[str] = None,
    ) -> None:
        """
        Mark job as completed.

        Args:
            job_id: Job ID
            result: Final result payload
            message: Optional completion message
        """
        try:
            self._job_repository.update_status(
                job_id=job_id,
                status=AgentJobStatus.COMPLETED,
                result=result,
                message=message,
            )
            logger.info(f"Job {job_id} marked as completed")
        except RepoJobNotFoundError:
            logger.warning(f"Job {job_id} not found when completing")
        except Exception as exc:
            logger.error(f"Failed to complete job {job_id}: {exc}", exc_info=True)

    def fail_job(
        self,
        *,
        job_id: str,
        error: Dict[str, Any],
        message: Optional[str] = None,
    ) -> None:
        """
        Mark job as failed.

        Args:
            job_id: Job ID
            error: Error payload
            message: Optional error message
        """
        try:
            self._job_repository.update_status(
                job_id=job_id,
                status=AgentJobStatus.FAILED,
                error=error,
                message=message,
            )
            logger.info(f"Job {job_id} marked as failed")
        except RepoJobNotFoundError:
            logger.warning(f"Job {job_id} not found when failing")
        except Exception as exc:
            logger.error(f"Failed to fail job {job_id}: {exc}", exc_info=True)

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------

    def _job_to_response(self, job: AgentJob) -> "AgentJobResponse":
        """Convert AgentJob model to AgentJobResponse schema."""
        # Lazy import to avoid circular dependency
        from textmsa.services.api.schemas import AgentJobResponse, AgentJobStep

        # Convert steps
        steps = []
        for step in job.steps:
            steps.append(
                AgentJobStep(
                    name=step.name,
                    status=step.status.value,
                    started_at=step.started_at.isoformat() if step.started_at else None,
                    finished_at=step.finished_at.isoformat()
                    if step.finished_at
                    else None,
                    output=step.output,
                    metadata=step.metadata,
                    message=step.message,
                )
            )

        return AgentJobResponse(
            job_id=job.job_id,
            project_id=job.project_id,
            status=job.status.value,
            cancel_requested=job.cancel_requested,
            message=getattr(job, "message", None),
            metadata=job.metadata,
            created_at=job.created_at.isoformat() if job.created_at else None,
            updated_at=job.updated_at.isoformat() if job.updated_at else None,
            finished_at=job.finished_at.isoformat() if job.finished_at else None,
            payload=job.payload,
            steps=steps,
            result=job.result,
            error=getattr(job, "error", None),
        )

    def _is_job_cancelled(self, job_id: str) -> bool:
        """
        Check if a job has been cancelled.

        Args:
            job_id: Job ID to check

        Returns:
            True if job is cancelled, False otherwise
        """
        try:
            job = self._job_repository.get_job(job_id=job_id, user_id=None)
            if not job:
                return False
            return job.cancel_requested or job.status == AgentJobStatus.CANCELLING
        except Exception as exc:
            logger.warning(f"Failed to check job cancellation status: {exc}")
            return False

    async def _monitor_cancellation(
        self, job_id: str, cancel_token: asyncio.Event
    ) -> None:
        """
        Monitor job cancellation status and set cancel token.

        This task runs in the background and periodically checks if the job
        has been cancelled, setting the cancel_token event if so.

        Args:
            job_id: Job ID to monitor
            cancel_token: Event to set when cancellation is detected
        """
        try:
            while True:
                await asyncio.sleep(0.5)  # Check every 500ms
                if self._is_job_cancelled(job_id):
                    cancel_token.set()
                    logger.info(f"Cancellation detected for job {job_id}")
                    break
        except asyncio.CancelledError:
            pass

    def _run_langgraph_sync(
        self,
        payload: Dict[str, Any],
        job_id: str,
        cancel_token: asyncio.Event,
    ) -> Dict[str, Any]:
        """
        Run LangGraph pipeline synchronously (called from executor).

        We currently support coarse-grained cancellation: if the job is
        marked as cancelling before or after the graph run, a JobCancelled
        error is raised so the caller can update job status accordingly.

        Args:
            payload: LangGraph payload
            job_id: Job ID
            cancel_token: Cancellation token

        Returns:
            Result dictionary from LangGraph execution

        Raises:
            JobCancelled: If job was cancelled before or during execution
        """
        # Check cancellation before starting
        if self._is_job_cancelled(job_id) or cancel_token.is_set():
            raise JobCancelled(job_id, "Job was cancelled before LangGraph started")

        # Execute LangGraph
        result = run_agent_graph(payload)

        # Check cancellation after completion
        if self._is_job_cancelled(job_id) or cancel_token.is_set():
            raise JobCancelled(job_id, "Job was cancelled during LangGraph execution")

        # Convert GraphState to dict
        if isinstance(result, dict):
            return result
        # If result is a GraphState object, convert to dict
        return dict(result or {})


_JOB_SERVICE_INSTANCE: AgentJobService | None = None


def get_agent_job_service() -> AgentJobService:
    """Get global job service instance (singleton)."""
    global _JOB_SERVICE_INSTANCE
    if _JOB_SERVICE_INSTANCE is None:
        _JOB_SERVICE_INSTANCE = AgentJobService()
    return _JOB_SERVICE_INSTANCE

