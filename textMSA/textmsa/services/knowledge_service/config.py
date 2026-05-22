"""Project-level datasource configuration stubs."""
from __future__ import annotations

from typing import List

# 默认可用数据源
DEFAULT_SOURCES: List[str] = ["pubmed", "arxiv", "crossref"]


def get_project_sources(project_id: str) -> List[str]:
    """
    Return datasource list for a project.

    当前使用静态默认值，后续可从数据库/配置中心读取。
    """
    return list(DEFAULT_SOURCES)

