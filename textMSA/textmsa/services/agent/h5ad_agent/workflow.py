"""
H5AD Agent 工作流构建

构建 LangGraph 工作流图，连接所有节点并设置条件路由。
"""

from langgraph.graph import END, StateGraph

from textmsa.logging_config import get_logger

from .state import H5ADAgentState
from .nodes import (
    parse_query_node,
    generate_code_node,
    execute_code_node,
    check_result_node,
    synthesize_result_node,
)

logger = get_logger(__name__)


def _check_result_router(state: H5ADAgentState) -> str:
    """
    检查结果节点的条件路由函数
    
    根据执行结果决定下一步：
    - 如果成功 → synthesize_result
    - 如果失败且可重试 → generate_code（重试）
    - 如果失败且不可重试 → synthesize_result（即使失败也要给出结果）
    
    注意：check_result_node 已经处理了重试逻辑，这里只需要根据 should_retry 和 is_complete 路由
    
    Args:
        state: H5AD Agent 状态
    
    Returns:
        下一个节点的名称或 END
    """
    is_complete = state.get("is_complete", False)
    should_retry = state.get("should_retry", False)
    execution_attempts = state.get("execution_attempts", 0)
    
    logger.info(
        "H5AD Agent - check_result_router 路由决策",
        extra={
            "is_complete": is_complete,
            "should_retry": should_retry,
            "execution_attempts": execution_attempts,
        },
    )
    
    if should_retry:
        # 执行失败但可以重试，回到代码生成
        logger.info(
            "H5AD Agent - check_result_router 路由到 generate_code (重试)",
            extra={
                "reason": "should_retry=True",
                "execution_attempts": execution_attempts,
            },
        )
        return "generate_code"
    elif is_complete:
        # 执行成功或超过重试次数，进入结果合成
        # 即使执行失败，也要进入结果合成，让 synthesize_result_node 处理错误情况
        logger.info(
            "H5AD Agent - check_result_router 路由到 synthesize_result",
            extra={
                "reason": "is_complete=True",
                "execution_attempts": execution_attempts,
            },
        )
        return "synthesize_result"
    else:
        # 理论上不应该到达这里，但为了安全起见，进入结果合成
        logger.warning(
            "H5AD Agent - check_result_router 路由到 synthesize_result (默认)",
            extra={
                "reason": "未预期的状态，默认进入结果合成",
                "is_complete": is_complete,
                "should_retry": should_retry,
                "execution_attempts": execution_attempts,
            },
        )
        return "synthesize_result"


def build_h5ad_agent_workflow() -> StateGraph:
    """
    构建 H5AD Agent 工作流图
    
    Returns:
        构建好的 LangGraph StateGraph
    """
    logger.info("Building H5AD Agent workflow")
    
    # 创建 StateGraph
    workflow = StateGraph(H5ADAgentState)
    
    # 添加节点
    logger.debug("Adding nodes to workflow")
    workflow.add_node("parse_query", parse_query_node)
    workflow.add_node("generate_code", generate_code_node)
    workflow.add_node("execute_code", execute_code_node)
    workflow.add_node("check_result", check_result_node)
    workflow.add_node("synthesize_result", synthesize_result_node)
    
    # 设置边
    logger.debug("Setting edges in workflow")
    
    # 入口：START → parse_query
    workflow.set_entry_point("parse_query")
    
    # 线性流程
    workflow.add_edge("parse_query", "generate_code")
    workflow.add_edge("generate_code", "execute_code")
    workflow.add_edge("execute_code", "check_result")
    
    # 条件路由：check_result → synthesize_result 或 generate_code 或 END
    workflow.add_conditional_edges(
        "check_result",
        _check_result_router,
        {
            "synthesize_result": "synthesize_result",
            "generate_code": "generate_code",
            END: END,
        },
    )
    
    # 出口：synthesize_result → END
    workflow.add_edge("synthesize_result", END)
    
    logger.info("H5AD Agent workflow built successfully")
    
    return workflow


def compile_h5ad_agent_workflow() -> StateGraph:
    """
    编译 H5AD Agent 工作流图
    
    Returns:
        编译后的工作流图（可直接调用）
    """
    logger.info("Compiling H5AD Agent workflow")
    
    workflow = build_h5ad_agent_workflow()
    compiled_workflow = workflow.compile()
    
    logger.info("H5AD Agent workflow compiled successfully")
    
    return compiled_workflow

