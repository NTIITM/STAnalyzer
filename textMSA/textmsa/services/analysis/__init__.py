"""
分析流程模块：轻量级包入口，避免在导入时触发循环依赖。

使用懒加载方式导出核心类/工厂函数，只有被访问时才真正导入对应模块。
"""

from __future__ import annotations

import importlib
from typing import Any, Dict, Tuple

# name -> (module_path, attr_name)
_LAZY_MAP: Dict[str, Tuple[str, str]] = {
    "FileNodeModel": ("textmsa.services.analysis.models", "FileNodeModel"),
    "AlgorithmEdgeModel": ("textmsa.services.analysis.models", "AlgorithmEdgeModel"),
    "AnalysisTreeModel": ("textmsa.services.analysis.models", "AnalysisTreeModel"),
    "get_analysis_service": ("textmsa.services.analysis.analysis_service", "get_analysis_service"),
    "AnalysisService": ("textmsa.services.analysis.analysis_service", "AnalysisService"),
    "CascadeDeletionService": ("textmsa.services.analysis.cascade_deletion_service", "CascadeDeletionService"),
    "get_cascade_deletion_service": ("textmsa.services.analysis.cascade_deletion_service", "get_cascade_deletion_service"),
    "FileAnalysisService": ("textmsa.services.analysis.file_analysis_service", "FileAnalysisService"),
    "get_file_analysis_service": ("textmsa.services.analysis.file_analysis_service", "get_file_analysis_service"),
}

__all__ = list(_LAZY_MAP.keys())


def __getattr__(name: str) -> Any:
    """Lazily import requested symbol to avoid circular imports."""
    if name not in _LAZY_MAP:
        raise AttributeError(f"module {__name__} has no attribute {name}")
    module_path, attr_name = _LAZY_MAP[name]
    module = importlib.import_module(module_path)
    value = getattr(module, attr_name)
    globals()[name] = value  # cache for future lookups
    return value


