"""
API路由统一导出
"""
from textmsa.services.api.routers.user import user_router
from textmsa.services.api.routers.file import file_router
from textmsa.services.api.routers.file_type import file_type_router
from textmsa.services.api.routers.analysis import analysis_router
from textmsa.services.api.routers.spatial import spatial_router
from textmsa.services.api.routers.service import service_router
from textmsa.services.api.routers.knowledge import knowledge_router
from textmsa.services.api.routers.project import project_router
from textmsa.services.api.routers.visualization import visualization_router
from textmsa.services.api.routers.agent import agent_router

__all__ = [
    "user_router",
    "file_router",
    "file_type_router",
    "analysis_router",
    "spatial_router",
    "service_router",
    "knowledge_router",
    "project_router",
    "visualization_router",
    "agent_router",
]
