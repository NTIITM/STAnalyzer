"""
Knowledge Agent 工作流
"""

from langgraph.graph import END, StateGraph

from textmsa.logging_config import get_logger

from .state import KnowledgeAgentState
from .nodes import intent_node, plan_node, execute_plan_node, read_node, answer_node, search_node, gene_relation_node

logger = get_logger(__name__)


def _route_after_execute(state: KnowledgeAgentState) -> str:
    """路由函数：根据 next_route 决定下一步"""
    next_route = state.get("next_route", "")
    return next_route or "read"


def build_knowledge_agent_workflow() -> StateGraph:
    """构建 Knowledge Agent 工作流"""
    workflow = StateGraph(KnowledgeAgentState)

    # 添加节点
    workflow.add_node("intent", intent_node)
    workflow.add_node("gene_relation", gene_relation_node)
    workflow.add_node("search", search_node)
    workflow.add_node("plan", plan_node)
    workflow.add_node("execute_plan", execute_plan_node)
    workflow.add_node("read", read_node)
    workflow.add_node("answer", answer_node)

    # 设置入口点：从意图识别开始
    workflow.set_entry_point("intent")

    # 添加边
    workflow.add_edge("intent", "gene_relation")
    workflow.add_edge("gene_relation", "search")
    workflow.add_edge("search", "plan")
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


def compile_knowledge_agent_workflow():
    """编译 Knowledge Agent 工作流"""
    wf = build_knowledge_agent_workflow()
    return wf.compile()

