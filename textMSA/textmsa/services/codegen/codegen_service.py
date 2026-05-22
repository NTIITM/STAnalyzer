"""
代码生成服务
管理代码生成、确认、执行的完整流程
支持保存执行环境和代码
"""
import os
import uuid
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure
from fastapi import HTTPException, status

from textmsa.logging_config import get_logger
from textmsa.settings import get_mongodb_config, get_storage_config
from textmsa.services.data.mongodb_models import (
    CodegenRequest,
    CodegenTemplate,
    CodegenExecution,
    CodegenStatus,
    CodegenLanguage,
    CodegenExecutionStatus,
    FileInfo,
    SupportedLanguage,
    ServiceOutputConfig,
    codegen_template_from_dict,
    codegen_execution_from_dict,
)
from textmsa.services.codegen.codegen_agent import CodegenAgent
from textmsa.services.codegen.codegen_executor import CodegenExecutor
from textmsa.services.file.file_service import get_file_service
from textmsa.services.file.file_manager import get_file_manager
from concurrent.futures import ThreadPoolExecutor

logger = get_logger(__name__)


class CodegenService:
    """代码生成服务类"""
    
    def __init__(self, connection_string: Optional[str] = None, database_name: Optional[str] = None):
        """
        初始化代码生成服务
        
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
            logger.info("代码生成服务：成功连接到MongoDB")
        except ConnectionFailure as e:
            logger.error(f"代码生成服务：无法连接到MongoDB: {e}")
            raise
        
        # 选择数据库
        self.db = self.client[database_name]
        self.database_name = database_name
        
        # 集合
        self.templates_collection = self.db.codegen_templates
        self.executions_collection = self.db.codegen_executions
        
        # 创建索引
        self._create_indexes()
        
        # 获取其他服务
        self.file_service = get_file_service()
        self.file_manager = get_file_manager()
        self.agent = CodegenAgent()
        
        # 存储配置
        storage_config = get_storage_config()
        self.codegen_dir = Path(storage_config.get("codegen_dir", storage_config["base_dir"])) / "codegen"
        self.codegen_dir.mkdir(parents=True, exist_ok=True)
        
        # 线程池用于后台任务
        self.executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="codegen_executor")
        
        logger.info(f"CodegenService初始化完成: 数据库={database_name}, 代码目录={self.codegen_dir}")
    
    def _create_indexes(self):
        """创建索引"""
        try:
            # 模板集合索引
            self.templates_collection.create_index([("template_id", ASCENDING)], unique=True)
            self.templates_collection.create_index([("status", ASCENDING)])
            self.templates_collection.create_index([("user_id", ASCENDING)])
            self.templates_collection.create_index([("created_at", DESCENDING)])
            
            # 执行集合索引
            self.executions_collection.create_index([("execution_id", ASCENDING)], unique=True)
            self.executions_collection.create_index([("template_id", ASCENDING)])
            self.executions_collection.create_index([("user_id", ASCENDING)])
            self.executions_collection.create_index([("status", ASCENDING)])
            self.executions_collection.create_index([("created_at", DESCENDING)])
            
            logger.debug("代码生成集合索引创建完成")
        except Exception as e:
            logger.warning(f"创建索引时出错: {e}")
    
    # ============= 代码生成 =============
    
    def generate_template(self, request: CodegenRequest, user_id: str) -> Dict[str, Any]:
        """
        生成代码模板
        
        Args:
            request: 代码生成请求
            user_id: 用户ID
        
        Returns:
            生成的模板信息
        """
        try:
            # 验证用户ID
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="必须提供用户ID"
                )
            
            # 获取输入文件信息
            file_info = self.file_service.get_file_info(request.input_file.file_id, user_id)
            if not file_info:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"输入文件 '{request.input_file.file_id}' 不存在"
                )
            
            # 获取文件内容预览（可选）
            file_content_preview = None
            try:
                file_path = self.file_manager.get_file_path(request.input_file.file_id)
                if file_path and os.path.exists(file_path):
                    # 只读取前1000字符作为预览
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        file_content_preview = f.read(1000)
            except Exception as e:
                logger.warning(f"读取文件预览失败: {e}")
            
            # 使用Agent生成服务模板（类似service_config.json）
            template = self.agent.generate_template(request, file_info, file_content_preview, user_id)
            
            # 保存到MongoDB
            template_doc = template.to_dict()
            self.templates_collection.insert_one(template_doc)
            
            logger.info(f"代码模板生成成功: {template.template_id}, 用户: {user_id}")
            
            # 保存代码到文件系统（用于后续编辑和执行）
            self._save_template_code(template)
            
            return self._template_to_response(template)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"生成代码模板失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"生成代码模板失败: {str(e)}"
            )
    
    def _save_template_code(self, template: CodegenTemplate):
        """保存模板代码到文件系统"""
        try:
            template_dir = self.codegen_dir / template.template_id
            template_dir.mkdir(parents=True, exist_ok=True)
            
            # 根据语言确定文件扩展名
            ext_map = {
                SupportedLanguage.PYTHON: '.py',
                SupportedLanguage.R: '.R',
                SupportedLanguage.JULIA: '.jl',
                SupportedLanguage.BASH: '.sh'
            }
            ext = ext_map.get(template.code_language, '.py')
            
            code_file = template_dir / f"code{ext}"
            with open(code_file, 'w', encoding='utf-8') as f:
                f.write(template.generated_code or '')
            
            # 保存环境配置
            if template.execution_environment:
                import json
                env_file = template_dir / "environment.json"
                with open(env_file, 'w', encoding='utf-8') as f:
                    json.dump(template.execution_environment.to_dict(), f, indent=2)
            
            logger.debug(f"模板代码已保存: {code_file}")
            
        except Exception as e:
            logger.warning(f"保存模板代码失败: {e}")
    
    # ============= 模板管理 =============
    
    def get_template(self, template_id: str) -> Dict[str, Any]:
        """
        获取模板信息
        
        Args:
            template_id: 模板ID
            user_id: 用户ID（可选，用于权限检查）
        
        Returns:
            模板信息
        """
        try:
            template_doc = self.templates_collection.find_one({"template_id": template_id})
            
            if not template_doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"模板 '{template_id}' 不存在"
                )
            
            template = codegen_template_from_dict(template_doc)
            
            return self._template_to_response(template)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取模板信息失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"获取模板信息失败: {str(e)}"
            )
    
    def list_templates(self, user_id: Optional[str] = None, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        """
        获取模板列表
        
        Args:
            user_id: 用户ID（可选，用于过滤）
            skip: 跳过数量
            limit: 返回数量
        
        Returns:
            模板列表和总数
        """
        try:
            query = {}
            if user_id:
                query["user_id"] = user_id
            
            # 查询总数
            total = self.templates_collection.count_documents(query)
            
            # 查询列表
            cursor = self.templates_collection.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit)
            
            templates = []
            for template_doc in cursor:
                try:
                    template = codegen_template_from_dict(template_doc)
                    templates.append(self._template_to_response(template))
                except Exception as e:
                    logger.warning(f"解析模板文档失败: {e}")
                    continue
            
            return {
                "templates": templates,
                "total": total
            }
            
        except Exception as e:
            logger.error(f"获取模板列表失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"获取模板列表失败: {str(e)}"
            )
    
    def update_template(self, template_id: str, update_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        更新模板（主要用于用户确认或修改代码）
        
        Args:
            template_id: 模板ID
            update_data: 更新数据
            user_id: 用户ID
        
        Returns:
            更新后的模板信息
        """
        try:
            # 检查模板是否存在
            template_doc = self.templates_collection.find_one({"template_id": template_id})
            if not template_doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"模板 '{template_id}' 不存在"
                )
            
            template = codegen_template_from_dict(template_doc)
            
            # 权限检查
            if template.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"无权修改模板 '{template_id}'"
                )
            
            # 构建更新文档
            update_doc = {}
            
            if 'generated_code' in update_data:
                update_doc['generated_code'] = update_data['generated_code']
            if 'status' in update_data:
                update_doc['status'] = update_data['status']
            if 'parameters' in update_data:
                # 更新参数模板
                if isinstance(update_data['parameters'], dict):
                    current_params = template.parameter_template.to_dict()
                    merged_params = {**current_params, **update_data['parameters']}
                    update_doc['parameter_template'] = merged_params
            
            # 更新updated_at
            update_doc['updated_at'] = datetime.now()
            
            # 执行更新
            self.templates_collection.update_one(
                {"template_id": template_id},
                {"$set": update_doc}
            )
            
            logger.info(f"模板更新成功: {template_id}")
            
            # 如果更新了代码，保存到文件系统
            if 'generated_code' in update_doc:
                template.generated_code = update_doc['generated_code']
                self._save_template_code(template)
            
            # 返回更新后的模板
            return self.get_template(template_id)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"更新模板失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"更新模板失败: {str(e)}"
            )
    
    def confirm_template(self, template_id: str, user_id: str) -> Dict[str, Any]:
        """
        确认模板（用户确认模板后，状态变为TEMPLATE_CONFIRMED，可以生成代码）
        
        Args:
            template_id: 模板ID
            user_id: 用户ID
        
        Returns:
            更新后的模板信息
        """
        return self.update_template(template_id, {"status": CodegenStatus.TEMPLATE_CONFIRMED.value}, user_id)
    
    def generate_code(self, template_id: str, user_id: str) -> Dict[str, Any]:
        """
        生成代码（模板确认后，生成代码，状态变为CODE_GENERATED）
        
        Args:
            template_id: 模板ID
            user_id: 用户ID
        
        Returns:
            更新后的模板信息
        """
        try:
            # 检查模板是否存在
            template_doc = self.templates_collection.find_one({"template_id": template_id})
            if not template_doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"模板 '{template_id}' 不存在"
                )
            
            template = codegen_template_from_dict(template_doc)
            
            # 权限检查
            if template.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"无权操作模板 '{template_id}'"
                )
            
            # 检查状态：必须是TEMPLATE_CONFIRMED
            if template.status != CodegenStatus.TEMPLATE_CONFIRMED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"模板状态必须是 'template_confirmed'，当前状态: {template.status.value}"
                )
            
            # 如果还没有代码，使用Agent生成代码
            if not template.generated_code:
                # 重新生成代码（基于确认的模板）
                # 保存原有的metadata（包含conda_env）
                original_metadata = template.meta.copy() if template.meta else {}
                
                # 获取文件信息
                file_info = self.file_service.get_file_info(template.input_file_id, user_id)
                if not file_info:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"输入文件 '{template.input_file_id}' 不存在"
                    )
                
                # 使用Agent生成代码
                new_template = self.agent.generate_template(
                    user_requirement=template.user_requirement,
                    file_info=file_info,
                    user_id=user_id
                )
                new_template.template_id = template_id  # 保持原ID
                # 恢复原有的meta（特别是conda_env，应该保持不变）
                if original_metadata:
                    new_template.meta = {**new_template.meta, **original_metadata}
                template = new_template
                template.status = CodegenStatus.CODE_GENERATED
            
            # 更新状态为CODE_GENERATED
            self.templates_collection.update_one(
                {"template_id": template_id},
                {
                    "$set": {
                        "status": CodegenStatus.CODE_GENERATED.value,
                        "generated_code": template.generated_code,
                        "updated_at": datetime.now()
                    }
                }
            )
            
            # 保存代码到文件系统
            template.status = CodegenStatus.CODE_GENERATED
            self._save_template_code(template)
            
            logger.info(f"代码生成成功: {template_id}")
            
            return self.get_template(template_id, user_id)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"生成代码失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"生成代码失败: {str(e)}"
            )
    
    def finalize_template(self, template_id: str, user_id: str) -> Dict[str, Any]:
        """
        最终确认并保存（用户确认执行结果后，保存所有信息，状态变为FINALIZED）
        
        Args:
            template_id: 模板ID
            user_id: 用户ID
        
        Returns:
            更新后的模板信息
        """
        try:
            # 检查模板是否存在
            template_doc = self.templates_collection.find_one({"template_id": template_id})
            if not template_doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"模板 '{template_id}' 不存在"
                )
            
            template = codegen_template_from_dict(template_doc)
            
            # 权限检查
            if template.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"无权操作模板 '{template_id}'"
                )
            
            # 检查状态：必须是EXECUTION_COMPLETED
            if template.status != CodegenStatus.EXECUTION_COMPLETED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"模板状态必须是 'execution_completed'，当前状态: {template.status.value}"
                )
            
            # 更新状态为FINALIZED
            self.templates_collection.update_one(
                {"template_id": template_id},
                {
                    "$set": {
                        "status": CodegenStatus.FINALIZED.value,
                        "updated_at": datetime.now()
                    }
                }
            )
            
            # 保存所有信息到文件系统（代码、环境配置、执行结果等）
            self._save_finalized_template(template)
            
            logger.info(f"模板最终确认并保存成功: {template_id}")
            
            return self.get_template(template_id, user_id)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"最终确认失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"最终确认失败: {str(e)}"
            )
    
    def _save_finalized_template(self, template: CodegenTemplate):
        """保存最终确认的模板（代码、环境、执行结果等）"""
        try:
            template_dir = self.codegen_dir / template.template_id / "finalized"
            template_dir.mkdir(parents=True, exist_ok=True)
            
            # 保存代码
            ext_map = {
                SupportedLanguage.PYTHON: '.py',
                SupportedLanguage.R: '.R',
                SupportedLanguage.JULIA: '.jl',
                SupportedLanguage.BASH: '.sh'
            }
            ext = ext_map.get(template.code_language, '.py')
            code_file = template_dir / f"code{ext}"
            with open(code_file, 'w', encoding='utf-8') as f:
                f.write(template.generated_code or '')
            
            # 保存环境配置
            if template.execution_environment:
                import json
                env_file = template_dir / "environment.json"
                with open(env_file, 'w', encoding='utf-8') as f:
                    json.dump(template.execution_environment.to_dict(), f, indent=2)
            
            # 保存模板配置（类似service_config.json）
            config_file = template_dir / "service_config.json"
            config_data = {
                "service_id": template.service_id or template.template_id,
                "name": template.name,
                "description": template.description,
                "version": template.version,
                "tags": template.tags,
                "parameter_template": template.parameter_template.to_dict() if template.parameter_template else {},
                "parameter_schema": {
                    k: v.model_dump() if hasattr(v, 'model_dump') else v
                    for k, v in (template.parameter_schema or {}).items()
                },
                "output_config": template.output_config.model_dump() if template.output_config else None
            }
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            # 保存执行结果（如果有）
            if template.execution_result:
                result_file = template_dir / "execution_result.json"
                with open(result_file, 'w', encoding='utf-8') as f:
                    json.dump(template.execution_result, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"最终模板已保存: {template_dir}")
            
        except Exception as e:
            logger.warning(f"保存最终模板失败: {e}")
    
    # ============= 代码执行 =============
    
    def execute_template(
        self,
        template_id: str,
        user_id: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行模板代码
        
        Args:
            template_id: 模板ID
            user_id: 用户ID
            parameters: 执行参数（覆盖模板默认参数）
        
        Returns:
            执行结果
        """
        execution_id = str(uuid.uuid4())
        start_time = time.time()
        
        try:
            # 获取模板
            template_doc = self.templates_collection.find_one({"template_id": template_id})
            if not template_doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"模板 '{template_id}' 不存在"
                )
            
            template = codegen_template_from_dict(template_doc)
            
            # 权限检查
            if template.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"无权执行模板 '{template_id}'"
                )
            
            # 检查模板状态：必须是CODE_GENERATED
            if template.status != CodegenStatus.CODE_GENERATED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"模板状态为 '{template.status.value}'，无法执行。请先确认模板并生成代码。"
                )
            
            # 获取输入文件路径
            file_info = self.file_service.get_file_info(template.input_file_id, user_id)
            if not file_info:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"输入文件 '{template.input_file_id}' 不存在"
                )
            
            input_file_path = self.file_manager.get_file_path(template.input_file_id)
            if not input_file_path or not os.path.exists(input_file_path):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"输入文件路径不存在: {template.input_file_id}"
                )
            
            # 合并参数
            template_params = template.parameter_template.to_dict()
            final_params = {**template_params, **(parameters or {})}
            
            # 验证参数（如果定义了schema）
            if template.parameter_schema:
                temp_template = template.parameter_template.__class__(**final_params)
                schema_dict = {}
                for key, value in template.parameter_schema.items():
                    if isinstance(value, type(template.parameter_schema[key])):
                        schema_dict[key] = value.model_dump() if hasattr(value, 'model_dump') else value
                    else:
                        schema_dict[key] = value
                
                is_valid, error_msg, error_details = temp_template.validate_against_schema(schema_dict)
                if not is_valid:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"参数验证失败: {error_msg}"
                    )
            
            # 确保 execution_environment 存在（从 meta 中读取 conda_env）
            execution_environment = template.execution_environment
            if not execution_environment and template.code_language == SupportedLanguage.PYTHON:
                conda_env = template.meta.get('conda_env')
                if conda_env:
                    from textmsa.services.data.mongodb_models import ExecutionEnvironment
                    execution_environment = ExecutionEnvironment(
                        language=template.code_language,
                        conda_env=conda_env
                    )
            
            # 创建执行记录
            execution = CodegenExecution(
                execution_id=execution_id,
                template_id=template_id,
                user_id=user_id,
                code=template.generated_code or '',
                language=template.code_language,
                environment=execution_environment,
                parameters=final_params,
                status=CodegenExecutionStatus.RUNNING
            )
            
            self.executions_collection.insert_one(execution.to_dict())
            
            # 更新模板状态
            self.templates_collection.update_one(
                {"template_id": template_id},
                {"$set": {
                    "status": CodegenStatus.EXECUTING.value,
                    "execution_id": execution_id,
                    "updated_at": datetime.now()
                }}
            )
            
            # 提交后台任务异步执行
            self.executor.submit(
                self._execute_template_async,
                execution_id=execution_id,
                template=template,
                input_file_path=input_file_path,
                parameters=final_params,
                user_id=user_id,
                start_time=start_time
            )
            
            # 立即返回
            return {
                "execution_id": execution_id,
                "template_id": template_id,
                "status": CodegenStatus.EXECUTING.value,
                "created_at": datetime.now().isoformat()
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"执行模板失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"执行模板失败: {str(e)}"
            )
    
    def _execute_template_async(
        self,
        execution_id: str,
        template: CodegenTemplate,
        input_file_path: str,
        parameters: Dict[str, Any],
        user_id: str,
        start_time: float
    ):
        """后台异步执行模板代码"""
        executor = None
        try:
            logger.info(f"开始异步执行模板: {execution_id}")
            
            # 确保 execution_environment 存在（从 meta 中读取 conda_env）
            execution_environment = template.execution_environment
            if not execution_environment and template.code_language == SupportedLanguage.PYTHON:
                conda_env = template.meta.get('conda_env')
                if conda_env:
                    from textmsa.services.data.mongodb_models import ExecutionEnvironment
                    execution_environment = ExecutionEnvironment(
                        language=template.code_language,
                        conda_env=conda_env
                    )
            
            # 创建执行器
            executor = CodegenExecutor()
            
            # 执行代码
            result = executor.execute_code(
                code=template.generated_code or '',
                language=template.code_language,
                environment=execution_environment,
                input_file_path=input_file_path,
                parameters=parameters,
                timeout=3600
            )
            
            # 处理输出文件
            output_file_id = None
            if result.get('output_files'):
                # 保存第一个输出文件
                output_file_path = result['output_files'][0]
                if os.path.exists(output_file_path):
                    saved_file_info = self.file_manager.save_uploaded_file(
                        file_obj=output_file_path,
                        filename=os.path.basename(output_file_path),
                        user_id=user_id
                    )
                    output_file_id = saved_file_info['file_id']
            
            # 更新执行记录
            self.executions_collection.update_one(
                {"execution_id": execution_id},
                {"$set": {
                    "status": CodegenExecutionStatus.COMPLETED.value if result['status'] == 'success' else CodegenExecutionStatus.FAILED.value,
                    "output_file_id": output_file_id,
                    "output_data": {
                        "output": result.get('output', ''),
                        "output_files": result.get('output_files', [])
                    },
                    "error_message": result.get('error'),
                    "execution_log": f"{result.get('output', '')}\n{result.get('error', '')}",
                    "completed_at": datetime.now(),
                    "duration_seconds": result.get('execution_time', 0)
                }}
            )
            
            # 更新模板状态（执行完成后状态变为EXECUTION_COMPLETED）
            execution_status = CodegenStatus.EXECUTION_COMPLETED if result['status'] == 'success' else CodegenStatus.FAILED
            self.templates_collection.update_one(
                {"template_id": template.template_id},
                {"$set": {
                    "status": execution_status.value,
                    "execution_id": execution_id,
                    "execution_result": {
                        "execution_id": execution_id,
                        "output_file_id": output_file_id,
                        "output_data": {
                            "output": result.get('output', ''),
                            "output_files": result.get('output_files', [])
                        },
                        "status": result['status']
                    },
                    "error_message": result.get('error'),
                    "updated_at": datetime.now()
                }}
            )
            
            logger.info(f"模板执行完成: {execution_id}, 状态: {execution_status.value}")
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"异步执行模板失败: {execution_id}, 错误: {e}", exc_info=True)
            
            # 更新执行记录为失败
            self.executions_collection.update_one(
                {"execution_id": execution_id},
                {"$set": {
                    "status": CodegenExecutionStatus.FAILED.value,
                    "error_message": error_message,
                    "completed_at": datetime.now(),
                    "duration_seconds": time.time() - start_time
                }}
            )
            
            # 更新模板状态
            self.templates_collection.update_one(
                {"template_id": template.template_id},
                {"$set": {
                    "status": CodegenStatus.FAILED.value,
                    "error_message": error_message,
                    "updated_at": datetime.now()
                }}
            )
        finally:
            # 清理执行器
            if executor:
                executor.cleanup()
    
    # ============= 执行记录管理 =============
    
    def get_execution(self, execution_id: str) -> Dict[str, Any]:
        """获取执行记录"""
        try:
            execution_doc = self.executions_collection.find_one({"execution_id": execution_id})
            
            if not execution_doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"执行记录 '{execution_id}' 不存在"
                )
            
            execution = codegen_execution_from_dict(execution_doc)
            return self._execution_to_response(execution)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取执行记录失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"获取执行记录失败: {str(e)}"
            )
    
    def list_executions(
        self,
        template_id: Optional[str] = None,
        user_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> Dict[str, Any]:
        """获取执行记录列表"""
        try:
            query = {}
            if template_id:
                query["template_id"] = template_id
            if user_id:
                query["user_id"] = user_id
            
            total = self.executions_collection.count_documents(query)
            cursor = self.executions_collection.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit)
            
            executions = []
            for execution_doc in cursor:
                try:
                    execution = codegen_execution_from_dict(execution_doc)
                    executions.append(self._execution_to_response(execution))
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
    
    def _template_to_response(self, template: CodegenTemplate) -> Dict[str, Any]:
        """将模板转换为API响应格式"""
        return {
            "template_id": template.template_id,
            "name": template.name,
            "description": template.description,
            "version": template.version,
            "tags": template.tags,
            "user_requirement": template.user_requirement,
            "input_file_id": template.input_file_id,
            "input_file_description": template.input_file_description,
            "parameter_template": template.parameter_template.to_dict(),
            "parameter_schema": {
                k: v.model_dump() if hasattr(v, 'model_dump') else v
                for k, v in (template.parameter_schema or {}).items()
            } if template.parameter_schema else None,
            "output_config": template.output_config.model_dump() if template.output_config else None,
            "generated_code": template.generated_code,
            "code_language": template.code_language.value,
            "execution_environment": template.execution_environment.to_dict() if template.execution_environment else None,
            "meta": template.meta,
            "status": template.status.value,
            "created_at": template.created_at.isoformat() if template.created_at else None,
            "updated_at": template.updated_at.isoformat() if template.updated_at else None,
            "user_id": template.user_id,
            "service_id": template.service_id,
            "execution_id": template.execution_id,
            "execution_result": template.execution_result,
            "error_message": template.error_message
        }
    
    def _execution_to_response(self, execution: CodegenExecution) -> Dict[str, Any]:
        """将执行记录转换为API响应格式"""
        return {
            "execution_id": execution.execution_id,
            "template_id": execution.template_id,
            "user_id": execution.user_id,
            "code": execution.code,
            "language": execution.language.value,
            "environment": execution.environment.to_dict() if execution.environment else None,
            "parameters": execution.parameters,
            "status": execution.status.value,
            "output_file_id": execution.output_file_id,
            "output_data": execution.output_data,
            "error_message": execution.error_message,
            "execution_log": execution.execution_log,
            "created_at": execution.created_at.isoformat() if execution.created_at else None,
            "started_at": execution.started_at.isoformat() if execution.started_at else None,
            "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
            "duration_seconds": execution.duration_seconds
        }

    def _build_virtual_file_info(
        self,
        user_id: str,
        service_id: Optional[str],
        project_id: Optional[str],
        input_filename: Optional[str],
        input_file_description: Optional[str]
    ) -> FileInfo:
        """构造用于对话的虚拟文件信息"""
        filename = (input_filename or "virtual_input.txt").strip()
        file_id = f"virtual_{uuid.uuid4().hex[:16]}"
        file_path = str(self.codegen_dir / f"{file_id}.virtual")
        metadata = {
            "source": "codegen_conversation",
            "service_id": service_id,
            "project_id": project_id
        }
        return FileInfo(
            user_id=user_id,
            file_id=file_id,
            filename=filename,
            file_path=file_path,
            description=input_file_description,
            metadata={k: v for k, v in metadata.items() if v is not None}
        )
    
    # ============= 对话管理 =============
    
    def start_conversation(
        self,
        user_id: str,
        user_requirement: str,
        service_id: Optional[str] = None,
        project_id: Optional[str] = None,
        input_filename: Optional[str] = None,
        input_file_description: Optional[str] = None,
        context: Optional[str] = None,
        output_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        开始对话，创建初始模板和对话记录
        
        Args:
            request: 代码生成请求
            user_id: 用户ID
        
        Returns:
            包含template_id, conversation_id, template, agent_message的字典
        """
        logger.info("Codegen conversations have been deprecated; start_conversation is disabled.")
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Codegen conversations have been removed. Use agent APIs instead.",
        )
    
    def continue_conversation(
        self,
        template_id: str,
        user_message: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        继续对话，根据用户消息更新模板
        
        Args:
            template_id: 模板ID
            user_message: 用户消息
            user_id: 用户ID
        
        Returns:
            包含template, agent_message, requires_action, conversation_ended的字典
        """
        logger.info("Codegen conversations have been deprecated; continue_conversation is disabled.")
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Codegen conversations have been removed. Use agent APIs instead.",
        )
    
    def get_conversation(self, template_id: str, user_id: str) -> Dict[str, Any]:
        """
        获取对话历史
        
        Args:
            template_id: 模板ID
            user_id: 用户ID
        
        Returns:
            对话历史信息
        """
        logger.info("Codegen conversations have been deprecated; get_conversation is disabled.")
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Codegen conversations have been removed. Use agent APIs instead.",
        )
    
    def end_conversation(self, template_id: str, user_id: str) -> Dict[str, Any]:
        """
        结束对话（用户确认模板）
        
        Args:
            template_id: 模板ID
            user_id: 用户ID
        
        Returns:
            更新后的模板信息
        """
        # 结束对话就是确认模板
        return self.confirm_template(template_id, user_id)


# 全局服务实例
_codegen_service: Optional[CodegenService] = None


def get_codegen_service() -> CodegenService:
    """获取全局代码生成服务实例（单例模式）"""
    global _codegen_service
    if _codegen_service is None:
        _codegen_service = CodegenService()
    return _codegen_service
