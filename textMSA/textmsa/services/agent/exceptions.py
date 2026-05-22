"""
Agent service layer exceptions.
"""


class AgentServiceError(RuntimeError):
    """Base exception for agent service layer errors."""


class ActiveJobExistsError(AgentServiceError):
    """Raised when attempting to start a job while another active job exists."""

    def __init__(self, job_id: str, message: str | None = None) -> None:
        self.job_id = job_id
        super().__init__(message or f"An active job already exists: {job_id}")


class JobNotFoundError(AgentServiceError):
    """Raised when a job cannot be found."""

    def __init__(self, job_id: str, message: str | None = None) -> None:
        self.job_id = job_id
        super().__init__(message or f"Job not found: {job_id}")


class JobAccessDeniedError(AgentServiceError):
    """Raised when a user attempts to access a job they don't own."""

    def __init__(self, job_id: str, user_id: str, message: str | None = None) -> None:
        self.job_id = job_id
        self.user_id = user_id
        super().__init__(
            message or f"User {user_id} does not have access to job {job_id}"
        )


class JobCancelled(AgentServiceError):
    """Raised when a job is cancelled during execution."""

    def __init__(self, job_id: str, message: str | None = None) -> None:
        self.job_id = job_id
        super().__init__(message or f"Job {job_id} was cancelled")

