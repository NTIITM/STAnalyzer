"""
Service服务
算法/Service管理服务，用于管理算法执行和tag分配
统一通过后端转发数据和请求到远程服务器处理
支持权限控制（private/public）和审核机制
"""
import os
import uuid
import time
import json
import tempfile
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any, Union, Tuple
from datetime import datetime
from urllib.parse import urljoin
import httpx
from fastapi import HTTPException, status
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure, DuplicateKeyError
from pydantic import ValidationError

from textmsa.logging_config import get_logger
from textmsa.settings import get_mongodb_config
from textmsa.services.data.mongodb_models import (
    ServiceInfo, ServiceExecution, ServiceExecutionStatus, ServiceVisibility,
    TaskRequestConfig, TaskParameterTemplate, ParameterDefinition, ParameterType,
    OutputTemplate, ServiceOutputConfig, HttpMethod, ServiceOutputItemType,
    service_info_from_dict, service_execution_from_dict
)
from textmsa.services.file.file_service import get_file_service
from textmsa.services.file.file_manager import get_file_manager
from textmsa.services.file.file_type_service import get_file_type_service
import asyncio
import threading


logger = get_logger(__name__)


class ServiceService:
    """Service服务类"""
    
    _FILE_TYPE_HINTS: Dict[str, Dict[str, Optional[str]]] = {
        ".png": {"file_type": "png", "mime_type": "image/png"},
        ".jpg": {"file_type": "jpg", "mime_type": "image/jpeg"},
        ".jpeg": {"file_type": "jpg", "mime_type": "image/jpeg"},
        ".csv": {"file_type": "csv", "mime_type": "text/csv"},
        ".tsv": {"file_type": "tsv", "mime_type": "text/tab-separated-values"},
        ".txt": {"file_type": "txt", "mime_type": "text/plain"},
        ".pdf": {"file_type": "pdf", "mime_type": "application/pdf"}
    }
    
    def __init__(self, connection_string: Optional[str] = None, database_name: Optional[str] = None):
        """
        初始化Service服务
        
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
            logger.info("Service服务：成功连接到MongoDB")
        except ConnectionFailure as e:
            logger.error(f"Service服务：无法连接到MongoDB: {e}")
            raise
        
        # 选择数据库
        self.db = self.client[database_name]
        self.database_name = database_name
        
        # 集合
        self.services_collection = self.db.services
        self.service_executions_collection = self.db.service_executions
        
        # 创建索引
        self._create_indexes()
        
        # 获取其他服务
        self.file_service = get_file_service()
        self.file_manager = get_file_manager()
        self.file_type_service = get_file_type_service()
        # 延迟导入 ProjectService 以避免循环依赖
        self._project_service = None
        
        # 注意：Service执行生成的文件不需要保存到MongoDB
        # MongoDB只存储用户直接上传的文件
        # 因此ServiceService不需要user_data_manager
        # 分析树现在完全由MongoDB管理，不再需要Neo4j
        
        # 服务执行队列（控制最大并发数）
        from textmsa.services.service.service_queue import ServiceQueue
        self.service_queue = ServiceQueue(max_concurrent=3)
        
        # 执行完成事件注册表：{execution_id: threading.Event}
        self._execution_events: Dict[str, threading.Event] = {}
        self._execution_events_lock = threading.Lock()
        
        logger.info(f"ServiceService初始化完成: 数据库={database_name}")
    
    @staticmethod
    def _infer_download_hints_from_filename(filename: Optional[str]) -> Dict[str, Optional[str]]:
        """
        根据文件名推断下载所需的扩展名、file_type参数和MIME类型
        """
        if not filename:
            return {"extension": None, "file_type": None, "mime_type": None}
        
        # Path.suffix 会返回包含 '.' 的小写扩展名
        extension = Path(filename).suffix.lower()
        if not extension:
            return {"extension": None, "file_type": None, "mime_type": None}
        
        hints = ServiceService._FILE_TYPE_HINTS.get(extension, {})
        return {
            "extension": extension,
            "file_type": hints.get("file_type"),
            "mime_type": hints.get("mime_type")
        }
    
    def _create_indexes(self):
        """创建索引"""
        try:
            # Service集合索引
            self.services_collection.create_index([("service_id", ASCENDING)], unique=True)
            self.services_collection.create_index([("visibility", ASCENDING)])
            self.services_collection.create_index([("created_by", ASCENDING)])
            self.services_collection.create_index([("created_at", DESCENDING)])
            
            # Service执行集合索引
            self.service_executions_collection.create_index([("execution_id", ASCENDING)], unique=True)
            self.service_executions_collection.create_index([("service_id", ASCENDING)])
            self.service_executions_collection.create_index([("user_id", ASCENDING)])
            self.service_executions_collection.create_index([("status", ASCENDING)])
            self.service_executions_collection.create_index([("created_at", DESCENDING)])
            
            logger.debug("Service集合索引创建完成")
        except Exception as e:
            logger.warning(f"创建索引时出错: {e}")
    
    # ============= 权限检查方法 =============
    
    def _can_access_service(self, service_info: ServiceInfo, user_id: Optional[str] = None) -> bool:
        """
        检查用户是否可以访问Service
        
        Args:
            service_info: Service信息
            user_id: 用户ID（可选，None表示未登录用户）
        
        Returns:
            是否可以访问
        """
        # PUBLIC或SYSTEM的Service所有人都可以访问
        if service_info.visibility in (ServiceVisibility.PUBLIC, ServiceVisibility.SYSTEM):
            return True
        
        # PRIVATE的Service只有创建者可以访问
        if service_info.visibility == ServiceVisibility.PRIVATE:
            return user_id is not None and service_info.created_by == user_id
        
        return False
    
    def _apply_project_service_filter(
        self, 
        base_query: Dict[str, Any], 
        project_id: str, 
        user_id: Optional[str]
    ) -> Dict[str, Any]:
        """
        应用项目服务过滤
        
        Args:
            base_query: 基础查询
            project_id: 项目ID
            user_id: 用户ID（用于获取项目配置）
        
        Returns:
            应用项目过滤后的查询
        """
        try:
            from textmsa.services.project.project_service import get_project_service
            
            project_service = get_project_service()
            project = project_service.get_project(project_id=project_id, user_id=user_id)
            config = project.service_config
            
            # 如果模式是 "all"，不进行过滤
            if config.mode == "all":
                return base_query
            
            # 如果模式是 "whitelist"，只返回白名单中的服务
            if config.mode == "whitelist":
                if not config.whitelist:
                    # 白名单为空，返回空结果
                    return {"service_id": "__no_match__"}
                # 添加 service_id 在白名单中的条件
                service_id_filter = {"service_id": {"$in": config.whitelist}}
                # 处理 $or 查询的情况
                if "$or" in base_query:
                    # 如果已有 $or，需要将 service_id 过滤添加到每个 $or 条件中
                    # 或者创建一个新的 $and 来组合
                    if "$and" not in base_query:
                        base_query["$and"] = []
                    base_query["$and"].append(service_id_filter)
                else:
                    # 没有 $or，直接添加
                    if "$and" not in base_query:
                        base_query["$and"] = []
                    base_query["$and"].append(service_id_filter)
                return base_query
            
            # 如果模式是 "blacklist"，排除黑名单中的服务
            if config.mode == "blacklist":
                if config.blacklist:
                    # 添加 service_id 不在黑名单中的条件
                    service_id_filter = {"service_id": {"$nin": config.blacklist}}
                    if "$and" not in base_query:
                        base_query["$and"] = []
                    base_query["$and"].append(service_id_filter)
                return base_query
            
            # 默认返回原查询
            return base_query
            
        except Exception as e:
            logger.warning(f"应用项目服务过滤失败: {e}，返回原查询")
            return base_query
    
    def _check_service_access(self, service_info: ServiceInfo, user_id: Optional[str] = None):
        """
        检查用户是否可以访问Service，如果不行则抛出异常
        
        Args:
            service_info: Service信息
            user_id: 用户ID（可选，None表示未登录用户）
        
        Raises:
            HTTPException: 如果用户无权访问
        """
        if not self._can_access_service(service_info, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Service '{service_info.service_id}' 是私有服务，仅创建者可以访问"
            )
    
    # ============= Service CRUD操作 =============
    
    def _check_service_url(self, url: str, timeout: int = 5) -> bool:
        """
        检查Service URL是否可达（ping检查）
        
        Args:
            url: 要检查的URL
            timeout: 超时时间（秒），默认5秒
        
        Returns:
            bool: True表示URL可达，False表示不可达
        
        TODO: 后续会增加更详细的校验逻辑（如检查响应格式、健康检查端点等）
        """
        try:
            # 使用HEAD请求检查URL是否可达（更轻量）
            # 如果HEAD不支持，则使用GET请求
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                try:
                    # 先尝试HEAD请求（更轻量）
                    response = client.head(url)
                    # 任何2xx、3xx、4xx状态码都表示服务器可达（4xx表示服务器响应了，只是请求有问题）
                    # 5xx可能表示服务器有问题，但也算可达
                    return response.status_code < 600
                except httpx.HTTPError:
                    # HEAD失败，尝试GET请求
                    try:
                        response = client.get(url, timeout=timeout)
                        return response.status_code < 600
                    except httpx.HTTPError:
                        return False
        except Exception as e:
            logger.warning(f"检查Service URL失败: {url}, 错误: {e}")
            return False
    
    def create_service(self, service_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        创建Service
        
        Args:
            service_data: Service数据（包含name, url等，如果不提供则由系统自动生成UUID）
            user_id: 创建者用户ID（必填）
        
        Returns:
            创建的Service信息
        
        注意：
            - service_id 如果未提供，系统会自动生成 UUID
            - 默认visibility为PRIVATE（仅创建者可见）
        """
        try:
            # 验证用户ID必填
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="创建Service必须提供用户ID"
                )
            
            # 验证必需字段
            baseurl = service_data.get('baseurl')
            service_suffix = service_data.get('service_suffix')
            
            if not baseurl or not baseurl.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="创建Service必须提供baseurl字段"
                )
            
            if not service_suffix or not service_suffix.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="创建Service必须提供service_suffix字段"
                )
            
            # 检查Service URL是否可达（ping检查）
            service_url = f"{baseurl.strip()}{service_suffix.strip()}"
            if not service_url:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Service URL不能为空"
                )
            
            logger.info(f"检查Service URL可达性: {service_url}")
            if not self._check_service_url(service_url):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Service URL不可达: {service_url}，请检查URL是否正确或服务是否运行"
                )
            logger.info(f"Service URL检查通过: {service_url}")
            
            # 新增：验证服务配置
            try:
                self._validate_service_config(service_data)
            except ValueError as e:
                logger.error(f"服务配置验证失败: {e}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"服务配置验证失败: {str(e)}"
                )
            
            # 构建ServiceInfo模型
            request_config = service_data.get('request_config', {})
            parameter_template_data = service_data.get('parameter_template', {})
            parameter_schema_data = service_data.get('parameter_schema', {})
            
            # 处理parameter_schema（转换为ParameterDefinition对象）
            parameter_schema = None
            if parameter_schema_data:
                schema_dict = {}
                for key, value in parameter_schema_data.items():
                    if isinstance(value, dict):
                        schema_dict[key] = ParameterDefinition(**value)
                    elif isinstance(value, ParameterDefinition):
                        schema_dict[key] = value
                    else:
                        raise ValueError(f"parameter_schema[{key}]必须是字典或ParameterDefinition对象")
                parameter_schema = schema_dict
            
            # 处理output_config（转换为ServiceOutputConfig对象）
            output_config_data = service_data.get('output_config')
            output_config = None
            if output_config_data:
                if isinstance(output_config_data, dict):
                    output_config = ServiceOutputConfig(**output_config_data)
                elif isinstance(output_config_data, ServiceOutputConfig):
                    output_config = output_config_data
                else:
                    raise ValueError("output_config必须是字典或ServiceOutputConfig对象")
            
            # 获取权限（默认值）
            visibility = ServiceVisibility(service_data.get('visibility', 'private'))
            
            # 获取 accepted_files
            accepted_files = service_data.get('accepted_files')
            
            # 生成 service_id（如果未提供，则使用 UUID）
            service_id = str(uuid.uuid4())

            service_info = ServiceInfo(
                service_id=service_id,
                name=service_data['name'],
                description=service_data.get('description'),
                version=service_data.get('version', '1.0.0'),
                baseurl=baseurl.strip(),
                service_suffix=service_suffix.strip(),
                download_suffix=service_data.get('download_suffix'),
                request_config=TaskRequestConfig(**request_config) if request_config else TaskRequestConfig(),
                parameter_template=TaskParameterTemplate(**parameter_template_data) if parameter_template_data else TaskParameterTemplate(),
                output_config=output_config,
                parameter_schema=parameter_schema,
                accepted_files=accepted_files,  # 新增
                visibility=visibility,
                created_by=user_id  # 必填
            )
            
            # 转换为字典并插入
            service_doc = service_info.to_dict()
            self.services_collection.insert_one(service_doc)
            
            logger.info(f"成功创建Service: {service_id}, 用户: {user_id}, 权限: {visibility.value}")
            
            # 返回Service信息
            return self._service_to_response(service_info)
            
        except HTTPException:
            # HTTPException 应该直接传播，不被转换为 500 错误
            raise
        except DuplicateKeyError:
            service_id = service_data.get('service_id', '未知')
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Service ID '{service_id}' 已存在"
            )
        except ValidationError as e:
            logger.error(f"Service数据验证失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Service数据验证失败: {str(e)}"
            )
        except Exception as e:
            logger.error(f"创建Service失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"创建Service失败: {str(e)}"
            )
    
    def get_service(self, service_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取Service信息
        
        Args:
            service_id: Service ID
            user_id: 用户ID（可选，用于权限检查）
        
        Returns:
            Service信息
        
        Raises:
            HTTPException: 如果Service不存在或用户无权访问
        """
        try:
            service_doc = self.services_collection.find_one({"service_id": service_id})
            
            if not service_doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Service '{service_id}' 不存在"
                )
            
            service_info = service_info_from_dict(service_doc)
            
            # 权限检查：只有PUBLIC/SYSTEM或创建者可以访问
            self._check_service_access(service_info, user_id)
            
            return self._service_to_response(service_info)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取Service信息失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"获取Service信息失败: {str(e)}"
            )
    
    def _get_project_service(self):
        """获取 ProjectService 实例（延迟导入以避免循环依赖）"""
        if self._project_service is None:
            from textmsa.services.project.project_service import get_project_service
            self._project_service = get_project_service()
        return self._project_service
    
    def _apply_project_service_filter(self, query: Dict[str, Any], project_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        根据项目配置应用服务过滤
        
        Args:
            query: MongoDB 查询字典（会被修改）
            project_id: 项目ID
            user_id: 用户ID（用于验证项目所有权）
        
        Returns:
            修改后的查询字典
    
        """
        try:
            # 获取项目信息
            project_service = self._get_project_service()
            
            # 验证项目存在且用户有权限访问
            if not user_id:
                logger.warning(f"应用项目过滤时未提供 user_id，跳过项目过滤")
                return query
            
            try:
                project = project_service.get_project(project_id, user_id)
            except HTTPException:
                # 项目不存在或无权访问，跳过项目过滤
                logger.warning(f"项目 {project_id} 不存在或用户 {user_id} 无权访问，跳过项目过滤")
                return query
            
            return query
        
        except Exception as e:
            logger.error(f"应用项目服务过滤失败: {e}", exc_info=True)
            # 出错时返回原始查询，不应用过滤
            return query

    def _extract_output_item_fields(self, item: Any) -> Tuple[ServiceOutputItemType, str, str]:
        """
        统一解析输出项字段，兼容旧字段（如 text/file_extension 等）
        """
        raw_type = None
        filename = None
        description = ''
        
        if isinstance(item, dict):
            raw_type = item.get('type')
            filename = item.get('filename') or item.get('text') or item.get('name')
            description = item.get('description', '') or ''
        else:
            raw_type = getattr(item, 'type', None)
            filename = (
                getattr(item, 'filename', None)
                or getattr(item, 'text', None)
                or getattr(item, 'name', None)
            )
            description = getattr(item, 'description', '') or ''
        
        if isinstance(raw_type, ServiceOutputItemType):
            item_type = raw_type
        elif isinstance(raw_type, str):
            try:
                item_type = ServiceOutputItemType(raw_type)
            except ValueError:
                item_type = ServiceOutputItemType.FILE
        else:
            item_type = ServiceOutputItemType.FILE
        
        filename = str(filename).strip() if filename else ''
        if not filename:
            filename = f"{item_type.value}_output_{uuid.uuid4().hex[:8]}"
        description = str(description).strip() if isinstance(description, str) else ''
        
        return item_type, filename, description
    
    def _validate_service_config(self, config: Dict[str, Any]) -> None:
        """
        验证服务配置是否符合新格式要求
        
        验证规则：
        1. accepted_files 字段必须存在且格式正确
        2. output_config.items 中所有文件类型项必须包含 file_type_id
        
        Args:
            config: 服务配置字典
        
        Raises:
            ValueError: 如果配置不符合要求
        """
        # 验证 accepted_files
        if 'accepted_files' not in config:
            raise ValueError(
                "服务配置缺少必需字段 'accepted_files'。"
                "该字段用于定义服务接受的输入文件类型。"
            )
        
        accepted_files = config.get('accepted_files')
        if accepted_files is None:
            raise ValueError("'accepted_files' 不能为 None")
        
        if not isinstance(accepted_files, dict):
            raise ValueError(f"'accepted_files' 必须是字典类型，当前类型: {type(accepted_files).__name__}")
        
        if not accepted_files:
            raise ValueError("'accepted_files' 不能为空字典")
        
        # 验证 accepted_files 的每个条目
        for filename, file_config in accepted_files.items():
            if not isinstance(file_config, dict):
                raise ValueError(f"'accepted_files.{filename}' 必须是字典类型")
            
            if 'file_type_ids' not in file_config:
                raise ValueError(f"'accepted_files.{filename}' 缺少 'file_type_ids' 字段")
            
            file_type_ids = file_config['file_type_ids']
            if not isinstance(file_type_ids, list):
                raise ValueError(f"'accepted_files.{filename}.file_type_ids' 必须是列表类型")
            
            if not file_type_ids:
                raise ValueError(f"'accepted_files.{filename}.file_type_ids' 不能为空列表")
            
            # 验证 file_type_ids 中的每个元素都是字符串
            for idx, ft_id in enumerate(file_type_ids):
                if not isinstance(ft_id, str) or not ft_id.strip():
                    raise ValueError(
                        f"'accepted_files.{filename}.file_type_ids[{idx}]' 必须是非空字符串"
                    )
        
        # 验证 output_config
        if 'output_config' not in config:
            raise ValueError(
                "服务配置缺少必需字段 'output_config'。"
                "该字段用于定义服务的输出结果。"
            )
        
        output_config = config.get('output_config')
        if output_config is None:
            raise ValueError("'output_config' 不能为 None")
        
        if not isinstance(output_config, dict):
            raise ValueError(f"'output_config' 必须是字典类型，当前类型: {type(output_config).__name__}")
        
        if 'items' not in output_config:
            raise ValueError("'output_config' 缺少 'items' 字段")
        
        items = output_config['items']
        if not isinstance(items, list):
            raise ValueError(f"'output_config.items' 必须是列表类型，当前类型: {type(items).__name__}")
        
        if not items:
            raise ValueError("'output_config.items' 不能为空列表")
        
        # 验证每个输出项都包含 file_type_id（仅对文件类型）
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(f"'output_config.items[{idx}]' 必须是字典类型")
            
            item_type = item.get('type')
            # 支持枚举值和字符串
            if item_type == ServiceOutputItemType.FILE or item_type == 'file':
                if 'file_type_id' not in item:
                    raise ValueError(
                        f"'output_config.items[{idx}]' 缺少必需字段 'file_type_id'"
                    )
                file_type_id = item['file_type_id']
                if not isinstance(file_type_id, str) or not file_type_id.strip():
                    raise ValueError(
                        f"'output_config.items[{idx}].file_type_id' 必须是非空字符串"
                    )
    
    def _check_service_access(self, service_info: ServiceInfo, user_id: Optional[str] = None):
        """
        检查用户是否有权限访问服务
        
        Args:
            service_info: Service信息
            user_id: 用户ID（可选）
        
        Raises:
            HTTPException: 如果用户无权访问
        """
        # PUBLIC 或 SYSTEM 服务所有人都可以访问
        if service_info.visibility in (ServiceVisibility.PUBLIC, ServiceVisibility.SYSTEM):
            return
        
        # PRIVATE 服务只有创建者可以访问
        if service_info.visibility == ServiceVisibility.PRIVATE:
            if not user_id or service_info.created_by != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="无权访问此服务"
                )
    
    def _can_access_service(self, service_info: ServiceInfo, user_id: Optional[str] = None) -> bool:
        """
        检查用户是否有权限访问服务（不抛出异常）
        
        Args:
            service_info: Service信息
            user_id: 用户ID（可选）
        
        Returns:
            True 如果有权限，False 如果无权限
        """
        try:
            self._check_service_access(service_info, user_id)
            return True
        except HTTPException:
            return False
    
    def _service_accepts_file_type(self, service_info: ServiceInfo, file_type_id: str) -> bool:
        """
        检查服务是否接受指定的文件类型
        
        Args:
            service_info: Service信息
            file_type_id: 文件类型ID
        
        Returns:
            是否接受该文件类型
        """
        if not service_info.accepted_files:
            return False
        
        # accepted_files 结构: {filename: {file_type_ids: [...], description: ...}}
        # 遍历所有 filename，检查是否有任何 file_type_ids 包含指定的 file_type_id
        for filename, file_config in service_info.accepted_files.items():
            if isinstance(file_config, dict):
                file_type_ids = file_config.get("file_type_ids", [])
                if isinstance(file_type_ids, list) and file_type_id in file_type_ids:
                    return True
        
            return False
    
    def _service_to_response(self, service_info: ServiceInfo) -> Dict[str, Any]:
        """
        将 ServiceInfo 转换为响应字典
        
        Args:
            service_info: Service信息
        
        Returns:
            响应字典
        """
        response = {
            "service_id": service_info.service_id,
            "name": service_info.name,
            "description": service_info.description,
            "version": service_info.version,
            "baseurl": service_info.baseurl,
            "service_suffix": service_info.service_suffix,
            "download_suffix": service_info.download_suffix,
            "visibility": service_info.visibility.value if isinstance(service_info.visibility, ServiceVisibility) else service_info.visibility,
            "created_at": service_info.created_at.isoformat() if service_info.created_at else None,
            "updated_at": service_info.updated_at.isoformat() if service_info.updated_at else None,
            "created_by": service_info.created_by,
        }
        
        # 添加请求配置
        if service_info.request_config:
            response["request_config"] = service_info.request_config.model_dump() if hasattr(service_info.request_config, 'model_dump') else service_info.request_config
        
        # 添加参数模板
        if service_info.parameter_template:
            response["parameter_template"] = service_info.parameter_template.model_dump() if hasattr(service_info.parameter_template, 'model_dump') else service_info.parameter_template
        
        # 添加接受的文件类型配置（始终包含，即使为 None）
        response["accepted_files"] = service_info.accepted_files
        
        # 添加参数schema
        if service_info.parameter_schema:
            schema_dict = {}
            for key, value in service_info.parameter_schema.items():
                if isinstance(value, ParameterDefinition):
                    schema_dict[key] = value.model_dump()
                else:
                    schema_dict[key] = value
            response["parameter_schema"] = schema_dict
        
        # 添加输出配置
        if service_info.output_config:
            output_config_dict = service_info.output_config.model_dump() if hasattr(service_info.output_config, 'model_dump') else service_info.output_config
            # 处理items中的模型对象
            if 'items' in output_config_dict and isinstance(output_config_dict['items'], list):
                items_list = []
                for item in output_config_dict['items']:
                    if hasattr(item, 'model_dump'):
                        items_list.append(item.model_dump())
                    else:
                        items_list.append(item)
                output_config_dict['items'] = items_list
            response["output_config"] = output_config_dict
        
        # 审核相关字段已移除
        
        return response
    
    def list_services(self, visibility_filter: Optional[str] = None, user_id: Optional[str] = None,
                      skip: int = 0, limit: int = 100, project_id: Optional[str] = None,
                      input_file_type_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取Service列表（根据权限过滤）
        
        Args:
            status_filter: 状态过滤（可选）
            tag_filter: Tag过滤（可选）
            visibility_filter: 权限过滤（可选，private/public/system）
            user_id: 用户ID（可选，用于权限过滤）
            skip: 跳过数量
            limit: 返回数量
            project_id: 项目ID（可选，用于项目过滤）
            input_file_type_id: 输入文件类型ID（可选，用于筛选接受该文件类型的服务）
        
        Returns:
            Service列表和总数
        
        注意：
            - 只返回用户有权限访问的Service（PUBLIC或用户创建的PRIVATE）
            - 如果提供user_id，会过滤PRIVATE的Service，只返回PUBLIC或该用户创建的
            - 如果提供project_id，会根据项目配置进行过滤
            - 如果提供input_file_type_id，只返回接受该文件类型的服务
        """
        try:
            query = {}
            
            if visibility_filter:
                query["visibility"] = visibility_filter
            
            # 权限过滤：如果不是所有人，只返回PUBLIC或用户创建的PRIVATE
            if user_id:
                # 查询PUBLIC/SYSTEM的Service或用户创建的PRIVATE Service
                query["$or"] = [
                    {"visibility": "public"},
                    {"visibility": "system"},
                    {"visibility": "private", "created_by": user_id}
                ]
            else:
                # 未登录用户只能看到PUBLIC和SYSTEM的Service
                query["visibility"] = {"$in": ["public", "system"]}
            
            # 应用项目过滤
            if project_id:
                query = self._apply_project_service_filter(query, project_id, user_id)
            
            # 查询总数（先不应用 input_file_type_id 过滤，因为需要在内存中过滤）
            total_query = query.copy()
            # 如果提供了 input_file_type_id，需要在 MongoDB 查询中过滤 accepted_files
            if input_file_type_id:
                # 使用 MongoDB 查询来匹配 accepted_files 中包含指定 file_type_id 的服务
                # accepted_files 结构: {filename: {file_type_ids: [...], description: ...}}
                # 需要检查任何 filename 的 file_type_ids 数组中是否包含 input_file_type_id
                query["accepted_files"] = {
                    "$exists": True,
                    "$ne": None
                }
                # 使用 $elemMatch 或 $regex 来匹配嵌套结构
                # 由于 MongoDB 的嵌套查询限制，我们使用 $where 或者先查询所有，然后在内存中过滤
                # 为了性能，我们使用更简单的方法：查询所有有 accepted_files 的，然后在内存中过滤
            
            # 查询列表
            cursor = self.services_collection.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit * 2 if input_file_type_id else limit)
            
            services = []
            for service_doc in cursor:
                try:
                    service_info = service_info_from_dict(service_doc)
                    # 再次检查权限（防止查询条件不完整）
                    if not self._can_access_service(service_info, user_id):
                        continue
                    
                    # 如果提供了 input_file_type_id，检查服务是否接受该文件类型
                    if input_file_type_id:
                        if not self._service_accepts_file_type(service_info, input_file_type_id):
                            continue
                    
                    # 添加到服务列表（无论是否提供了 input_file_type_id）
                    services.append(self._service_to_response(service_info))
                    
                    # 如果已经收集到足够的服务，停止查询
                    if len(services) >= limit:
                        break
                        
                except Exception as e:
                    service_id = service_doc.get('service_id', 'unknown')
                    logger.warning(f"解析Service文档失败 (service_id: {service_id}): {e}")
                    continue
            
            # 如果提供了 input_file_type_id，需要重新计算总数
            if input_file_type_id:
                # 重新查询所有符合条件的服务来计算总数
                total = 0
                count_cursor = self.services_collection.find(query).sort("created_at", DESCENDING)
                for service_doc in count_cursor:
                    try:
                        service_info = service_info_from_dict(service_doc)
                        if self._can_access_service(service_info, user_id) and \
                           self._service_accepts_file_type(service_info, input_file_type_id):
                            total += 1
                    except Exception:
                        continue
            else:
                # 查询总数
                total = self.services_collection.count_documents(query)
            
            return {
                "services": services,
                "total": total
            }
            
        except Exception as e:
            logger.error(f"获取Service列表失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"获取Service列表失败: {str(e)}"
            )
    
    def update_service(self, service_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新Service信息
        
        Args:
            service_id: Service ID
            update_data: 更新数据（只包含要更新的字段）
        
        Returns:
            更新后的Service信息
        """
        try:
            # 检查Service是否存在
            service_doc = self.services_collection.find_one({"service_id": service_id})
            if not service_doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Service '{service_id}' 不存在"
                )
            
            # 如果更新配置相关字段，进行验证
            if 'accepted_files' in update_data or 'output_config' in update_data:
                # 获取现有服务信息
                existing_service_info = service_info_from_dict(service_doc)
                existing_service = self._service_to_response(existing_service_info)
                
                # 合并现有配置和更新数据
                merged_config = {
                    **existing_service,
                    **update_data
                }
                
                # 验证合并后的配置
                try:
                    self._validate_service_config(merged_config)
                except ValueError as e:
                    logger.error(f"服务配置验证失败: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"服务配置验证失败: {str(e)}"
                )
            
            # 构建更新文档
            update_doc = {}
            
            if 'name' in update_data:
                update_doc['name'] = update_data['name']
            if 'description' in update_data:
                update_doc['description'] = update_data['description']
            if 'version' in update_data:
                update_doc['version'] = update_data['version']
            if 'visibility' in update_data:
                update_doc['visibility'] = update_data['visibility']
                
            # 处理baseurl和service字段（如果更新了baseurl或service，需要重新检查URL）
            if 'baseurl' in update_data or 'service' in update_data:
                # 获取新的baseurl和service（如果更新了则使用新值，否则使用原值）
                new_baseurl = update_data.get('baseurl') or service_doc.get('baseurl')
                new_service_suffix = update_data.get('service_suffix') or service_doc.get('service_suffix')
                
                if not new_baseurl or not new_service_suffix:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Service baseurl和service_suffix字段不能为空"
                    )
                
                # 构建完整的service URL
                new_service_url = f"{new_baseurl}{new_service_suffix}"
                
                # 检查新URL是否可达（ping检查）
                logger.info(f"检查更新后的Service URL可达性: {new_service_url}")
                if not self._check_service_url(new_service_url):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Service URL不可达: {new_service_url}，请检查URL是否正确或服务是否运行"
                    )
                update_doc['request_config'] = update_data['request_config']
            if 'parameter_template' in update_data:
                update_doc['parameter_template'] = update_data['parameter_template']

            if 'parameter_schema' in update_data:
                # 处理parameter_schema（转换为ParameterDefinition对象）
                schema_data = update_data['parameter_schema']
                if schema_data:
                    schema_dict = {}
                    for key, value in schema_data.items():
                        if isinstance(value, dict):
                            schema_dict[key] = ParameterDefinition(**value)
                        elif isinstance(value, ParameterDefinition):
                            schema_dict[key] = value
                        else:
                            raise ValueError(f"parameter_schema[{key}]必须是字典或ParameterDefinition对象")
                    update_doc['parameter_schema'] = {k: v.model_dump() for k, v in schema_dict.items()}
                else:
                    update_doc['parameter_schema'] = None
            if 'accepted_files' in update_data:
                # 处理accepted_files
                accepted_files_data = update_data['accepted_files']
                if accepted_files_data is not None:
                    if not isinstance(accepted_files_data, dict):
                        raise ValueError("accepted_files必须是字典类型")
                    update_doc['accepted_files'] = accepted_files_data
                else:
                    update_doc['accepted_files'] = None
            if 'output_config' in update_data:
                # 处理output_config（转换为ServiceOutputConfig对象）
                output_config_data = update_data['output_config']
                if output_config_data:
                    if isinstance(output_config_data, dict):
                        output_config = ServiceOutputConfig(**output_config_data)
                        update_doc['output_config'] = output_config.model_dump()
                    elif isinstance(output_config_data, ServiceOutputConfig):
                        update_doc['output_config'] = output_config_data.model_dump()
                    else:
                        raise ValueError("output_config必须是字典或ServiceOutputConfig对象")
                else:
                    update_doc['output_config'] = None
            if 'status' in update_data:
                update_doc['status'] = update_data['status']
            
            # 更新updated_at
            update_doc['updated_at'] = datetime.now()
            
            # 获取服务的创建者ID，用于后续获取服务信息时的权限检查
            created_by = service_doc.get('created_by')
            
            # 执行更新
            self.services_collection.update_one(
                {"service_id": service_id},
                {"$set": update_doc}
            )
            
            logger.info(f"成功更新Service: {service_id}")
            
            # 返回更新后的Service信息（传入创建者ID以通过权限检查）
            return self.get_service(service_id, created_by)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"更新Service失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"更新Service失败: {str(e)}"
            )
    
    def delete_service(self, service_id: str) -> bool:
        """
        删除Service
        
        Args:
            service_id: Service ID
        
        Returns:
            是否成功
        """
        try:
            # 检查Service是否存在
            service_doc = self.services_collection.find_one({"service_id": service_id})
            if not service_doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Service '{service_id}' 不存在"
                )
            
            # 检查是否有执行记录
            execution_count = self.service_executions_collection.count_documents({"service_id": service_id})
            if execution_count > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"无法删除Service '{service_id}'，存在 {execution_count} 条执行记录。请先删除所有执行记录或联系管理员"
                )
            
            # 删除Service
            result = self.services_collection.delete_one({"service_id": service_id})
               
            if result.deleted_count > 0:
                logger.info(f"成功删除Service: {service_id}")
                
                # 同步更新所有项目的服务配置
                try:
                    from textmsa.services.data.user_data_manager_mongodb import get_user_data_manager
                    user_data_manager = get_user_data_manager()
                    stats = user_data_manager.remove_service_from_project_configs(service_id)
                    logger.info(
                        f"Service {service_id} 已从项目配置中移除，统计: {stats}"
                    )
                except Exception as e:
                    logger.warning(
                        f"删除Service后更新项目服务配置失败: {service_id}, error: {e}"
                    )
                return True
            else:
                return False
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"删除Service失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"删除Service失败: {str(e)}"
            )
    
    # ============= 队列状态 =============
    
    def get_queue_status(self) -> Dict[str, Any]:
        """获取服务执行队列状态"""
        return self.service_queue.get_queue_status()
    
    def wait_for_execution(self, execution_id: str, timeout: float = 3000.0) -> Dict[str, Any]:
        """
        等待执行完成（基于 Event 通知，非轮询）。
        
        线程会挂起在 event.wait() 上，不消耗 CPU，不查询数据库。
        当 _execute_service_async 完成后 set Event，等待线程立即被唤醒。
        
        Args:
            execution_id: 执行 ID
            timeout: 最大等待秒数（默认 3000 秒）
            
        Returns:
            执行记录 dict
            
        Raises:
            TimeoutError: 超时
        """
        with self._execution_events_lock:
            event = self._execution_events.get(execution_id)
        
        if event:
            logger.info(f"[Service等待] 开始等待执行完成 - execution_id: {execution_id}, timeout: {timeout}s")
            completed = event.wait(timeout=timeout)
            if not completed:
                logger.error(f"[Service等待] 等待超时 - execution_id: {execution_id}, timeout: {timeout}s")
                raise TimeoutError(f"服务执行超时 (execution_id={execution_id}, timeout={timeout}s)")
            logger.info(f"[Service等待] 执行已完成，获取结果 - execution_id: {execution_id}")
        else:
            # Event 不存在：可能已经完成并被清理了，直接查库
            logger.info(f"[Service等待] Event 不存在（可能已完成），直接查询结果 - execution_id: {execution_id}")
        
        return self.get_execution(execution_id)
    
    def _notify_execution_complete(self, execution_id: str) -> None:
        """通知等待该 execution 的线程（任务完成/失败时调用）"""
        with self._execution_events_lock:
            event = self._execution_events.pop(execution_id, None)
        if event:
            event.set()
            logger.info(f"[Service通知] 已通知等待线程 - execution_id: {execution_id}")
    
    # ============= Task执行 =============
    
    def execute_service(self, service_id: str, input_file_ids: List[str], user_id: str, 
                     parameters: Optional[Dict[str, Any]] = None, project_id: Optional[str] = None,
                     validate_input_types: bool = True) -> Dict[str, Any]:
        """
        执行Service（异步执行）
        
        新的执行逻辑：
        1. 根据service模板，立刻生成新的文件id以及execution id
        2. 创建执行记录以及文件记录（占位），并存储到数据库中
        3. 告诉前端，前端刷新页面（立刻可以看到灰色的节点等）
        4. 待后端转发请求执行完，将数据库中对应元素未填的元素更新，并且更新对应状态
        
        Args:
            service_id: Service ID
            input_file_ids: 输入文件ID列表（支持多文件输入）
            user_id: 用户ID
            parameters: 执行参数（覆盖parameter_template）
            project_id: 项目ID（可选）
            validate_input_types: 是否进行输入文件类型检查（默认True，设为False可跳过类型验证）
        
        Returns:
            执行结果（包含execution_id, output_file_ids, status=running等）
        """
        execution_id = str(uuid.uuid4())
        start_time = time.time()
        
        try:
            # 获取Service信息
            service_doc = self.services_collection.find_one({"service_id": service_id})
            if not service_doc:
                logger.error(f"[Service执行] Service不存在 - execution_id: {execution_id}, service_id: {service_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Service '{service_id}' 不存在"
                )
            
            service_info = service_info_from_dict(service_doc)
            
            # 权限检查：只有PUBLIC/SYSTEM或创建者可以执行
            self._check_service_access(service_info, user_id)
            
            # 验证和处理input_file_ids列表
            if not isinstance(input_file_ids, list):
                logger.error(f"[Service执行] input_file_ids类型错误 - execution_id: {execution_id}, 类型: {type(input_file_ids)}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="input_file_ids必须是字符串列表"
                )
            
            # 过滤空值并验证
            input_file_ids = [fid.strip() for fid in input_file_ids if fid and fid.strip()]
            if len(input_file_ids) == 0:
                logger.error(f"[Service执行] input_file_ids列表为空 - execution_id: {execution_id}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="input_file_ids列表不能为空，必须包含至少一个有效的文件ID"
                )
            
            # 从服务配置中获取 accepted_files
            accepted_files = service_info.accepted_files
            if not accepted_files:
                logger.error(f"[Service执行] 服务配置缺少 accepted_files - execution_id: {execution_id}, service_id: {service_id}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"服务 '{service_id}' 配置缺少 'accepted_files' 字段，无法验证输入文件类型"
                )
            
            # 支持多文件输入：根据accepted_files逐个验证文件
            # accepted_files 结构: {filename: {file_type_ids: [...], description: ...}}
            # 例如: {"file": {...}, "reference": {...}}
            # 将 input_file_ids 按照 accepted_files 的顺序进行匹配和验证
            validated_file_infos = {}  # {filename: file_info} 映射
            used_file_ids = set()  # 已使用的文件ID，避免重复使用
            
            if validate_input_types:
                # ========== 执行类型检查的完整验证逻辑 ==========
                # 遍历 accepted_files 的每个配置项
                for filename, file_config in accepted_files.items():
                    file_type_ids = file_config.get('file_type_ids', [])
                    if not file_type_ids:
                        logger.warning(
                            f"[Service执行] accepted_files.{filename} 缺少 file_type_ids - "
                            f"execution_id: {execution_id}, service_id: {service_id}"
                        )
                        continue
                    
                    # 从 input_file_ids 中找到匹配的文件（通过文件类型验证）
                    matched_file_info = None
                    matched_file_id = None
                    provided_file_types = []  # 收集提供的文件类型信息
                    
                    logger.info(
                        f"[Service执行] 开始匹配文件 - execution_id: {execution_id}, "
                        f"filename: {filename}, required_file_type_ids: {file_type_ids}, "
                        f"available_file_ids: {[fid for fid in input_file_ids if fid not in used_file_ids]}"
                    )
                    
                    for file_id in input_file_ids:
                        if file_id in used_file_ids:
                            # 记录已使用的文件信息，以便调试
                            try:
                                file_info = self.file_service.get_file_info(file_id, user_id)
                                input_file_name = file_info.get('filename', '未知文件名')
                                input_file_type_id = file_info.get('file_type_id')
                                input_file_type_name = file_info.get('file_type_name', '未知类型')
                                if input_file_type_id:
                                    provided_file_types.append(f"{file_id}({input_file_name}, 类型ID:{input_file_type_id}, 类型名:{input_file_type_name}, 已使用)")
                                else:
                                    provided_file_types.append(f"{file_id}({input_file_name}, 缺少类型, 已使用)")
                            except Exception:
                                provided_file_types.append(f"{file_id}(已使用, 无法获取详细信息)")
                            continue  # 跳过已使用的文件
                        
                        try:
                            file_info = self.file_service.get_file_info(file_id, user_id)
                            logger.info(
                                f"[Service执行] 正在检查文件 - execution_id: {execution_id}, "
                                f"filename: {filename}, file_id: {file_id}, "
                                f"file_name: {file_info.get('filename')}, "
                                f"file_type_id: {file_info.get('file_type_id')}, "
                                f"file_type_name: {file_info.get('file_type_name')}, "
                                f"file_path: {file_info.get('file_path')}"
                            )
                        except HTTPException as e:
                            if e.status_code == status.HTTP_404_NOT_FOUND:
                                logger.warning(
                                    f"[Service执行] 输入文件不存在，跳过 - execution_id: {execution_id}, "
                                    f"filename: {filename}, file_id: {file_id}, user_id: {user_id}"
                                )
                                provided_file_types.append(f"{file_id}(文件不存在)")
                            else:
                                logger.warning(
                                    f"[Service执行] 获取文件信息失败 - execution_id: {execution_id}, "
                                    f"filename: {filename}, file_id: {file_id}, "
                                    f"status_code: {e.status_code}, detail: {e.detail}"
                                )
                                provided_file_types.append(f"{file_id}(获取文件信息失败: {e.detail})")
                            continue
                        except Exception as e:
                            logger.error(
                                f"[Service执行] 获取文件信息时发生异常 - execution_id: {execution_id}, "
                                f"filename: {filename}, file_id: {file_id}, "
                                f"error: {str(e)}"
                            )
                            provided_file_types.append(f"{file_id}(获取文件信息异常: {str(e)})")
                            continue
                        
                        # 验证文件类型
                        input_file_type_id = file_info.get("file_type_id")
                        input_file_type_name = file_info.get("file_type_name", "未知类型")
                        input_file_name = file_info.get("filename", "未知文件名")
                        
                        if not input_file_type_id:
                            logger.warning(
                                f"[Service执行] 输入文件缺少 file_type_id，跳过 - "
                                f"execution_id: {execution_id}, filename: {filename}, "
                                f"file_id: {file_id}, file_name: {input_file_name}"
                            )
                            provided_file_types.append(f"{file_id}({input_file_name}, 缺少类型)")
                            continue
                        
                        # 记录提供的文件类型信息
                        provided_file_types.append(f"{file_id}({input_file_name}, 类型ID:{input_file_type_id}, 类型名:{input_file_type_name})")
                        
                        # 检查文件类型是否匹配当前 accepted_files 配置
                        if input_file_type_id in file_type_ids:
                            matched_file_info = file_info
                            matched_file_id = file_id
                            logger.info(
                                f"[Service执行] 文件类型匹配 - execution_id: {execution_id}, "
                                f"filename: {filename}, file_id: {file_id}, "
                                f"file_type_id: {input_file_type_id}"
                            )
                            break
                        else:
                            logger.debug(
                                f"[Service执行] 文件类型不匹配 - execution_id: {execution_id}, "
                                f"filename: {filename}, file_id: {file_id}, "
                                f"file_type_id: {input_file_type_id}, required_types: {file_type_ids}"
                            )
                    
                    # 如果找到匹配的文件，添加到已验证文件列表
                    if matched_file_info:
                        validated_file_infos[filename] = matched_file_info
                        used_file_ids.add(matched_file_id)
                        logger.info(
                            f"[Service执行] 文件匹配成功 - execution_id: {execution_id}, "
                            f"filename: {filename}, file_id: {matched_file_id}, "
                            f"file_name: {matched_file_info.get('filename')}, "
                            f"file_type_id: {matched_file_info.get('file_type_id')}, "
                            f"file_type_name: {matched_file_info.get('file_type_name')}, "
                            f"file_path: {matched_file_info.get('file_path')}, "
                            f"file_size: {os.path.getsize(matched_file_info.get('file_path')) if matched_file_info.get('file_path') and os.path.exists(matched_file_info.get('file_path')) else 'N/A'} bytes"
                        )
                    else:
                        # 如果没有找到匹配的文件，检查是否是必需的文件
                        # 目前假设所有 accepted_files 中的文件都是必需的
                        accepted_type_ids_str = ', '.join(set(file_type_ids))
                        provided_file_types_str = '; '.join(provided_file_types) if provided_file_types else '无'
                        logger.error(
                            f"[Service执行] 未找到匹配的文件 - execution_id: {execution_id}, "
                            f"filename: {filename}, required_file_type_ids: {accepted_type_ids_str}, "
                            f"provided_file_types: {provided_file_types_str}"
                        )
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=(
                                f"文件类型不匹配。请检查输入文件的文件类型是否正确。"
                                f"需要文件类型：{accepted_type_ids_str}。"
                                f"提供的文件类型：{provided_file_types_str}。"
                                f"提供的文件ID：{', '.join(input_file_ids)}"
                            )
                        )
                
                # 检查是否有未使用的文件（可选：如果服务不接受额外文件，可以报错）
                unused_file_ids = [fid for fid in input_file_ids if fid not in used_file_ids]
                if unused_file_ids:
                    logger.warning(
                        f"[Service执行] 有未使用的输入文件 - execution_id: {execution_id}, "
                        f"unused_file_ids: {unused_file_ids}"
                    )
            else:
                # ========== 跳过类型检查，仅进行基本文件验证 ==========
                logger.info(
                    f"[Service执行] 跳过输入文件类型检查 - execution_id: {execution_id}, "
                    f"service_id: {service_id}, input_file_ids: {input_file_ids}"
                )
                
                # 按照 accepted_files 的顺序分配文件（不检查类型）
                accepted_filenames = list(accepted_files.keys())
                available_file_ids = list(input_file_ids)
                
                if len(available_file_ids) < len(accepted_filenames):
                    logger.error(
                        f"[Service执行] 输入文件数量不足 - execution_id: {execution_id}, "
                        f"required_files: {len(accepted_filenames)}, provided_files: {len(available_file_ids)}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"输入文件数量不足。需要 {len(accepted_filenames)} 个文件（{', '.join(accepted_filenames)}），"
                            f"但只提供了 {len(available_file_ids)} 个文件。"
                        )
                    )
                
                # 按顺序分配文件
                for idx, filename in enumerate(accepted_filenames):
                    if idx >= len(available_file_ids):
                        logger.error(
                            f"[Service执行] 输入文件数量不足，无法分配文件给 {filename} - "
                            f"execution_id: {execution_id}"
                        )
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"输入文件数量不足，无法分配文件给 '{filename}'"
                        )
                    
                    file_id = available_file_ids[idx]
                    
                    try:
                        file_info = self.file_service.get_file_info(file_id, user_id)
                        validated_file_infos[filename] = file_info
                        used_file_ids.add(file_id)
                        logger.info(
                            f"[Service执行] 文件分配成功（跳过类型检查） - execution_id: {execution_id}, "
                            f"filename: {filename}, file_id: {file_id}, "
                            f"file_name: {file_info.get('filename')}, "
                            f"file_path: {file_info.get('file_path')}"
                        )
                    except HTTPException as e:
                        if e.status_code == status.HTTP_404_NOT_FOUND:
                            logger.error(
                                f"[Service执行] 输入文件不存在 - execution_id: {execution_id}, "
                                f"filename: {filename}, file_id: {file_id}"
                            )
                            raise HTTPException(
                                status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"输入文件不存在（file_id: {file_id}）"
                            )
                        else:
                            raise
                    except Exception as e:
                        logger.error(
                            f"[Service执行] 获取文件信息失败 - execution_id: {execution_id}, "
                            f"filename: {filename}, file_id: {file_id}, error: {str(e)}"
                        )
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"获取文件信息失败: {str(e)}"
                        )
                
                # 检查是否有未使用的文件
                unused_file_ids = [fid for fid in input_file_ids if fid not in used_file_ids]
                if unused_file_ids:
                    logger.warning(
                        f"[Service执行] 有未使用的输入文件（跳过类型检查模式） - execution_id: {execution_id}, "
                        f"unused_file_ids: {unused_file_ids}"
                    )
            
            # 为了向后兼容，保留 primary_file_info（使用第一个匹配的文件）
            # 如果 accepted_files 只有一个键，使用它；否则使用第一个
            primary_filename = list(validated_file_infos.keys())[0] if validated_file_infos else None
            file_info = validated_file_infos[primary_filename] if primary_filename else None
            
            if not file_info:
                logger.error(
                    f"[Service执行] 未找到任何匹配的文件 - execution_id: {execution_id}, "
                    f"accepted_files: {list(accepted_files.keys())}, input_file_ids: {input_file_ids}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="未找到任何匹配的输入文件"
                )
            
            # 构建详细的文件信息日志
            validated_files_detail = []
            for fn, fi in validated_file_infos.items():
                file_path = fi.get('file_path')
                file_size = os.path.getsize(file_path) if file_path and os.path.exists(file_path) else 'N/A'
                validated_files_detail.append(
                    f"{fn}={{file_id: {fi.get('file_id')}, "
                    f"file_name: {fi.get('filename')}, "
                    f"file_type: {fi.get('file_type_name')}, "
                    f"file_path: {file_path}, "
                    f"file_size: {file_size} bytes}}"
                )
            
            logger.info(
                f"[Service执行] 输入文件验证完成 - execution_id: {execution_id}, "
                f"validated_files_count: {len(validated_file_infos)}, "
                f"validated_files: {validated_files_detail}, "
                f"primary_file: {primary_filename}"
            )
            
            # 验证参数（如果定义了parameter_schema）
            template_dict = service_info.parameter_template.to_dict() if isinstance(service_info.parameter_template, TaskParameterTemplate) else service_info.parameter_template
            final_params = {**template_dict, **(parameters or {})}
            
            if service_info.parameter_schema:
                allowed_keys = set(service_info.parameter_schema.keys())
                filtered_params = {k: v for k, v in final_params.items() if k in allowed_keys}
                extra_keys = set(final_params.keys()) - allowed_keys
                if extra_keys:
                    logger.info(f"[Service执行] 忽略未定义的参数 - execution_id: {execution_id}, extra_keys: {sorted(extra_keys)}")
                
                temp_template = TaskParameterTemplate(**filtered_params)
                schema_dict = {}
                for key, value in service_info.parameter_schema.items():
                    if isinstance(value, ParameterDefinition):
                        schema_dict[key] = value.model_dump()
                    else:
                        schema_dict[key] = value
                
                is_valid, error_msg, error_details = temp_template.validate_against_schema(schema_dict)
                if not is_valid:
                    logger.error(f"[Service执行] 参数验证失败 - execution_id: {execution_id}, error_msg: {error_msg}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"参数验证失败: {error_msg}"
                    )
                
                # 使用过滤后的参数执行后续流程，忽略多余参数
                final_params = filtered_params
                logger.info(
                    f"[Service执行] 参数验证成功 - execution_id: {execution_id}, "
                    f"params: {final_params}, ignored_extra_keys: {sorted(extra_keys) if extra_keys else []}"
                )
            
            # ========== 根据service模板生成输出文件ID和占位文件记录 ==========
            # 要求Service必须有output_config
            if not service_info.output_config or not service_info.output_config.items:
                logger.error(f"[Service执行] Service缺少output_config - execution_id: {execution_id}, service_id: {service_id}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Service '{service_id}' 必须配置output_config才能执行"
                )
            # logger.info(f"[Service执行] Service输出配置 - execution_id: {execution_id}, service_id: {service_id}, output_config: {service_info.output_config}")
            for item in service_info.output_config.items:
                item_type, item_filename, item_description = self._extract_output_item_fields(item)
                logger.info(f"[Service执行] 输出项 - execution_id: {execution_id}, item_type: {item_type}, item_filename: {item_filename}, item_description: {item_description}")
            output_file_ids = []            
            from textmsa.services.data.user_data_manager_mongodb import get_user_data_manager
            from textmsa.services.data.mongodb_models import AnalysisStatus, ServiceOutputItemType
            from textmsa.services.file.file_manager import get_file_manager
            user_data_manager = get_user_data_manager()
            output_file_infos = []
            # 遍历output_config中的每个输出项
            for item in service_info.output_config.items:
                item_type, item_filename, item_description = self._extract_output_item_fields(item)
                
                # 新增：从配置中获取 file_type_id
                file_type_id = None
                if isinstance(item, dict):
                    file_type_id = item.get('file_type_id')
                elif hasattr(item, 'file_type_id'):
                    file_type_id = item.file_type_id
                
                logger.info(
                    f"[Service执行] 输出项 - execution_id: {execution_id}, "
                    f"item_type: {item_type}, item_filename: {item_filename}, "
                    f"item_description: {item_description}, file_type_id: {file_type_id}"
                )
                
                # 生成文件ID
                output_file_id = str(uuid.uuid4())
                output_file_ids.append(output_file_id)
                    
                # 占位路径格式：output_dir/user_id/execution_id_filename
                placeholder_dir = self._get_output_user_dir(user_id)
                
                if item_type == ServiceOutputItemType.TEXT:
                    item_filename = f"{item_filename}.txt"
                item_filename = f"{item_filename}"

                # 占位文件路径（文件还不存在，但路径已确定）
                placeholder_file_path = str(placeholder_dir /f"{execution_id}_{item_filename}")
                
                # 构建generated_by信息
                generated_by = {
                    "execution_id": execution_id,
                    "service_id": service_info.service_id
                }
                
                # 创建占位文件记录（状态为PROCESSING，表示正在生成）
                try:
                    placeholder_file_metadata = {
                        "size": 0,  # 占位文件大小为0
                        "upload_time": datetime.now().isoformat(),
                        "is_placeholder": True,  # 标记为占位文件
                    }
                    
                    # 根据输出项类型决定如何解析文件类型
                    resolved_file_type = None
                    
                    # 辅助函数：解析文件类型，如果不存在则使用 unknown 作为备用
                    def resolve_file_type_with_fallback(file_type_id_to_resolve: str, fallback_type: str = "unknown") -> Dict[str, Any]:
                        """解析文件类型，如果不存在则使用备用类型"""
                        try:
                            return self.file_type_service.resolve_type(
                                file_type_id=file_type_id_to_resolve,
                        user_id=user_id,
                    )
                        except HTTPException as e:
                            if e.status_code == status.HTTP_404_NOT_FOUND:
                                logger.warning(
                                    f"[Service执行] 文件类型ID '{file_type_id_to_resolve}' 未找到，使用备用类型 '{fallback_type}' - "
                                    f"execution_id: {execution_id}, output_item_filename: {item_filename}, "
                                    f"requested_file_type_id: {file_type_id_to_resolve}, fallback_file_type_id: {fallback_type}"
                                )
                                try:
                                    return self.file_type_service.resolve_type(
                                        file_type_id=fallback_type,
                                        user_id=user_id,
                                    )
                                except HTTPException:
                                    # 如果备用类型也不存在，记录错误但继续使用 unknown
                                    logger.error(
                                        f"[Service执行] 备用文件类型 '{fallback_type}' 也不存在，请运行种子脚本初始化文件类型 - "
                                        f"execution_id: {execution_id}, filename: {item_filename}"
                                    )
                                    raise HTTPException(
                                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                        detail=f"文件类型 '{file_type_id_to_resolve}' 不存在，且备用类型 '{fallback_type}' 也不存在。请运行 'poetry run python scripts/seed_file_types.py' 初始化文件类型。"
                                    )
                            raise
                    
                    if item_type == ServiceOutputItemType.FILE:
                        # 文件类型：使用配置中的 file_type_id
                        if not file_type_id:
                            logger.error(
                                f"[Service执行] 输出项缺少 file_type_id - "
                                f"execution_id: {execution_id}, filename: {item_filename}"
                            )
                            raise HTTPException(
                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail=f"输出项 '{item_filename}' 缺少必需字段 'file_type_id'"
                            )
                        
                        # 使用配置中的 file_type_id，而不是通过文件名推断
                        resolved_file_type = resolve_file_type_with_fallback(file_type_id, fallback_type="unknown")
                        logger.info(
                            f"[Service执行] 使用配置中的 file_type_id 解析文件类型 - "
                            f"execution_id: {execution_id}, file_type_id: {file_type_id}, "
                            f"filename: {item_filename}"
                        )
                    elif item_type == ServiceOutputItemType.TEXT:
                        # 文本类型：使用配置中的 file_type_id，如果没有则使用默认的 txt
                        if not file_type_id:
                            file_type_id = "txt"  # 默认使用 txt 文件类型
                            logger.info(
                                f"[Service执行] TEXT 类型输出项未指定 file_type_id，使用默认值 'txt' - "
                                f"execution_id: {execution_id}, filename: {item_filename}"
                            )
                        
                        resolved_file_type = resolve_file_type_with_fallback(file_type_id, fallback_type="unknown")
                        logger.info(
                            f"[Service执行] 使用配置中的 file_type_id 解析文本文件类型 - "
                            f"execution_id: {execution_id}, file_type_id: {file_type_id}, "
                            f"filename: {item_filename}"
                        )
                    else:
                        # 未知类型，使用默认的 txt
                        logger.warning(
                            f"[Service执行] 未知的输出项类型，使用默认文件类型 'txt' - "
                            f"execution_id: {execution_id}, item_type: {item_type}, filename: {item_filename}"
                        )
                        resolved_file_type = resolve_file_type_with_fallback("txt", fallback_type="unknown")

                    placeholder_file_metadata["file_type"] = self.file_type_service.build_metadata_block(resolved_file_type)
                    
                    mongo_success = user_data_manager.add_user_file(
                        user_id=user_id,
                        file_id=output_file_id,
                        filename=item_filename,
                        file_type_id=resolved_file_type["file_type_id"],
                        file_type_name=resolved_file_type["name"],
                        file_type_display_name=resolved_file_type["display_name"],
                        description=item_description,
                        file_path=placeholder_file_path,  # 占位路径
                        file_info=placeholder_file_metadata,
                        generated_by=generated_by  # 标记为Service生成的文件
                    )
                    
                    if mongo_success:
                        # 更新文件状态为PROCESSING（正在处理中）
                        user_data_manager.update_file_info(user_id, output_file_id, analysis_status=AnalysisStatus.PROCESSING.value)
                        logger.info(
                            f"[Service执行] 占位文件已创建 - execution_id: {execution_id}, "
                            f"file_id: {output_file_id}, description: {item_description}, "
                            f"filename: {item_filename}, file_path: {placeholder_file_path}, "
                            f"file_type_id: {resolved_file_type['file_type_id']}"
                        )
                    else:
                        logger.warning(f"[Service执行] 占位文件记录创建失败 - execution_id: {execution_id}, file_id: {output_file_id}, file_path: {placeholder_file_path}")
                    output_file_infos.append({
                        "file_id": output_file_id,
                        "filename": item_filename,
                        "file_path": placeholder_file_path,
                        "description": item_description,
                        "generated_by": generated_by
                    })
                except Exception as placeholder_error:
                    logger.error(f"[Service执行] 创建占位文件记录异常 - execution_id: {execution_id}, file_id: {output_file_id}, file_path: {placeholder_file_path}, error: {placeholder_error}", exc_info=True)
                    # 占位文件创建失败不影响执行流程，但记录错误
            
            # ========== 创建执行记录（包含output_file_ids） ==========

            execution = ServiceExecution(
                execution_id=execution_id,
                service_id=service_id,
                service_name=service_info.name,
                user_id=user_id,
                input_file_ids=input_file_ids,  # 输入文件ID列表
                output_file_ids=output_file_ids,  # 输出文件ID列表（已生成占位）
                status=ServiceExecutionStatus.PENDING,
                parameters=parameters or {},
                project_id=project_id
            )
            
            execution_dict = execution.to_dict()
            self.service_executions_collection.insert_one(execution_dict)
            logger.info(f"[Service执行] 执行记录已创建 - execution_id: {execution_id}, status: PENDING, output_file_ids: {output_file_ids}")
            
            # 如果提供了project_id，将execution_id添加到项目的execution_ids列表
            if project_id:
                try:
                    user_data_manager.add_execution_to_project(user_id, project_id, execution_id)
                except Exception as e:
                    logger.warning(f"[Service执行] 添加执行到项目失败 - execution_id: {execution_id}, project_id: {project_id}, error: {e}")
                    # 不中断执行流程，仅记录警告
            
            # 如果提供了project_id且有输出文件，将输出文件添加到项目
            if project_id and output_file_ids:
                for output_file_id in output_file_ids:
                    try:
                        logger.info(f"[Service执行] 添加输出文件到项目 - execution_id: {execution_id}, project_id: {project_id}, output_file_id: {output_file_id}")
                        user_data_manager.add_file_to_project(user_id, project_id, output_file_id)
                    except Exception as e:
                        logger.warning(f"[Service执行] 添加输出文件到项目失败 - execution_id: {execution_id}, project_id: {project_id}, error: {e}")
            
            # 更新执行状态为RUNNING
            self.service_executions_collection.update_one(
                {"execution_id": execution_id},
                {"$set": {
                    "status": ServiceExecutionStatus.RUNNING.value,
                    "started_at": datetime.now()
                }}
            )
            logger.info(f"[Service执行] 执行状态已更新 - execution_id: {execution_id}, status: PENDING -> RUNNING")
            
            # 提交后台任务异步执行HTTP请求
            # 构建文件路径映射：{filename: file_path}，其中 filename 是 accepted_files 的键
            input_file_paths = {
                filename: file_info['file_path']
                for filename, file_info in validated_file_infos.items()
            }
            
            # 注册执行完成事件（供 wait_for_execution 使用）
            completion_event = threading.Event()
            with self._execution_events_lock:
                self._execution_events[execution_id] = completion_event
            
            self.service_queue.submit(
                self._execute_service_async,
                execution_id=execution_id,
                service_info=service_info,
                input_file_paths=input_file_paths,  # 传递多文件路径映射 {filename: file_path}
                user_id=user_id,
                parameters=final_params,
                start_time=start_time,
                output_file_infos=output_file_infos,
                project_id=project_id,  # 传递 project_id 以便后续使用
                input_file_ids=input_file_ids  # 传递 input_file_ids 以便创建文件关系
            )
            
            # 立即返回给前端（包含output_file_ids，前端可以立即看到灰色节点）
            result = {
                "execution_id": execution_id,
                "service_id": service_id,
                "service_name": service_info.name,  # 添加 service_name
                "input_file_ids": input_file_ids,
                "output_file_ids": output_file_ids,  # 已生成的输出文件ID列表
                "status": ServiceExecutionStatus.RUNNING.value,
                "response_data": None,
                "error_message": None,
                "created_at": datetime.now().isoformat(),
                "started_at": datetime.now().isoformat(),
                "completed_at": None,
                "duration_seconds": None
            }
            return result
                
        except HTTPException as http_ex:
            logger.error(f"[Service执行] HTTP异常 - execution_id: {execution_id}, "
                        f"status_code: {http_ex.status_code}, detail: {http_ex.detail}")
            raise
        except Exception as e:
            logger.error(f"[Service执行] 执行Service失败 - execution_id: {execution_id}, "
                        f"service_id: {service_id}, error_type: {type(e).__name__}, error: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"执行Service失败: {str(e)}"
            )
    
    def _get_output_user_dir(self, user_id: str) -> Path:
        """获取输出目录"""
        output_dir = self.file_manager.output_dir
        if user_id:
            placeholder_dir = output_dir / user_id
            placeholder_dir.mkdir(parents=True, exist_ok=True)
            return placeholder_dir
        else:
            raise ValueError("user_id为空，无法获取输出目录")

    def _execute_service_async(
        self,
        execution_id: str,
        service_info: ServiceInfo,
        input_file_paths: Dict[str, str],  # 修改为多文件路径映射 {filename: file_path}
        user_id: str,
        parameters: Dict[str, Any],
        start_time: float,
        output_file_infos: List[Dict[str, Any]],
        project_id: Optional[str] = None,  # 添加 project_id 参数
        input_file_ids: Optional[List[str]] = None  # 添加 input_file_ids 参数以便创建文件关系
    ) -> None:
        """
        后台异步执行Service的HTTP请求
        
        执行完成后，更新占位文件记录：
        - 如果返回了实际文件，更新文件路径、大小、状态等
        - 如果执行失败，更新文件状态为ERROR

        Args:
            input_file_paths: 文件路径映射 {filename: file_path}，其中 filename 对应 accepted_files 的键

        """
        logger.info(f"[Service执行-异步] ========== 开始执行 ========== - execution_id: {execution_id}, "
                   f"service_id: {service_info.service_id}, service_name: {service_info.name}, "
                   f"user_id: {user_id}, input_files: {list(input_file_paths.keys())}, "
                   f"output_file_ids_count: {len(output_file_infos) if output_file_infos else 0}, "
                   f"project_id: {project_id}")
        
        # 保留传入的 output_file_ids，不要覆盖
        response_data = None
        error_message = None
        step_start_time = time.time()
        
        try:
            # ========== 步骤1: 验证输入文件 ==========
            logger.info(f"[Service执行-异步] [步骤1] 验证输入文件路径 - execution_id: {execution_id}, input_files: {list(input_file_paths.keys())}")
            
            for filename, file_path in input_file_paths.items():
                if file_path and not os.path.exists(file_path):
                    error_msg = f"输入文件路径不存在: {filename}={file_path}"
                    logger.error(f"[Service执行-异步] {error_msg} - execution_id: {execution_id}")
                    raise FileNotFoundError(error_msg)
            
            logger.info(f"[Service执行-异步] ✓ 输入文件验证通过 - execution_id: {execution_id}, files: {list(input_file_paths.keys())}")
            
            # ========== 步骤2: 发送HTTP请求 ==========
            logger.info(f"[Service执行-异步] [步骤2] 开始发送HTTP请求 - execution_id: {execution_id}, "
                       f"url: {service_info.get_service_url()}, method: {service_info.request_config.http_method.value}")
            
            http_request_start = time.time()
            response_data = self._send_http_request(
                service_info=service_info,
                input_file_paths=input_file_paths,  # 传递多文件路径映射
                parameters=parameters,
                output_config=service_info.output_config,  # 传递output_config用于解析响应
                execution_id=execution_id,  # 传递execution_id用于日志
            )
            http_request_duration = time.time() - http_request_start
            
            logger.info(f"[Service执行-异步] ✓ HTTP请求完成 - execution_id: {execution_id}, "
                       f"duration: {http_request_duration:.2f}s, response_type: {type(response_data).__name__}")
            
            # ========== 步骤3: 解析响应数据 ==========
            logger.info(f"[Service执行-异步] [步骤3] 解析响应数据 - execution_id: {execution_id}")
            
            # 从 response_data 中提取文件信息
            # response_data 格式：
            # 1. 结构化格式：{"outputs": [{"type": "file", "file_path": str, "size": int, ...}, ...], ...}
            # 输出都是文件类型，文本也转为了文件类型
            generated_output_file_infos = []
            if isinstance(response_data, dict):
                if "outputs" in response_data:
                    # 结构化格式：从 outputs 数组中提取文件信息
                    for output_item in response_data["outputs"]:
                        generated_output_file_infos.append(output_item)
                    logger.info(f"[Service执行-异步] ✓ 解析到 {len(generated_output_file_infos)} 个输出文件 - execution_id: {execution_id}, generated_output_file_infos: {generated_output_file_infos}")
                else:
                    logger.warning(f"[Service执行-异步] 响应中没有 'outputs' 键 - execution_id: {execution_id}, response_keys: {list(response_data.keys())}")
            else:
                logger.warning(f"[Service执行-异步] 响应数据不是字典类型 - execution_id: {execution_id}, response_type: {type(response_data).__name__}")
            
            # ========== 步骤4: 处理输出文件 ==========
            if output_file_infos and generated_output_file_infos:
                logger.info(f"[Service执行-异步] [步骤4] 开始处理输出文件 - execution_id: {execution_id}, "
                           f"file_ids_count: {len(output_file_infos)}, output_files_count: {len(generated_output_file_infos)}")
                from textmsa.services.data.user_data_manager_mongodb import get_user_data_manager
                from textmsa.services.data.mongodb_models import AnalysisStatus
                
                user_data_manager = get_user_data_manager()
                user_dir = self._get_output_user_dir(user_id)

                logger.info(f"[Service执行-异步] 用户目录已准备 - execution_id: {execution_id}, user_dir: {user_dir}")
                        
                # 遍历输出文件，将文件移动到用户目录并更新数据库
                processed_count = 0

                def mark_all_outputs_error(error_msg: str) -> None:
                    for target_file_info in output_file_infos:
                        try:
                            user_data_manager.update_file_info(
                                user_id=user_id,
                                file_id=target_file_info["file_id"],
                                analysis_status=AnalysisStatus.ERROR,
                                metadata={"error_message": error_msg}
                            )
                        except Exception as update_error:
                            logger.error(f"[Service执行] 批量更新输出文件状态失败 - execution_id: {execution_id}, file_id: {target_file_info.get('file_id', 'unknown')}, error: {update_error}")

                expected_count = len(output_file_infos)
                actual_count = len(generated_output_file_infos)
                
                # 允许实际输出数量 <= 配置数量（允许部分输出）
                if actual_count > expected_count:
                    mismatch_msg = (
                        f"输出文件数量超过配置 - execution_id: {execution_id}, "
                        f"expected: {expected_count}, actual: {actual_count}"
                    )
                    logger.error(f"[Service执行] {mismatch_msg}")
                    mark_all_outputs_error("执行服务返回的输出文件数量超过配置")
                    raise RuntimeError(mismatch_msg)
                
                # 如果实际数量少于配置数量，删除未返回的文件的占位记录，继续处理已返回的文件
                if actual_count < expected_count:
                    missing_count = expected_count - actual_count
                    logger.warning(
                        f"[Service执行] 输出文件数量少于配置，将删除未返回文件的占位记录 - execution_id: {execution_id}, "
                        f"expected: {expected_count}, actual: {actual_count}, missing: {missing_count}"
                    )
                    # 删除未返回的文件的占位记录
                    for idx in range(actual_count, expected_count):
                        missing_file_id = output_file_infos[idx]["file_id"]
                        try:
                            # 如果文件在项目中，先从项目移除
                            if project_id:
                                try:
                                    user_data_manager.remove_file_from_project(
                                        user_id=user_id,
                                        project_id=project_id,
                                        file_id=missing_file_id
                                    )
                                    logger.info(
                                        f"[Service执行] 未返回文件的占位记录已从项目移除 - execution_id: {execution_id}, "
                                        f"file_id: {missing_file_id}"
                                    )
                                except Exception as remove_error:
                                    logger.warning(
                                        f"[Service执行] 从项目中移除未返回文件占位记录失败 - execution_id: {execution_id}, "
                                        f"file_id: {missing_file_id}, error: {remove_error}"
                                    )
                            
                            # 删除文件记录
                            user_data_manager.delete_file(
                                user_id=user_id,
                                file_id=missing_file_id
                            )
                            logger.info(
                                f"[Service执行] 未返回文件的占位记录已删除 - execution_id: {execution_id}, "
                                f"file_id: {missing_file_id}"
                            )
                        except Exception as e:
                            logger.error(
                                f"[Service执行] 删除未返回文件占位记录失败 - execution_id: {execution_id}, "
                                f"file_id: {missing_file_id}, error: {e}"
                            )
                    
                    # 从output_file_infos中移除未返回的文件，使后续处理时索引对应
                    output_file_infos = output_file_infos[:actual_count]
                    logger.info(
                        f"[Service执行] 已从output_file_infos中移除未返回的文件 - execution_id: {execution_id}, "
                        f"剩余文件数量: {len(output_file_infos)}"
                    )

                for idx, tmp_file_info in enumerate(generated_output_file_infos):
                    # 从output_file_infos获取对应的file_id，因为generated_output_file_infos可能没有file_id字段
                    target_file_id = output_file_infos[idx]["file_id"]
                    logger.info(f'[Service执行-异步] 处理文件 [{idx+1}/{len(output_file_infos)}] - execution_id: {execution_id}, file_id: {target_file_id}')
                    tmp_file_path = tmp_file_info.get("file_path")

                    if not tmp_file_path or not os.path.exists(tmp_file_path):
                        error_msg = f'源文件不存在 - execution_id: {execution_id}, file_id: {target_file_id}, source_path: {tmp_file_path}'
                        logger.warning(f"[Service执行] {error_msg}")
                        try:
                            user_data_manager.update_file_info(
                                user_id=user_id,
                                file_id=target_file_id,
                                analysis_status=AnalysisStatus.ERROR,
                                metadata={"error_message": error_msg}
                            )
                        except Exception as e:
                            logger.error(f"[Service执行] 更新文件状态失败 - execution_id: {execution_id}, file_id: {target_file_id}, error: {e}")
                        mark_all_outputs_error("执行服务返回的输出文件缺失或无效")
                        raise RuntimeError(error_msg)
                    
                    try:
                        # 1. 移动文件到用户目录
                        tmp_path = Path(tmp_file_path)
                        # 保持原文件名，如果冲突则添加文件ID前缀
                        target_path = output_file_infos[idx].get("file_path")
                        
                        
                        # 移动文件
                        shutil.move(str(tmp_path), str(target_path))
                        logger.info(f"[Service执行] 文件已移动到用户目录 - execution_id: {execution_id}, file_id: {target_file_id}, target_path: {target_path}")
                        
                        # 2. 更新数据库中的文件信息
                        # 获取文件大小
                        file_size = os.path.getsize(target_path)
                        
                        # 准备更新数据
                        update_metadata = {
                            "size": file_size,
                            "is_placeholder": False
                        }
                        
                        # 如果文件信息中有其他元数据，也一并更新
                        if "size" in tmp_file_info:
                            update_metadata["size"] = tmp_file_info["size"]
                        if "metadata" in tmp_file_info and isinstance(tmp_file_info["metadata"], dict):
                            update_metadata.update(tmp_file_info["metadata"])
                        
                        # 更新文件信息
                        result = user_data_manager.update_file_info(
                            user_id=user_id,
                            file_id=target_file_id,
                            analysis_status=AnalysisStatus.COMPLETED,
                            metadata=update_metadata
                        )
                        
                        if not result or not result.get("success"):
                            failure_msg = result.get('message') if isinstance(result, dict) else "未知错误"
                            logger.warning(f"[Service执行] 文件信息更新失败 - execution_id: {execution_id}, file_id: {target_file_id}, message: {failure_msg}")
                            mark_all_outputs_error(f"更新文件信息失败: {failure_msg}")
                            raise RuntimeError(f"更新输出文件信息失败: {failure_msg}")
                        
                        processed_count += 1
                        logger.info(f"[Service执行] 文件信息已更新 - execution_id: {execution_id}, file_id: {target_file_id}, status: COMPLETED")
                        
                        # 3. 创建文件关系（输出文件与输入文件的父子关系）
                        if input_file_ids:
                            try:
                                relation_result = user_data_manager.create_file_relations(
                                    parent_file_ids=input_file_ids,
                                    child_file_id=target_file_id,
                                    description=f"由Service '{service_info.name }' 生成"
                                )
                                logger.info(
                                    f"[Service执行] 成功创建文件关系 - execution_id: {execution_id}, "
                                    f"file_id: {target_file_id}, "
                                    f"父文件: {input_file_ids}, "
                                    f"创建数量: {relation_result.get('created_count', 0)}"
                                )
                            except Exception as relation_error:
                                logger.warning(
                                    f"[Service执行] 创建文件关系失败 - execution_id: {execution_id}, "
                                    f"file_id: {target_file_id}, error: {relation_error}"
                                )
                                # 不抛出异常，允许文件处理成功，但关系创建失败
                            
                    except Exception as file_error:
                        logger.error(f"[Service执行] 处理输出文件失败 - execution_id: {execution_id}, file_id: {target_file_id}, error: {file_error}", exc_info=True)
                        # 更新文件状态为ERROR
                        try:
                            user_data_manager.update_file_info(
                                user_id=user_id,
                                file_id=target_file_id,
                                analysis_status=AnalysisStatus.ERROR,
                                metadata={"error_message": str(file_error)}
                            )
                        except Exception as e:
                            logger.error(f"[Service执行] 更新文件状态为ERROR失败 - execution_id: {execution_id}, file_id: {target_file_id}, error: {e}")
                        mark_all_outputs_error(f"处理输出文件失败: {file_error}")
                        raise
                
                logger.info(f"[Service执行-异步] ✓ 文件处理完成 - execution_id: {execution_id}, processed: {processed_count}/{len(output_file_infos)}")
            
            # 如果没有返回文件信息，但已有文件ID，保持原文件ID列表
            if not generated_output_file_infos and output_file_infos:
                logger.error(f"[Service执行] 未返回任何输出文件信息 - execution_id: {execution_id}, file_ids: {output_file_infos}")
                from textmsa.services.data.user_data_manager_mongodb import get_user_data_manager
                from textmsa.services.data.mongodb_models import AnalysisStatus
                user_data_manager = get_user_data_manager()
                for file_info in output_file_infos:
                    try:
                        user_data_manager.update_file_info(
                            user_id=user_id,
                            file_id=file_info["file_id"],
                            analysis_status=AnalysisStatus.ERROR,
                            metadata={"error_message": "执行服务未返回任何输出"}
                        )
                    except Exception as update_error:
                        logger.error(f"[Service执行] 更新输出文件状态失败 - execution_id: {execution_id}, file_id: {file_info.get('file_id', 'unknown')}, error: {update_error}")
                raise RuntimeError("执行服务未返回任何输出文件信息")
            
            # ========== 步骤5: 更新执行状态为COMPLETED ==========
            logger.info(f"[Service执行-异步] [步骤5] 更新执行状态为COMPLETED - execution_id: {execution_id}")
            
            output_file_ids = [file_info["file_id"] for file_info in output_file_infos]

            total_duration = time.time() - start_time
            self.service_executions_collection.update_one(
                {"execution_id": execution_id},
                {"$set": {
                    "status": ServiceExecutionStatus.COMPLETED.value,
                    "completed_at": datetime.now(),
                    "duration_seconds": total_duration,
                    "output_file_ids": output_file_ids,  # 确保是列表，不是 None
                    "response_data": response_data
                }}
            )
            logger.info(f"[Service执行] 执行状态已更新 - execution_id: {execution_id}, status: RUNNING -> COMPLETED, duration: {total_duration:.2f}s")
            
            # 通知等待线程
            self._notify_execution_complete(execution_id)
            
            # ========== 步骤6: 添加文件到项目（如果提供project_id） ==========
            if project_id and output_file_ids:
                logger.info(f"[Service执行-异步] [步骤6] 添加输出文件到项目 - execution_id: {execution_id}, project_id: {project_id}")
                try:
                    from textmsa.services.project.project_service import get_project_service
                    project_service = get_project_service()
                    
                    added_count = 0
                    # 将每个输出文件添加到项目
                    for output_file_id in output_file_ids:
                        if output_file_id:  # 确保文件ID不为空
                            try:
                                project_service.add_file_to_project(
                                    project_id=project_id,
                                    file_id=output_file_id,
                                    user_id=user_id
                                )
                                added_count += 1
                            except Exception as file_error:
                                # 单个文件添加失败不影响其他文件，只记录警告
                                logger.warning(f"[Service执行] 添加输出文件到项目失败 - execution_id: {execution_id}, file_id: {output_file_id}, error: {file_error}")
                except Exception as e:
                    # 项目服务调用失败不影响执行完成状态，只记录警告
                    logger.warning(f"[Service执行] 添加输出文件到项目失败 - execution_id: {execution_id}, project_id: {project_id}, error: {e}")
            
            # ========== 执行成功完成 ==========
            logger.info(f"[Service执行-异步] ========== 执行成功完成 ========== - execution_id: {execution_id}, "
                       f"total_duration: {total_duration:.2f}s, output_files_count: {len(output_file_ids) if output_file_ids else 0}")
            
        except Exception as e:
            error_message = str(e)
            total_duration = time.time() - start_time
            error_type = type(e).__name__
            
            # 如果是HTTPStatusError，尝试从响应体中提取详细的错误消息
            if isinstance(e, httpx.HTTPStatusError):
                try:
                    response = e.response
                    if response:
                        try:
                            response_json = response.json()
                            if isinstance(response_json, dict) and "message" in response_json:
                                # 提取响应体中的message字段作为详细的错误信息
                                detailed_message = response_json.get("message")
                                if detailed_message:
                                    error_message = detailed_message
                                    logger.info(f"[Service执行-异步] 已从HTTP响应中提取详细错误消息 - execution_id: {execution_id}")
                        except Exception:
                            # 如果无法解析JSON，使用原始错误消息
                            pass
                except Exception as extract_error:
                    logger.debug(f"[Service执行-异步] 提取HTTP响应错误消息失败 - execution_id: {execution_id}, error: {extract_error}")
            
            logger.error(f"[Service执行-异步] ========== 执行失败 ========== - execution_id: {execution_id}, "
                        f"error_type: {error_type}, error: {error_message}, duration: {total_duration:.2f}s", exc_info=True)
            
            # ========== 更新占位文件状态为ERROR ==========
            # 从output_file_infos提取file_id列表
            output_file_ids = [file_info["file_id"] for file_info in output_file_infos] if output_file_infos else []
            if output_file_ids:
                try:
                    from textmsa.services.data.user_data_manager_mongodb import get_user_data_manager
                    from textmsa.services.data.mongodb_models import AnalysisStatus
                    user_data_manager = get_user_data_manager()
                    
                    for file_id in output_file_ids:
                        try:
                            user_data_manager.files_collection.update_one(
                                {"file_id": file_id},
                                {"$set": {
                                    "analysis_status": AnalysisStatus.ERROR.value,
                                    "metadata.error_message": error_message
                                }}
                            )
                            logger.info(f"[Service执行] 文件状态已更新 - execution_id: {execution_id}, file_id: {file_id}, status: -> ERROR")
                        except Exception as update_error:
                            logger.warning(f"[Service执行] 更新占位文件状态失败 - execution_id: {execution_id}, file_id: {file_id}, error: {update_error}")
                except Exception as placeholder_update_error:
                    logger.warning(f"[Service执行] 更新占位文件状态异常 - execution_id: {execution_id}, error: {placeholder_update_error}")
            
            # 删除占位文件的数据库记录，避免错误文件残留
            try:
                from textmsa.services.data.user_data_manager_mongodb import get_user_data_manager
                cleanup_user_data_manager = get_user_data_manager()
                
                for file_info in output_file_infos or []:
                    file_id = file_info.get("file_id")
                    if not file_id:
                        continue
                    
                    if project_id:
                        try:
                            cleanup_user_data_manager.remove_file_from_project(
                                user_id=user_id,
                                project_id=project_id,
                                file_id=file_id
                            )
                        except Exception as remove_error:
                            logger.warning(
                                f"[Service执行] 从项目中移除错误文件失败 - execution_id: {execution_id}, file_id: {file_id}, error: {remove_error}"
                            )
                    
                    try:
                        cleanup_user_data_manager.delete_file(
                            user_id=user_id,
                            file_id=file_id
                        )
                        logger.info(
                            f"[Service执行] 错误输出文件记录已删除 - execution_id: {execution_id}, file_id: {file_id}"
                        )
                    except Exception as delete_error:
                        logger.warning(
                            f"[Service执行] 删除错误输出文件记录失败 - execution_id: {execution_id}, file_id: {file_id}, error: {delete_error}"
                        )
            except Exception as cleanup_error:
                logger.warning(
                    f"[Service执行] 清理错误输出文件记录异常 - execution_id: {execution_id}, error: {cleanup_error}"
                )
            
            # ========== 更新MongoDB执行状态为FAILED ==========
            self.service_executions_collection.update_one(
                {"execution_id": execution_id},
                {"$set": {
                    "status": ServiceExecutionStatus.FAILED.value,
                    "completed_at": datetime.now(),
                    "duration_seconds": total_duration,
                    "error_message": error_message
                }}
            )
            logger.info(f"[Service执行] 执行状态已更新 - execution_id: {execution_id}, status: RUNNING -> FAILED, duration: {total_duration:.2f}s")
            
            # 通知等待线程
            self._notify_execution_complete(execution_id)
    
    def _send_http_request(self, service_info: ServiceInfo, input_file_paths: Dict[str, str],
                          parameters: Dict[str, Any], output_config: ServiceOutputConfig,
                          execution_id: Optional[str] = None) -> Dict[str, Any]:
        """
        发送HTTP请求到远程服务器
        
        统一使用multipart/form-data格式发送文件，文件参数名根据accepted_files配置确定：
        1. 如果accepted_files配置中存在param_name字段，使用它作为HTTP请求参数名
        2. 否则使用accepted_files的键作为参数名
        
        例如：
        - accepted_files为{"file": {...}}，则文件参数名为"file"
        - accepted_files为{"spatial_data.h5ad": {param_name: "spatial_file", ...}}，则文件参数名为"spatial_file"
        - accepted_files为{"file": {...}, "reference": {...}}，则发送两个文件参数
        
        处理新的响应格式：
        {
          "success": true,
          "message": "预处理完成",
          "data": {
            "preprocessed_data.h5ad": "./outputs/preprocessed_xxx.h5ad",
            "处理统计信息": "文本内容..."
          }
        }
        
        Args:
            service_info: Service信息
            input_file_paths: 输入文件路径映射 {filename: file_path}，其中 filename 对应 accepted_files 的键
            parameters: 请求参数
            execution_id: 执行ID（用于日志）
            output_config: 输出配置，用于解析响应格式
        
        Returns:
            response_data: 响应数据（Dict，包含所有输出项）
            格式：{"outputs": [{"type": "file", "file_path": str, "size": int, "description": str}, ...], "status": "success"}
        """
        # 固定使用默认请求配置（POST + multipart/form-data），忽略Service上保存的配置
        request_config = TaskRequestConfig()
        
        # 验证输入文件路径
        for filename, file_path in input_file_paths.items():
            if file_path and not os.path.exists(file_path):
                error_msg = f"输入文件路径不存在: {filename}={file_path}"
                logger.error(f"[Service执行-HTTP] {error_msg} - execution_id: {execution_id}")
                raise FileNotFoundError(error_msg)
        
        # 准备请求头（移除Content-Type，让httpx自动设置multipart/form-data）
        headers = {}
        for key, value in request_config.headers.items():
            if key.lower() != 'content-type':
                headers[key] = value
        
        # 发送请求（带重试）
        max_retries = request_config.retry_count + 1
        last_error = None
        
        for attempt in range(max_retries):
            file_objs = []  # 保存所有打开的文件对象，用于后续关闭
            try:
                # 准备请求体
                files = None
                data = None
                
                if request_config.http_method in [HttpMethod.POST, HttpMethod.PUT, HttpMethod.PATCH]:
                    # 构建多文件上传：根据accepted_files的键或param_name作为参数名
                    files = {}
                    file_details = []
                    accepted_files_config = service_info.accepted_files or {}
                    
                    for filename, file_path in input_file_paths.items():
                        file_obj = open(file_path, 'rb')
                        file_objs.append(file_obj)
                        
                        # 确定HTTP请求参数名：
                        # 1. 如果accepted_files配置中存在param_name字段，使用它
                        # 2. 否则使用filename（accepted_files的键）作为参数名
                        file_config = accepted_files_config.get(filename, {})
                        param_name = file_config.get('param_name', filename)
                        
                        file_basename = os.path.basename(file_path)
                        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 'N/A'
                        files[param_name] = (file_basename, file_obj, "application/octet-stream")
                        file_details.append(
                            f"{filename}={{param_name: {param_name}, "
                            f"file_name: {file_basename}, "
                            f"file_path: {file_path}, "
                            f"file_size: {file_size} bytes}}"
                        )
                    
                    # 添加其他参数（转换为字符串格式）
                    form_data = {}
                    for key, value in parameters.items():
                        if isinstance(value, bool):
                            form_data[key] = str(value).lower()  # True -> "true", False -> "false"
                        elif value is None:
                            continue
                        else:
                            form_data[key] = str(value)
                    data = form_data
                else:
                    data = parameters
                
                try:
                    with httpx.Client(timeout=request_config.timeout_seconds) as client:
                        response = client.request(
                            method=request_config.http_method.value,
                            url=service_info.get_service_url(),
                            headers=headers,
                            data=data,
                            files=files
                        )
                        
                        if response.status_code != 200:
                            # 尝试读取响应体内容以便调试
                            try:
                                response_text = response.text
                                # 尝试解析JSON响应体
                                try:
                                    response_json_error = response.json()
                                    logger.warning(
                                        f"[Service执行-HTTP] HTTP请求返回非200状态码: {response.status_code} - "
                                        f"execution_id: {execution_id}, base_url: {service_info.baseurl}, "
                                        f"response_body: {response_json_error}"
                                    )
                                except Exception:
                                    # 如果不是JSON，记录文本内容（限制长度）
                                    response_preview = response_text[:500] if len(response_text) > 500 else response_text
                                    logger.warning(
                                        f"[Service执行-HTTP] HTTP请求返回非200状态码: {response.status_code} - "
                                        f"execution_id: {execution_id}, base_url: {service_info.baseurl}, "
                                        f"response_body_preview: {response_preview}"
                                    )
                            except Exception as e:
                                logger.warning(
                                    f"[Service执行-HTTP] HTTP请求返回非200状态码: {response.status_code} - "
                                    f"execution_id: {execution_id}, base_url: {service_info.baseurl}, "
                                    f"无法读取响应体: {e}"
                                )
                        
                        response.raise_for_status()
                        
                        # 解析JSON响应
                        try:
                            response_json = response.json()
                        except Exception as e:
                            logger.error(f"[Service执行-HTTP] 响应不是JSON格式 - execution_id: {execution_id}, error: {e}")
                            raise ValueError(f"响应不是有效的JSON格式: {e}")
                        
                        # 处理新的响应格式
                        if isinstance(response_json, dict) and "success" in response_json and "data" in response_json:
                            # 检查success字段，如果为false则抛出异常
                            success = response_json.get("success", False)
                            if not success:
                                error_msg = response_json.get("message", "服务执行失败")
                                logger.error(f"[Service执行-HTTP] 服务返回失败状态 - execution_id: {execution_id}, message: {error_msg}")
                                raise ValueError(f"服务执行失败: {error_msg}")
                            
                            data_dict = response_json.get("data", {})
                            if not isinstance(data_dict, dict):
                                error_msg = f"响应data字段不是字典类型 - execution_id: {execution_id}"
                                logger.error(f"[Service执行-HTTP] {error_msg}")
                                raise ValueError(error_msg)
                            
                            if not data_dict:
                                error_msg = f"响应data字段为空 - execution_id: {execution_id}"
                                logger.error(f"[Service执行-HTTP] {error_msg}")
                                raise ValueError(error_msg)
                            
                            structured_outputs = []
                            failed_items = []  # 记录处理失败的项目
                            
                            # 根据output_config.items处理响应数据
                            # 使用output_config中定义的filename来匹配data中的键
                            
                            for item in output_config.items:
                                item_type, item_filename, item_description = self._extract_output_item_fields(item)
                                
                                # 在data中查找匹配的键（仅支持精确匹配）
                                matched_key = None
                                matched_value = None
                                
                                # 精确匹配
                                if item_filename in data_dict:
                                    matched_key = item_filename
                                    matched_value = data_dict[item_filename]
                                else:
                                    # 未找到输出项时，只记录警告，不当作错误处理（允许部分输出文件缺失）
                                    logger.warning(f"[Service执行-HTTP] 未找到匹配的输出项（允许缺失） - execution_id: {execution_id}, filename: {item_filename}")
                                    continue
                                
                                if item_type == ServiceOutputItemType.FILE:
                                    download_hints = self._infer_download_hints_from_filename(item_filename)
                                    download_endpoint = service_info.get_download_url()
                                    if not download_endpoint:
                                        error_msg = f"Service未配置download_suffix，无法下载文件 - execution_id: {execution_id}"
                                        logger.error(f"[Service执行-HTTP] {error_msg}")
                                        failed_items.append(error_msg)
                                        continue
                                    # 文件类型：下载文件
                                    try:
                                        temp_file_path = self._download_file_from_path(
                                            file_path=matched_value,
                                            download_url=download_endpoint,
                                            execution_id=execution_id,
                                            expected_extension=download_hints.get("extension"),
                                            file_type=download_hints.get("file_type")
                                        )
                                        
                                        if temp_file_path and os.path.exists(temp_file_path):
                                            file_size = os.path.getsize(temp_file_path)
                                            structured_outputs.append({
                                                "type": "file",
                                                "file_path": temp_file_path,
                                                "size": file_size,
                                                "description": item_description or matched_key,
                                                "metadata": {
                                                    "filename": item_filename,
                                                    "file_extension": download_hints.get("extension"),
                                                    "mime_type": download_hints.get("mime_type")
                                                }
                                            })
                                            logger.info(f"[Service执行-HTTP] 下载文件成功 - execution_id: {execution_id}, filename: {item_filename}, key: {matched_key}, size: {file_size}")
                                        else:
                                            error_msg = f"文件下载失败 - execution_id: {execution_id}, filename: {item_filename}, key: {matched_key}, path: {matched_value}"
                                            logger.error(f"[Service执行-HTTP] {error_msg}")
                                            failed_items.append(f"文件下载失败: {item_filename}")
                                    except Exception as e:
                                        error_msg = f"下载文件异常: {item_filename} ({e})"
                                        logger.error(f"[Service执行-HTTP] 下载文件异常 - execution_id: {execution_id}, filename: {item_filename}, key: {matched_key}, path: {matched_value}, error: {e}")
                                        failed_items.append(error_msg)
                                else:
                                    logger.warning(f"[Service执行-HTTP] 未知的输出项类型 - execution_id: {execution_id}, filename: {item_filename}, type: {item_type}")
                                    failed_items.append(f"未知类型: {item_filename}")
                            
                            # 检查是否有处理失败的项目，如果有则抛出异常
                            if failed_items:
                                error_msg = f"部分输出项处理失败 - execution_id: {execution_id}, failed_items: {failed_items}"
                                logger.error(f"[Service执行-HTTP] {error_msg}")
                                raise ValueError(f"输出数据处理失败: {', '.join(failed_items)}")
                            
                            # 检查是否至少有一个输出项成功处理
                            if not structured_outputs:
                                error_msg = f"没有成功处理的输出项 - execution_id: {execution_id}"
                                logger.error(f"[Service执行-HTTP] {error_msg}")
                                raise ValueError(error_msg)
                            
                            return {
                                "outputs": structured_outputs,
                                "status": "success",
                                "message": response_json.get("message", "")
                            }
                        else:
                            # 响应格式不符合预期：不是 {"success": true, "data": {...}} 格式
                            error_msg = f"响应格式不符合预期 - execution_id: {execution_id}, 期望格式: {{'success': true, 'data': {{...}}}}, 实际响应: {response_json}"
                            logger.error(f"[Service执行-HTTP] {error_msg}")
                            raise ValueError(f"响应格式不符合预期: 期望包含 'success' 和 'data' 字段的字典格式")
                            
                finally:
                    # 关闭所有打开的文件对象
                    for file_obj in file_objs:
                        if file_obj:
                            try:
                                file_obj.close()
                            except Exception as e:
                                logger.warning(f"[Service执行-HTTP] 关闭文件失败 - execution_id: {execution_id}, error: {e}")
                    
            except httpx.HTTPStatusError as e:
                # HTTP状态错误，尝试提取响应体信息
                last_error = e
                response_body_info = ""
                status_code = "unknown"
                try:
                    status_code = e.response.status_code
                    # 尝试读取响应体
                    try:
                        response_json_error = e.response.json()
                        response_body_info = f", response_body: {response_json_error}"
                    except Exception:
                        # 如果不是JSON，记录文本内容（限制长度）
                        response_text = e.response.text
                        response_preview = response_text[:500] if len(response_text) > 500 else response_text
                        response_body_info = f", response_body_preview: {response_preview}"
                except Exception as ex:
                    # 如果无法读取响应，至少记录状态码
                    logger.debug(f"[Service执行-HTTP] 无法读取响应体 - execution_id: {execution_id}, error: {ex}")
                
                if attempt < max_retries - 1:
                    time.sleep(request_config.retry_delay_seconds)
                    logger.warning(
                        f"[Service执行-HTTP] 请求失败，重试 {attempt + 1}/{max_retries} - "
                        f"execution_id: {execution_id}, status_code: {status_code}, "
                        f"error: {e}{response_body_info}"
                    )
                else:
                    logger.error(
                        f"[Service执行-HTTP] 请求最终失败 - execution_id: {execution_id}, "
                        f"status_code: {status_code}, error: {e}{response_body_info}",
                        exc_info=True
                    )
                    raise
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    time.sleep(request_config.retry_delay_seconds)
                    logger.warning(f"[Service执行-HTTP] 请求失败，重试 {attempt + 1}/{max_retries} - execution_id: {execution_id}, error: {e}")
                else:
                    logger.error(f"[Service执行-HTTP] 请求最终失败 - execution_id: {execution_id}, error: {e}", exc_info=True)
                    raise
        
        # 如果循环正常结束但没有成功返回，且 last_error 为 None，抛出默认异常
        if last_error is None:
            error_msg = f"HTTP请求失败：所有重试尝试都已完成，但未成功返回响应 - execution_id: {execution_id}"
            logger.error(f"[Service执行-HTTP] {error_msg}")
            raise RuntimeError(error_msg)
        
        raise last_error
    
    def _download_file_from_path(
        self,
        file_path: str,
        download_url: str,
        execution_id: Optional[str] = None,
        expected_extension: Optional[str] = None,
        file_type: Optional[str] = None
    ) -> Optional[str]:
        """
        从文件路径下载文件（支持相对路径和绝对路径）
        
        Args:
            file_path: 文件路径（相对路径或绝对路径）
            download_url: 下载URL
            execution_id: 执行ID（用于日志）
            expected_extension: 预期的文件扩展名（用于生成临时文件后缀）
            file_type: 需要传递给 system service 的 file_type 查询参数
        
        Returns:
            下载后的临时文件路径，失败返回None
        """
        try:
            from urllib.parse import urlparse, urljoin
            
            
            download_url = urljoin(f"{download_url}/", file_path)
            if file_type:
                separator = '&' if '?' in download_url else '?'
                download_url = f"{download_url}{separator}file_type={file_type}"
            logger.info(f"[Service执行-HTTP] 开始下载文件 - execution_id: {execution_id}, original_path: {file_path}, url: {download_url}")
            
            # 下载文件
            extension = None
            if expected_extension:
                extension = expected_extension if expected_extension.startswith('.') else f".{expected_extension}"
            temp_file_path = os.path.join(
                tempfile.gettempdir(),
                f"service_download_{uuid.uuid4().hex}{extension or '.tmp'}"
            )
            
            with httpx.Client(timeout=7200.0) as client:
                with open(temp_file_path, 'wb') as f:
                    with client.stream('GET', download_url) as response:
                        response.raise_for_status()
                        for chunk in response.iter_bytes():
                            if chunk:
                                f.write(chunk)
            
            file_size = os.path.getsize(temp_file_path)
            logger.info(f"[Service执行-HTTP] 文件下载完成 - execution_id: {execution_id}, size: {file_size} bytes")
            return temp_file_path
            
        except Exception as e:
            logger.error(f"[Service执行-HTTP] 下载文件失败 - execution_id: {execution_id}, path: {file_path}, error: {e}", exc_info=True)
            return None
    
    
    def get_execution(self, execution_id: str) -> Dict[str, Any]:
        """
        获取执行记录
        
        Args:
            execution_id: 执行ID
        
        Returns:
            执行记录
        """
        try:
            execution_doc = self.service_executions_collection.find_one({"execution_id": execution_id})
            
            if not execution_doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"执行记录 '{execution_id}' 不存在"
                )
            
            execution = service_execution_from_dict(execution_doc)
            
            # 获取Service名称与描述
            service_doc = self.services_collection.find_one({"service_id": execution.service_id})
            service_name = service_doc.get('name') if service_doc else None
            service_description = service_doc.get('description') if service_doc else None
            
            return {
                "execution_id": execution.execution_id,
                "service_id": execution.service_id,
                "service_name": service_name,
                "service_description": service_description,
                "user_id": execution.user_id,
                "input_file_ids": execution.input_file_ids,
                "output_file_ids": execution.output_file_ids,
                "project_id": execution.project_id,
                "status": execution.status.value,
                "parameters": execution.parameters,
                "response_data": execution.response_data,
                "error_message": execution.error_message,
                "created_at": execution.created_at.isoformat() if execution.created_at else None,
                "started_at": execution.started_at.isoformat() if execution.started_at else None,
                "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                "duration_seconds": execution.duration_seconds
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取执行记录失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"获取执行记录失败: {str(e)}"
            )
    
    def list_executions(self, service_id: Optional[str] = None, user_id: Optional[str] = None,
                       status_filter: Optional[str] = None, project_id: Optional[str] = None,
                       skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        """
        获取执行记录列表
        
        Args:
            service_id: Service ID过滤（可选）
            user_id: 用户ID过滤（可选）
            status_filter: 状态过滤（可选）
            project_id: Project ID过滤（可选）
            skip: 跳过数量
            limit: 返回数量
        
        Returns:
            执行记录列表和总数
        """
        try:
            query = {}
            
            if service_id:
                query["service_id"] = service_id
            if user_id:
                query["user_id"] = user_id
            if status_filter:
                query["status"] = status_filter
            if project_id:
                query["project_id"] = project_id
            
            # 查询总数
            total = self.service_executions_collection.count_documents(query)
            
            # 查询列表
            cursor = self.service_executions_collection.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit)
            
            executions = []
            for execution_doc in cursor:
                try:
                    execution = service_execution_from_dict(execution_doc)
                    
                    # 获取Service名称
                    service_doc = self.services_collection.find_one({"service_id": execution.service_id})
                    service_name = service_doc.get('name') if service_doc else None
                    
                    executions.append({
                        "execution_id": execution.execution_id,
                        "service_id": execution.service_id,
                        "service_name": service_name,
                        "user_id": execution.user_id,
                        "input_file_ids": execution.input_file_ids,
                        "output_file_ids": execution.output_file_ids,
                        "project_id": execution.project_id,
                        "status": execution.status.value,
                        "parameters": execution.parameters,
                        "response_data": execution.response_data,
                        "error_message": execution.error_message,
                        "created_at": execution.created_at.isoformat() if execution.created_at else None,
                        "started_at": execution.started_at.isoformat() if execution.started_at else None,
                        "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                        "duration_seconds": execution.duration_seconds
                    })
                except Exception as e:
                    logger.warning(f"解析执行记录失败: {e}")
                    continue
            
            return {
                "executions": executions,
                "total": total
            }
            
        except Exception as e:
            logger.error(f"获取执行记录列表失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"获取执行记录列表失败: {str(e)}"
            )
    
    # ============= 辅助方法 =============
    
    def _service_to_response(self, service_info: ServiceInfo) -> Dict[str, Any]:
        """将ServiceInfo转换为API响应格式"""
        response = {
            "service_id": service_info.service_id,
            "name": service_info.name,
            "description": service_info.description,
            "version": service_info.version,
            "request_config": service_info.request_config.model_dump() if isinstance(service_info.request_config, TaskRequestConfig) else service_info.request_config,
            "parameter_template": service_info.parameter_template.model_dump() if isinstance(service_info.parameter_template, TaskParameterTemplate) else service_info.parameter_template,
            "output_config": service_info.output_config.model_dump() if isinstance(service_info.output_config, ServiceOutputConfig) else (service_info.output_config if service_info.output_config else None),
            "parameter_schema": {k: v.model_dump() if isinstance(v, ParameterDefinition) else v for k, v in (service_info.parameter_schema or {}).items()} if service_info.parameter_schema else None,
            "visibility": service_info.visibility.value,
            "created_at": service_info.created_at.isoformat() if service_info.created_at else None,
            "updated_at": service_info.updated_at.isoformat() if service_info.updated_at else None,
            "created_by": service_info.created_by,
        }
        
        # 添加接受的文件类型配置（始终包含，即使为 None）
        response["accepted_files"] = service_info.accepted_files
        
        return response


# 全局服务实例
_service_service: Optional[ServiceService] = None


def get_service_service() -> ServiceService:
    """获取全局Service服务实例（单例模式）"""
    global _service_service
    if _service_service is None:
        _service_service = ServiceService()
    return _service_service
