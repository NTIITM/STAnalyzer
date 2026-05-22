"""
用户数据管理器 - MongoDB版本
负责管理用户相关的数据：上传的文件列表、对话记录、中间文件等
使用 MongoDB 存储，支持高性能查询和扩展
使用 Pydantic 进行数据验证和规范
"""
from typing import Any, Dict, List, Optional, Sequence, Set
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from pymongo import MongoClient, ASCENDING, DESCENDING, ReturnDocument
from pymongo.errors import ConnectionFailure, DuplicateKeyError, PyMongoError, BulkWriteError
from bson import ObjectId
from pydantic import ValidationError

from textmsa.logging_config import get_logger
from textmsa.settings import get_mongodb_config
from textmsa.services.data.mongodb_models import (
    FileInfo,
    FileType,
    AnalysisStatus,
    file_info_from_dict,
    file_type_from_dict,
    Project,
    project_from_dict,
    Knowledge,
    KnowledgeScope,
    knowledge_from_dict,
    AgentConversation,
    agent_conversation_from_dict,
    AgentMessage,
    AgentMessageRole,
    FileRelation,
    file_relation_from_dict,
    Memory,
    MemoryCollection,
    memory_collection_from_dict,
)

logger = get_logger(__name__)
DEFAULT_AGENT_MESSAGE_WINDOW = 50


class UserDataManagerMongoDB:
    """用户数据管理器，使用 MongoDB 存储用户数据"""
    
    def __init__(self, connection_string: Optional[str] = None, database_name: Optional[str] = None):
        """
        初始化用户数据管理器
        
        Args:
            connection_string: MongoDB 连接字符串（可选，优先使用配置）
            database_name: 数据库名称（可选，优先使用配置）
        """
        # 从配置文件读取 MongoDB 配置
        mongo_config = get_mongodb_config()
        
        # 优先使用传入参数，然后使用配置
        connection_string = connection_string or mongo_config["uri"]
        database_name = database_name or mongo_config["database"]
        
        # 连接 MongoDB
        try:
            self.client = MongoClient(
                connection_string,
                serverSelectionTimeoutMS=mongo_config["server_selection_timeout_ms"],
                connectTimeoutMS=mongo_config["connect_timeout_ms"],
                socketTimeoutMS=mongo_config["socket_timeout_ms"],
                maxPoolSize=mongo_config["max_pool_size"],
                minPoolSize=mongo_config["min_pool_size"]
            )
            # 测试连接
            self.client.admin.command('ping')
            logger.info("成功连接到 MongoDB")
        except ConnectionFailure as e:
            logger.error(f"无法连接到 MongoDB: {e}")
            raise
        
        # 选择数据库
        self.db = self.client[database_name]
        self.database_name = database_name
        self._file_type_cache: Dict[str, Optional[Dict[str, Any]]] = {}
        self._file_type_extension_cache: Dict[str, Optional[Dict[str, Any]]] = {}
        
        # 检查数据库是否存在，如果不存在则初始化
        if mongo_config.get("auto_init", True):
            self._ensure_database_initialized()
        
        # 集合
        self.users_collection = self.db.users
        self.files_collection = self.db.files
        self.projects_collection = self.db.projects
        self.knowledge_collection = self.db.knowledge
        self.agent_conversations_collection = self.db.agent_conversations
        self.agent_jobs_collection = self.db.agent_jobs
        self.file_types_collection = self.db.file_types
        self.file_relations_collection = self.db.file_relations
        # 记忆集合（按项目维度组织）
        self.memories_collection = self.db.memories
        # 会话集合
        self.sessions_collection = self.db.sessions
        
        # 创建索引
        self._create_indexes()
        
        logger.info(f"UserDataManagerMongoDB 初始化完成:")
        logger.info(f"  数据库: {database_name}")
        logger.info(f"  连接: {connection_string.split('@')[-1]}")  # 不显示密码
    
    def _ensure_database_initialized(self):
        """确保数据库已初始化"""
        try:
            # 检查数据库是否存在（通过检查是否有集合）
            collections = self.db.list_collection_names()
            
            if not collections:
                logger.info(f"数据库 '{self.database_name}' 不存在或为空，开始初始化...")
                # 创建初始集合（通过插入一个文档然后删除）
                self.files_collection.insert_one({
                    "_init": True,
                    "created_at": datetime.now()
                })
                self.files_collection.delete_one({"_init": True})
                logger.info(f"数据库 '{self.database_name}' 初始化完成")
            else:
                logger.debug(f"数据库 '{self.database_name}' 已存在，包含 {len(collections)} 个集合")
        except Exception as e:
            logger.warning(f"检查数据库状态时出错: {e}，继续执行...")
    
    def _create_indexes(self):
        """创建数据库索引（使用蛇形命名）"""
        try:
            # 先删除可能存在的旧索引（使用驼峰命名）
            try:
                self.files_collection.drop_index("user_file_unique")
            except:
                pass
            try:
                self.files_collection.drop_index("user_upload_time")
            except:
                pass
            try:
                self.files_collection.drop_index("user_last_viewed")
            except:
                pass
            try:
                self.files_collection.drop_index("file_id_unique")
            except:
                pass
            
            # 文件集合索引（使用蛇形命名）
            self.files_collection.create_index(
                [("user_id", ASCENDING), ("file_id", ASCENDING)], 
                unique=True,
                name="user_file_unique"
            )
            self.files_collection.create_index(
                [("user_id", ASCENDING), ("upload_time", DESCENDING)],
                name="user_upload_time"
            )
            self.files_collection.create_index(
                [("user_id", ASCENDING), ("last_viewed_time", DESCENDING)],
                name="user_last_viewed"
            )
            self.files_collection.create_index(
                "file_id", 
                unique=True,
                name="file_id_unique"
            )
            # 项目集合索引（使用蛇形命名）
            self.projects_collection.create_index(
                [("user_id", ASCENDING), ("project_id", ASCENDING)],
                unique=True,
                name="user_project_unique"
            )
            self.projects_collection.create_index(
                [("user_id", ASCENDING), ("created_at", DESCENDING)],
                name="user_project_created"
            )
            self.projects_collection.create_index(
                "project_id",
                unique=True,
                name="project_id_unique"
            )
            
            # 知识集合索引（使用蛇形命名）
            self.knowledge_collection.create_index(
                [("knowledge_id", ASCENDING)],
                unique=True,
                name="knowledge_id_unique"
            )
            self.knowledge_collection.create_index(
                [("user_id", ASCENDING), ("scope", ASCENDING)],
                name="user_scope"
            )
            self.knowledge_collection.create_index(
                [("user_id", ASCENDING), ("updated_at", DESCENDING)],
                name="user_updated"
            )
            self.knowledge_collection.create_index(
                [("scope", ASCENDING), ("updated_at", DESCENDING)],
                name="scope_updated"
            )
            # 文本搜索索引（用于keyword搜索）
            # 注意：MongoDB文本索引需要特殊语法，但这里使用regex搜索，所以不需要text索引
            # 如果需要更好的性能，可以考虑使用MongoDB Atlas Search或Elasticsearch
            # 这里使用普通索引支持排序和过滤即可
            
            # Agent 对话集合索引
            self.agent_conversations_collection.create_index(
                [("conversation_id", ASCENDING)],
                unique=True,
                name="agent_conversation_id_unique"
            )
            self.agent_conversations_collection.create_index(
                [("project_id", ASCENDING)],
                unique=True,
                name="agent_project_unique"
            )
            self.agent_conversations_collection.create_index(
                [("user_id", ASCENDING), ("updated_at", DESCENDING)],
                name="agent_conversation_updated"
            )
            # Agent job 索引（保留作业持久化，但不再依赖对话存储）
            self.agent_jobs_collection.create_index(
                [("job_id", ASCENDING)],
                unique=True,
                name="agent_job_id_unique",
            )
            self.agent_jobs_collection.create_index(
                [("updated_at", DESCENDING), ("status", ASCENDING)],
                name="agent_job_status_updated",
            )
            # 文件类型集合索引
            self.file_types_collection.create_index(
                [("file_type_id", ASCENDING)],
                unique=True,
                name="file_type_id_unique",
            )
            self.file_types_collection.create_index(
                [("name", ASCENDING)],
                unique=True,
                name="file_type_name_unique",
            )
            self.file_types_collection.create_index(
                [("category", ASCENDING)],
                name="file_type_category",
            )
            
            # 文件关系集合索引
            try:
                # 复合唯一索引：确保同一项目下同一父子关系唯一
                self.file_relations_collection.create_index(
                    [("parent_file_id", ASCENDING), ("child_file_id", ASCENDING), ("project_id", ASCENDING)],
                    unique=True,
                    name="parent_child_project_unique",
                    background=True  # 后台创建，不阻塞
                )
                
                # 单字段索引：用于查询父文件的所有子文件
                self.file_relations_collection.create_index(
                    [("parent_file_id", ASCENDING)],
                    name="parent_file_idx",
                    background=True
                )
                
                # 单字段索引：用于查询子文件的所有父文件
                self.file_relations_collection.create_index(
                    [("child_file_id", ASCENDING)],
                    name="child_file_idx",
                    background=True
                )
                
                # 单字段索引：用于查询项目下的所有关系
                self.file_relations_collection.create_index(
                    [("project_id", ASCENDING)],
                    name="project_idx",
                    background=True
                )
                
                logger.info("成功创建 file_relations 集合索引")
            except Exception as e:
                logger.error(f"创建 file_relations 索引失败: {e}", exc_info=True)
                # 不抛出异常，允许后续操作继续

            # 记忆集合索引
            try:
                self.memories_collection.create_index(
                    "project_id",
                    unique=True,
                    name="memory_project_id_unique",
                )
                self.memories_collection.create_index(
                    [("project_id", ASCENDING), ("updated_at", DESCENDING)],
                    name="memory_project_updated",
                )
            except Exception as e:
                logger.error(f"创建 memories 索引失败: {e}", exc_info=True)
                # 不中断初始化流程

            # 会话集合索引
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
            except Exception as e:
                logger.error(f"创建 sessions 索引失败: {e}", exc_info=True)
                # 不中断初始化流程

            logger.debug("数据库索引创建完成")
        except Exception as e:
            logger.warning(f"创建索引时出错（可能已存在）: {e}")
    
    def _sanitize_user_id(self, user_id: str) -> str:
        """清理用户ID，确保安全"""
        user_id = user_id.strip()[:100]
        safe = []
        for ch in user_id:
            if ch.isalnum() or ch in ("_", "-", "."):
                safe.append(ch)
            else:
                safe.append("_")
        return "".join(safe) or "anonymous"

    def _sanitize_project_id(self, project_id: str) -> str:
        """清理项目ID"""
        return (project_id or "").strip()

    def _normalize_extensions(self, extensions: Sequence[str]) -> List[str]:
        """统一扩展名格式（小写且以.开头）"""
        if not extensions:
            raise ValueError("extensions 不能为空")
        normalized: List[str] = []
        for ext in extensions:
            if not isinstance(ext, str):
                continue
            candidate = ext.strip().lower()
            if not candidate:
                continue
            if not candidate.startswith("."):
                candidate = f".{candidate}"
            normalized.append(candidate)
        if not normalized:
            raise ValueError("extensions 不能为空")
        # 去重但保持顺序
        return list(dict.fromkeys(normalized))

    def _serialize_file_type(self, file_type: FileType) -> Dict[str, Any]:
        """将 FileType 模型转换为可序列化字典"""
        data = file_type.to_dict()
        for key in ("created_at", "updated_at"):
            value = data.get(key)
            if isinstance(value, datetime):
                data[key] = value.isoformat()
        return data

    def _ensure_file_type_cache(self) -> Dict[str, Optional[Dict[str, Any]]]:
        """确保文件类型缓存可用"""
        if getattr(self, "_file_type_cache", None) is None:
            self._file_type_cache = {}
        return self._file_type_cache

    def _ensure_file_type_extension_cache(self) -> Dict[str, Optional[Dict[str, Any]]]:
        """确保扩展名缓存可用"""
        if getattr(self, "_file_type_extension_cache", None) is None:
            self._file_type_extension_cache = {}
        return self._file_type_extension_cache

    def _invalidate_file_type_cache(self, file_type_id: Optional[str] = None) -> None:
        """失效文件类型缓存"""
        cache = self._ensure_file_type_cache()
        if file_type_id:
            cache.pop(file_type_id, None)
        else:
            cache.clear()
        self._ensure_file_type_extension_cache().clear()
    
    def _get_file_type_details_from_cache(
        self,
        file_type_id: str,
    ) -> Optional[Dict[str, Any]]:
        """根据 file_type_id 获取详细信息并缓存"""
        if not file_type_id:
            return None
        cache = self._ensure_file_type_cache()
        if file_type_id in cache:
            cached = cache[file_type_id]
            return cached.copy() if isinstance(cached, dict) else cached
        try:
            doc = self.file_types_collection.find_one({"file_type_id": file_type_id})
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("查询文件类型失败: %s", exc)
            cache[file_type_id] = None
            return None
        if not doc:
            cache[file_type_id] = None
            return None
        try:
            file_type = file_type_from_dict(doc)
        except ValidationError as exc:
            logger.warning("文件类型数据解析失败: %s", exc)
            cache[file_type_id] = None
            return None
        payload = {
            "id": file_type.file_type_id,
            "name": file_type.name,
            "display_name": file_type.display_name,
            "description": file_type.description,
            "category": file_type.category,
            "extensions": file_type.extensions,
        }
        cache[file_type_id] = payload
        return payload.copy()

    def infer_file_type_by_extension(self, filename: Optional[str]) -> Optional[Dict[str, Any]]:
        """根据文件扩展名推断文件类型"""
        if not filename:
            return None
        extension = Path(filename).suffix.lower()
        if not extension:
            return None
        cache = self._ensure_file_type_extension_cache()
        if extension in cache:
            cached = cache[extension]
            return cached.copy() if isinstance(cached, dict) else cached
        try:
            doc = self.file_types_collection.find_one({"extensions": extension})
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("根据扩展名查询文件类型失败: %s", exc)
            cache[extension] = None
            return None
        if not doc:
            cache[extension] = None
            return None
        try:
            file_type = file_type_from_dict(doc)
        except ValidationError as exc:
            logger.warning("扩展名推断文件类型解析失败: %s", exc)
            cache[extension] = None
            return None
        payload = self._serialize_file_type(file_type)
        cache[extension] = payload
        return payload.copy()
    
    def _build_file_type_response(
        self,
        file_info: FileInfo,
    ) -> Dict[str, Any]:
        """基于 FileInfo 构建 file_type 响应"""
        details = self._get_file_type_details_from_cache(file_info.file_type_id)
        response = {
            "id": file_info.file_type_id,
            "name": file_info.file_type_name,
            "display_name": file_info.file_type_display_name,
            "description": None,
            "category": None,
            "extensions": [],
        }
        if details:
            response["description"] = details.get("description")
            response["category"] = details.get("category")
            response["extensions"] = details.get("extensions") or []
        return response

    # ============= 文件类型管理 =============

    def list_file_types(self, *, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出文件类型"""
        query: Dict[str, Any] = {}
        if category:
            query["category"] = category.strip()
        cursor = self.file_types_collection.find(query).sort("created_at", DESCENDING)
        results: List[Dict[str, Any]] = []
        for doc in cursor:
            try:
                file_type = file_type_from_dict(doc)
            except ValidationError as exc:
                logger.warning("文件类型数据解析失败，跳过: %s", exc)
                continue
            results.append(self._serialize_file_type(file_type))
        return results

    def get_file_type_by_id(self, file_type_id: str) -> Optional[Dict[str, Any]]:
        """通过ID获取文件类型"""
        if not file_type_id:
            return None
        doc = self.file_types_collection.find_one({"file_type_id": file_type_id})
        if not doc:
            return None
        try:
            file_type = file_type_from_dict(doc)
        except ValidationError as exc:
            logger.warning("文件类型数据解析失败: %s", exc)
            return None
        return self._serialize_file_type(file_type)

    def get_file_type_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """通过唯一名称获取文件类型"""
        if not name or not name.strip():
            return None
        doc = self.file_types_collection.find_one({"name": name.strip()})
        if not doc:
            return None
        try:
            file_type = file_type_from_dict(doc)
        except ValidationError as exc:
            logger.warning("文件类型数据解析失败: %s", exc)
            return None
        return self._serialize_file_type(file_type)

    def create_file_type(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """创建文件类型"""
        if not isinstance(payload, dict):
            raise ValueError("payload 必须是字典")
        data = payload.copy()
        data.setdefault("file_type_id", str(uuid4()))
        now = datetime.now(timezone.utc)
        data.setdefault("created_at", now)
        data["updated_at"] = now
        if "extensions" not in data:
            raise ValueError("extensions 为必填字段")
        data["extensions"] = self._normalize_extensions(data["extensions"])
        try:
            file_type = FileType(**data)
        except ValidationError as exc:
            logger.error("文件类型数据验证失败: %s", exc)
            raise
        doc = file_type.to_dict()
        try:
            self.file_types_collection.insert_one(doc)
        except DuplicateKeyError as exc:
            logger.error("文件类型已存在: %s", exc)
            raise
        self._invalidate_file_type_cache(file_type.file_type_id)
        return self._serialize_file_type(file_type)

    def update_file_type(self, file_type_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """更新文件类型"""
        if not file_type_id:
            raise ValueError("file_type_id 不能为空")
        if not updates:
            raise ValueError("updates 不能为空")
        data = updates.copy()
        if "name" in data and data["name"] is not None:
            name = str(data["name"]).strip()
            if not name:
                raise ValueError("name 不能为空")
            data["name"] = name
        if "display_name" in data and data["display_name"] is not None:
            display_name = str(data["display_name"]).strip()
            if not display_name:
                raise ValueError("display_name 不能为空")
            data["display_name"] = display_name
        if "extensions" in data:
            data["extensions"] = self._normalize_extensions(data["extensions"])
        data["updated_at"] = datetime.now(timezone.utc)
        doc = self.file_types_collection.find_one_and_update(
            {"file_type_id": file_type_id},
            {"$set": data},
            return_document=ReturnDocument.AFTER,
        )
        if not doc:
            return None
        try:
            file_type = file_type_from_dict(doc)
        except ValidationError as exc:
            logger.warning("文件类型数据解析失败: %s", exc)
            return None
        self._invalidate_file_type_cache(file_type.file_type_id)
        return self._serialize_file_type(file_type)

    def delete_file_type(self, file_type_id: str) -> bool:
        """删除文件类型"""
        if not file_type_id:
            return False
        result = self.file_types_collection.delete_one({"file_type_id": file_type_id})
        if result.deleted_count > 0:
            self._invalidate_file_type_cache(file_type_id)
            return True
        return False

    def count_files_by_file_type(self, file_type_id: str) -> int:
        """统计引用某文件类型的文件数量"""
        if not file_type_id:
            return 0
        try:
            return int(self.files_collection.count_documents({"file_type_id": file_type_id}))
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("统计文件类型引用失败: %s", exc)
            return 0
    
    # ============= 用户文件管理 =============
    
    def add_user_file(
        self,
        user_id: str,
        file_id: str,
        filename: str,
        file_type_id: str,
        file_type_name: str,
        file_type_display_name: str,
        description: Optional[str] = None,
        file_path: Optional[str] = None,
                                file_info: Optional[Dict[str, Any]] = None,
        generated_by: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        添加用户上传的文件到MongoDB（使用 Pydantic 验证）
        
        注意：此方法用于存储用户直接上传的文件或Service执行生成的文件。
        
        Args:
            user_id: 用户ID
            file_id: 文件ID（UUID格式）
            filename: 文件名
            file_type_id: 文件类型ID（必填）
            file_type_name: 文件类型唯一名称（必填）
            file_type_display_name: 文件类型展示名称（必填）
            file_path: 文件路径（可选,占位时可能为空）
            file_info: 额外文件信息（如 n_spots, n_genes 等），将存储在metadata中
            generated_by: 生成信息（如果是生成的文件，包含executionId, serviceId等）
        
        Returns:
            是否成功
        """
        try:
            user_id = self._sanitize_user_id(user_id)
            
            # 使用 Pydantic 模型验证和创建数据（使用蛇形命名）
            # metadata现在是动态结构，直接使用file_info
            file_info_model = FileInfo(
                user_id=user_id,  # 使用蛇形命名
                file_id=file_id,
                filename=filename,
                file_type_id=file_type_id,
                file_type_name=file_type_name,
                file_type_display_name=file_type_display_name,
                description=description,
                file_path=file_path,
                upload_time=datetime.now(),
                last_viewed_time=datetime.now(),
                analysis_status=AnalysisStatus.UPLOADED,
                metadata=file_info or {},  # 动态结构
                generated_by=generated_by,
            )
            
            # 转换为字典并插入
            file_doc = file_info_model.to_dict()
            self.files_collection.insert_one(file_doc)
            
            logger.info(f"文件已添加: {user_id}/{file_id}")
            return True
            
        except ValidationError as e:
            logger.error(f"文件数据验证失败: {e}")
            return False
        except DuplicateKeyError:
            logger.warning(f"文件已存在: {user_id}/{file_id}")
            return False
        except Exception as e:
            logger.error(f"添加文件失败: {e}")
            return False
    
    def get_user_uploaded_files(self, user_id: str) -> List[Dict[str, Any]]:
        """
        获取用户上传的所有文件列表（包括Service执行生成的文件）
        
        Args:
            user_id: 用户ID
        
        Returns:
            文件列表（使用驼峰命名）
        """
        try:
            user_id = self._sanitize_user_id(user_id)
            
            files = []
            # 使用蛇形命名字段查询
            for file_doc in self.files_collection.find(
                {"user_id": user_id}
            ).sort("upload_time", DESCENDING):
                
                # 使用 Pydantic 模型验证数据
                try:
                    file_info = file_info_from_dict(file_doc)
                except ValidationError as e:
                    logger.warning(f"文件数据格式错误，跳过: {file_doc.get('file_id')}, 错误: {e}")
                    continue
                
                # 构建返回数据（使用蛇形命名）
                result = {
                    "file_id": file_info.file_id,
                    "filename": file_info.filename,
                    "file_path": file_info.file_path,
                    "upload_time": file_info.upload_time.isoformat(),
                    "last_viewed_time": file_info.last_viewed_time.isoformat(),
                    "analysis_status": file_info.analysis_status.value,
                    "metadata": file_info.metadata,  # 已经是字典
                    "generated_by": file_info.generated_by,
                    "file_type": self._build_file_type_response(file_info),
                }
                files.append(result)
            
            return files
            
        except Exception as e:
            logger.error(f"获取用户文件失败: {e}")
            return []
    
    def get_file_info(self, user_id: str, file_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定文件的信息
        
        Args:
            user_id: 用户ID
            file_id: 文件ID（UUID格式）
        
        Returns:
            文件信息（使用蛇形命名），如果不存在返回 None
        """
        try:
            user_id = self._sanitize_user_id(user_id)
            
            # 使用蛇形命名查询
            file_doc = self.files_collection.find_one({
                "user_id": user_id,
                "file_id": file_id
            })
            
            if not file_doc:
                return None
            
            # 使用 Pydantic 模型验证
            file_info = file_info_from_dict(file_doc)
    
            return {
                "file_id": file_info.file_id,
                "filename": file_info.filename,
                "file_path": file_info.file_path,
                "upload_time": file_info.upload_time.isoformat() if hasattr(file_info.upload_time, 'isoformat') else str(file_info.upload_time),
                "last_viewed_time": file_info.last_viewed_time.isoformat() if hasattr(file_info.last_viewed_time, 'isoformat') else str(file_info.last_viewed_time),
                "analysis_status": file_info.analysis_status.value if hasattr(file_info.analysis_status, 'value') else str(file_info.analysis_status),
                "description": file_info.description,
                "metadata": file_info.metadata if isinstance(file_info.metadata, dict) else {},
                "generated_by": file_info.generated_by,
                "file_type_id": file_info.file_type_id,
                "file_type_name": file_info.file_type_name,
                "file_type_display_name": file_info.file_type_display_name,
            }
            
        except Exception as e:
            logger.error(f"获取文件信息失败: {e}")
            return None
    
    def delete_file(self, user_id: str, file_id: str) -> bool:
        """
        删除用户文件（从数据记录中删除，不删除物理文件）
        
        Args:
            user_id: 用户ID
            file_id: 文件ID
        
        Returns:
            是否成功
        """
        try:
            user_id = self._sanitize_user_id(user_id)
            
            # 删除文件记录（使用蛇形命名）
            result = self.files_collection.delete_one({
                "user_id": user_id,
                "file_id": file_id
            })
            
            if result.deleted_count > 0:
                logger.info(f"文件已删除: {user_id}/{file_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"删除文件失败: {e}")
            return False
    
    def update_file_view_time(self, user_id: str, file_id: str) -> bool:
        """
        更新文件最后查看时间
        
        Args:
            user_id: 用户ID
            file_id: 文件ID
        
        Returns:
            是否成功
        """
        try:
            user_id = self._sanitize_user_id(user_id)
            
            # 使用蛇形命名
            result = self.files_collection.update_one(
                {"user_id": user_id, "file_id": file_id},
                {"$set": {"last_viewed_time": datetime.now()}}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"更新查看时间失败: {e}")
            return False
    
    def update_file_status(self, user_id: str, file_id: str, status: str) -> bool:
        """
        更新文件分析状态
        
        Args:
            user_id: 用户ID
            file_id: 文件ID
            status: 状态 (uploaded, processing, completed, error)
        
        Returns:
            是否成功
        """
        try:
            user_id = self._sanitize_user_id(user_id)
            
            # 验证状态值
            try:
                status_enum = AnalysisStatus(status)
            except ValueError:
                logger.error(f"无效的状态值: {status}")
                return False
            
            # 使用蛇形命名
            result = self.files_collection.update_one(
                {"user_id": user_id, "file_id": file_id},
                {"$set": {"analysis_status": status_enum.value}}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"更新文件状态失败: {e}")
            return False
    
    def update_file_info(self, user_id: str, file_id: str, filename: Optional[str] = None,
    description: Optional[str] = None,
    file_path: Optional[str] = None,
    analysis_status: Optional[AnalysisStatus] = None,
    metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        更新文件基本信息（文件名和描述）
        
        Args:
            user_id: 用户ID
            file_id: 文件ID
            filename: 新的文件名（可选）
            description: 新的文件描述（可选）
            file_path: 新的文件路径（可选）
            analysis_status: 新的分析状态（可选）
            metadata: 新的元数据（可选）
        Returns:
            包含更新结果的字典: {"success": bool, "modified": bool, "message": str}
            - success: 操作是否成功
            - modified: 是否实际修改了数据
            - message: 操作结果消息
        """
        try:
            user_id = self._sanitize_user_id(user_id)
            
            # 构建更新字段
            update_fields = {}
            if filename is not None:
                update_fields["filename"] = filename
            if description is not None:
                # description 作为独立字段存储
                update_fields["description"] = description
            if file_path is not None:
                update_fields["file_path"] = file_path
            if analysis_status is not None:
                # 兼容处理：支持枚举对象和字符串两种类型
                update_fields["analysis_status"] = analysis_status.value if hasattr(analysis_status, 'value') else str(analysis_status)
            if metadata is not None:
                update_fields["metadata"] = metadata
                
            if not update_fields:
                logger.warning("没有提供要更新的字段")
                return {"success": False, "modified": False, "message": "没有提供要更新的字段"}
            
            # 执行更新（使用蛇形命名）
            result = self.files_collection.update_one(
                {"user_id": user_id, "file_id": file_id},
                {"$set": update_fields}
            )
            
            if result.modified_count > 0:
                logger.info(f"文件信息已更新: {user_id}/{file_id}")
                return {"success": True, "modified": True, "message": "文件信息已更新"}
            elif result.matched_count > 0:
                # 找到了记录但没有修改（字段值相同）
                logger.info(f"文件信息未变化: {user_id}/{file_id}")
                return {"success": True, "modified": False, "message": "文件信息未变化"}
            else:
                logger.warning(f"文件信息未更新（文件不存在）: {user_id}/{file_id}")
                return {"success": False, "modified": False, "message": "文件不存在"}
                
        except Exception as e:
            logger.error(f"更新文件信息失败: {e}")
            return {"success": False, "modified": False, "message": f"更新失败: {str(e)}"}
    
    def update_file_metadata(self, user_id: str, file_id: str, metadata: Dict[str, Any]) -> bool:
        """
        更新文件元数据
        
        Args:
            user_id: 用户ID
            file_id: 文件ID
            metadata: 元数据字典
        
        Returns:
            是否成功
        """
        try:
            user_id = self._sanitize_user_id(user_id)
            
            # 验证metadata是字典类型
            if not isinstance(metadata, dict):
                logger.error(f"元数据必须是字典类型，得到: {type(metadata)}")
                return False
            
            # 使用蛇形命名
            result = self.files_collection.update_one(
                {"user_id": user_id, "file_id": file_id},
                {"$set": {"metadata": metadata}}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"更新文件元数据失败: {e}")
            return False
    
    # ============= Project Agent 数据管理 =============

    def ensure_agent_conversation(self, user_id: str, project_id: str) -> Dict[str, Any]:
        """确保项目级对话存在，不存在则创建"""
        project_id = self._sanitize_project_id(project_id)
        if not project_id:
            raise ValueError("project_id is required")
        
        now = datetime.utcnow()
        conversation_doc = self.agent_conversations_collection.find_one_and_update(
            {"project_id": project_id},
            {
                "$setOnInsert": {
                    "conversation_id": str(uuid4()),
                    "project_id": project_id,
                    "messages": [],
                    "created_at": now
                },
                "$set": {
                    "updated_at": now
                }
            },
            upsert=True,
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER
        )
        conversation_id = conversation_doc.get("conversation_id")
        if not conversation_id:
            raise RuntimeError("无法创建或获取项目对话")
        # 更新项目对话ID
        self.projects_collection.update_one(
            {"project_id": project_id},
            {"$set": {"conversation_id": conversation_id}}
        )
        if not conversation_doc:
            raise RuntimeError("无法创建或获取项目对话")
        
        conversation = agent_conversation_from_dict(conversation_doc)
        return self._format_agent_conversation(conversation)

    def get_agent_conversation(self, project_id: str) -> Optional[Dict[str, Any]]:
        """获取项目级对话"""
        project_id = self._sanitize_project_id(project_id)
        if not project_id:
            return None
        conversation_doc = self.agent_conversations_collection.find_one(
            {"project_id": project_id},
            {"_id": 0}
        )
        if not conversation_doc:
            return None
        try:
            conversation = agent_conversation_from_dict(conversation_doc)
        except ValidationError as exc:
            logger.warning(f"Agent 对话数据解析失败: {exc}")
            return None
        return self._format_agent_conversation(conversation)

    def get_agent_conversation_by_id(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """通过 conversation_id 获取 Agent 对话"""
        if not conversation_id:
            return None
        conversation_doc = self.agent_conversations_collection.find_one(
            {"conversation_id": conversation_id},
            {"_id": 0},
        )
        if not conversation_doc:
            return None
        try:
            conversation = agent_conversation_from_dict(conversation_doc)
        except ValidationError as exc:
            logger.warning("Agent 对话数据解析失败: %s", exc)
            return None
        return self._format_agent_conversation(conversation)

    def add_agent_message(
        self,
        user_id: str,
        project_id: str,
        role: str,
        message: Optional[str] = None,
        *,
        extra: Optional[Dict[str, Any]] = None,
        time: Optional[datetime] = None,
        max_messages: Optional[int] = None,
        message_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """追加 Agent 对话消息（统一字段：role/message/time/extra）
        
        Args:
            max_messages: 如果指定且大于0，则只保留最后N条消息；如果为None，则保留所有消息
        """
        conversation = self.ensure_agent_conversation(user_id, project_id)
        try:
            role_enum = AgentMessageRole(role)
        except ValueError as exc:
            raise ValueError(f"无效的角色: {role}") from exc

        agent_message = AgentMessage(
            message_id=message_id or str(uuid4()),
            role=role_enum,
            message=message or "",
            time=time or datetime.utcnow(),
            extra=extra or {},
        )
        # 构建更新操作
        push_operation = {
            "$each": [agent_message.model_dump(exclude_none=True)]
        }
        # 只有当 max_messages 明确指定且大于 0 时才限制消息数量
        if max_messages is not None and max_messages > 0:
            limit = max(max_messages, 1)
            push_operation["$slice"] = -limit
        
        updated = self.agent_conversations_collection.find_one_and_update(
            {"conversation_id": conversation["conversation_id"]},
            {
                "$push": {
                    "messages": push_operation
                },
                "$set": {"updated_at": datetime.utcnow()}
            },
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER
        )
        if not updated:
            raise RuntimeError("更新对话消息失败")
        return agent_message.model_dump()

    def update_agent_message(
        self,
        *,
        conversation_id: str,
        message_id: str,
        message: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
        time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """更新指定消息内容或附加信息"""
        if not conversation_id:
            raise ValueError("conversation_id is required")
        if not message_id:
            raise ValueError("message_id is required")
        updates: Dict[str, Any] = {}
        if message is not None:
            updates["messages.$[msg].message"] = message
        if extra is not None:
            updates["messages.$[msg].extra"] = extra
        if time is not None:
            updates["messages.$[msg].time"] = time
        if not updates:
            raise ValueError("message, extra or time must be provided")
        updates["updated_at"] = datetime.utcnow()
        updated = self.agent_conversations_collection.find_one_and_update(
            {"conversation_id": conversation_id},
            {"$set": updates},
            array_filters=[{"msg.message_id": message_id}],
            projection={"_id": 0, "messages": {"$elemMatch": {"message_id": message_id}}},
            return_document=ReturnDocument.AFTER,
        )
        messages = (updated or {}).get("messages") if updated else None
        if not messages:
            raise RuntimeError("指定的消息不存在")
        message = messages[0]
        ts = message.get("time")
        if isinstance(ts, datetime):
            message["time"] = ts.isoformat()
        return message

    def _format_agent_conversation(self, conversation: AgentConversation) -> Dict[str, Any]:
        """格式化 Agent 对话"""
        data = conversation.to_dict()
        if isinstance(conversation.created_at, datetime):
            data["created_at"] = conversation.created_at.isoformat()
        if isinstance(conversation.updated_at, datetime):
            data["updated_at"] = conversation.updated_at.isoformat()
        formatted_messages = []
        for msg in conversation.messages:
            if isinstance(msg, AgentMessage):
                formatted = msg.model_dump(exclude_none=True)
            else:
                formatted = msg
            ts = formatted.get("time")
            if isinstance(ts, datetime):
                formatted["time"] = ts.isoformat()
            formatted_messages.append(formatted)
        data["messages"] = formatted_messages
        return data

    def clear_agent_conversation(self, user_id: str, project_id: str) -> bool:
        """
        清空项目的 Agent 对话内容（清空所有消息）
        
        Args:
            user_id: 用户ID
            project_id: 项目ID
        
        Returns:
            是否成功清空
        """
        try:
            project_id = self._sanitize_project_id(project_id)
            user_id = self._sanitize_user_id(user_id)
            
            if not project_id:
                raise ValueError("project_id is required")
            
            # 验证项目存在且用户有权限
            project = self.projects_collection.find_one(
                {"project_id": project_id, "user_id": user_id},
                {"_id": 0, "project_id": 1}
            )
            if not project:
                logger.warning(f"项目不存在或无权限: user_id={user_id}, project_id={project_id}")
                return False
            
            # 清空 conversation 的 messages 数组
            now = datetime.utcnow()
            result = self.agent_conversations_collection.update_one(
                {"project_id": project_id},
                {
                    "$set": {
                        "messages": [],
                        "updated_at": now
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"已清空 Agent 对话内容: user_id={user_id}, project_id={project_id}")
                return True
            elif result.matched_count > 0:
                # 对话存在但已经是空的
                logger.info(f"Agent 对话内容已为空: user_id={user_id}, project_id={project_id}")
                return True
            else:
                # 对话不存在，创建一个空的
                self.ensure_agent_conversation(user_id, project_id)
                logger.info(f"创建了空的 Agent 对话: user_id={user_id}, project_id={project_id}")
                return True
                
        except Exception as e:
            logger.error(f"清空 Agent 对话内容失败: {e}", exc_info=True)
            return False

    # ===== 便捷会话接口（统一命名，与计划文档对齐） =====

    def create_conversation(self, user_id: str, project_id: str) -> Dict[str, Any]:
        """
        便捷方法：创建或获取项目会话。

        Note:
            等价于 ensure_agent_conversation，保留旧方法用于向后兼容。
        """
        return self.ensure_agent_conversation(user_id=user_id, project_id=project_id)

    def append_message(
        self,
        user_id: str,
        project_id: str,
        role: str,
        message: Optional[str] = None,
        *,
        extra: Optional[Dict[str, Any]] = None,
        time: Optional[datetime] = None,
        max_messages: Optional[int] = None,
        message_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        便捷方法：在项目会话中追加一条消息。

        Note:
            等价于 add_agent_message，统一字段：role/message/time/extra。
        """
        return self.add_agent_message(
            user_id=user_id,
            project_id=project_id,
            role=role,
            message=message,
            extra=extra,
            time=time,
            max_messages=max_messages,
            message_id=message_id,
        )

    def get_conversation(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        便捷方法：获取项目会话详情。

        Note:
            等价于 get_agent_conversation。
        """
        return self.get_agent_conversation(project_id=project_id)

    def clear_conversation(self, user_id: str, project_id: str) -> bool:
        """
        便捷方法：清空项目会话中的所有消息。

        Note:
            等价于 clear_agent_conversation。
        """
        return self.clear_agent_conversation(user_id=user_id, project_id=project_id)

    # ============= 项目管理 =============
    
    def create_project(self, user_id: str, project_id: str, name: str, description: Optional[str] = None) -> Dict[str, Any]:
        """
        创建项目
        
        Args:
            user_id: 用户ID
            project_id: 项目ID（UUID格式）
            name: 项目名称（不能为空）
            description: 项目描述（可选）
        
        Returns:
            项目信息字典（使用蛇形命名）
        
        Raises:
            ValueError: 如果项目名称为空
            DuplicateKeyError: 如果项目ID已存在
        """
        try:
            user_id = self._sanitize_user_id(user_id)
            
            # 验证项目名称不能为空
            if not name or not name.strip():
                raise ValueError("项目名称不能为空")
            
            # 创建项目模型
            project = Project(
                project_id=project_id,
                user_id=user_id,
                name=name.strip(),
                description=description.strip() if description else None,
                knowledge_ids=[],
                service_ids=[],
                file_ids=[],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            self.projects_collection.insert_one(project.to_dict())
            logger.info(f"项目创建成功: {user_id}/{project_id}")
            return project.to_dict()
            
        except DuplicateKeyError:
            logger.error(f"项目ID已存在: {project_id}")
            raise
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"创建项目失败: {e}", exc_info=True)
            raise
    
    def get_project(self, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        """
        获取项目信息
        
        Args:
            user_id: 用户ID
            project_id: 项目ID
        Returns:
            项目信息字典，如果不存在返回 None
        """
        try:
            user_id = self._sanitize_user_id(user_id)
            
            project_doc = self.projects_collection.find_one({
                "user_id": user_id,
                "project_id": project_id
            })
            
            if not project_doc:
                return None
            
            # 使用 Pydantic 模型验证
            try:
                project = project_from_dict(project_doc)
            except ValidationError as e:
                logger.warning(f"项目数据格式验证失败: {e}")
                # 如果验证失败，直接返回原始数据
                project_doc.pop("_id", None)
                return project_doc
            
            # 转换为字典返回
            result = project.to_dict()
            # 处理 datetime 字段
            if isinstance(result.get("created_at"), datetime):
                result["created_at"] = result["created_at"].isoformat()
            if isinstance(result.get("updated_at"), datetime):
                result["updated_at"] = result["updated_at"].isoformat()
            
            return result
            
        except Exception as e:
            logger.error(f"获取项目信息失败: {e}", exc_info=True)
            return None
    
    def list_projects(self, user_id: str, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取用户项目列表（分页）
        
        Args:
            user_id: 用户ID
            skip: 跳过数量（默认0）
            limit: 返回数量限制（默认100，最大1000）
        
        Returns:
            项目列表（使用蛇形命名）
        """
        try:
            user_id = self._sanitize_user_id(user_id)
            
            # 限制最大返回数量为1000
            limit = min(limit, 1000)
            skip = max(0, skip)
            
            projects = []
            for project_doc in self.projects_collection.find(
                {"user_id": user_id}
            ).sort("created_at", DESCENDING).skip(skip).limit(limit):
                
                # 使用 Pydantic 模型验证
                try:
                    project = project_from_dict(project_doc)
                except ValidationError as e:
                    logger.warning(f"项目数据格式错误，跳过: {project_doc.get('project_id')}, 错误: {e}")
                    continue
                
                # 转换为字典
                result = project.to_dict()
                # 处理 datetime 字段
                if isinstance(result.get("created_at"), datetime):
                    result["created_at"] = result["created_at"].isoformat()
                if isinstance(result.get("updated_at"), datetime):
                    result["updated_at"] = result["updated_at"].isoformat()
                
                projects.append(result)
            
            return projects
            
        except Exception as e:
            logger.error(f"获取项目列表失败: {e}", exc_info=True)
            return []
    
    def update_project(self, user_id: str, project_id: str, name: Optional[str] = None, description: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        更新项目信息
        
        Args:
            user_id: 用户ID
            project_id: 项目ID
            name: 新的项目名称（可选）
            description: 新的项目描述（可选）
        
        Returns:
            更新后的项目信息字典（使用蛇形命名），如果项目不存在返回 None
        """
        try:
            user_id = self._sanitize_user_id(user_id)
            
            # 检查项目是否存在
            project = self.get_project(user_id, project_id)
            if not project:
                return None
            
            # 构建更新数据
            update_data = {}
            if name is not None:
                if not name.strip():
                    raise ValueError("项目名称不能为空")
                update_data["name"] = name.strip()
            if description is not None:
                update_data["description"] = description.strip() if description else None
            
            # 如果没有要更新的字段，直接返回
            if not update_data:
                return project
            
            # 更新 updated_at
            update_data["updated_at"] = datetime.utcnow()
            
            # 执行更新
            result = self.projects_collection.update_one(
                {"user_id": user_id, "project_id": project_id},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                logger.info(f"项目更新成功: {user_id}/{project_id}")
                # 返回更新后的项目信息
                return self.get_project(user_id, project_id)
            else:
                logger.warning(f"项目更新未修改任何字段: {user_id}/{project_id}")
                return project
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"更新项目失败: {e}", exc_info=True)
            raise
    
    def delete_project(self, user_id: str, project_id: str) -> bool:
        """
        删除项目
        
        Args:
            user_id: 用户ID
            project_id: 项目ID
        
        Returns:
            是否成功删除
        """
        try:
            user_id = self._sanitize_user_id(user_id)
            
            result = self.projects_collection.delete_one({
                "user_id": user_id,
                "project_id": project_id
            })
            
            if result.deleted_count > 0:
                logger.info(f"项目已删除: {user_id}/{project_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"删除项目失败: {e}", exc_info=True)
            return False
    
    def add_file_to_project(self, user_id: str, project_id: str, file_id: str) -> Optional[Dict[str, Any]]:
        """
        添加文件到项目
        
        Args:
            user_id: 用户ID
            project_id: 项目ID
            file_id: 文件ID
        
        Returns:
            更新后的项目信息字典（使用蛇形命名），如果项目不存在返回 None
        """
        try:
            user_id = self._sanitize_user_id(user_id)
            
            # 检查项目是否存在
            project = self.get_project(user_id, project_id)
            if not project:
                return None
            
            # 检查文件是否已在项目中
            file_ids = project.get("file_ids", [])
            if file_id in file_ids:
                logger.warning(f"文件已在项目中: {file_id}")
                return project
            
            # 添加文件ID到列表
            file_ids.append(file_id)
            
            # 更新项目
            result = self.projects_collection.update_one(
                {"user_id": user_id, "project_id": project_id},
                {
                    "$set": {
                        "file_ids": file_ids,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"文件已添加到项目: {user_id}/{project_id}/{file_id}")
                return self.get_project(user_id, project_id)
            else:
                return project
            
        except Exception as e:
            logger.error(f"添加文件到项目失败: {e}", exc_info=True)
            raise
    
    def remove_file_from_project(self, user_id: str, project_id: str, file_id: str) -> Optional[Dict[str, Any]]:
        """
        从项目中移除文件
        
        Args:
            user_id: 用户ID
            project_id: 项目ID
            file_id: 文件ID
        
        Returns:
            更新后的项目信息字典（使用蛇形命名），如果项目不存在返回 None
        """
        try:
            user_id = self._sanitize_user_id(user_id)
            
            # 检查项目是否存在
            project = self.get_project(user_id, project_id)
            if not project:
                return None
            
            # 检查文件是否在项目中
            file_ids = project.get("file_ids", [])
            if file_id not in file_ids:
                logger.warning(f"文件不在项目中: {file_id}")
                return project
            
            # 从列表中移除文件ID
            file_ids.remove(file_id)
            
            # 更新项目
            result = self.projects_collection.update_one(
                {"user_id": user_id, "project_id": project_id},
                {
                    "$set": {
                        "file_ids": file_ids,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"文件已从项目中移除: {user_id}/{project_id}/{file_id}")
                return self.get_project(user_id, project_id)
            else:
                return project
            
        except Exception as e:
            logger.error(f"从项目中移除文件失败: {e}", exc_info=True)
            raise

    def find_project_ids_by_file(self, user_id: str, file_id: str) -> List[str]:
        """
        查找包含指定文件的项目ID列表

        Args:
            user_id: 用户ID
            file_id: 文件ID

        Returns:
            项目ID列表
        """
        try:
            user_id = self._sanitize_user_id(user_id)
            cursor = self.projects_collection.find(
                {"user_id": user_id, "file_ids": file_id},
                {"project_id": 1, "_id": 0},
            )
            return [doc.get("project_id") for doc in cursor if doc.get("project_id")]
        except Exception as e:
            logger.error(f"查找包含文件的项目失败: {e}", exc_info=True)
            return []

    def find_project_ids_by_execution(self, user_id: str, execution_id: str) -> List[str]:
        """
        查找包含指定执行记录的项目ID列表

        Args:
            user_id: 用户ID
            execution_id: 执行ID

        Returns:
            项目ID列表
        """
        try:
            user_id = self._sanitize_user_id(user_id)
            cursor = self.projects_collection.find(
                {"user_id": user_id, "execution_ids": execution_id},
                {"project_id": 1, "_id": 0},
            )
            return [doc.get("project_id") for doc in cursor if doc.get("project_id")]
        except Exception as e:
            logger.error(f"查找包含执行的项目失败: {e}", exc_info=True)
            return []
    
    def get_project_files(self, user_id: str, project_id: str) -> List[str]:
        """
        获取项目文件列表
        
        Args:
            user_id: 用户ID
            project_id: 项目ID
        
        Returns:
            文件ID列表，如果项目不存在返回空列表
        """
        try:
            user_id = self._sanitize_user_id(user_id)
            
            project = self.get_project(user_id, project_id)
            if not project:
                return []
            
            return project.get("file_ids", [])
            
        except Exception as e:
            logger.error(f"获取项目文件列表失败: {e}", exc_info=True)
            return []
    
    def add_execution_to_project(self, user_id: str, project_id: str, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        添加执行记录到项目
        
        Args:
            user_id: 用户ID
            project_id: 项目ID
            execution_id: 执行ID
        
        Returns:
            更新后的项目信息字典（使用蛇形命名），如果项目不存在返回 None
        """
        try:
            user_id = self._sanitize_user_id(user_id)
            
            # 检查项目是否存在
            project = self.get_project(user_id, project_id)
            if not project:
                return None
            
            # 检查执行是否已在项目中
            execution_ids = project.get("execution_ids", [])
            if execution_id in execution_ids:
                logger.warning(f"执行已在项目中: {execution_id}")
                return project
            
            # 添加执行ID到列表
            execution_ids.append(execution_id)
            
            # 更新项目
            result = self.projects_collection.update_one(
                {"user_id": user_id, "project_id": project_id},
                {
                    "$set": {
                        "execution_ids": execution_ids,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"执行已添加到项目: {user_id}/{project_id}/{execution_id}")
                return self.get_project(user_id, project_id)
            else:
                return project
            
        except Exception as e:
            logger.error(f"添加执行到项目失败: {e}", exc_info=True)
            raise

    def remove_execution_from_project(self, user_id: str, project_id: str, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        从项目中移除执行记录

        Args:
            user_id: 用户ID
            project_id: 项目ID
            execution_id: 执行ID

        Returns:
            更新后的项目（若项目不存在则返回 None）
        """
        try:
            user_id = self._sanitize_user_id(user_id)
            project = self.get_project(user_id, project_id)
            if not project:
                return None

            execution_ids = project.get("execution_ids", [])
            if execution_id not in execution_ids:
                logger.warning(f"执行不在项目中: {execution_id}")
                return project

            execution_ids.remove(execution_id)
            result = self.projects_collection.update_one(
                {"user_id": user_id, "project_id": project_id},
                {
                    "$set": {
                        "execution_ids": execution_ids,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
            if result.modified_count > 0:
                logger.info(f"执行已从项目中移除: {user_id}/{project_id}/{execution_id}")
                return self.get_project(user_id, project_id)
            return project
        except Exception as e:
            logger.error(f"从项目中移除执行失败: {e}", exc_info=True)
            raise

    def add_knowledge_to_project(self, user_id: str, project_id: str, knowledge_id: str) -> Optional[Dict[str, Any]]:
        """
        将知识条目关联到项目
        """
        try:
            user_id = self._sanitize_user_id(user_id)
            project = self.get_project(user_id, project_id)
            if not project:
                return None

            knowledge_ids = project.get("knowledge_ids", [])
            if knowledge_id in knowledge_ids:
                return project

            knowledge_ids.append(knowledge_id)
            result = self.projects_collection.update_one(
                {"user_id": user_id, "project_id": project_id},
                {
                    "$set": {
                        "knowledge_ids": knowledge_ids,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            if result.modified_count > 0:
                logger.info(f"知识已添加到项目: {user_id}/{project_id}/{knowledge_id}")
                return self.get_project(user_id, project_id)
            return project
        except Exception as e:
            logger.error(f"添加知识到项目失败: {e}", exc_info=True)
            raise
    
    def update_project_knowledge_config(self, user_id: str, project_id: str, mode: str, whitelist: Optional[List[str]] = None, blacklist: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """
        更新项目知识配置
        
        Args:
            user_id: 用户ID
            project_id: 项目ID
            mode: 配置模式（all/whitelist/blacklist）
            whitelist: 知识ID白名单（mode=whitelist时生效）
            blacklist: 知识ID黑名单（mode=blacklist时生效）
        
        Returns:
            更新后的项目信息字典（使用蛇形命名），如果项目不存在返回 None
        """
        try:
            user_id = self._sanitize_user_id(user_id)
            
            # 验证模式
            if mode not in ["all", "whitelist", "blacklist"]:
                raise ValueError(f"无效的配置模式: {mode}，必须是 all/whitelist/blacklist")
            
            # 检查项目是否存在
            project = self.get_project(user_id, project_id)
            if not project:
                return None
            
            # 构建知识配置
            from textmsa.services.data.mongodb_models import ProjectKnowledgeConfig
            knowledge_config = ProjectKnowledgeConfig(
                mode=mode,
                whitelist=whitelist if whitelist is not None else (project.get("knowledge_config", {}).get("whitelist", []) if mode == "whitelist" else []),
                blacklist=blacklist if blacklist is not None else (project.get("knowledge_config", {}).get("blacklist", []) if mode == "blacklist" else [])
            )
            
            # 更新项目
            result = self.projects_collection.update_one(
                {"user_id": user_id, "project_id": project_id},
                {
                    "$set": {
                        "knowledge_config": knowledge_config.model_dump(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"项目知识配置已更新: {user_id}/{project_id}")
                return self.get_project(user_id, project_id)
            else:
                return project
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"更新项目知识配置失败: {e}", exc_info=True)
            raise
    
    def update_project_service_config(self, user_id: str, project_id: str, mode: str, whitelist: Optional[List[str]] = None, blacklist: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """
        更新项目服务配置
        
        Args:
            user_id: 用户ID
            project_id: 项目ID
            mode: 配置模式（all/whitelist/blacklist）
            whitelist: 服务ID白名单（mode=whitelist时生效）
            blacklist: 服务ID黑名单（mode=blacklist时生效）
        
        Returns:
            更新后的项目信息字典（使用蛇形命名），如果项目不存在返回 None
        """
        try:
            user_id = self._sanitize_user_id(user_id)
            
            # 验证模式
            if mode not in ["all", "whitelist", "blacklist"]:
                raise ValueError(f"无效的配置模式: {mode}，必须是 all/whitelist/blacklist")
            
            # 检查项目是否存在
            project = self.get_project(user_id, project_id)
            if not project:
                return None
            
            # 构建服务配置
            from textmsa.services.data.mongodb_models import ProjectServiceConfig
            service_config = ProjectServiceConfig(
                mode=mode,
                whitelist=whitelist if whitelist is not None else (project.get("service_config", {}).get("whitelist", []) if mode == "whitelist" else []),
                blacklist=blacklist if blacklist is not None else (project.get("service_config", {}).get("blacklist", []) if mode == "blacklist" else [])
            )
            
            # 更新项目
            result = self.projects_collection.update_one(
                {"user_id": user_id, "project_id": project_id},
                {
                    "$set": {
                        "service_config": service_config.model_dump(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"项目服务配置已更新: {user_id}/{project_id}")
                return self.get_project(user_id, project_id)
            else:
                return project
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"更新项目服务配置失败: {e}", exc_info=True)
            raise

    def remove_service_from_project_configs(self, service_id: str) -> Dict[str, int]:
        """
        将指定 service_id 从所有项目的服务配置中移除/加入黑名单
        
        - 当项目处于 whitelist 模式时，从 whitelist 中删除该 service
        - 当项目处于 blacklist 模式时，将该 service 加入 blacklist（如果尚未存在）
        - mode == all 的项目保持不变
        
        Returns:
            dict，包含更新的项目数量统计
        """
        if not service_id or not service_id.strip():
            raise ValueError("service_id 不能为空")
        
        service_id = service_id.strip()
        stats = {"whitelist_updated": 0, "blacklist_updated": 0}
        
        try:
            now = datetime.utcnow()
            whitelist_result = self.projects_collection.update_many(
                {
                    "service_config.mode": "whitelist",
                    "service_config.whitelist": service_id
                },
                {
                    "$pull": {"service_config.whitelist": service_id},
                    "$set": {"updated_at": now}
                }
            )
            stats["whitelist_updated"] = whitelist_result.modified_count
            
            blacklist_result = self.projects_collection.update_many(
                {
                    "service_config.mode": "blacklist",
                    "service_config.blacklist": {"$ne": service_id}
                },
                {
                    "$addToSet": {"service_config.blacklist": service_id},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
            stats["blacklist_updated"] = blacklist_result.modified_count
            
            if stats["whitelist_updated"] or stats["blacklist_updated"]:
                logger.info(
                    f"Service {service_id} 已从项目服务配置中移除/加入黑名单："
                    f"{stats['whitelist_updated']} 个白名单项目更新，"
                    f"{stats['blacklist_updated']} 个黑名单项目更新"
                )
            
            return stats
        except Exception as e:
            logger.error(f"移除 service_id={service_id} 的项目服务支持失败: {e}", exc_info=True)
            raise

    # ============= Memory 管理 =============

    def get_memory_collection(self, project_id: str) -> Optional[MemoryCollection]:
        """获取项目的记忆集合。"""
        project_id = self._sanitize_project_id(project_id)
        if not project_id:
            return None
        doc = self.memories_collection.find_one({"project_id": project_id})
        if not doc:
            return None
        try:
            return memory_collection_from_dict(doc)
        except ValidationError as exc:
            logger.warning("记忆集合数据解析失败: %s", exc)
            return None

    def add_memories(self, project_id: str, memories: List[Memory]) -> MemoryCollection:
        """向项目追加记忆（不存在则创建集合）。"""
        if not project_id:
            raise ValueError("project_id 不能为空")
        if not memories:
            raise ValueError("memories 不能为空")

        project_id = self._sanitize_project_id(project_id)
        now = datetime.now(timezone.utc)

        # 确保所有 Memory 对象合法
        normalized_memories: List[Memory] = []
        for mem in memories:
            if isinstance(mem, Memory):
                normalized_memories.append(mem)
            elif isinstance(mem, dict):
                normalized_memories.append(Memory(**mem))
            else:
                raise ValueError(f"无效的 Memory 类型: {type(mem)}")

        existing = self.get_memory_collection(project_id)
        if existing:
            existing.memory_list.extend(normalized_memories)
            existing.updated_at = now
            payload = existing.to_dict()
            self.memories_collection.update_one(
                {"project_id": project_id},
                {
                    "$set": {
                        "memory_list": payload.get("memory_list", []),
                        "updated_at": payload.get("updated_at", now),
                    }
                },
            )
            return existing

        # 创建新的集合文档
        collection = MemoryCollection(
            project_id=project_id,
            memory_list=normalized_memories,
            created_at=now,
            updated_at=now,
        )
        self.memories_collection.insert_one(collection.to_dict())
        return collection

    def delete_memory(self, project_id: str, memory_id: str) -> bool:
        """删除单个记忆。"""
        project_id = self._sanitize_project_id(project_id)
        if not project_id or not memory_id:
            return False
        result = self.memories_collection.update_one(
            {"project_id": project_id},
            {"$pull": {"memory_list": {"memory_id": memory_id}}},
        )
        return result.modified_count > 0

    def delete_memory_collection(self, project_id: str) -> bool:
        """删除项目的整套记忆。"""
        project_id = self._sanitize_project_id(project_id)
        if not project_id:
            return False
        result = self.memories_collection.delete_one({"project_id": project_id})
        return result.deleted_count > 0

    # ============= 知识管理 =============
    
    def create_knowledge(self, knowledge: Knowledge) -> Dict[str, Any]:
        """
        创建知识条目
        
        Args:
            knowledge: Knowledge 模型对象
        
        Returns:
            创建的知识信息字典（使用蛇形命名）
        """
        try:
            # 验证知识对象
            if not isinstance(knowledge, Knowledge):
                raise ValueError("knowledge 必须是 Knowledge 对象")
            
            # 转换为字典
            knowledge_dict = knowledge.to_dict()
            
            # 确保时间字段正确
            if not knowledge_dict.get("created_at"):
                knowledge_dict["created_at"] = datetime.utcnow()
            if not knowledge_dict.get("updated_at"):
                knowledge_dict["updated_at"] = datetime.utcnow()
            
            # 插入到数据库
            try:
                self.knowledge_collection.insert_one(knowledge_dict)
                logger.info(f"知识条目已创建: {knowledge.knowledge_id}")
            except DuplicateKeyError:
                raise ValueError(f"知识ID已存在: {knowledge.knowledge_id}")
            
            # 返回创建的知识信息
            result = knowledge.to_dict()
            # 处理 datetime 字段
            if isinstance(result.get("created_at"), datetime):
                result["created_at"] = result["created_at"].isoformat()
            if isinstance(result.get("updated_at"), datetime):
                result["updated_at"] = result["updated_at"].isoformat()
            if isinstance(result.get("shared_at"), datetime):
                result["shared_at"] = result["shared_at"].isoformat()
            
            return result
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"创建知识条目失败: {e}", exc_info=True)
            raise
    
    def get_knowledge(self, user_id: str, knowledge_id: str) -> Optional[Dict[str, Any]]:
        """
        获取知识条目详情
        
        Args:
            user_id: 用户ID（用于权限检查）
            knowledge_id: 知识ID
        
        Returns:
            知识信息字典（使用蛇形命名），如果不存在或无权访问返回 None
        """
        try:
            user_id = self._sanitize_user_id(user_id)
            
            # 查询知识条目
            knowledge_doc = self.knowledge_collection.find_one({"knowledge_id": knowledge_id})
            if not knowledge_doc:
                return None
            
            # 使用 Pydantic 模型验证
            try:
                knowledge = knowledge_from_dict(knowledge_doc)
            except ValidationError as e:
                logger.warning(f"知识数据格式错误: {knowledge_id}, 错误: {e}")
                return None
            
            # 权限检查：用户只能访问自己的知识、公共知识或系统知识
            if knowledge.user_id and knowledge.user_id != user_id:
                # 如果不是自己的知识，检查是否是公共或系统知识
                if knowledge.scope not in [KnowledgeScope.PUBLIC, KnowledgeScope.SYSTEM]:
                    return None
            
            # 转换为字典
            result = knowledge.to_dict()
            # 处理 datetime 字段
            if isinstance(result.get("created_at"), datetime):
                result["created_at"] = result["created_at"].isoformat()
            if isinstance(result.get("updated_at"), datetime):
                result["updated_at"] = result["updated_at"].isoformat()
            if isinstance(result.get("shared_at"), datetime):
                result["shared_at"] = result["shared_at"].isoformat()
            
            return result
            
        except Exception as e:
            logger.error(f"获取知识条目失败: {e}", exc_info=True)
            return None
    
    def list_knowledge(
        self,
        user_id: str,
        scope: Optional[str] = None,
        keyword: Optional[str] = None,
        edited_only: bool = False,
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "updated_at",
        sort_order: str = "desc"
    ) -> List[Dict[str, Any]]:
        """
        获取知识列表（支持过滤、分页、排序）
        
        Args:
            user_id: 用户ID
            scope: 范围过滤（private/public/system），None表示不过滤
            keyword: 关键词搜索（在title和description中搜索）
            edited_only: 是否只返回已编辑的知识（updated_at != created_at）
            skip: 跳过数量（默认0）
            limit: 返回数量限制（默认100，最大1000）
            sort_by: 排序字段（默认updated_at）
            sort_order: 排序顺序（asc/desc，默认desc）
        
        Returns:
            知识列表（使用蛇形命名）
        """
        try:
            user_id = self._sanitize_user_id(user_id)
            
            # 限制最大返回数量为1000
            limit = min(limit, 1000)
            skip = max(0, skip)
            
            # 构建查询条件
            query = {}
            
            # 权限过滤：用户可以看到自己的知识、公共知识和系统知识
            scope_conditions = []
            if user_id:
                scope_conditions.append({"user_id": user_id, "scope": KnowledgeScope.PRIVATE.value})
            scope_conditions.append({"scope": KnowledgeScope.PUBLIC.value})
            scope_conditions.append({"scope": KnowledgeScope.SYSTEM.value})
            
            if len(scope_conditions) > 1:
                query["$or"] = scope_conditions
            else:
                query.update(scope_conditions[0])
            
            # scope过滤
            if scope:
                try:
                    scope_enum = KnowledgeScope(scope)
                    # 如果指定了scope，需要同时满足权限和scope条件
                    if scope_enum == KnowledgeScope.PRIVATE:
                        # 私有知识必须是用户自己的
                        query = {"user_id": user_id, "scope": scope_enum.value}
                    else:
                        # 公共或系统知识
                        query = {"scope": scope_enum.value}
                except ValueError:
                    logger.warning(f"无效的scope值: {scope}，忽略此过滤条件")
            
            # keyword搜索（在title和description中搜索）
            if keyword:
                keyword = keyword.strip()
                if keyword:
                    keyword_condition = {
                        "$or": [
                            {"title": {"$regex": keyword, "$options": "i"}},
                            {"description": {"$regex": keyword, "$options": "i"}}
                        ]
                    }
                    # 如果已经有$or（权限条件），需要使用$and来组合
                    if "$or" in query:
                        original_or = query.pop("$or")
                        query["$and"] = [
                            {"$or": original_or},
                            keyword_condition
                        ]
                    else:
                        # 如果没有权限条件，直接添加keyword条件
                        query.update(keyword_condition)
            
            # edited_only过滤（只返回已编辑的知识）
            if edited_only:
                # 如果已经有$and，需要添加到$and中
                if "$and" in query:
                    query["$and"].append({"$expr": {"$ne": ["$updated_at", "$created_at"]}})
                else:
                    # 如果已经有其他条件，使用$and组合
                    if len(query) > 0:
                        existing_query = query.copy()
                        query.clear()
                        query["$and"] = [
                            existing_query,
                            {"$expr": {"$ne": ["$updated_at", "$created_at"]}}
                        ]
                    else:
                        query["$expr"] = {"$ne": ["$updated_at", "$created_at"]}
            
            # 排序
            sort_direction = DESCENDING if sort_order.lower() == "desc" else ASCENDING
            # 验证sort_by字段
            valid_sort_fields = ["created_at", "updated_at", "title", "knowledge_id"]
            if sort_by not in valid_sort_fields:
                logger.warning(f"无效的排序字段: {sort_by}，使用默认值 updated_at")
                sort_by = "updated_at"
            
            # 执行查询
            knowledge_list = []
            cursor = self.knowledge_collection.find(query).sort(sort_by, sort_direction).skip(skip).limit(limit)
            
            for knowledge_doc in cursor:
                # 使用 Pydantic 模型验证
                try:
                    knowledge = knowledge_from_dict(knowledge_doc)
                except ValidationError as e:
                    logger.warning(f"知识数据格式错误，跳过: {knowledge_doc.get('knowledge_id')}, 错误: {e}")
                    continue
                
                # 转换为字典
                result = knowledge.to_dict()
                # 处理 datetime 字段
                if isinstance(result.get("created_at"), datetime):
                    result["created_at"] = result["created_at"].isoformat()
                if isinstance(result.get("updated_at"), datetime):
                    result["updated_at"] = result["updated_at"].isoformat()
                if isinstance(result.get("shared_at"), datetime):
                    result["shared_at"] = result["shared_at"].isoformat()
                
                knowledge_list.append(result)
            
            return knowledge_list
            
        except Exception as e:
            logger.error(f"获取知识列表失败: {e}", exc_info=True)
            return []
    
    def update_knowledge(
        self,
        user_id: str,
        knowledge_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        relation_summary: Optional[Dict[str, Any]] = None,
        source: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        更新知识条目
        
        Args:
            user_id: 用户ID
            knowledge_id: 知识ID
            title: 新的标题（可选）
            description: 新的描述（可选）
            relation_summary: 新的关系摘要（可选）
            source: 新的来源说明（可选）
            metadata: 新的元数据（可选，会合并到现有metadata）
        
        Returns:
            更新后的知识信息字典（使用蛇形命名），如果知识不存在或无权访问返回 None
        """
        try:
            user_id = self._sanitize_user_id(user_id)
            
            # 检查知识是否存在且用户有权限
            knowledge = self.get_knowledge(user_id, knowledge_id)
            if not knowledge:
                return None
            
            # 权限检查：只有创建者可以更新（系统知识除外）
            if knowledge.get("user_id") and knowledge["user_id"] != user_id:
                if knowledge.get("scope") != KnowledgeScope.SYSTEM.value:
                    logger.warning(f"用户 {user_id} 尝试更新无权限的知识: {knowledge_id}")
                    return None
            
            # 构建更新数据
            update_data = {}
            if title is not None:
                title = title.strip()
                if not title:
                    raise ValueError("标题不能为空")
                update_data["title"] = title
            if description is not None:
                description = description.strip()
                if not description:
                    raise ValueError("描述不能为空")
                update_data["description"] = description
            if relation_summary is not None:
                from textmsa.services.data.mongodb_models import KnowledgeRelationSummary
                # 验证relation_summary格式
                relation = KnowledgeRelationSummary(**relation_summary)
                update_data["relation_summary"] = relation.model_dump()
            if source is not None:
                update_data["source"] = source.strip() if source else None
            if metadata is not None:
                # 合并到现有metadata
                existing_metadata = knowledge.get("metadata", {})
                if isinstance(existing_metadata, dict):
                    existing_metadata.update(metadata)
                    update_data["metadata"] = existing_metadata
                else:
                    update_data["metadata"] = metadata
            
            # 如果没有要更新的字段，直接返回
            if not update_data:
                return knowledge
            
            # 更新 updated_at
            update_data["updated_at"] = datetime.utcnow()
            
            # 更新数据库
            result = self.knowledge_collection.update_one(
                {"knowledge_id": knowledge_id},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                logger.info(f"知识条目已更新: {user_id}/{knowledge_id}")
                return self.get_knowledge(user_id, knowledge_id)
            else:
                return knowledge
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"更新知识条目失败: {e}", exc_info=True)
            raise
    
    def delete_knowledge(self, user_id: str, knowledge_id: str) -> bool:
        """
        删除知识条目
        
        Args:
            user_id: 用户ID
            knowledge_id: 知识ID
        
        Returns:
            是否成功删除
        """
        try:
            user_id = self._sanitize_user_id(user_id)
            
            # 检查知识是否存在且用户有权限
            knowledge = self.get_knowledge(user_id, knowledge_id)
            if not knowledge:
                return False
            
            # 权限检查：只有创建者可以删除（系统知识除外）
            if knowledge.get("user_id") and knowledge["user_id"] != user_id:
                if knowledge.get("scope") != KnowledgeScope.SYSTEM.value:
                    logger.warning(f"用户 {user_id} 尝试删除无权限的知识: {knowledge_id}")
                    return False
            
            # 删除知识条目
            result = self.knowledge_collection.delete_one({"knowledge_id": knowledge_id})
            
            if result.deleted_count > 0:
                logger.info(f"知识条目已删除: {user_id}/{knowledge_id}")
                return True
            else:
                return False
            
        except Exception as e:
            logger.error(f"删除知识条目失败: {e}", exc_info=True)
            return False
    
    def share_knowledge(self, user_id: str, knowledge_id: str, share_note: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        分享知识到公共范围
        
        Args:
            user_id: 用户ID
            knowledge_id: 知识ID
            share_note: 分享说明（可选）
        
        Returns:
            更新后的知识信息字典（使用蛇形命名），如果知识不存在或无权访问返回 None
        """
        try:
            user_id = self._sanitize_user_id(user_id)
            
            # 检查知识是否存在且用户有权限
            knowledge = self.get_knowledge(user_id, knowledge_id)
            if not knowledge:
                return None
            
            # 权限检查：只有创建者可以分享
            if knowledge.get("user_id") and knowledge["user_id"] != user_id:
                logger.warning(f"用户 {user_id} 尝试分享无权限的知识: {knowledge_id}")
                return None
            
            # 更新为公共范围
            update_data = {
                "scope": KnowledgeScope.PUBLIC.value,
                "shared_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            if share_note is not None:
                update_data["share_note"] = share_note.strip() if share_note else None
            
            # 更新数据库
            result = self.knowledge_collection.update_one(
                {"knowledge_id": knowledge_id},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                logger.info(f"知识条目已分享: {user_id}/{knowledge_id}")
                return self.get_knowledge(user_id, knowledge_id)
            else:
                return knowledge
            
        except Exception as e:
            logger.error(f"分享知识条目失败: {e}", exc_info=True)
            raise
    
    # ==================== 文件关系管理方法 ====================
    
    def get_file_relations(
        self,
        project_id: Optional[str] = None,
        parent_file_id: Optional[str] = None,
        child_file_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        查询文件关系
        
        Args:
            project_id: 项目ID（可选）
            parent_file_id: 父文件ID（可选）
            child_file_id: 子文件ID（可选）
        
        Returns:
            关系记录列表
        """
        try:
            query = {}
            if project_id:
                query["project_id"] = project_id
            if parent_file_id:
                query["parent_file_id"] = parent_file_id
            if child_file_id:
                query["child_file_id"] = child_file_id
            
            cursor = self.file_relations_collection.find(query)
            relations = []
            for doc in cursor:
                try:
                    relation = file_relation_from_dict(doc)
                    relation_dict = relation.to_dict()
                    # 添加 MongoDB _id 到返回结果
                    if "_id" in doc:
                        relation_dict["_id"] = str(doc["_id"])
                    relations.append(relation_dict)
                except Exception as e:
                    logger.warning(f"解析关系记录失败: {doc.get('_id')}, {e}")
                    continue
            
            return relations
        except Exception as e:
            logger.error(f"查询文件关系失败: {e}", exc_info=True)
            raise
    
    def get_file_children(
        self,
        parent_file_id: str,
        project_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取文件的所有子文件
        
        Args:
            parent_file_id: 父文件ID
            project_id: 项目ID（可选，用于过滤）
        
        Returns:
            子文件关系列表
        """
        return self.get_file_relations(
            parent_file_id=parent_file_id,
            project_id=project_id,
        )
    
    def get_file_parents(
        self,
        child_file_id: str,
        project_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取文件的所有父文件
        
        Args:
            child_file_id: 子文件ID
            project_id: 项目ID（可选，用于过滤）
        
        Returns:
            父文件关系列表
        """
        return self.get_file_relations(
            child_file_id=child_file_id,
            project_id=project_id,
        )
    
    def _check_circular_reference(
        self,
        parent_file_id: str,
        child_file_id: str,
    ) -> bool:
        """
        检查创建关系是否会导致循环引用
        
        Args:
            parent_file_id: 父文件ID
            child_file_id: 子文件ID
        
        Returns:
            True 如果存在循环引用，False 否则
        """
        # 检查 child_file_id 是否是 parent_file_id 的祖先
        visited = set()
        queue = [child_file_id]
        
        while queue:
            current = queue.pop(0)
            if current == parent_file_id:
                return True  # 发现循环
            if current in visited:
                continue
            visited.add(current)
            
            # 获取当前文件的所有父文件
            parents = self.get_file_parents(current)
            queue.extend([p["parent_file_id"] for p in parents])
        
        return False
    
    def create_file_relations(
        self,
        parent_file_ids: List[str],
        child_file_id: str,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        创建文件关系
        
        Args:
            parent_file_ids: 父文件ID列表（多个）
            child_file_id: 子文件ID
            description: 关系描述（可选）
        
        Returns:
            {
                "success": bool,
                "created_count": int,
                "message": str,
                "project_id": str,
            }
        
        Raises:
            ValueError: 如果parent_file_ids为空或parent文件不属于同一project_id
        """
        try:
            # 1. 验证参数
            if not parent_file_ids:
                raise ValueError("parent_file_ids 不能为空")
            
            if child_file_id in parent_file_ids:
                raise ValueError("子文件ID不能在父文件ID列表中")
            
            # 2. 验证所有父文件存在并获取 project_id 和 user_id
            project_ids = set()
            user_ids = set()
            
            for parent_id in parent_file_ids:
                # 通过 file_id 直接查询文件（file_id 是唯一索引）
                file_doc = self.files_collection.find_one({"file_id": parent_id})
                if not file_doc:
                    raise ValueError(f"父文件不存在: {parent_id}")
                
                # 获取 user_id
                user_id = file_doc.get("user_id")
                if user_id:
                    user_ids.add(user_id)
                
                # 通过 find_project_ids_by_file 获取 project_id
                if user_id:
                    parent_projects = self.find_project_ids_by_file(
                        user_id=user_id,
                        file_id=parent_id
                    )
                    if parent_projects:
                        project_ids.update(parent_projects)
            
            # 3. 验证所有父文件属于同一项目（如果多个，取第一个并记录警告）
            if len(project_ids) > 1:
                logger.warning(
                    f"父文件属于不同项目: {project_ids}，将使用第一个项目"
                )
            project_id = list(project_ids)[0] if project_ids else None
            
            if not project_id:
                raise ValueError("无法确定项目ID：父文件未关联到任何项目")
            
            # 4. 验证所有父文件属于同一用户（如果多个，取第一个并记录警告）
            if len(user_ids) > 1:
                logger.warning(
                    f"父文件属于不同用户: {user_ids}，将使用第一个用户"
                )
            user_id = list(user_ids)[0] if user_ids else None
            
            # 5. 验证子文件存在（可选，根据需求决定）
            child_file_doc = self.files_collection.find_one({"file_id": child_file_id})
            if not child_file_doc:
                raise ValueError(f"子文件不存在: {child_file_id}")
            
            # 验证子文件是否属于同一项目（如果子文件已关联项目）
            if user_id:
                child_projects = self.find_project_ids_by_file(
                    user_id=user_id,
                    file_id=child_file_id
                )
                if child_projects and project_id not in child_projects:
                    logger.warning(
                        f"子文件 {child_file_id} 不属于项目 {project_id}"
                    )
            
            # 6. 检查循环引用
            for parent_id in parent_file_ids:
                if self._check_circular_reference(parent_id, child_file_id):
                    raise ValueError(
                        f"创建关系会导致循环引用: {parent_id} -> {child_file_id}"
                    )
            
            # 7. 批量创建关系记录
            relations_to_insert = []
            for parent_id in parent_file_ids:
                relation = FileRelation(
                    parent_file_id=parent_id,
                    child_file_id=child_file_id,
                    project_id=project_id,
                    description=description,
                )
                relations_to_insert.append(relation.to_dict())
            
            # 8. 使用 insert_many，忽略重复
            created_count = 0
            try:
                result = self.file_relations_collection.insert_many(
                    relations_to_insert,
                    ordered=False,  # 即使部分失败也继续
                )
                created_count = len(result.inserted_ids)
            except BulkWriteError as e:
                # 处理重复键错误
                duplicate_count = sum(
                    1 for error in e.details.get("writeErrors", [])
                    if error.get("code") == 11000  # Duplicate key error
                )
                created_count = len(relations_to_insert) - duplicate_count
                if duplicate_count > 0:
                    logger.warning(
                        f"创建关系时发现 {duplicate_count} 个重复关系，已跳过"
                    )
                # 如果有其他错误，抛出异常
                if duplicate_count < len(relations_to_insert):
                    non_duplicate_errors = [
                        err for err in e.details.get("writeErrors", [])
                        if err.get("code") != 11000
                    ]
                    if non_duplicate_errors:
                        raise
            
            return {
                "success": True,
                "created_count": created_count,
                "message": f"成功创建 {created_count} 个关系",
                "project_id": project_id,
            }
        except ValueError as e:
            logger.error(f"创建文件关系失败（参数错误）: {e}")
            raise
        except Exception as e:
            logger.error(f"创建文件关系失败: {e}", exc_info=True)
            raise
    
    def delete_file_relations(
        self,
        project_id: Optional[str] = None,
        parent_file_id: Optional[str] = None,
        child_file_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        删除文件关系（支持级联删除）
        
        Args:
            project_id: 项目ID（可选）
            parent_file_id: 父文件ID（可选）
            child_file_id: 子文件ID（可选）
        
        Returns:
            {
                "success": bool,
                "deleted_count": int,
                "cascaded_relations": List[str],  # 级联删除的关系ID列表
            }
        
        注意:
            - 如果只提供 parent_file_id，会递归删除所有子文件的关系
            - 级联删除逻辑：删除父文件时，递归删除所有子文件及其关系
        """
        try:
            deleted_relation_ids = []
            
            # 如果提供了 parent_file_id，进行级联删除
            if parent_file_id:
                # 递归收集所有需要删除的关系
                def collect_relations_recursive(
                    p_file_id: str,
                    visited: Set[str]
                ) -> Set[str]:
                    """递归收集所有子文件的关系ID"""
                    if p_file_id in visited:
                        return set()
                    visited.add(p_file_id)
                    
                    # 查找所有直接子文件
                    children = self.get_file_children(
                        p_file_id,
                        project_id=project_id
                    )
                    
                    relation_ids = {c.get("_id") for c in children if c.get("_id")}
                    
                    # 递归处理每个子文件
                    for child_relation in children:
                        child_id = child_relation.get("child_file_id")
                        if child_id:
                            relation_ids.update(
                                collect_relations_recursive(child_id, visited)
                            )
                    
                    return relation_ids
                
                visited = set()
                all_relation_ids = collect_relations_recursive(parent_file_id, visited)
                
                # 删除所有收集到的关系
                if all_relation_ids:
                    # 将字符串 ID 转换为 ObjectId
                    object_ids = [ObjectId(rid) for rid in all_relation_ids if rid]
                    if object_ids:
                        result = self.file_relations_collection.delete_many(
                            {"_id": {"$in": object_ids}}
                        )
                        deleted_relation_ids.extend([str(oid) for oid in object_ids])
            else:
                # 普通删除：根据查询条件删除
                query = {}
                if project_id:
                    query["project_id"] = project_id
                if parent_file_id:
                    query["parent_file_id"] = parent_file_id
                if child_file_id:
                    query["child_file_id"] = child_file_id
                
                # 先查询要删除的关系ID
                cursor = self.file_relations_collection.find(query)
                relation_ids_to_delete = [str(doc["_id"]) for doc in cursor]
                
                # 删除关系
                if relation_ids_to_delete:
                    result = self.file_relations_collection.delete_many(query)
                    deleted_relation_ids.extend(relation_ids_to_delete)
                else:
                    # 创建一个模拟的结果对象
                    class MockResult:
                        deleted_count = 0
                    result = MockResult()
            
            return {
                "success": True,
                "deleted_count": len(deleted_relation_ids),
                "cascaded_relations": deleted_relation_ids,
            }
        except Exception as e:
            logger.error(f"删除文件关系失败: {e}", exc_info=True)
            raise
    
    def close(self):
        """关闭数据库连接"""
        if self.client:
            self.client.close()
            logger.info("MongoDB 连接已关闭")


# 全局用户数据管理器实例
_user_data_manager: Optional[UserDataManagerMongoDB] = None


def get_user_data_manager() -> UserDataManagerMongoDB:
    """获取全局用户数据管理器实例"""
    global _user_data_manager
    if _user_data_manager is None:
        _user_data_manager = UserDataManagerMongoDB()
    return _user_data_manager
