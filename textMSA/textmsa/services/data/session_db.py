"""
Session 数据库服务 - MongoDB版本
负责管理用户会话数据
"""
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure, DuplicateKeyError
from pydantic import ValidationError

from textmsa.logging_config import get_logger
from textmsa.settings import get_mongodb_config
from textmsa.services.data.session_model import Session, session_from_dict

logger = get_logger(__name__)


class SessionDB:
    """Session 数据库服务，使用 MongoDB 存储会话数据"""

    def __init__(self, connection_string: Optional[str] = None, database_name: Optional[str] = None):
        """
        初始化 Session 数据库服务
        
        Args:
            connection_string: MongoDB 连接字符串（可选，优先使用配置）
            database_name: 数据库名称（可选，优先使用配置）
        """
        mongo_config = get_mongodb_config()
        
        connection_string = connection_string or mongo_config["uri"]
        database_name = database_name or mongo_config["database"]
        
        try:
            self.client = MongoClient(
                connection_string,
                serverSelectionTimeoutMS=mongo_config["server_selection_timeout_ms"],
                connectTimeoutMS=mongo_config["connect_timeout_ms"],
                socketTimeoutMS=mongo_config["socket_timeout_ms"],
                maxPoolSize=mongo_config["max_pool_size"],
                minPoolSize=mongo_config["min_pool_size"]
            )
            self.client.admin.command('ping')
            logger.info("成功连接到 MongoDB (SessionDB)")
        except ConnectionFailure as e:
            logger.error(f"无法连接到 MongoDB: {e}")
            raise
        
        self.db = self.client[database_name]
        self.sessions_collection = self.db.sessions
        
        self._create_indexes()
    
    def _create_indexes(self):
        """创建数据库索引"""
        try:
            self.sessions_collection.create_index(
                [("session_id", ASCENDING)],
                unique=True,
                name="session_id_unique",
            )
            self.sessions_collection.create_index(
                [("user_id", ASCENDING)],
                name="session_user_id_index",
            )
            self.sessions_collection.create_index(
                [("expires_at", ASCENDING)],
                name="session_expires_at_index",
                expireAfterSeconds=0,
            )
            self.sessions_collection.create_index(
                [("created_at", DESCENDING)],
                name="session_created_at_index",
            )
            logger.debug("SessionDB 索引创建完成")
        except Exception as e:
            logger.warning(f"创建索引时出错（可能已存在）: {e}")
    
    def create_session(self, session_id: str, user_id: str) -> bool:
        """
        创建会话
        
        Args:
            session_id: 会话ID
            user_id: 用户ID
        
        Returns:
            是否成功
        """
        try:
            now = datetime.now(timezone.utc)
            session = Session(
                session_id=session_id,
                user_id=user_id,
                created_at=now,
                expires_at=now + timedelta(days=30*12),  # 12个月
            )
            
            doc = session.to_dict()
            
            self.sessions_collection.insert_one(doc)
            logger.debug(f"创建会话成功: session_id={session_id}, user_id={user_id}")
            return True
            
        except DuplicateKeyError:
            logger.warning(f"会话已存在: session_id={session_id}")
            return False
        except ValidationError as e:
            logger.error(f"会话数据验证失败: {e}")
            return False
        except Exception as e:
            logger.error(f"创建会话失败: {e}")
            return False
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        获取会话数据
        
        Args:
            session_id: 会话ID
        
        Returns:
            会话数据字典，如果不存在返回 None
        """
        try:
            doc = self.sessions_collection.find_one({"session_id": session_id})
            
            if not doc:
                logger.debug(f"会话不存在: session_id={session_id}")
                return None
            
            session = session_from_dict(doc)
            
            return {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "created_at": session.created_at.isoformat() if hasattr(session.created_at, 'isoformat') else str(session.created_at),
                "expires_at": session.expires_at.isoformat() if hasattr(session.expires_at, 'isoformat') else str(session.expires_at),
            }
            
        except ValidationError as e:
            logger.error(f"会话数据解析失败: {e}")
            return None
        except Exception as e:
            logger.error(f"获取会话失败: {e}")
            return None
    
    def delete_session(self, session_id: str) -> bool:
        """
        删除会话
        
        Args:
            session_id: 会话ID
        
        Returns:
            是否成功
        """
        try:
            result = self.sessions_collection.delete_one({"session_id": session_id})
            
            if result.deleted_count > 0:
                logger.debug(f"删除会话成功: session_id={session_id}")
                return True
            
            logger.debug(f"会话不存在: session_id={session_id}")
            return False
            
        except Exception as e:
            logger.error(f"删除会话失败: {e}")
            return False
    
    def delete_user_sessions(self, user_id: str) -> int:
        """
        删除用户的所有会话
        
        Args:
            user_id: 用户ID
        
        Returns:
            删除的会话数量
        """
        try:
            result = self.sessions_collection.delete_many({"user_id": user_id})
            deleted_count = result.deleted_count
            logger.debug(f"删除用户会话成功: user_id={user_id}, count={deleted_count}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"删除用户会话失败: {e}")
            return 0
    
    def update_session_expiry(self, session_id: str, expires_weeks: int = 48) -> bool:
        """
        更新会话过期时间
        
        Args:
            session_id: 会话ID
            expires_weeks: 新的过期时间（周）
        
        Returns:
            是否成功
        """
        
        try:
            expires_at = datetime.now(timezone.utc) + timedelta(weeks=expires_weeks)
            
            result = self.sessions_collection.update_one(
                {"session_id": session_id},
                {"$set": {"expires_at": expires_at}}
            )
            
            if result.modified_count > 0:
                logger.debug(f"更新会话过期时间成功: session_id={session_id}")
                return True
            
            logger.debug(f"会话不存在: session_id={session_id}")
            return False
            
        except Exception as e:
            logger.error(f"更新会话过期时间失败: {e}")
            return False


_session_db_instance: Optional[SessionDB] = None


def get_session_db() -> SessionDB:
    """获取 SessionDB 单例实例"""
    global _session_db_instance
    if _session_db_instance is None:
        _session_db_instance = SessionDB()
    return _session_db_instance
