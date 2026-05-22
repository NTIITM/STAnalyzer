"""
Files Deep Read Agent 工作流
"""

from langgraph.graph import END, StateGraph

from textmsa.logging_config import get_logger

from .state import FilesDeepReadAgentState
from .nodes import analysis_plan_node, read_plan_node, analyze_node, decision_node, read_node, failure_node

logger = get_logger(__name__)


def _plan_router(state: FilesDeepReadAgentState) -> str:
    next_route = state.get("next_route")
    return next_route

def build_files_deep_read_agent_workflow() -> StateGraph:
    workflow = StateGraph(FilesDeepReadAgentState)

    workflow.add_node("decision", decision_node)
    workflow.add_node("analysis_plan", analysis_plan_node)
    workflow.add_node("read_plan", read_plan_node)

    workflow.add_node("analyze", analyze_node)
    # workflow.add_node("integrate", integrate_node)
    workflow.add_node("read", read_node)
    workflow.add_node("failure", failure_node)

    workflow.set_entry_point("decision")

    workflow.add_conditional_edges(
        "decision",
        _plan_router,
        {
            "analysis": "analysis_plan",
            "read": "read_plan",
            "failure": "failure",
        },
    )
    workflow.add_edge("analysis_plan", "analyze")
    workflow.add_edge("analyze", "decision")
    workflow.add_edge("read_plan", "read")
    workflow.add_edge("read", END)
    workflow.add_edge("failure", END)

    return workflow


def compile_files_deep_read_agent_workflow():
    wf = build_files_deep_read_agent_workflow()
    return wf.compile()


