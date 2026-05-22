from __future__ import annotations

from threading import Lock
from typing import Any, Mapping

from langgraph.graph import END, StateGraph

from textmsa.logging_config import get_logger
from textmsa.services.agent.exceptions import JobCancelled
from textmsa.services.agent.langgraph.jobs import check_job_cancelled

from .state import GraphState, InitialStatePayload, build_initial_state

logger = get_logger(__name__)


class AgentGraphSingleton:
    """
    单例模式管理编译后的 LangGraph，避免重复创建。
    """

    _instance: Any = None  # CompiledStateGraph
    _lock = Lock()

    @classmethod
    def get_compiled_graph(cls) -> Any:  # Returns CompiledStateGraph
        """
        获取编译后的图实例（单例）。
        如果尚未编译，则创建并缓存。
        """
        if cls._instance is None:
            with cls._lock:
                # 双重检查锁定
                if cls._instance is None:
                    logger.info("Compiling agent graph (first time)")
                    cls._instance = build_agent_graph().compile()
                    logger.info("Agent graph compiled and cached")
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """
        重置单例（主要用于测试）。
        """
        with cls._lock:
            cls._instance = None
            logger.debug("Agent graph singleton reset")


def _planner_router(state: GraphState) -> str:
    """
    路由函数：根据 planner 写入的 next_task_type 决定下一步节点。
    - knowledge: 进入知识检索
    - analyst: 进入分析执行
    - done: 进入最终回答
    """
    next_task_type = (state.get("next_task_type") or "").lower()
    if next_task_type == "analyst":
        return "analyst"
    if next_task_type == "done":
        return "done"
    if next_task_type == "knowledge":
        return "knowledge"
    raise ValueError(f"Invalid next task type: {next_task_type}")


def build_agent_graph() -> StateGraph:
    """
    Build the optimized LangGraph pipeline with new flow:
    1. Task planning -> Serial task execution (knowledge/analyst)
       -> Planner loop or final answer

    New flow features:
    - Serial task execution with planner-controlled loop
    - Final answer generation based on all results
    - Model question detection in final answer node (returns standard response)
    """

    logger.debug("Building optimized agent graph structure")
    # 延迟导入子图以避免在 import 阶段出现循环依赖
    from textmsa.services.agent.langgraph.subgraphs import (
        build_analyst_graph,
        final_answer_node,
        planner_node,
        knowledge_node,
    )

    graph = StateGraph(GraphState)
    
    # 编译子图
    analyst_subgraph = build_analyst_graph().compile()
    
    # 添加所有节点
    graph.add_node("planner", planner_node)
    graph.add_node("knowledge", knowledge_node)
    graph.add_node("analyst", analyst_subgraph)  # 使用编译后的子图而不是单个节点
    # 使用与 state key 区分开的节点名，避免 LangGraph 冲突
    graph.add_node("node_final_answer", final_answer_node)
    
    # 设置入口点
    graph.set_entry_point("planner")
    
    # 规划后根据 next_task_type 路由到具体执行节点或直接结束
    graph.add_conditional_edges(
        "planner",
        _planner_router,
        {
            "knowledge": "knowledge",
            "analyst": "analyst",
            "done": "node_final_answer",
        },
    )
    
    # Knowledge / Analyst 执行后直接回到 planner 做复盘与下轮决策
    graph.add_edge("knowledge", "planner")
    graph.add_edge("analyst", "planner")
    
    # 最终回答后结束
    graph.add_edge("node_final_answer", END)
    
    logger.debug("Optimized agent graph structure built successfully")
    return graph


REQUIRED_PAYLOAD_FIELDS = ("job_id", "user_id", "project_id", "message")


def _validate_payload(payload: Mapping[str, Any]) -> None:
    missing = [field for field in REQUIRED_PAYLOAD_FIELDS if not payload.get(field)]
    if missing:
        raise ValueError(f"payload missing required fields: {', '.join(missing)}")


def run_agent_graph(payload: Mapping[str, Any]) -> GraphState:
    """
    Validate the API payload, build the graph, and execute a single invocation.
    """

    job_id = str(payload.get("job_id", "unknown"))
    logger.info(
        "Starting agent graph execution",
        extra={
            "job_id": job_id,
            "user_id": str(payload.get("user_id", "unknown")),
            "project_id": str(payload.get("project_id", "unknown")),
            "message_length": len(str(payload.get("message", ""))),
        },
    )

    _validate_payload(payload)
    logger.debug("Payload validation passed", extra={"job_id": job_id})

    initial_payload: InitialStatePayload = {
        "job_id": job_id,
        "user_id": str(payload["user_id"]),
        "project_id": str(payload["project_id"]),
        "user_message": str(payload["message"]),
        # TODO：后续考虑利用，会话历史可能需要调整
        "conversation_history": [],
    }
    context: dict[str, Any] = dict(payload.get("context") or {})
    selected_file = payload.get("selected_file")
    if selected_file:
        if isinstance(selected_file, str):
            context.setdefault("selected_file_path", selected_file)
            logger.debug(
                "Selected file from string",
                extra={"job_id": job_id, "file_path": selected_file},
            )
        elif isinstance(selected_file, Mapping):
            if selected_file.get("id"):
                context.setdefault("selected_file_id", selected_file["id"])
                logger.debug(
                    "Selected file ID from mapping",
                    extra={"job_id": job_id, "file_id": selected_file["id"]},
                )
            if selected_file.get("path"):
                context.setdefault("selected_file_path", selected_file["path"])
                logger.debug(
                    "Selected file path from mapping",
                    extra={"job_id": job_id, "file_path": selected_file["path"]},
                )
    if context:
        initial_payload["context"] = context
        logger.debug(
            "Context added to initial payload",
            extra={"job_id": job_id, "context_keys": list(context.keys())},
        )

    logger.info("Building initial state", extra={"job_id": job_id})
    initial_state = build_initial_state(initial_payload)

    logger.info("Getting compiled agent graph (singleton)", extra={"job_id": job_id})
    compiled = AgentGraphSingleton.get_compiled_graph()

    logger.info("Invoking agent graph with cancellation support", extra={"job_id": job_id})
    try:
        # Check cancellation before starting
        check_job_cancelled(job_id)
        
        # Use stream to support cancellation checks between nodes
        # LangGraph stream returns events where keys are node names and values are state updates
        result = None
        for event in compiled.stream(initial_state):
            # Check cancellation after each node execution
            check_job_cancelled(job_id)
            
            # Collect the final state from stream events
            # Events are dictionaries with node names as keys and state updates as values
            # The last non-None state update should be the final result
            for node_name, node_state in event.items():
                if node_state is not None and isinstance(node_state, dict):
                    result = node_state
        
        # If no result was collected from stream, fall back to invoke
        # This should not happen in normal operation, but provides a fallback
        if result is None:
            logger.warning("No result from stream, falling back to invoke", extra={"job_id": job_id})
            # Check cancellation before fallback invoke
            check_job_cancelled(job_id)
        result = compiled.invoke(initial_state)
        
        # Final cancellation check
        check_job_cancelled(job_id)
        
        logger.info(
            "Agent graph execution completed",
            extra={
                "job_id": job_id,
                "has_final_answer": bool(result.get("final_answer")),
            },
        )
        return result
    except JobCancelled:
        logger.info(f"Job {job_id} was cancelled during graph execution")
        raise
    except Exception as exc:
        logger.error(
            "Agent graph execution failed",
            extra={"job_id": job_id},
            exc_info=True,
        )
        raise



