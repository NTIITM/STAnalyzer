"""
Read Agent 工作流
"""

from langgraph.graph import END, StateGraph

from textmsa.logging_config import get_logger

from .state import ReadAgentState
from .nodes import plan_node, execute_plan_node, read_node, answer_node

logger = get_logger(__name__)


def _route_after_execute(state: ReadAgentState) -> str:
    """路由函数：根据 next_route 决定下一步"""
    next_route = state.get("next_route", "")
    return next_route or "read"


def build_read_agent_workflow() -> StateGraph:
    """构建 Read Agent 工作流"""
    workflow = StateGraph(ReadAgentState)

    # 添加节点
    workflow.add_node("plan", plan_node)
    workflow.add_node("execute_plan", execute_plan_node)
    workflow.add_node("read", read_node)
    workflow.add_node("answer", answer_node)

    # 设置入口点
    workflow.set_entry_point("plan")

    # 添加边
    workflow.add_edge("plan", "execute_plan")

    # execute_plan 节点根据状态路由到 read 或 answer
    workflow.add_conditional_edges(
        "execute_plan",
        _route_after_execute,
        {
            "read": "read",
            "answer": "answer",
        },
    )
    
    # read 节点执行完后回到 execute_plan 判断是否还有计划
    workflow.add_edge("read", "execute_plan")
    
    # answer 节点是终点
    workflow.add_edge("answer", END)

    return workflow


def compile_read_agent_workflow():
    """编译 Read Agent 工作流"""
    wf = build_read_agent_workflow()
    return wf.compile()
