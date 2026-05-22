from __future__ import annotations

from typing import Any, Literal, Mapping, Sequence, TypeVar, TypedDict

try:  # Python <3.11 compatibility
    from typing import NotRequired  # type: ignore
except ImportError:  # pragma: no cover - typing_extensions fallback
    from typing_extensions import NotRequired

from textmsa.logging_config import get_logger

T = TypeVar("T")

logger = get_logger(__name__)


class MessageDict(TypedDict, total=False):
    role: str
    content: str


class ContextFile(TypedDict, total=False):
    file_id: str
    file_path: str
    file_name: NotRequired[str]
    metadata: NotRequired[Mapping[str, Any]]


class PlannerTask(TypedDict, total=False):
    task_id: str
    description: NotRequired[str]
    status: NotRequired[Literal["pending", "running", "completed"]]
    metadata: NotRequired[Mapping[str, Any]]


class PlannerTodo(TypedDict, total=False):
    goal: NotRequired[str]
    assignee: NotRequired[Literal["knowledge", "analyst"]]
    status: NotRequired[
        Literal["pending", "running", "completed"]
    ]
    metadata: NotRequired[Mapping[str, Any]]


class KnowledgeQuery(TypedDict, total=False):
    query: str
    source: NotRequired[str]
    metadata: NotRequired[Mapping[str, Any]]


class KnowledgeDocument(TypedDict, total=False):
    doc_id: str
    title: NotRequired[str]
    snippet: NotRequired[str]
    source: NotRequired[str]
    metadata: NotRequired[Mapping[str, Any]]


class KnowledgeResult(TypedDict, total=False):
    query: NotRequired[str]
    documents: NotRequired[list[KnowledgeDocument]]
    insights: NotRequired[list[str]]
    metadata: NotRequired[Mapping[str, Any]]


class GraphState(TypedDict, total=False):
    # 基础信息
    job_id: str
    user_id: str
    project_id: str
    user_message: str
    conversation_history: list[MessageDict]

    # 上下文
    selected_file_id: NotRequired[str]
    context_files: list[ContextFile]

    # Planner 维护状态
    planner_todos: NotRequired[list[PlannerTodo]]
    final_answer: NotRequired[str] # planner对于最终答案的总结
    next_task_type: NotRequired[Literal["knowledge", "analyst", "done"]]

    # Knowledge 结果
    knowledge_results: list[KnowledgeResult]
    knowledge_summary: NotRequired[str]
    knowledge_final_answer: NotRequired[str] # knowledge对于最终答案的总结

    # Analyst 状态
    active_task: NotRequired[str] # 当前正在执行的任务（由todo拆解实现）
    active_todo: NotRequired[PlannerTodo] # 当前正在执行的任务（每次从todo中取出一项执行）
    matched_service_id: NotRequired[str] # 对应任务需要调用的服务ID
    execution_history: NotRequired[list[Mapping[str, Any]]]  # 记录执行历史，用于反思
    analyst_next_step: NotRequired[Literal["select_file", "summarize"]] # 根据执行结果反思下一步动作
    analyst_summary_plan: NotRequired[Mapping[str, str]] # 总结计划，用于反思
    analyst_final_answer: NotRequired[str] # analyst对于最终答案的总结


class InitialStateContext(TypedDict, total=False):
    selected_file_id: str | None
    context_files: Sequence[ContextFile]


class InitialStatePayload(TypedDict, total=False):
    job_id: str
    user_id: str
    project_id: str
    user_message: str
    conversation_history: NotRequired[Sequence[MessageDict]]
    context: NotRequired[InitialStateContext]


class StateUpdate(GraphState, total=False):
    """
    Partial state diff returned by LangGraph nodes.
    """


def _coerce_sequence(seq: Sequence[T] | None) -> list[T]:
    return list(seq) if seq else []


def build_initial_state(payload: InitialStatePayload) -> GraphState:
    """
    Map the orchestrator payload into a LangGraph-friendly state structure.
    """

    job_id = str(payload.get("job_id", "unknown"))
    logger.debug("Building initial state", extra={"job_id": job_id})

    conversation_history = _coerce_sequence(payload.get("conversation_history"))
    context = payload.get("context") or {}

    selected_file_id = context.get("selected_file_id")
    context_files = _coerce_sequence(context.get("context_files"))

    logger.debug(
        "Initial state context resolved",
        extra={
            "job_id": job_id,
            "conversation_history_length": len(conversation_history),
            "context_files_count": len(context_files),
            "has_selected_file_id": bool(selected_file_id),
        },
    )

    state: GraphState = {
        "job_id": job_id,
        "user_id": str(payload["user_id"]),
        "project_id": str(payload["project_id"]),
        "user_message": payload["user_message"],
        "conversation_history": conversation_history,
        "context_files": context_files,
        "knowledge_results": [],
        "private_docs": [],
        "execution_history": [],
        "evidence_summary": "",
    }

    if selected_file_id:
        state["selected_file_id"] = selected_file_id
        logger.debug("Selected file ID added to state", extra={"job_id": job_id, "file_id": selected_file_id})

    logger.info(
        "Initial state built successfully",
        extra={
            "job_id": job_id,
            "user_message_length": len(payload["user_message"]),
        },
    )

    return state


def merge_lists(old: Sequence[T] | None, new: Sequence[T] | None) -> list[T]:
    """
    Reducer helper for list fields shared across nodes.
    """

    merged = list(old or [])
    if new:
        merged.extend(new)
    return merged


def apply_state_update(state: GraphState, update: StateUpdate) -> GraphState:
    """
    Merge partial updates coming from LangGraph nodes.
    """

    next_state = GraphState(**state)
    for key, value in update.items():
        next_state[key] = value
    return next_state


def with_task(state: GraphState, task_id: str) -> GraphState:
    """
    Convenience helper for tracking the planner's active task.
    """

    next_state = GraphState(**state)
    next_state["active_task"] = task_id
    return next_state


__all__ = [
    "ContextFile",
    "GraphState",
    "InitialStatePayload",
    "KnowledgeDocument",
    "KnowledgeQuery",
    "KnowledgeResult",
    "MessageDict",
    "PlannerTodo",
    "PlannerTask",
    "StateUpdate",
    "apply_state_update",
    "build_initial_state",
    "merge_lists",
    "with_task",
]
