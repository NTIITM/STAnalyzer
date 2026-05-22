"""
项目服务
用于管理项目（Project）的创建、更新、删除和配置
整合user_data_manager，提供统一的项目管理API
"""
import os
import uuid
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple, Set
from datetime import datetime
from fastapi import HTTPException, status
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

from textmsa.logging_config import get_logger
from textmsa.services.data.user_data_manager_mongodb import get_user_data_manager

from textmsa.settings import get_mongodb_config

logger = get_logger(__name__)

# 全局单例
_project_service_instance: Optional["ProjectService"] = None


def get_project_service() -> "ProjectService":
    """获取ProjectService单例"""
    global _project_service_instance
    if _project_service_instance is None:
        _project_service_instance = ProjectService()
    return _project_service_instance


class ProjectService:
    """项目服务类"""
    
    def __init__(self):
        """初始化项目服务"""
        self.user_data_manager = get_user_data_manager()
        # 延迟导入以避免循环导入
        from textmsa.services.file.file_service import get_file_service
        self.file_service = get_file_service()
        from textmsa.services.knowledge.knowledge_service import get_knowledge_service
        self.knowledge_service = get_knowledge_service()
        logger.info("ProjectService初始化完成")
    
    # ============= 项目CRUD操作 =============
    
    def create_project(
        self,
        user_id: str,
        name: str,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        创建项目
        
        Args:
            user_id: 用户ID
            name: 项目名称（不能为空）
            description: 项目描述（可选）
        
        Returns:
            项目信息字典（使用蛇形命名）
        
        Raises:
            HTTPException: 如果项目名称为空或创建失败
        """
        try:
            # 开发模式：如果user_id是test_user_id，尝试从数据库获取test_user的实际ID
            from textmsa.services.auth.auth_service import resolve_test_user_id
            user_id = resolve_test_user_id(user_id)
            
            # 验证项目名称不能为空
            if not name or not name.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="项目名称不能为空"
                )
            
            # 生成项目ID（UUID格式）
            project_id = str(uuid.uuid4())
            
            # 创建项目（使用默认配置：all模式）
            # UserDataManagerMongoDB.create_project 会自动设置默认的 all 模式
            project_dict = self.user_data_manager.create_project(
                user_id=user_id,
                project_id=project_id,
                name=name.strip(),
                description=description.strip() if description else None
            )
            
            logger.info(f"项目创建成功: {user_id}/{project_id}")
            
            return project_dict
            
        except HTTPException:
            # 重新抛出 HTTPException，不进行包装
            raise
        except ValueError as e:
            logger.error(f"创建项目失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"创建项目失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"创建项目失败: {str(e)}"
            )
    
    def get_project(self, project_id: str, user_id: str) -> Dict[str, Any]:
        """
        获取项目详情
        
        Args:
            project_id: 项目ID
            user_id: 用户ID（用于权限检查）
        
        Returns:
            项目信息字典（使用蛇形命名）
        
        Raises:
            HTTPException: 项目不存在或无权访问
        """
        try:
            # 开发模式：如果user_id是test_user_id，尝试从数据库获取test_user的实际ID
            from textmsa.services.auth.auth_service import resolve_test_user_id
            user_id = resolve_test_user_id(user_id)
            
            project = self.user_data_manager.get_project(user_id, project_id)
            
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"项目不存在: {project_id}"
                )
            
            return project
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取项目信息失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="获取项目信息失败"
            )
    
    def get_project_detail(self, project_id: str, user_id: str) -> Dict[str, Any]:
        """
        获取项目详细信息（包含关联的文件和执行记录）
        
        Args:
            project_id: 项目ID
            user_id: 用户ID（用于权限检查）
        
        Returns:
            项目详细信息字典，包含：
            - project_id: 项目ID
            - project_name: 项目名称
            - project_description: 项目描述
            - files: 文件列表（包含详细信息）
            - executions: 执行记录列表（包含详细信息）
            - knowledges: 知识列表（暂时为空，待实现）
        
        Raises:
            HTTPException: 项目不存在或无权访问
        """
        try:
            # 开发模式：如果user_id是test_user_id，尝试从数据库获取test_user的实际ID
            from textmsa.services.auth.auth_service import resolve_test_user_id
            user_id = resolve_test_user_id(user_id)
            
            # 获取项目基本信息
            project_dict = self.get_project(project_id=project_id, user_id=user_id)
            
            # 获取文件ID列表和执行ID列表
            file_ids = project_dict.get("file_ids") or []
            execution_ids = project_dict.get("execution_ids") or []
            
            # 1. 获取文件详细信息
            files_list = []
            if file_ids:
                try:
                    sanitized_user_id = self.user_data_manager._sanitize_user_id(user_id)
                    
                    file_docs = list(self.user_data_manager.files_collection.find({
                        "user_id": sanitized_user_id,
                        "file_id": {"$in": list(file_ids)}
                    }))
                    
                    for file_doc in file_docs:
                        file_id = file_doc.get("file_id")
                        if file_id:
                            try:
                                from textmsa.services.data.mongodb_models import file_info_from_dict
                                file_info = file_info_from_dict(file_doc)
                                files_list.append({
                                    "file_id": file_info.file_id,
                                    "filename": file_info.filename,
                                    "file_path": file_info.file_path,
                                    "file_type": file_info.filename.split('.')[-1] if '.' in file_info.filename else "",
                                    "upload_time": file_info.upload_time.isoformat() if file_info.upload_time else None,
                                    "last_viewed_time": file_info.last_viewed_time.isoformat() if file_info.last_viewed_time else None,
                                    "status": file_info.analysis_status.value if hasattr(file_info.analysis_status, 'value') else str(file_info.analysis_status),
                                    "analysis_status": file_info.analysis_status.value if hasattr(file_info.analysis_status, 'value') else str(file_info.analysis_status),
                                    "metadata": file_info.metadata if isinstance(file_info.metadata, dict) else {},
                                    "generated_by": file_info.generated_by,
                                    "created_at": file_info.upload_time.isoformat() if file_info.upload_time else None,
                                    "updated_at": file_info.last_viewed_time.isoformat() if file_info.last_viewed_time else None
                                })
                            except Exception as e:
                                logger.warning(f"解析文件信息失败 {file_doc.get('file_id')}: {e}")
                                continue
                except Exception as e:
                    logger.warning(f"获取文件信息失败: {e}")
            
            # 2. 获取执行记录详细信息
            executions_list = []
            if execution_ids:
                try:
                    # 连接MongoDB获取执行记录
                    mongo_config = get_mongodb_config()
                    mongo_client = MongoClient(
                        mongo_config["uri"],
                        serverSelectionTimeoutMS=mongo_config["server_selection_timeout_ms"],
                        connectTimeoutMS=mongo_config["connect_timeout_ms"],
                        socketTimeoutMS=mongo_config["socket_timeout_ms"],
                        maxPoolSize=mongo_config["max_pool_size"],
                        minPoolSize=mongo_config["min_pool_size"]
                    )
                    db = mongo_client[mongo_config["database"]]
                    service_executions_collection = db.service_executions
                    services_collection = db.services
                    
                    # 批量获取执行记录
                    all_executions = list(service_executions_collection.find({
                        "execution_id": {"$in": execution_ids}
                    }))
                    
                    # 获取相关的服务信息
                    service_ids = list(set(exec_doc.get("service_id") for exec_doc in all_executions if exec_doc.get("service_id")))
                    services_map = {}
                    if service_ids:
                        service_docs = list(services_collection.find({
                            "service_id": {"$in": service_ids}
                        }))
                        for service_doc in service_docs:
                            service_id = service_doc.get("service_id")
                            if service_id:
                                services_map[service_id] = {
                                    "service_id": service_doc.get("service_id"),
                                    "service_name": service_doc.get("service_name"),
                                    "service_description": service_doc.get("service_description")
                                }
                    
                    # 格式化执行记录
                    def format_datetime(dt):
                        """格式化datetime对象为ISO字符串"""
                        if dt is None:
                            return None
                        if isinstance(dt, datetime):
                            return dt.isoformat()
                        if isinstance(dt, str):
                            return dt
                        return str(dt)
                    
                    for exec_doc in all_executions:
                        service_id = exec_doc.get("service_id")
                        service_info = services_map.get(service_id, {})
                        
                        # 兼容单文件格式和多文件格式
                        input_file_ids = exec_doc.get("input_file_ids") or []
                        output_file_ids = exec_doc.get("output_file_ids") or []
                        # 如果input_file_ids为空，尝试使用input_file_id
                        if not input_file_ids:
                            input_file_id = exec_doc.get("input_file_id")
                            if input_file_id:
                                input_file_ids = [input_file_id]
                        # 如果output_file_ids为空，尝试使用output_file_id
                        if not output_file_ids:
                            output_file_id = exec_doc.get("output_file_id")
                            if output_file_id:
                                output_file_ids = [output_file_id]
                        
                        execution_dict = {
                            "execution_id": exec_doc.get("execution_id"),
                            "service_id": service_id,
                            "service_name": service_info.get("service_name"),
                            "service_description": service_info.get("service_description"),
                            "user_id": exec_doc.get("user_id"),
                            "input_file_ids": input_file_ids,
                            "output_file_ids": output_file_ids,
                            "project_id": exec_doc.get("project_id"),
                            "status": exec_doc.get("status"),
                            "parameters": exec_doc.get("parameters", {}),
                            "response_data": exec_doc.get("response_data"),
                            "error_message": exec_doc.get("error_message"),
                            "created_at": format_datetime(exec_doc.get("created_at")),
                            "started_at": format_datetime(exec_doc.get("started_at")),
                            "completed_at": format_datetime(exec_doc.get("completed_at")),
                            "duration_seconds": exec_doc.get("duration_seconds")
                        }
                        executions_list.append(execution_dict)
                    
                    # 关闭MongoDB连接
                    mongo_client.close()
                except ConnectionFailure as e:
                    logger.warning(f"连接MongoDB失败，无法获取执行记录: {e}")
                except Exception as e:
                    logger.warning(f"获取执行记录失败: {e}")
            
            knowledge_list = []
            if project_dict.get("knowledge_ids"):
                knowledge_list = self.knowledge_service.get_knowledges(project_dict.get("knowledge_ids"),user_id)

            # 构建详细的响应数据
            detail_data = {
                "project_id": project_dict["project_id"],
                "project_name": project_dict["name"],
                "project_description": project_dict.get("description"),
                "files": files_list,
                "executions": executions_list,
                "knowledges": knowledge_list
            }
            
            return detail_data
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取项目详细信息失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="获取项目详细信息失败"
            )
    
    def get_project_files_relations(self, project_id: str, user_id: str) -> Dict[str, Any]:
        """
        获取项目下的文件信息及文件关系
        
        Args:
            project_id: 项目ID
            user_id: 用户ID（用于权限检查）
        
        Returns:
            {
                "project_id": str,
                "project_name": str,
                "description": str | None,
                "files": [文件详细信息...],
                "relations": [文件关系...]
            }
        """
        try:
            # 开发模式：如果user_id是test_user_id，尝试从数据库获取test_user的实际ID
            from textmsa.services.auth.auth_service import resolve_test_user_id
            user_id = resolve_test_user_id(user_id)
            
            # 确认项目存在且用户有权限
            project_dict = self.get_project(project_id=project_id, user_id=user_id)
            
            # 1) 获取文件详细信息
            file_ids = project_dict.get("file_ids") or []
            files_list: List[Dict[str, Any]] = []
            if file_ids:
                try:
                    sanitized_user_id = self.user_data_manager._sanitize_user_id(user_id)
                    
                    file_docs = list(self.user_data_manager.files_collection.find({
                        "user_id": sanitized_user_id,
                        "file_id": {"$in": list(file_ids)}
                    }))
                    
                    from textmsa.services.data.mongodb_models import file_info_from_dict
                    for file_doc in file_docs:
                        try:
                            file_info = file_info_from_dict(file_doc)
                            analysis_status = file_info.analysis_status.value if hasattr(file_info.analysis_status, "value") else str(file_info.analysis_status)
                            
                            # 仅保留 analysis_status 为 "completed" 的文件
                            if analysis_status == "completed" or analysis_status == "uploaded":
                                files_list.append({
                                "file_id": file_info.file_id,
                                "filename": file_info.filename,
                                "file_path": file_info.file_path,
                                "file_type_id": file_info.file_type_id,
                                "file_type_name": file_info.file_type_name,
                                "file_type_display_name": file_info.file_type_display_name,
                                "upload_time": file_info.upload_time.isoformat() if hasattr(file_info.upload_time, "isoformat") else file_info.upload_time,
                                "last_viewed_time": file_info.last_viewed_time.isoformat() if hasattr(file_info.last_viewed_time, "isoformat") else file_info.last_viewed_time,
                                "analysis_status": analysis_status,
                                "description": file_info.description,
                                "metadata": file_info.metadata if isinstance(file_info.metadata, dict) else {},
                                "generated_by": file_info.generated_by,
                            })
                        except Exception as e:
                            logger.warning(f"解析文件信息失败 {file_doc.get('file_id')}: {e}")
                except Exception as e:
                    logger.warning(f"获取项目文件信息失败: {e}")
            
            # 2) 获取文件关系
            relations: List[Dict[str, Any]] = []
            try:
                relations = self.user_data_manager.get_file_relations(project_id=project_id) or []
            except Exception as e:
                logger.warning(f"获取项目文件关系失败: {e}")
            
            # 统一序列化关系中的时间字段，避免 JSONResponse 失败
            for relation in relations:
                created_at = relation.get("created_at")
                if isinstance(created_at, datetime):
                    relation["created_at"] = created_at.isoformat()
            
            return {
                "project_id": project_id,
                "project_name": project_dict.get("name"),
                "description": project_dict.get("description"),
                "files": files_list,
                "relations": relations,
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取项目文件与关系失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="获取项目文件与关系失败"
            )
    
    def list_projects(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取用户的项目列表（分页）
        
        Args:
            user_id: 用户ID
            skip: 跳过数量（默认0）
            limit: 返回数量限制（默认100，最大1000）
        
        Returns:
            项目列表（使用蛇形命名）
        """
        try:
            # 开发模式：如果user_id是test_user_id，尝试从数据库获取test_user的实际ID
            from textmsa.services.auth.auth_service import resolve_test_user_id
            user_id = resolve_test_user_id(user_id)
            
            # 限制最大返回数量为1000
            limit = min(limit, 1000)
            skip = max(0, skip)
            
            projects = self.user_data_manager.list_projects(
                user_id=user_id,
                skip=skip,
                limit=limit
            )
            
            return projects
            
        except Exception as e:
            logger.error(f"获取项目列表失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="获取项目列表失败"
            )
    
    def update_project(
        self,
        project_id: str,
        user_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        更新项目信息
        
        Args:
            project_id: 项目ID
            user_id: 用户ID
            name: 新的项目名称（可选）
            description: 新的项目描述（可选）
        
        Returns:
            更新后的项目信息字典（使用蛇形命名）
        
        Raises:
            HTTPException: 项目不存在或无权访问
        """
        try:
            # 开发模式：如果user_id是test_user_id，尝试从数据库获取test_user的实际ID
            from textmsa.services.auth.auth_service import resolve_test_user_id
            user_id = resolve_test_user_id(user_id)
            
            # 检查项目是否存在
            project = self.user_data_manager.get_project(user_id, project_id)
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"项目不存在: {project_id}"
                )
            
            # 更新项目
            updated_project = self.user_data_manager.update_project(
                user_id=user_id,
                project_id=project_id,
                name=name,
                description=description
            )
            
            if not updated_project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"项目不存在: {project_id}"
                )
            
            logger.info(f"项目更新成功: {user_id}/{project_id}")
            return updated_project
            
        except HTTPException:
            raise
        except ValueError as e:
            logger.error(f"更新项目失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"更新项目失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="更新项目失败"
            )
    
    def delete_project(self, project_id: str, user_id: str) -> bool:
        """
        删除项目
        
        Args:
            project_id: 项目ID
            user_id: 用户ID
        
        Returns:
            是否删除成功
        
        Raises:
            HTTPException: 项目不存在或无权访问
        """
        try:
            # 开发模式：如果user_id是test_user_id，尝试从数据库获取test_user的实际ID
            from textmsa.services.auth.auth_service import resolve_test_user_id
            user_id = resolve_test_user_id(user_id)
            
            # 检查项目是否存在
            project = self.user_data_manager.get_project(user_id, project_id)
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"项目不存在: {project_id}"
                )
            
            # 删除项目
            success = self.user_data_manager.delete_project(user_id, project_id)
            
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"项目不存在: {project_id}"
                )
            
            logger.info(f"项目删除成功: {user_id}/{project_id}")
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"删除项目失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="删除项目失败"
            )
    
    def get_project_work_dir_path(self, project_id: str) -> str:
        """
        获取项目的工作目录路径（output文件夹）
        
        Args:
            project_id: 项目ID
        
        Returns:
            工作目录路径（字符串格式）
        """
        base_dir = Path(os.getcwd())
        work_dir_name = f"tmp{project_id}"
        work_dir_path = str(base_dir / work_dir_name)
        return work_dir_path
    
    # ============= 项目文件管理 =============
    
    def add_file_to_project(self, project_id: str, file_id: str, user_id: str) -> Dict[str, Any]:
        """
        向项目添加文件
        
        Args:
            project_id: 项目ID
            file_id: 文件ID
            user_id: 用户ID
        
        Returns:
            更新后的项目信息字典（使用蛇形命名）
        
        Raises:
            HTTPException: 项目不存在、文件不存在、无权访问或文件不属于用户
        """
        try:
            # 开发模式：如果user_id是test_user_id，尝试从数据库获取test_user的实际ID
            from textmsa.services.auth.auth_service import resolve_test_user_id
            user_id = resolve_test_user_id(user_id)
            
            # 验证项目所有权
            project = self.user_data_manager.get_project(user_id, project_id)
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"项目不存在: {project_id}"
                )
            
            # 验证文件所有权
            try:
                file_info = self.file_service.get_file_info(file_id, user_id)
            except HTTPException as e:
                if e.status_code == status.HTTP_404_NOT_FOUND:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"文件不存在: {file_id}"
                    )
                raise
            
            # 添加文件到项目
            updated_project = self.user_data_manager.add_file_to_project(
                user_id=user_id,
                project_id=project_id,
                file_id=file_id
            )
            
            if not updated_project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"项目不存在: {project_id}"
                )
            
            logger.info(f"文件已添加到项目: {user_id}/{project_id}/{file_id}")
            return updated_project
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"添加文件到项目失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="添加文件到项目失败"
            )
    
    def remove_file_from_project(self, project_id: str, file_id: str, user_id: str) -> Dict[str, Any]:
        """
        从项目移除文件
        
        Args:
            project_id: 项目ID
            file_id: 文件ID
            user_id: 用户ID
        
        Returns:
            更新后的项目信息字典（使用蛇形命名）
        
        Raises:
            HTTPException: 项目不存在或无权访问
        """
        try:
            # 开发模式：如果user_id是test_user_id，尝试从数据库获取test_user的实际ID
            from textmsa.services.auth.auth_service import resolve_test_user_id
            user_id = resolve_test_user_id(user_id)
            
            # 验证项目所有权
            project = self.user_data_manager.get_project(user_id, project_id)
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"项目不存在: {project_id}"
                )
            
            # 从项目中移除文件
            updated_project = self.user_data_manager.remove_file_from_project(
                user_id=user_id,
                project_id=project_id,
                file_id=file_id
            )
            
            if not updated_project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"项目不存在: {project_id}"
                )
            
            logger.info(f"文件已从项目中移除: {user_id}/{project_id}/{file_id}")
            return updated_project
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"从项目中移除文件失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="从项目中移除文件失败"
            )
    
    def get_project_files(self, project_id: str, user_id: str) -> List[str]:
        """
        获取项目的文件列表
        
        Args:
            project_id: 项目ID
            user_id: 用户ID
        
        Returns:
            文件ID列表
        
        Raises:
            HTTPException: 项目不存在或无权访问
        """
        try:
            # 开发模式：如果user_id是test_user_id，尝试从数据库获取test_user的实际ID
            from textmsa.services.auth.auth_service import resolve_test_user_id
            user_id = resolve_test_user_id(user_id)
            
            # 验证项目所有权
            project = self.user_data_manager.get_project(user_id, project_id)
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"项目不存在: {project_id}"
                )
            
            # 获取项目文件列表
            file_ids = self.user_data_manager.get_project_files(user_id, project_id)
            
            return file_ids
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取项目文件列表失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="获取项目文件列表失败"
            )
    
    # ============= 项目配置管理 =============
    
    def update_knowledge_config(
        self,
        project_id: str,
        user_id: str,
        mode: str,
        whitelist: Optional[List[str]] = None,
        blacklist: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        更新项目知识配置
        
        Args:
            project_id: 项目ID
            user_id: 用户ID
            mode: 配置模式（all/whitelist/blacklist）
            whitelist: 知识ID白名单（mode=whitelist时生效）
            blacklist: 知识ID黑名单（mode=blacklist时生效）
        
        Returns:
            更新后的项目信息字典（使用蛇形命名）
        
        Raises:
            HTTPException: 项目不存在、无权访问或配置模式无效
        """
        try:
            # 开发模式：如果user_id是test_user_id，尝试从数据库获取test_user的实际ID
            from textmsa.services.auth.auth_service import resolve_test_user_id
            user_id = resolve_test_user_id(user_id)
            
            # 验证项目所有权
            project = self.user_data_manager.get_project(user_id, project_id)
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"项目不存在: {project_id}"
                )
            
            # 更新知识配置
            updated_project = self.user_data_manager.update_project_knowledge_config(
                user_id=user_id,
                project_id=project_id,
                mode=mode,
                whitelist=whitelist,
                blacklist=blacklist
            )
            
            if not updated_project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"项目不存在: {project_id}"
                )
            
            logger.info(f"项目知识配置已更新: {user_id}/{project_id}")
            return updated_project
            
        except HTTPException:
            raise
        except ValueError as e:
            logger.error(f"更新项目知识配置失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"更新项目知识配置失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="更新项目知识配置失败"
            )
    
    def update_service_config(
        self,
        project_id: str,
        user_id: str,
        mode: str,
        whitelist: Optional[List[str]] = None,
        blacklist: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        更新项目服务配置
        
        Args:
            project_id: 项目ID
            user_id: 用户ID
            mode: 配置模式（all/whitelist/blacklist）
            whitelist: 服务ID白名单（mode=whitelist时生效）
            blacklist: 服务ID黑名单（mode=blacklist时生效）
        
        Returns:
            更新后的项目信息字典（使用蛇形命名）
        
        Raises:
            HTTPException: 项目不存在、无权访问或配置模式无效
        """
        try:
            # 开发模式：如果user_id是test_user_id，尝试从数据库获取test_user的实际ID
            from textmsa.services.auth.auth_service import resolve_test_user_id
            user_id = resolve_test_user_id(user_id)
            
            # 验证项目所有权
            project = self.user_data_manager.get_project(user_id, project_id)
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"项目不存在: {project_id}"
                )
            
            # 更新服务配置
            updated_project = self.user_data_manager.update_project_service_config(
                user_id=user_id,
                project_id=project_id,
                mode=mode,
                whitelist=whitelist,
                blacklist=blacklist
            )
            
            if not updated_project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"项目不存在: {project_id}"
                )
            
            logger.info(f"项目服务配置已更新: {user_id}/{project_id}")
            return updated_project
            
        except HTTPException:
            raise
        except ValueError as e:
            logger.error(f"更新项目服务配置失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"更新项目服务配置失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="更新项目服务配置失败"
            )

    # ============= 项目内 Service 与 FileType 关系图 =============

    def get_service_file_type_graph(
        self,
        project_id: Optional[str],
        user_id: str,
        file_type_id: Optional[str] = None,
        depth: Optional[int] = None,
        root_file_type_list: Optional[List[str]] = ["spatial_rna_seq_data", "single_cell_rna_seq_data"],
    ) -> Dict[str, Any]:
        """
        构建 Service 与 FileType 的关系有向图，并可按起始文件类型与深度裁剪。

        图中包含两类节点：
        - type = "service": 服务节点
        - type = "file_type": 文件类型节点

        以树结构返回 Service 与 FileType 的关系。

        - 如果提供 project_id，则只返回该项目内的服务；若不提供，则返回所有可见服务。
        - 如果提供 file_type_id，则以该文件类型为根节点，按 depth 沿有向边方向做 BFS，
          并将访问到的节点组织成树（children）。
        - 如果不提供 file_type_id，则以所有 file_type 节点作为根节点，
          并从每个文件类型沿有向边方向继续展开。

        返回示例（data）：
        {
            "roots": [
                {
                    "node_type": "file_type" | "service",
                    "id": "...",
                    "name": "...",
                    "display_name": "...",
                    "category": "...",
                    "description": "...",
                    "children": [ ... 同结构 ... ]
                }
            ]
        }
        """
        # 统一处理测试用户ID
        from textmsa.services.auth.auth_service import resolve_test_user_id
        from textmsa.services.service.service_service import get_service_service
        from textmsa.services.file.file_type_service import get_file_type_service
        from collections import deque

        user_id = resolve_test_user_id(user_id)

        # 1. 如果提供了 project_id，获取项目并校验权限
        if project_id:
            project = self.user_data_manager.get_project(user_id, project_id)
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"项目不存在: {project_id}",
                )

        # 2. 获取服务服务和文件类型服务
        service_service = get_service_service()
        file_type_service = get_file_type_service()

        # 3. 确定起始文件类型列表
        start_file_type_ids: List[str] = []
        if file_type_id:
            start_file_type_ids = [file_type_id]
        elif root_file_type_list:
            start_file_type_ids = root_file_type_list
        else:
            return {"roots": []}

        # 4. 定义节点键类型和数据结构
        NodeKey = Tuple[str, str]  # (type, id)
        nodes: Dict[NodeKey, Dict[str, Any]] = {}
        children_map: Dict[NodeKey, List[NodeKey]] = {}
        visited_nodes: Set[NodeKey] = set()

        # 5. 辅助函数：添加节点
        def add_node(node_type: str, node_id: str, payload: Dict[str, Any]) -> NodeKey:
            key: NodeKey = (node_type, node_id)
            if key not in nodes:
                if node_type == "service":
                    nodes[key] = {
                        "service_id": node_id,
                        "node_type": node_type,
                        "name": payload.get("name"),
                        # "description": payload.get("description"),
                    }
                else:
                    nodes[key] = {
                        "file_type_id": node_id,
                        "node_type": node_type,
                        "name": payload.get("display_name"),
                        "display_name": payload.get("display_name"),
                        "category": payload.get("category"),
                    }
                children_map[key] = []
            return key

        # 6. 辅助函数：获取文件类型信息（如果不存在返回 None）
        # 注意：resolve_type 在文件类型不存在时会抛出 HTTPException
        # 为保持代码可用，在辅助函数中处理异常，主要逻辑不需要 try-catch
        def get_file_type_info(ft_id: str) -> Optional[Dict[str, Any]]:
            try:
                ft_resolved = file_type_service.resolve_type(
                    file_type_id=ft_id, user_id=user_id
                )
                return {
                    "file_type_id": ft_id,
                    "name": ft_resolved.get("name"),
                    "display_name": ft_resolved.get("display_name"),
                    "category": ft_resolved.get("category"),
                }
            except HTTPException as e:
                if e.status_code == status.HTTP_404_NOT_FOUND:
                    logger.warning(f"文件类型不存在，跳过: {ft_id}")
                    return None
                # 其他HTTP异常继续抛出
                raise
            except Exception as e:
                logger.warning(f"获取文件类型信息失败，跳过: {ft_id}, 错误: {e}")
                return None

        # 7. 辅助函数：查找接受指定文件类型的服务
        def find_services_accepting_file_type(ft_id: str) -> List[Dict[str, Any]]:
            all_services = service_service.list_services(
                user_id=user_id, project_id=project_id
            ).get("services", [])
            matching_services = []
            for service_info in all_services:
                accepted_files = service_info.get("accepted_files") or {}
                for file_config in accepted_files.values():
                    if not isinstance(file_config, dict):
                        continue
                    ft_ids = file_config.get("file_type_ids") or []
                    if isinstance(ft_ids, list) and ft_id in ft_ids:
                        matching_services.append(service_info)
                        break
            return matching_services

        # 8. 辅助函数：获取服务产生的文件类型
        def get_service_output_file_types(service_info: Dict[str, Any]) -> List[str]:
            output_file_types = []
            output_config = service_info.get("output_config") or {}
            items = output_config.get("items") if isinstance(output_config, dict) else None
            if items:
                for item in items:
                    if isinstance(item, dict):
                        ft_id = item.get("file_type_id")
                        if isinstance(ft_id, str) and ft_id.strip():
                            output_file_types.append(ft_id.strip())
            return output_file_types

        # 9. BFS 遍历，逐步扩充节点
        max_depth = depth if depth is not None and depth >= 0 else None
        queue: deque[Tuple[NodeKey, int, Tuple[NodeKey, ...]]] = deque()
        root_keys: List[NodeKey] = []

        # 初始化：添加起始文件类型节点
        for ft_id in start_file_type_ids:
            if not isinstance(ft_id, str) or not ft_id.strip():
                continue
            ft_id = ft_id.strip()
            ft_info = get_file_type_info(ft_id)
            if not ft_info:
                # 文件类型不存在已在 get_file_type_info 中记录日志，这里直接跳过
                continue
            ft_key = add_node("file_type", ft_id, ft_info)
            root_keys.append(ft_key)
            queue.append((ft_key, 0, (ft_key,)))

        # BFS 遍历
        while queue:
            current_key, current_depth, path = queue.popleft()
            
            # 检查深度限制
            if max_depth is not None and current_depth >= max_depth:
                continue

            # 如果当前节点是文件类型，查找接受它的服务
            if current_key[0] == "file_type":
                ft_id = current_key[1]
                services = find_services_accepting_file_type(ft_id)
                for service_info in services:
                    sid = service_info.get("service_id")
                    if not sid:
                        continue
                    service_key = add_node(
                        "service",
                        sid,
                        {
                            "name": service_info.get("name"),
                            "description": service_info.get("description"),
                        },
                    )
                    
                    # 检查是否形成环
                    if service_key in path:
                        logger.warning(
                            f"检测到环：文件类型 '{ft_id}' -> 服务 '{sid}' 形成循环引用，跳过该服务节点",
                            extra={
                                "file_type_id": ft_id,
                                "service_id": sid,
                                "path": [str(k) for k in path],
                            },
                        )
                        continue
                    
                    # 添加边：file_type -> service
                    if current_key not in children_map:
                        children_map[current_key] = []
                    if service_key not in children_map[current_key]:
                        children_map[current_key].append(service_key)
                    
                    # 如果服务节点未被访问，继续遍历
                    if service_key not in visited_nodes:
                        visited_nodes.add(service_key)
                        queue.append((service_key, current_depth + 1, path + (service_key,)))

            # 如果当前节点是服务，查找它产生的文件类型
            elif current_key[0] == "service":
                sid = current_key[1]
                # 获取服务信息
                all_services = service_service.list_services(
                    user_id=user_id, project_id=project_id
                ).get("services", [])
                service_info = None
                for svc in all_services:
                    if svc.get("service_id") == sid:
                        service_info = svc
                        break
                
                if not service_info:
                    continue
                
                output_ft_ids = get_service_output_file_types(service_info)
                for ft_id in output_ft_ids:
                    ft_info = get_file_type_info(ft_id)
                    if not ft_info:
                        logger.warning(f"服务 '{sid}' 输出的文件类型不存在，跳过: {ft_id}")
                        continue
                    ft_key = add_node("file_type", ft_id, ft_info)
                    
                    # 检查是否形成环
                    if ft_key in path:
                        logger.warning(
                            f"检测到环：服务 '{sid}' -> 文件类型 '{ft_id}' 形成循环引用，跳过该文件类型节点",
                            extra={
                                "service_id": sid,
                                "file_type_id": ft_id,
                                "path": [str(k) for k in path],
                            },
                        )
                        continue
                    
                    # 添加边：service -> file_type
                    if current_key not in children_map:
                        children_map[current_key] = []
                    if ft_key not in children_map[current_key]:
                        children_map[current_key].append(ft_key)
                    
                    # 如果文件类型节点未被访问，继续遍历
                    if ft_key not in visited_nodes:
                        visited_nodes.add(ft_key)
                        queue.append((ft_key, current_depth + 1, path + (ft_key,)))

        # 10. 如果没有节点，返回空树
        if not nodes:
            return {"roots": []}

        # 11. 递归构建树节点（处理环的情况）
        def build_tree_node(key: NodeKey, visited: Tuple[NodeKey, ...]) -> Dict[str, Any]:
            # 防止循环引用
            if key in visited:
                node_data = nodes[key].copy()
                node_data["children"] = []
                return node_data

            node_data = nodes[key].copy()
            new_visited = visited + (key,)
            node_children: List[Dict[str, Any]] = []
            for child_key in children_map.get(key, []):
                # 再次检查环（在构建树时）
                if child_key in new_visited:
                    logger.warning(
                        f"构建树时检测到环，跳过子节点: {child_key}",
                        extra={
                            "parent": str(key),
                            "child": str(child_key),
                            "path": [str(k) for k in new_visited],
                        },
                    )
                    continue
                node_children.append(build_tree_node(child_key, new_visited))
            node_data["children"] = node_children
            return node_data

        # 12. 构建根节点
        roots: List[Dict[str, Any]] = []
        seen_root_ids: Set[NodeKey] = set()
        for rk in root_keys:
            if rk not in nodes:
                continue
            if rk in seen_root_ids:
                continue
            roots.append(build_tree_node(rk, ()))
            seen_root_ids.add(rk)

        return {"roots": roots}
