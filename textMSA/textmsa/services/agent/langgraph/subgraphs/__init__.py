"""
Subgraph helpers for planner/knowledge/analyst components.

Exports are lazily loaded to avoid circular imports during module init.
"""

from __future__ import annotations

import importlib
from typing import Any, Dict, Tuple

_LAZY_MAP: Dict[str, Tuple[str, str]] = {
    "analyst_node": ("textmsa.services.agent.langgraph.subgraphs.analyst", "analyst_node"),
    "build_analyst_graph": ("textmsa.services.agent.langgraph.subgraphs.analyst", "build_analyst_graph"),
    "KnowledgeRetrievalResult": ("textmsa.services.agent.langgraph.subgraphs.knowledge", "KnowledgeRetrievalResult"),
    "build_knowledge_graph": ("textmsa.services.agent.langgraph.subgraphs.knowledge", "build_knowledge_graph"),
    "knowledge_analysis_router": ("textmsa.services.agent.langgraph.subgraphs.knowledge", "knowledge_analysis_router"),
    "knowledge_node": ("textmsa.services.agent.langgraph.subgraphs.knowledge", "knowledge_node"),
    "knowledge_router": ("textmsa.services.agent.langgraph.subgraphs.knowledge", "knowledge_router"),
    "to_state_update": ("textmsa.services.agent.langgraph.subgraphs.knowledge", "to_state_update"),
    "final_answer_node": ("textmsa.services.agent.langgraph.subgraphs.planner", "final_answer_node"),
    "planner_node": ("textmsa.services.agent.langgraph.subgraphs.planner", "planner_node"),
}

__all__ = list(_LAZY_MAP.keys())


def __getattr__(name: str) -> Any:
    if name not in _LAZY_MAP:
        raise AttributeError(f"module {__name__} has no attribute {name}")
    module_path, attr_name = _LAZY_MAP[name]
    module = importlib.import_module(module_path)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


