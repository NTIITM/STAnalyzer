"""
H5AD Agent 模块

提供 H5AD 文件查询和分析的 Agent 功能。

主要接口：
- run_h5ad_agent: 运行 H5AD Agent，处理用户查询并返回结果
- build_h5ad_agent_workflow: 构建工作流图
- compile_h5ad_agent_workflow: 编译工作流图
"""

from textmsa.logging_config import get_logger
from textmsa.services.agent.tools.file_reader_tool import FileReaderTool

from .state import H5ADAgentState, build_initial_state
from .workflow import build_h5ad_agent_workflow, compile_h5ad_agent_workflow

logger = get_logger(__name__)


def run_h5ad_agent(
    user_query: str,
    h5ad_file_path: str,
) -> dict:
    """
    运行 H5AD Agent，处理用户查询并返回结果
    
    Args:
        user_query: 用户查询
        h5ad_file_path: H5AD 文件路径
    
    Returns:
        包含最终答案和结构化结果的字典：
        {
            "final_answer": str,          # 最终答案
            "structured_result": dict,     # 结构化结果
            "is_complete": bool,           # 是否完成
            "error_message": str | None,   # 错误信息（如果有）
        }
    """
    logger.info(
        "Running H5AD Agent",
        extra={
            "user_query": user_query,
            "h5ad_file_path": h5ad_file_path,
            "query_length": len(user_query),
        },
    )
    
    # 获取文件预览信息
    file_preview = None
    try:
        logger.info("Extracting H5AD file preview information")
        file_reader_tool = FileReaderTool()
        file_preview = file_reader_tool.extract_h5ad_metadata(h5ad_file_path)
        # 如果提取失败，检查是否有错误信息
        if file_preview.get("error"):
            logger.warning(
                "Failed to extract H5AD file preview",
                extra={"error": file_preview.get("error")},
            )
            # 即使预览失败，也继续执行，只是没有预览信息
            file_preview = None
        else:
            logger.info(
                "H5AD file preview extracted",
                extra={
                    "n_spots": file_preview.get("n_spots"),
                    "n_genes": file_preview.get("n_genes"),
                    "has_spatial": file_preview.get("has_spatial"),
                },
            )
    except Exception as e:
        logger.warning(
            "Failed to extract H5AD file preview",
            extra={"error": str(e)},
            exc_info=True,
        )
        # 即使预览失败，也继续执行，只是没有预览信息
    
    # 构建初始状态
    initial_state = build_initial_state(
        user_query=user_query,
        h5ad_file_path=h5ad_file_path,
        file_preview=file_preview,
    )
    
    # 编译工作流
    workflow = compile_h5ad_agent_workflow()
    
    # 运行工作流
    logger.info("Invoking H5AD Agent workflow")
    final_state = workflow.invoke(initial_state)
    
    logger.info(
        "H5AD Agent workflow completed",
        extra={
            "is_complete": final_state.get("is_complete", False),
            "has_error": bool(final_state.get("error_message")),
            "final_answer_length": len(final_state.get("final_answer", "")),
        },
    )
    
    # 返回结果
    result = {
        "final_answer": final_state.get("final_answer", ""),
        "structured_result": final_state.get("structured_result", {}),
        "is_complete": final_state.get("is_complete", False),
        "error_message": final_state.get("error_message"),
    }
    
    logger.info(
        "H5AD Agent result prepared",
        extra={
            "is_complete": result["is_complete"],
            "has_error": bool(result["error_message"]),
            "final_answer_length": len(result["final_answer"]),
        },
    )
    
    return result


__all__ = [
    "H5ADAgentState",
    "build_initial_state",
    "build_h5ad_agent_workflow",
    "compile_h5ad_agent_workflow",
    "run_h5ad_agent",
]

