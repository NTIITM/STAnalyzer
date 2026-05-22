"""
File Analysis Agent 工作流构建

构建 LangGraph 工作流图，连接所有节点并设置条件路由。
"""

from langgraph.graph import END, StateGraph

from textmsa.logging_config import get_logger

from .state import FileAnalysisAgentState
from .nodes import (
    generate_sub_agent_info_node,
    generate_and_execute_sub_agent_node,
    return_result_node,
)

logger = get_logger(__name__)


def _generate_sub_agent_info_router(state: FileAnalysisAgentState) -> str:
    """
    生成子Agent信息节点的条件路由函数
    
    根据状态中的路由决策进行路由。
    
    Args:
        state: File Analysis Agent 状态
    
    Returns:
        下一个节点的名称
    """
    route = state.get("route_decision", "generate_code")
    
    logger.info(
        "File Analysis Agent - generate_sub_agent_info_router 路由决策",
        extra={
            "route": route,
            "has_sub_agent_info": "sub_agent_info" in state and state.get("sub_agent_info") is not None,
        },
    )
    
    return route


def build_file_analysis_agent_workflow() -> StateGraph:
    """
    构建 File Analysis Agent 工作流图
    
    Returns:
        构建好的 LangGraph StateGraph
    """
    logger.info("Building File Analysis Agent workflow")
    
    # 创建 StateGraph
    workflow = StateGraph(FileAnalysisAgentState)
    
    # 添加节点
    logger.debug("Adding nodes to workflow")
    workflow.add_node("generate_sub_agent_info", generate_sub_agent_info_node)
    workflow.add_node("generate_and_execute_sub_agent", generate_and_execute_sub_agent_node)
    workflow.add_node("return_result", return_result_node)
    
    # 设置入口
    logger.debug("Setting entry point")
    workflow.set_entry_point("generate_sub_agent_info")
    
    # 条件路由：generate_sub_agent_info
    # 路由决策：前往 generate_and_execute_sub_agent 或 return_result
    logger.debug("Setting conditional edges for generate_sub_agent_info")
    workflow.add_conditional_edges(
        "generate_sub_agent_info",
        _generate_sub_agent_info_router,
        {
            "generate_code": "generate_and_execute_sub_agent",
            "return_result": "return_result",
        },
    )
    
    # 直接边：generate_and_execute_sub_agent -> return_result
    # 无论成功还是失败都前往 return_result 节点
    logger.debug("Setting edge: generate_and_execute_sub_agent -> return_result")
    workflow.add_edge("generate_and_execute_sub_agent", "return_result")
    
    # 设置边：return_result -> END
    logger.debug("Setting edge: return_result -> END")
    workflow.add_edge("return_result", END)
    
    logger.info("File Analysis Agent workflow built successfully")
    
    return workflow


def compile_file_analysis_agent_workflow() -> StateGraph:
    """
    编译 File Analysis Agent 工作流图
    
    Returns:
        编译后的工作流图（可直接调用）
    """
    logger.info("Compiling File Analysis Agent workflow")
    
    workflow = build_file_analysis_agent_workflow()
    compiled_workflow = workflow.compile()
    
    logger.info("File Analysis Agent workflow compiled successfully")
    
    return compiled_workflow

