"""
KnowledgeDocumentDict service: handles CRUD operations for knowledge document dictionary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import ConnectionFailure, DuplicateKeyError

from textmsa.logging_config import get_logger
from textmsa.settings import get_mongodb_config
from textmsa.services.data.mongodb_models import (
    KnowledgeDocumentDict,
    knowledge_document_dict_from_dict,
)

logger = get_logger(__name__)

# 单例实例
_knowledge_document_dict_service: Optional[KnowledgeDocumentDictService] = None


class KnowledgeDocumentDictService:
    """知识文档字典服务"""

    def __init__(self, connection_string: Optional[str] = None, database_name: Optional[str] = None):
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
                minPoolSize=mongo_config["min_pool_size"],
            )
            self.client.admin.command("ping")
            logger.info("KnowledgeDocumentDictService: connected to MongoDB")
        except ConnectionFailure as exc:
            logger.error("KnowledgeDocumentDictService: failed to connect MongoDB: %s", exc)
            raise

        self.db = self.client[database_name]
        self.collection = self.db.knowledge_document_dicts
        self._create_indexes()

    def _create_indexes(self) -> None:
        """创建数据库索引"""
        try:
            # title 作为主键，创建唯一索引
            self.collection.create_index([("title", ASCENDING)], unique=True)
            # project_id 和 query 的复合索引，便于按 project_id 和 query 查询
            self.collection.create_index([("project_id", ASCENDING), ("query", ASCENDING)])
            # project_id 索引，便于按 project_id 查询
            self.collection.create_index([("project_id", ASCENDING)])
            # 创建时间索引，便于排序查询
            self.collection.create_index([("created_at", DESCENDING)])
            logger.debug("KnowledgeDocumentDictService: indexes created")
        except Exception as exc:
            logger.warning("KnowledgeDocumentDictService: failed to create indexes (%s)", exc)

    def create_or_update_document_dict(self, document: KnowledgeDocumentDict) -> KnowledgeDocumentDict:
        """创建或更新文档字典（以 title 为主键）
        
        Args:
            document: 知识文档字典对象
            
        Returns:
            创建或更新后的文档字典对象
            
        Raises:
            HTTPException: 如果数据验证失败或数据库操作失败
        """
        try:
            # 检查是否已存在相同 title 的文档
            existing = self.collection.find_one({"title": document.title})
            
            # 准备更新数据
            doc_dict = document.to_dict()
            doc_dict["updated_at"] = datetime.now(timezone.utc)
            
            if existing:
                # 更新现有文档
                self.collection.update_one(
                    {"title": document.title},
                    {"$set": doc_dict}
                )
                logger.info(f"KnowledgeDocumentDictService: updated document dict with title '{document.title}'")
            else:
                # 创建新文档
                doc_dict["created_at"] = datetime.now(timezone.utc)
                self.collection.insert_one(doc_dict)
                logger.info(f"KnowledgeDocumentDictService: created document dict with title '{document.title}'")
            
            # 返回更新后的文档
            result = self.collection.find_one({"title": document.title})
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="创建文档后查询失败"
                )
            return knowledge_document_dict_from_dict(result)
            
        except DuplicateKeyError:
            # 理论上不应该发生，因为我们已经检查了存在性
            logger.error(f"KnowledgeDocumentDictService: duplicate key error for title '{document.title}'")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"文档标题 '{document.title}' 已存在"
            )
        except Exception as exc:
            logger.error(f"KnowledgeDocumentDictService: failed to create/update document dict: {exc}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"创建或更新文档字典失败: {str(exc)}"
            )

    def get_document_dict_by_title(self, title: str) -> Optional[KnowledgeDocumentDict]:
        """根据 title 查询文档字典
        
        Args:
            title: 文档标题
            
        Returns:
            文档字典对象，如果不存在则返回 None
        """
        try:
            result = self.collection.find_one({"title": title})
            if not result:
                return None
            return knowledge_document_dict_from_dict(result)
        except Exception as exc:
            logger.error(f"KnowledgeDocumentDictService: failed to get document dict by title '{title}': {exc}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"查询文档字典失败: {str(exc)}"
            )

    def delete_document_dict_by_title(self, title: str) -> bool:
        """根据 title 删除文档字典
        
        Args:
            title: 文档标题
            
        Returns:
            如果删除成功返回 True，如果文档不存在返回 False
            
        Raises:
            HTTPException: 如果数据库操作失败
        """
        try:
            result = self.collection.delete_one({"title": title})
            deleted = result.deleted_count > 0
            if deleted:
                logger.info(f"KnowledgeDocumentDictService: deleted document dict with title '{title}'")
            else:
                logger.warning(f"KnowledgeDocumentDictService: document dict with title '{title}' not found")
            return deleted
        except Exception as exc:
            logger.error(f"KnowledgeDocumentDictService: failed to delete document dict by title '{title}': {exc}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"删除文档字典失败: {str(exc)}"
            )

    def list_document_dicts(
        self,
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "created_at",
        sort_order: int = DESCENDING
    ) -> List[KnowledgeDocumentDict]:
        """列出文档字典
        
        Args:
            skip: 跳过的记录数
            limit: 返回的记录数上限
            sort_by: 排序字段
            sort_order: 排序顺序（ASCENDING 或 DESCENDING）
            
        Returns:
            文档字典列表
        """
        try:
            cursor = self.collection.find().sort(sort_by, sort_order).skip(skip).limit(limit)
            results = list(cursor)
            return [knowledge_document_dict_from_dict(doc) for doc in results]
        except Exception as exc:
            logger.error(f"KnowledgeDocumentDictService: failed to list document dicts: {exc}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"查询文档字典列表失败: {str(exc)}"
            )

    def get_document_dicts_by_project_grouped_by_query(
        self,
        project_id: str
    ) -> Dict[str, List[KnowledgeDocumentDict]]:
        """根据 project_id 查询所有文档，并按 query 分组
        
        Args:
            project_id: 项目ID
            
        Returns:
            字典，key 为 query，value 为该 query 下的文档列表
            
        Raises:
            HTTPException: 如果数据库操作失败
        """
        try:
            # 查询该 project_id 下的所有文档
            cursor = self.collection.find({"project_id": project_id}).sort("created_at", DESCENDING)
            results = list(cursor)
            
            # 转换为模型对象
            documents = [knowledge_document_dict_from_dict(doc) for doc in results]
            
            # 按 query 分组
            grouped: Dict[str, List[KnowledgeDocumentDict]] = {}
            for doc in documents:
                query = doc.query
                if query not in grouped:
                    grouped[query] = []
                grouped[query].append(doc)
            
            logger.info(f"KnowledgeDocumentDictService: found {len(documents)} documents for project_id '{project_id}', grouped into {len(grouped)} queries")
            return grouped
            
        except Exception as exc:
            logger.error(f"KnowledgeDocumentDictService: failed to get document dicts by project_id '{project_id}': {exc}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"根据项目ID查询文档字典失败: {str(exc)}"
            )


def get_knowledge_document_dict_service(
    connection_string: Optional[str] = None,
    database_name: Optional[str] = None
) -> KnowledgeDocumentDictService:
    """获取 KnowledgeDocumentDictService 单例实例"""
    global _knowledge_document_dict_service
    if _knowledge_document_dict_service is None:
        _knowledge_document_dict_service = KnowledgeDocumentDictService(
            connection_string=connection_string,
            database_name=database_name
        )
    return _knowledge_document_dict_service

