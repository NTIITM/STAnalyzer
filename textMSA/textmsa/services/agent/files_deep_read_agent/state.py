"""
Files Deep Read Agent 状态定义
"""

from __future__ import annotations

from ast import List
from typing import Optional, TypedDict

try:  # Python <3.11
    from typing import NotRequired  # type: ignore
except ImportError:
    from typing_extensions import NotRequired

from textmsa.logging_config import get_logger

logger = get_logger(__name__)


class FileTreeNodeBase(TypedDict):
    """文件树节点的必填字段"""

    file_id: str


class FileTreeNode(FileTreeNodeBase, total=False):
    """
    文件树节点格式约束：
    - 支持 filename / file_name 两种写法，兼容已有结构
    - children 为同构节点列表
    """

    file_name: str
    file_path: str
    description: str
    preview: str
    from_agent: str
    children: list["FileTreeNode"]


class GeneratedFileEntry(TypedDict, total=False):
    """生成的文件记录"""

    file_id: str
    file_name: str
    file_path: str
    description: str
    from_agent: NotRequired[str]


class ReadPlan(TypedDict, total=False):
    """阅读计划"""

    file_ids: list[str]
    integration_plan: str
    report_plan: str
    need_script: bool


class AnalysisPlan(TypedDict, total=False):
    """分析计划"""

    file_ids: List[str]
    instruct: str
    result: NotRequired[str]

class PlanHistory(TypedDict, total=False):
    """计划历史记录"""

    plan_type: str
    plan: ReadPlan | list[AnalysisPlan]
    reasoning: NotRequired[str]
    result: NotRequired[str | None]


class FilesDeepReadAgentState(TypedDict, total=False):
    """Files Deep Read Agent 的状态"""

    user_query: str
    file_tree_list: list[FileTreeNode]
    language: NotRequired[str]
    analysis_plans: list[AnalysisPlan]
    history_plans: list[PlanHistory]
    read_plan: ReadPlan
    generated_files_info: list[GeneratedFileEntry]
    message: NotRequired[dict]
    work_dir_path: str
    integration_code: NotRequired[str | None]
    final_answer: NotRequired[str | None]
    plan_count: NotRequired[int]
    next_route: NotRequired[str]
    user_id: NotRequired[str]  # 新增：用户ID
    project_id: NotRequired[str]  # 新增：项目ID


def build_initial_state(
    user_query: str,
    file_tree_list: list[FileTreeNode],
    work_dir_path: str,
    user_id: Optional[str] = None,  # 新增
    project_id: Optional[str] = None,  # 新增
) -> FilesDeepReadAgentState:
    """构建初始状态"""
    state: FilesDeepReadAgentState = {
        "user_query": user_query,
        "file_tree_list": file_tree_list,
        "language": "zh",
        "analysis_plans": [],
        "history_plans": [],
        "read_plan": {
            "file_ids": [],
            "integration_plan": "",
            "report_plan": "",
            "need_script": False,
        },
        "generated_files": [],
        "work_dir_path": work_dir_path,
        "current_plan_idx": 0,
        "plan_count": 0,
    }
    
    # 新增：添加 user_id 和 project_id
    if user_id:
        state["user_id"] = user_id
    if project_id:
        state["project_id"] = project_id
    
    logger.info(
        "Files Deep Read Agent initial state ready",
        extra={
            "work_dir_path": work_dir_path,
            "file_tree_len": len(file_tree_list) if isinstance(file_tree_list, list) else "n/a",
            "user_id": user_id,  # 新增
            "project_id": project_id,  # 新增
        },
    )
    return state


