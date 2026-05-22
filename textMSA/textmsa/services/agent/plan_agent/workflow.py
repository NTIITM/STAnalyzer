"""
Plan Agent 工作流定义

定义基于 LangGraph 的工作流图。
"""

from typing import Any
from langgraph.graph import END, StateGraph

from textmsa.logging_config import get_logger
from textmsa.services.agent.plan_agent.state import PlanAgentState
from textmsa.services.agent.plan_agent.nodes import (
    plan_node,
    execute_node,
    wait_execution_node,
    codegen_node,
    check_plan_route,
    report_node,
)

logger = get_logger(__name__)


# 享元模式：全局工作流实例缓存
_WORKFLOW_INSTANCE: Any = None  # CompiledStateGraph


def build_plan_agent_workflow() -> StateGraph[PlanAgentState]:
    """
    构建 Plan Agent 工作流图
    
    Returns:
        工作流图
    """
    logger.info("Building plan agent workflow")
    
    # 创建状态图
    workflow = StateGraph(PlanAgentState)
    
    # 添加节点
    workflow.add_node("plan", plan_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("wait_execute", wait_execution_node)
    workflow.add_node("codegen", codegen_node)
    workflow.add_node("report", report_node)
    
    # 设置入口
    workflow.set_entry_point("plan")
    
    # 条件路由：plan -> execute, codegen 或 report
    workflow.add_conditional_edges(
        "plan",
        check_plan_route,
        {
            "execute": "execute",
            "codegen": "codegen",
            "report": "report",
        },
    )
    
    # execute -> wait_execute -> plan（继续规划下一步）
    workflow.add_edge("execute", "wait_execute")
    workflow.add_edge("wait_execute", "plan")
    
    # codegen -> plan（继续规划下一步）
    workflow.add_edge("codegen", "plan")
    
    # report -> END
    workflow.add_edge("report", END)
    
    logger.info("Plan agent workflow built")
    
    return workflow


def compile_plan_agent_workflow() -> Any:  # Returns CompiledStateGraph
    """
    编译 Plan Agent 工作流图（使用享元模式避免多次初始化）
    
    Returns:
        编译后的工作流图
    """
    global _WORKFLOW_INSTANCE
    
    if _WORKFLOW_INSTANCE is None:
        logger.info("Compiling plan agent workflow (first time)")
        workflow = build_plan_agent_workflow()
        _WORKFLOW_INSTANCE = workflow.compile()
        logger.info("Plan agent workflow compiled and cached")
    else:
        logger.debug("Reusing cached plan agent workflow instance")
    
    return _WORKFLOW_INSTANCE


def reset_workflow_instance() -> None:
    """
    重置工作流实例（主要用于测试）
    """
    global _WORKFLOW_INSTANCE
    _WORKFLOW_INSTANCE = None
    logger.info("Plan agent workflow instance reset")

