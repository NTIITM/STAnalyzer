"""
分析流程服务
管理文件分析流程的树形结构
使用MongoDB构建分析树，不再依赖Neo4j
"""
from typing import Optional, Dict, Any
from datetime import datetime
from fastapi import HTTPException
from fastapi import status as http_status
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

from textmsa.logging_config import get_logger
from textmsa.services.data.user_data_manager_mongodb import get_user_data_manager
from textmsa.services.analysis.models import FileStatus, AlgorithmStatus
from textmsa.settings import get_mongodb_config

logger = get_logger(__name__)


class AnalysisService:
    """分析流程服务类"""
    
    def __init__(self):
        """初始化分析服务"""
        self.user_data_manager = get_user_data_manager()
        
        # 直接连接MongoDB（用于查询service_executions）
        mongo_config = get_mongodb_config()
        try:
            self.mongo_client = MongoClient(
                mongo_config["uri"],
                serverSelectionTimeoutMS=mongo_config["server_selection_timeout_ms"],
                connectTimeoutMS=mongo_config["connect_timeout_ms"],
                socketTimeoutMS=mongo_config["socket_timeout_ms"],
                maxPoolSize=mongo_config["max_pool_size"],
                minPoolSize=mongo_config["min_pool_size"]
            )
            self.mongo_client.admin.command('ping')
            self.db = self.mongo_client[mongo_config["database"]]
            self.service_executions_collection = self.db.service_executions
            self.services_collection = self.db.services
            logger.info("AnalysisService: 成功连接到MongoDB")
        except ConnectionFailure as e:
            logger.error(f"AnalysisService: 无法连接到MongoDB: {e}")
            raise
    
    def get_project_analysis_tree(self, project_id: str, user_id: str) -> Dict[str, Any]:
        """
        获取项目的合并分析流程树形结构
        
        该方法会：
        1. 批量获取项目中的所有文件信息
        2. 批量获取项目相关的所有执行记录
        3. 批量获取所有相关的服务信息
        4. 构建简化的树形结构（只包含id、type、children）
        5. 提供扁平化的files和executions列表
        
        Args:
            project_id: 项目ID
            user_id: 用户ID
        
        Returns:
            项目分析流程树形结构（简化版本）
        """
        try:
            # 开发模式：如果user_id是test_user_id，尝试从数据库获取test_user的实际ID
            from textmsa.services.auth.auth_service import resolve_test_user_id
            user_id = resolve_test_user_id(user_id)
            
            # 获取项目信息（延迟导入以避免循环导入）
            from textmsa.services.project.project_service import get_project_service
            project_service = get_project_service()
            project_dict = project_service.get_project(project_id, user_id)
            
            if not project_dict:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail="项目不存在"
                )
            
            # 获取项目文件列表和执行ID列表（project 为 dict）
            file_ids = project_dict.get("file_ids") or []
            execution_ids = project_dict.get("execution_ids") or []
            
            if not file_ids and not execution_ids:
                # 如果项目没有文件和执行记录，返回空的分析树
                # 兼容 created_at/updated_at 可能为 datetime 或 str
                _created = project_dict.get("created_at")
                _updated = project_dict.get("updated_at")
                created_at_str = _created.isoformat() if hasattr(_created, "isoformat") else _created
                updated_at_str = _updated.isoformat() if hasattr(_updated, "isoformat") else _updated
                
                return {
                    "project_id": project_id,
                    "project_name": project_dict.get("name"),
                    "project_description": project_dict.get("description"),
                    "file_id": None,
                    "root": {
                        "id": project_id,
                        "type": "project",
                        "children": []
                    },
                    "files": [],
                    "executions": [],
                    "statistics": {
                        "total_files": 0,
                        "total_executions": 0,
                        "completed_files": 0,
                        "completed_executions": 0,
                        "failed_executions": 0,
                        "running_executions": 0
                    },
                    "created_at": created_at_str,
                    "updated_at": updated_at_str,
                    "status": "completed",
                    "progress": 100,
                    "total_nodes": 0,
                    "completed_nodes": 0
                }
            
            # 1. 批量获取项目相关的执行记录（优先使用execution_ids）
            all_executions = []
            if execution_ids:
                # 使用项目的execution_ids直接查询执行记录
                all_executions = list(self.service_executions_collection.find({
                    "execution_id": {"$in": execution_ids}
                }))
                logger.debug(f"从项目execution_ids获取到 {len(all_executions)} 条执行记录")
            else:
                # 如果没有execution_ids，回退到通过file_ids查询（向后兼容）
                logger.debug("项目没有execution_ids，使用file_ids查询执行记录（向后兼容）")
                visited_files = set(file_ids)
                queue = list(file_ids)
                
                while queue:
                    current_file_id = queue.pop(0)
                    
                    # 查找以当前文件为输入的执行
                    input_executions = list(self.service_executions_collection.find({
                        "input_file_id": current_file_id
                    }))
                    
                    for exec_doc in input_executions:
                        all_executions.append(exec_doc)
                        output_file_id = exec_doc.get("output_file_id")
                        if output_file_id and output_file_id not in visited_files:
                            visited_files.add(output_file_id)
                            queue.append(output_file_id)
                    
                    # 查找以当前文件为输出的执行（找到父文件）
                    output_executions = list(self.service_executions_collection.find({
                        "output_file_id": current_file_id
                    }))
                    
                    for exec_doc in output_executions:
                        all_executions.append(exec_doc)
                        input_file_id = exec_doc.get("input_file_id")
                        if input_file_id and input_file_id not in visited_files:
                            visited_files.add(input_file_id)
                            queue.append(input_file_id)
            
            # 2. 从执行记录中收集所有相关的文件ID
            all_file_ids = set(file_ids)  # 包含项目直接关联的文件
            for exec_doc in all_executions:
                # 收集输入文件ID
                input_file_id = exec_doc.get("input_file_id")
                if input_file_id:
                    all_file_ids.add(input_file_id)
                # 收集输出文件ID
                output_file_id = exec_doc.get("output_file_id")
                if output_file_id:
                    all_file_ids.add(output_file_id)
                # 也支持input_file_ids列表格式
                input_file_ids = exec_doc.get("input_file_ids", [])
                if input_file_ids:
                    all_file_ids.update(input_file_ids)
                # 也支持output_file_ids列表格式
                output_file_ids = exec_doc.get("output_file_ids", [])
                if output_file_ids:
                    all_file_ids.update(output_file_ids)
            
            # 3. 批量获取所有文件信息
            files_map = {}  # {file_id: file_info_dict}
            sanitized_user_id = self.user_data_manager._sanitize_user_id(user_id)
            
            if all_file_ids:
                file_docs = list(self.user_data_manager.files_collection.find({
                    "user_id": sanitized_user_id,
                    "file_id": {"$in": list(all_file_ids)}
                }))
            
                for file_doc in file_docs:
                    file_id = file_doc.get("file_id")
                    if file_id:
                        try:
                            from textmsa.services.data.mongodb_models import file_info_from_dict
                            file_info = file_info_from_dict(file_doc)
                            files_map[file_id] = {
                                "file_id": file_info.file_id,
                                "filename": file_info.filename,
                                "file_path": file_info.file_path,
                                "file_type_id": file_info.file_type_id,
                                "file_type_name": file_info.file_type_name,
                                "file_type_display_name": file_info.file_type_display_name,
                                "upload_time": file_info.upload_time.isoformat() if file_info.upload_time else None,
                                "last_viewed_time": file_info.last_viewed_time.isoformat() if file_info.last_viewed_time else None,
                                "status": file_info.analysis_status.value if hasattr(file_info.analysis_status, 'value') else str(file_info.analysis_status),
                                "analysis_status": file_info.analysis_status.value if hasattr(file_info.analysis_status, 'value') else str(file_info.analysis_status),
                                "metadata": file_info.metadata if isinstance(file_info.metadata, dict) else {},
                                "generated_by": file_info.generated_by,
                                "created_at": file_info.upload_time.isoformat() if file_info.upload_time else None,
                                "updated_at": file_info.last_viewed_time.isoformat() if file_info.last_viewed_time else None
                            }
                        except Exception as e:
                            logger.warning(f"解析文件信息失败 {file_doc.get('file_id')}: {e}")
                            continue
            
            # 3. 批量获取所有相关的服务信息
            service_ids = list(set(exec_doc.get("service_id") for exec_doc in all_executions if exec_doc.get("service_id")))
            services_map = {}  # {service_id: service_info_dict}
            
            if service_ids:
                service_docs = list(self.services_collection.find({
                    "service_id": {"$in": service_ids}
                }))
                
                for service_doc in service_docs:
                    service_id = service_doc.get("service_id")
                    if service_id:
                        services_map[service_id] = {
                            "service_id": service_doc.get("service_id"),
                            "service_name": service_doc.get("name"),  # 修复：使用 "name" 而不是 "service_name"
                            "service_description": service_doc.get("description")  # 修复：使用 "description" 而不是 "service_description"
                        }
            
            # 4. 构建文件关系映射（parent -> [(child, execution_id)]）
            file_relations = {}  
            output_files = set()  # 所有作为输出文件的ID
            
            for exec_doc in all_executions:
                execution_id = exec_doc.get("execution_id")
                if not execution_id:
                    continue
                
                # 支持单文件格式（input_file_id/output_file_id）
                input_file_id = exec_doc.get("input_file_id")
                output_file_id = exec_doc.get("output_file_id")
                
                # 支持多文件格式（input_file_ids/output_file_ids）
                input_file_ids = exec_doc.get("input_file_ids", [])
                output_file_ids = exec_doc.get("output_file_ids", [])
                
                # 合并单文件和列表格式
                if input_file_id and input_file_id not in input_file_ids:
                    input_file_ids.append(input_file_id)
                if output_file_id and output_file_id not in output_file_ids:
                    output_file_ids.append(output_file_id)
                
                # 构建文件关系（每个输入文件对应每个输出文件）
                for in_fid in input_file_ids:
                    if not in_fid:
                        continue
                    for out_fid in output_file_ids:
                        if not out_fid:
                            continue
                        if in_fid not in file_relations:
                            file_relations[in_fid] = []
                        file_relations[in_fid].append((out_fid, execution_id))
                        output_files.add(out_fid)
            
            # 5. 识别根文件（项目中的原始文件，不在任何执行的output_file_id中）
            root_file_ids = [fid for fid in file_ids if fid not in output_files and fid in files_map]
            
            # 6. 递归构建文件树节点
            def build_file_node(file_id: str) -> Dict[str, Any]:
                """构建文件树节点（简化结构）"""
                node = {
                    "id": file_id,
                    "type": "file",
                    "children": []
                }
                
                # 添加子节点
                if file_id in file_relations:
                    for child_file_id, execution_id in file_relations[file_id]:
                        if child_file_id in files_map:
                            child_node = build_file_node(child_file_id)
                            node["children"].append(child_node)
                
                return node
            
            # 7. 构建项目根节点的子节点
            project_children = []
            for root_file_id in root_file_ids:
                file_node = build_file_node(root_file_id)
                project_children.append(file_node)
            
            # 8. 构建简化的树结构
            root = {
                "id": project_id,
                "type": "project",
                "children": project_children
            }
            
            # 9. 构建files列表（扁平化，包含完整信息）
            files_list = list(files_map.values())
            
            # 10. 构建executions列表（扁平化，包含完整信息）
            def format_datetime(dt):
                """格式化datetime对象为ISO字符串"""
                if dt is None:
                    return None
                if isinstance(dt, datetime):
                    return dt.isoformat()
                if isinstance(dt, str):
                    return dt
                return str(dt)
            
            executions_list = []
            for exec_doc in all_executions:
                service_id = exec_doc.get("service_id")
                service_info = services_map.get(service_id, {})
                
                # 优先从 execution_doc 中获取 service_name（如果已保存）
                service_name = exec_doc.get("service_name") or service_info.get("service_name")
                
                execution_dict = {
                    "execution_id": exec_doc.get("execution_id"),
                    "service_id": service_id,
                    "service_name": service_name,  # 修复：优先使用 execution_doc 中的 service_name
                    "service_description": service_info.get("service_description"),
                    "user_id": exec_doc.get("user_id"),
                    "input_file_ids": exec_doc.get("input_file_ids"),
                    "output_file_ids": exec_doc.get("output_file_ids"),
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
            
            # 11. 计算统计信息
            total_files = len(files_list)
            total_executions = len(executions_list)
            completed_files = sum(1 for f in files_list if f.get("status") in ["completed", "COMPLETED"])
            completed_executions = sum(1 for e in executions_list if e.get("status") in ["completed", "COMPLETED"])
            failed_executions = sum(1 for e in executions_list if e.get("status") in ["failed", "FAILED"])
            running_executions = sum(1 for e in executions_list if e.get("status") in ["running", "RUNNING", "pending", "PENDING"])
            
            # 12. 计算项目状态和进度
            project_status = "completed"
            if running_executions > 0:
                project_status = "running"
            elif failed_executions > 0:
                project_status = "failed"
            
            total_nodes = total_files
            completed_nodes = completed_files
            
            # 13. 计算时间信息
            earliest_created_at = None
            latest_updated_at = None
            
            for file_info in files_list:
                if file_info.get("created_at"):
                    if not earliest_created_at or file_info["created_at"] < earliest_created_at:
                        earliest_created_at = file_info["created_at"]
                if file_info.get("updated_at"):
                    if not latest_updated_at or file_info["updated_at"] > latest_updated_at:
                        latest_updated_at = file_info["updated_at"]
            
            # 14. 构建最终响应
            # 兼容 created_at/updated_at 可能为 datetime 或 str
            _created = project_dict.get("created_at")
            _updated = project_dict.get("updated_at")
            created_at_str = _created.isoformat() if hasattr(_created, "isoformat") else _created
            updated_at_str = _updated.isoformat() if hasattr(_updated, "isoformat") else _updated
            
            project_tree = {
                "project_id": project_id,
                "project_name": project_dict.get("name"),
                "project_description": project_dict.get("description"),
                "file_id": None,
                "root": root,
                "files": files_list,
                "executions": executions_list,
                "statistics": {
                    "total_files": total_files,
                    "total_executions": total_executions,
                    "completed_files": completed_files,
                    "completed_executions": completed_executions,
                    "failed_executions": failed_executions,
                    "running_executions": running_executions
                },
                "created_at": earliest_created_at or created_at_str,
                "updated_at": latest_updated_at or updated_at_str,
                "status": project_status,
                "total_nodes": total_nodes,
                "completed_nodes": completed_nodes
            }
            
            return project_tree
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取项目分析树失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"获取项目分析树失败: {str(e)}"
            )

    def get_execution_by_id(self, execution_id: str, user_id: str) -> Dict[str, Any]:
        """
        通过executionId获取执行记录详情（不需要fileId）
        
        Args:
            execution_id: 执行ID（对应algorithm_id）
            user_id: 用户ID
        
        Returns:
            执行记录详情
        """
        try:
            # 开发模式：如果user_id是test_user_id，尝试从数据库获取test_user的实际ID
            from textmsa.services.auth.auth_service import resolve_test_user_id
            user_id = resolve_test_user_id(user_id)
            
            # 从MongoDB获取执行记录
            execution_doc = self.service_executions_collection.find_one({
                "execution_id": execution_id
            })
            
            if not execution_doc:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail="执行记录不存在"
                )
            
            # 获取Service信息（优先从 execution_doc 中获取，如果没有再查询 services_collection）
            service_id = execution_doc.get("service_id", "")
            service_name = execution_doc.get("service_name")  # 优先从 execution_doc 获取
            if not service_name and service_id:
                # 如果 execution_doc 中没有 service_name，则查询 services_collection
                service_doc = self.services_collection.find_one({"service_id": service_id})
                if service_doc:
                    service_name = service_doc.get("name", "")
            
            # 转换执行状态
            exec_status = execution_doc.get("status", "completed")
            if exec_status == "completed":
                algo_status = AlgorithmStatus.COMPLETED
            elif exec_status == "running":
                algo_status = AlgorithmStatus.RUNNING
            elif exec_status == "failed":
                algo_status = AlgorithmStatus.FAILED
            elif exec_status == "pending":
                algo_status = AlgorithmStatus.PENDING
            else:
                algo_status = AlgorithmStatus.COMPLETED
            
            # 计算执行耗时
            duration_ms = None
            if execution_doc.get("duration_seconds"):
                duration_ms = int(execution_doc.get("duration_seconds", 0) * 1000)
            elif execution_doc.get("started_at") and execution_doc.get("completed_at"):
                started = execution_doc.get("started_at")
                completed = execution_doc.get("completed_at")
                if isinstance(started, datetime) and isinstance(completed, datetime):
                    duration_ms = int((completed - started).total_seconds() * 1000)
            
            execution = {
                "execution_id": execution_id,
                "algorithm_id": execution_id,
                "algorithm_name": service_name or service_id,
                "description": f"服务执行: {service_name or service_id}",
                "service_id": service_id,  # 新增：包含 service_id
                "service_name": service_name,  # 新增：包含 service_name
                "status": algo_status.value,
                "duration": duration_ms,
                "key_params": execution_doc.get("parameters", {}),
                "input_file_id": execution_doc.get("input_file_id"),
                "output_file_id": execution_doc.get("output_file_id"),
                "error_message": execution_doc.get("error_message"),
                "response_data": execution_doc.get("response_data"),
                "created_at": execution_doc.get("created_at").isoformat() if isinstance(execution_doc.get("created_at"), datetime) else execution_doc.get("created_at"),
                "started_at": execution_doc.get("started_at").isoformat() if isinstance(execution_doc.get("started_at"), datetime) else execution_doc.get("started_at"),
                "completed_at": execution_doc.get("completed_at").isoformat() if isinstance(execution_doc.get("completed_at"), datetime) else execution_doc.get("completed_at")
            }
            
            return execution
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取执行记录失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="获取执行记录失败"
            )
    
    def update_execution_status_by_id(
        self,
        execution_id: str,
        user_id: str,
        status: str,
        output_file: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> bool:
        """
        通过executionId更新执行状态（不需要fileId）
        
        Args:
            execution_id: 执行ID（对应algorithm_id）
            user_id: 用户ID
            status: 新状态
            output_file: 输出的文件信息
            error: 错误信息
        
        Returns:
            是否成功
        """
        try:
            # 开发模式：如果user_id是test_user_id，尝试从数据库获取test_user的实际ID
            from textmsa.services.auth.auth_service import resolve_test_user_id
            user_id = resolve_test_user_id(user_id)
            
            # 查找执行记录
            execution_doc = self.service_executions_collection.find_one({
                "execution_id": execution_id
            })
            
            if not execution_doc:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail="执行记录不存在"
                )
            
            # 构建更新文档
            update_doc = {
                "status": status,
                "updated_at": datetime.now()
            }
            
            if status == "completed":
                update_doc["completed_at"] = datetime.now()
                if execution_doc.get("started_at"):
                    started = execution_doc.get("started_at")
                    if isinstance(started, datetime):
                        duration = (datetime.now() - started).total_seconds()
                        update_doc["duration_seconds"] = duration
            elif status == "running":
                update_doc["started_at"] = datetime.now()
            
            if output_file:
                # 提取输出文件ID
                output_file_id = output_file.get("file_id") or output_file.get("fileId") or output_file.get("id")
                if output_file_id and output_file_id.startswith("file_"):
                    output_file_id = output_file_id[5:]  # 去掉"file_"前缀
                update_doc["output_file_id"] = output_file_id
            
            if error:
                update_doc["error_message"] = error
            
            # 更新MongoDB执行记录
            result = self.service_executions_collection.update_one(
                {"execution_id": execution_id},
                {"$set": update_doc}
            )
            
            if result.modified_count == 0:
                logger.warning(f"更新执行状态失败，可能记录不存在: {execution_id}")
            
            return True
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"更新执行状态失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="更新执行状态失败"
            )


# 全局分析服务实例
_analysis_service: Optional[AnalysisService] = None


def get_analysis_service() -> AnalysisService:
    """获取全局分析服务实例"""
    global _analysis_service
    if _analysis_service is None:
        _analysis_service = AnalysisService()
    return _analysis_service
