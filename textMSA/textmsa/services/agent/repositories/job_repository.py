"""
Agent job persistence backed by MongoDB.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from pymongo import ReturnDocument
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, PyMongoError

from textmsa.logging_config import get_logger
from textmsa.services.data import UserDataManagerMongoDB, get_user_data_manager
from textmsa.services.data.mongodb_models import (
    AgentJob,
    AgentJobStatus,
    AgentJobStep,
    agent_job_from_dict,
)

logger = get_logger(__name__)


class AgentJobRepositoryError(RuntimeError):
    """Base repository error."""


class AgentJobAlreadyExistsError(AgentJobRepositoryError):
    """Raised when attempting to create a duplicate job."""


class AgentJobNotFoundError(AgentJobRepositoryError):
    """Raised when a job cannot be located."""


class AgentJobRepository:
    """
    Mongo-backed repository for Agent jobs.

    Provides basic CRUD primitives that higher-level services can build on.
    """

    ACTIVE_STATUSES = {
        AgentJobStatus.PENDING.value,
        AgentJobStatus.RUNNING.value,
        AgentJobStatus.CANCELLING.value,
    }
    STEP_HISTORY_LIMIT = 200

    def __init__(
        self,
        *,
        data_manager: Optional[UserDataManagerMongoDB] = None,
    ) -> None:
        self._data_manager = data_manager or get_user_data_manager()
        self._collection: Collection = self._data_manager.agent_jobs_collection

    # ---------------------------------------------------------------------
    # Creation & retrieval
    # ---------------------------------------------------------------------
    def create_job(
        self,
        *,
        user_id: str,
        project_id: str,
        conversation_id: Optional[str] = None,
        payload: Dict[str, Any],
        job_id: Optional[str] = None,
        status: AgentJobStatus = AgentJobStatus.PENDING,
    ) -> AgentJob:
        """Persist a new job row."""
        now = datetime.utcnow()
        job = AgentJob(
            job_id=job_id or str(uuid4()),
            user_id=user_id,
            project_id=project_id,
            conversation_id=conversation_id,
            status=status,
            payload=payload or {},
            steps=[],
            cancel_requested=False,
            created_at=now,
            updated_at=now,
        )
        try:
            self._collection.insert_one(job.to_dict())
            return job
        except DuplicateKeyError as exc:
            logger.warning("Agent job already exists: job_id=%s", job.job_id)
            raise AgentJobAlreadyExistsError(str(exc)) from exc
        except PyMongoError as exc:
            logger.error("Failed to create agent job: %s", exc, exc_info=True)
            raise AgentJobRepositoryError("database error when creating job") from exc

# TODO: 需要修改，简化，只有还在进行的任务会加入到job表，因此不需要get_job以及get_active_job，因为两者相同
    def get_active_job(self, *, user_id: str, project_id: str) -> Optional[AgentJob]:
        """Return the active job for a user/project pair (if any)."""
        filter_query = {
            "user_id": user_id,
            "project_id": project_id,
            "status": {"$in": list(self.ACTIVE_STATUSES)},
        }
        doc = self._collection.find_one(filter_query, {"_id": 0})
        return self._deserialize(doc)

    def get_job(self, *, job_id: str, user_id: Optional[str] = None) -> AgentJob:
        """Fetch a job by ID, optionally asserting ownership."""
        filter_query: Dict[str, Any] = {"job_id": job_id}
        if user_id:
            filter_query["user_id"] = user_id
        doc = self._collection.find_one(filter_query, {"_id": 0})
        if not doc:
            raise AgentJobNotFoundError(f"job {job_id} not found")
        return self._deserialize(doc)  # type: ignore[return-value]

    # ---------------------------------------------------------------------
    # Mutations
    # ---------------------------------------------------------------------
    def update_status(
        self,
        *,
        job_id: str,
        status: AgentJobStatus | str,
        message: Optional[str] = None,
        finished_at: Optional[datetime] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[Dict[str, Any]] = None,
    ) -> AgentJob:
        """Update status + optional metadata/result payload."""
        try:
            status_value = status.value if isinstance(status, AgentJobStatus) else AgentJobStatus(status).value
        except ValueError as exc:
            raise AgentJobRepositoryError(f"invalid status: {status}") from exc
        now = datetime.now()
        updates: Dict[str, Any] = {
            "status": status_value,
            "updated_at": now,
        }
        if finished_at:
            updates["finished_at"] = finished_at
        elif status_value in (
            AgentJobStatus.COMPLETED.value,
            AgentJobStatus.FAILED.value,
            AgentJobStatus.CANCELLED.value,
        ):
            updates["finished_at"] = now
        if message is not None:
            updates["message"] = message
        if result is not None:
            updates["result"] = result
        if error is not None:
            updates["error"] = error
        updated = self._collection.find_one_and_update(
            {"job_id": job_id},
            {"$set": updates},
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )
        if not updated:
            raise AgentJobNotFoundError(f"job {job_id} not found")
        return self._deserialize(updated)  # type: ignore[return-value]

    def append_step(
        self,
        *,
        job_id: str,
        step: AgentJobStep | Dict[str, Any],
    ) -> AgentJob:
        """Append a telemetry step, trimming to STEP_HISTORY_LIMIT."""
        payload = step if isinstance(step, dict) else step.model_dump(exclude_none=True)
        if "name" not in payload:
            raise AgentJobRepositoryError("step payload missing 'name'")
        payload.setdefault("status", "pending")
        payload.setdefault("started_at", datetime.now().isoformat())
        updated = self._collection.find_one_and_update(
            {"job_id": job_id},
            {
                "$push": {
                    "steps": {
                        "$each": [payload],
                        "$slice": -self.STEP_HISTORY_LIMIT,
                    }
                },
                "$set": {"updated_at": datetime.now()},
            },
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )
        if not updated:
            raise AgentJobNotFoundError(f"job {job_id} not found")
        return self._deserialize(updated)  # type: ignore[return-value]

    def mark_cancel_requested(self, *, job_id: str, reason: Optional[str] = None) -> AgentJob:
        """Flag a job so orchestrator can terminate it."""
        updates: Dict[str, Any] = {
            "cancel_requested": True,
            "updated_at": datetime.now(),
        }
        if reason:
            updates["message"] = reason
        updated = self._collection.find_one_and_update(
            {"job_id": job_id},
            {"$set": updates},
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )
        if not updated:
            raise AgentJobNotFoundError(f"job {job_id} not found")
        return self._deserialize(updated)  # type: ignore[return-value]

    def save_result(
        self,
        *,
        job_id: str,
        result: Dict[str, Any],
    ) -> AgentJob:
        """Persist result payload without changing status."""
        updated = self._collection.find_one_and_update(
            {"job_id": job_id},
            {
                "$set": {
                    "result": result,
                    "updated_at": datetime.now(),
                }
            },
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )
        if not updated:
            raise AgentJobNotFoundError(f"job {job_id} not found")
        return self._deserialize(updated)  # type: ignore[return-value]

    def clear_steps(self, *, job_id: str) -> AgentJob:
        """Utility used by tests to wipe historical steps."""
        updated = self._collection.find_one_and_update(
            {"job_id": job_id},
            {
                "$set": {
                    "steps": [],
                    "updated_at": datetime.now(),
                }
            },
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )
        if not updated:
            raise AgentJobNotFoundError(f"job {job_id} not found")
        return self._deserialize(updated)  # type: ignore[return-value]

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------
    def _deserialize(self, doc: Optional[Dict[str, Any]]) -> Optional[AgentJob]:
        if not doc:
            return None
        try:
            return agent_job_from_dict(doc)
        except Exception as exc:
            logger.error("Failed to deserialize AgentJob: %s", exc, exc_info=True)
            raise AgentJobRepositoryError("invalid agent job payload") from exc


def get_agent_job_repository() -> AgentJobRepository:
    """Convenience accessor mirroring other service singletons."""
    return AgentJobRepository()

