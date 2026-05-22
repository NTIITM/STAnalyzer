"""
Orchestrator Agent 工作流
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from textmsa.logging_config import get_logger

from .nodes import decision_node, intent_plan_node
from .state import OrchestratorAgentState

logger = get_logger(__name__)


def build_orchestrator_agent_workflow() -> StateGraph:
    """构建 Orchestrator Agent 工作流"""
    workflow = StateGraph(OrchestratorAgentState)
    
    # 添加节点
    workflow.add_node("intent_plan", intent_plan_node)
    workflow.add_node("decision", decision_node)
    
    # 设置入口点
    workflow.set_entry_point("intent_plan")
    
    # 添加边
    workflow.add_edge("intent_plan", "decision")
    workflow.add_edge("decision", END)
    
    return workflow


def compile_orchestrator_agent_workflow():
    """编译 Orchestrator Agent 工作流（使用内存 checkpoint）"""
    workflow = build_orchestrator_agent_workflow()
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)

