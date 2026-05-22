"""
数据管理模块
"""
from textmsa.services.data.user_data_manager_mongodb import (
    UserDataManagerMongoDB,
    get_user_data_manager
)

__all__ = [
    "UserDataManagerMongoDB",
    "get_user_data_manager",
]

