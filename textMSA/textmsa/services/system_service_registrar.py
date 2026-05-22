"""
从 system_server 获取服务列表并注册到数据库
"""
from __future__ import annotations

import httpx
import asyncio
import subprocess
import socket
import re
from urllib.parse import urlparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from textmsa.logging_config import get_logger
from textmsa.services.service.service_service import get_service_service
from textmsa.services.data.mongodb_models import ServiceVisibility

logger = get_logger(__name__)


class SystemServiceRegistrar:
    """从 system_server 同步服务到数据库"""
    
    def __init__(self, system_server_url: str = "http://localhost:9000", timeout: float = 10.0):
        """
        初始化服务注册器
        
        Args:
            system_server_url: system_server 的 URL
            timeout: HTTP 请求超时时间（秒）
        """
        self.system_server_url = system_server_url.rstrip('/')
        self.timeout = timeout
        self.service_service = get_service_service()
    
    async def fetch_services(self, retry_count: int = 3) -> List[Dict[str, Any]]:
        """
        从 system_server 获取服务列表（带重试）
        
        Args:
            retry_count: 重试次数
        
        Returns:
            服务列表
        
        Raises:
            httpx.HTTPError: 如果请求失败
        """
        last_error = None
        # 使用更详细的超时配置：连接超时 5 秒，读取超时使用配置的超时时间
        connect_timeout = min(5.0, self.timeout)
        read_timeout = self.timeout
        timeout_config = httpx.Timeout(connect=connect_timeout, read=read_timeout, write=10.0, pool=5.0)
        
        for attempt in range(retry_count):
            try:
                logger.debug(f"Fetching services from {self.system_server_url}/api/v1/services (attempt {attempt + 1}/{retry_count}, timeout={read_timeout}s)...")
                async with httpx.AsyncClient(timeout=timeout_config) as client:
                    response = await client.get(f"{self.system_server_url}/api/v1/services")
                    response.raise_for_status()
                    data = response.json()
                    services = data.get("services", [])
                    logger.info(f"Fetched {len(services)} services from system_server (attempt {attempt + 1})")
                    return services
            except httpx.ReadTimeout as e:
                last_error = e
                if attempt < retry_count - 1:
                    wait_time = 2 ** attempt  # 指数退避
                    logger.warning(
                        f"Read timeout while fetching services from {self.system_server_url}/api/v1/services "
                        f"(attempt {attempt + 1}/{retry_count}, timeout={read_timeout}s). "
                        f"This may indicate that system_server is slow or blocked. Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        f"Read timeout while fetching services from system_server after {retry_count} attempts. "
                        f"URL: {self.system_server_url}/api/v1/services, timeout: {read_timeout}s. "
                        f"This may indicate that system_server is slow, blocked, or has internal locks. Error: {e}"
                    )
                    raise
            except httpx.TimeoutException as e:
                last_error = e
                if attempt < retry_count - 1:
                    wait_time = 2 ** attempt  # 指数退避
                    logger.warning(f"Timeout while fetching services (attempt {attempt + 1}/{retry_count}), retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Timeout while fetching services from system_server after {retry_count} attempts: {e}")
                    raise
            except httpx.HTTPStatusError as e:
                last_error = e
                if attempt < retry_count - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"HTTP error while fetching services: {e.response.status_code} - {e.response.text} (attempt {attempt + 1}/{retry_count}), retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"HTTP error while fetching services: {e.response.status_code} - {e.response.text}")
                    raise
            except Exception as e:
                last_error = e
                if attempt < retry_count - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Failed to fetch services (attempt {attempt + 1}/{retry_count}), retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Failed to fetch services from system_server after {retry_count} attempts: {e}", exc_info=True)
                    raise
        
        # 如果所有重试都失败，抛出最后一个错误
        if last_error:
            raise last_error
    
    def _get_actual_port_from_listening(self, expected_port: Optional[int] = None) -> Optional[int]:
        """
        检查实际监听的端口（通过 netstat/ss 命令）
        
        Args:
            expected_port: 期望的端口号（用于过滤）
        
        Returns:
            实际监听的端口号，如果未找到则返回 None
        """
        try:
            # 尝试使用 ss 命令（更现代）
            result = subprocess.run(
                ["ss", "-tlnp"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'LISTEN' in line:
                        # 解析端口号：0.0.0.0:35987 或 *:35987
                        match = re.search(r':(\d+)', line)
                        if match:
                            port = int(match.group(1))
                            if expected_port is None or port == expected_port:
                                return port
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            pass
        
        try:
            # 备选方案：使用 netstat
            result = subprocess.run(
                ["netstat", "-tlnp"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'LISTEN' in line:
                        # 解析端口号
                        parts = line.split()
                        if len(parts) >= 4:
                            addr = parts[3]
                            match = re.search(r':(\d+)$', addr)
                            if match:
                                port = int(match.group(1))
                                if expected_port is None or port == expected_port:
                                    return port
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            pass
        
        return None
    
    def _read_port_from_config_file(self, config_path: str) -> Optional[int]:
        """
        从配置文件中读取端口号
        
        Args:
            config_path: 配置文件路径
        
        Returns:
            端口号，如果读取失败则返回 None
        """
        try:
            import json
            config_file = Path(config_path)
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    # 优先使用 port 字段
                    if 'port' in config_data:
                        return int(config_data['port'])
                    # 其次从 baseurl 中提取
                    if 'baseurl' in config_data:
                        parsed = urlparse(config_data['baseurl'])
                        if parsed.port:
                            return parsed.port
        except Exception as e:
            logger.debug(f"从配置文件读取端口失败: {config_path}, 错误: {e}")
        return None
    
    def _check_and_update_baseurl(self, service_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查并更新服务的 baseurl 为实际运行的端口
        
        优先级：
        1. 从配置文件读取最新端口（如果 config_path 存在）
        2. 检查实际监听的端口
        3. 使用配置中的端口
        
        Args:
            service_config: 服务配置
        
        Returns:
            更新后的服务配置
        """
        baseurl = service_config.get('baseurl', '')
        if not baseurl:
            return service_config
        
        try:
            # 从 baseurl 中提取端口
            parsed = urlparse(baseurl)
            config_port = parsed.port
            if config_port is None:
                # 如果没有端口，使用默认端口（http: 80, https: 443）
                config_port = 80 if parsed.scheme == 'http' else 443
            
            actual_port = None
            
            # 优先级1: 从配置文件读取最新端口
            config_path = service_config.get('config_path')
            if config_path:
                file_port = self._read_port_from_config_file(config_path)
                if file_port and file_port != config_port:
                    actual_port = file_port
                    logger.info(
                        f"从配置文件读取到新端口 - 服务: {service_config.get('name', 'unknown')}, "
                        f"配置端口: {config_port}, 文件端口: {file_port}"
                    )
            
            # 优先级2: 检查实际监听的端口（如果配置文件未提供或端口不匹配）
            if actual_port is None:
                listening_port = self._get_actual_port_from_listening(config_port)
                if listening_port and listening_port != config_port:
                    actual_port = listening_port
                    logger.info(
                        f"检测到服务实际监听端口 - 服务: {service_config.get('name', 'unknown')}, "
                        f"配置端口: {config_port}, 实际端口: {listening_port}"
                    )
            
            # 如果找到了不同的端口，更新 baseurl
            if actual_port and actual_port != config_port:
                new_baseurl = f"{parsed.scheme}://{parsed.hostname}:{actual_port}"
                logger.info(
                    f"更新服务 baseurl - 服务: {service_config.get('name', 'unknown')}, "
                    f"原端口: {config_port}, 新端口: {actual_port}, "
                    f"更新 baseurl: {baseurl} -> {new_baseurl}"
                )
                service_config['baseurl'] = new_baseurl
                # 同时更新 port 字段（如果存在）
                if 'port' in service_config:
                    service_config['port'] = actual_port
            else:
                # 端口一致或未找到，使用配置的端口
                logger.debug(
                    f"服务端口检查完成 - 服务: {service_config.get('name', 'unknown')}, "
                    f"使用端口: {config_port}"
                )
        except Exception as e:
            logger.warning(f"检查服务端口时出错 - 服务: {service_config.get('name', 'unknown')}, 错误: {e}")
        
        return service_config
    
    def _normalise_service_config(self, service_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        规范化服务配置，提取需要的字段
        
        Args:
            service_config: 从 system_server 获取的服务配置
        
        Returns:
            规范化后的服务配置
        
        Raises:
            ValueError: 如果缺少必需字段
        """
        # 在规范化之前，先检查并更新 baseurl 为实际运行的端口
        service_config = self._check_and_update_baseurl(service_config)
        
        # 需要提取的字段（参考 registrar.py 的 SERVICE_CREATE_FIELDS）
        fields = {
            "service_id",
            "name",
            "description",
            "version",
            "baseurl",
            "service_suffix",
            "download_suffix",
            "parameter_template",
            "parameter_schema",
            "accepted_files",  # 新增字段
            "output_config",
        }
        
        # 提取存在的字段
        cleaned = {key: service_config[key] for key in fields if key in service_config}
        
        # 确保 accepted_files 字段存在（即使为 None）
        if "accepted_files" not in cleaned:
            cleaned["accepted_files"] = None
        
        # 检查必需字段（不仅检查存在，还要检查值不为 None 或空字符串）
        required_fields = ("baseurl", "service_suffix", "name")
        missing = []
        for key in required_fields:
            if key not in cleaned or not cleaned[key]:
                missing.append(key)
        if missing:
            raise ValueError(f"Service config missing or empty required fields: {', '.join(missing)}")
        
        # 设置 visibility
        cleaned["visibility"] = ServiceVisibility.SYSTEM.value
        
        # 确保 service_id 存在
        if "service_id" not in cleaned:
            cleaned["service_id"] = cleaned.get("name", "").lower().replace(" ", "-")
        
        return cleaned
    
    async def synchronise_services(self) -> List[str]:
        """
        同步服务到数据库
        
        流程：
        1. 从 system_server 获取服务列表
        2. 强制删除所有旧的系统服务（visibility == "system"）
           - 即使有执行记录也允许删除（但保留执行记录）
           - 确保每次启动时清理旧服务，保存新服务
        3. 注册新服务
        
        Returns:
            成功注册的服务名称列表
        
        Raises:
            Exception: 如果同步失败
        """
        try:
            # 1. 获取服务列表
            services = await self.fetch_services()
            
            if not services:
                logger.warning("No services found from system_server")
                return []
            
            # 2. 强制删除旧的系统服务（启动时清理，即使有执行记录也删除，但保留执行记录）
            existing_cursor = self.service_service.services_collection.find(
                {"visibility": ServiceVisibility.SYSTEM.value}
            )
            existing_ids = [doc["service_id"] for doc in existing_cursor]
            logger.info(f"Found {len(existing_ids)} existing system services to remove before registering new ones")
            
            for service_id in existing_ids:
                try:
                    # 直接使用强制删除，跳过执行记录检查
                    self._force_delete_service(service_id)
                    logger.info(f"Force deleted existing system service: {service_id}")
                except Exception as e:
                    logger.error(f"Failed to force delete service {service_id}: {e}", exc_info=True)
                    # 继续删除其他服务，不中断流程
            
            # 3. 注册新服务
            created_names: List[str] = []
            for service_config in services:
                try:
                    # 规范化配置
                    normalised = self._normalise_service_config(service_config)
                    
                    # 对于系统服务，直接插入数据库（跳过 URL 可达性检查）
                    # 因为 create_service 会生成新的 UUID，而我们需要使用从 system_server 获取的 service_id
                    self._direct_insert_service(normalised)
                    service_name = normalised.get("name", "unknown")
                    created_names.append(service_name)
                    logger.info(f"Registered system service: {service_name}")
                        
                except ValueError as e:
                    service_name = service_config.get('name', service_config.get('service_id', 'unknown'))
                    logger.error(f"Skipping invalid service config for service '{service_name}': {e}")
                    continue
                except Exception as e:
                    logger.error(f"Failed to register service '{service_config.get('name', 'unknown')}': {e}", exc_info=True)
                    # 不中断整个流程，继续注册其他服务
                    continue
            
            logger.info(f"System service synchronisation complete. Created: {created_names}")
            return created_names
            
        except Exception as e:
            logger.error(f"Failed to synchronise services: {e}", exc_info=True)
            raise
    
    def _direct_insert_service(self, service_data: Dict[str, Any]) -> None:
        """
        直接插入服务到数据库（跳过 URL 检查）
        
        Args:
            service_data: 服务数据
        """
        from textmsa.services.data.mongodb_models import (
            ServiceInfo, TaskRequestConfig, TaskParameterTemplate,
            ParameterDefinition, OutputTemplate, ServiceOutputConfig
        )
        from datetime import datetime
        
        # 构建 ServiceInfo 对象
        request_config = service_data.get('request_config', {})
        parameter_template_data = service_data.get('parameter_template', {})
        parameter_schema_data = service_data.get('parameter_schema', {})
        output_config_data = service_data.get('output_config')
        
        # 处理 parameter_schema
        parameter_schema = None
        if parameter_schema_data:
            schema_dict = {}
            for key, value in parameter_schema_data.items():
                if isinstance(value, dict):
                    schema_dict[key] = ParameterDefinition(**value)
                elif isinstance(value, ParameterDefinition):
                    schema_dict[key] = value
            parameter_schema = schema_dict if schema_dict else None
        
        # 处理 output_config
        output_config = None
        if output_config_data:
            if isinstance(output_config_data, dict):
                output_config = ServiceOutputConfig(**output_config_data)
            elif isinstance(output_config_data, ServiceOutputConfig):
                output_config = output_config_data
        
        # 获取 accepted_files
        accepted_files = service_data.get('accepted_files')
        
        # 创建 ServiceInfo
        # 安全处理 baseurl 和 service_suffix（确保不为 None）
        baseurl = service_data.get('baseurl')
        if not baseurl:
            raise ValueError(f"Service '{service_data.get('service_id', 'unknown')}' has empty or missing 'baseurl'")
        baseurl = baseurl.strip()
        
        service_suffix = service_data.get('service_suffix')
        if not service_suffix:
            raise ValueError(f"Service '{service_data.get('service_id', 'unknown')}' has empty or missing 'service_suffix'")
        service_suffix = service_suffix.strip()
        
        service_info = ServiceInfo(
            service_id=service_data['service_id'],
            name=service_data['name'],
            description=service_data.get('description'),
            version=service_data.get('version', '1.0.0'),
            baseurl=baseurl,
            service_suffix=service_suffix,
            download_suffix=service_data.get('download_suffix'),
            request_config=TaskRequestConfig(**request_config) if request_config else TaskRequestConfig(),
            parameter_template=TaskParameterTemplate(**parameter_template_data) if parameter_template_data else TaskParameterTemplate(),
            accepted_files=accepted_files,  # 新增
            output_config=output_config,
            parameter_schema=parameter_schema,
            visibility=ServiceVisibility.SYSTEM,
            created_by="system",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # 转换为字典并插入或更新（使用 upsert）
        service_doc = service_info.to_dict()
        # 移除 _id 字段（如果存在），让 MongoDB 自动生成
        if "_id" in service_doc:
            del service_doc["_id"]
        
        # 检查服务是否已存在
        existing = self.service_service.services_collection.find_one(
            {"service_id": service_data['service_id']}
        )
        
        if existing:
            # 如果已存在，保留 created_at，只更新其他字段
            if "created_at" in existing:
                service_doc["created_at"] = existing["created_at"]
            # 使用 replace_one 替换整个文档（保留 _id）
            service_doc["_id"] = existing["_id"]
            self.service_service.services_collection.replace_one(
                {"service_id": service_data['service_id']},
                service_doc
            )
            logger.info(f"Direct updated system service: {service_data['service_id']}")
        else:
            # 如果不存在，直接插入
            self.service_service.services_collection.insert_one(service_doc)
            logger.info(f"Direct inserted system service: {service_data['service_id']}")
    
    def _force_delete_service(self, service_id: str) -> None:
        """
        强制删除服务（用于清理旧服务）
        
        即使存在执行记录也允许删除，但保留执行记录。
        
        包括：
        1. 删除服务记录（跳过执行记录检查）
        2. 从项目配置中移除服务引用
        
        Args:
            service_id: 服务 ID
        """
        logger.info(f"Force deleting system service: {service_id} (execution records will be preserved)")
        
        # 检查是否有执行记录（仅用于日志）
        try:
            execution_count = self.service_service.service_executions_collection.count_documents(
                {"service_id": service_id}
            )
            if execution_count > 0:
                logger.info(
                    f"Service {service_id} has {execution_count} execution records, "
                    f"but will be deleted anyway (execution records preserved)"
                )
        except Exception as e:
            logger.warning(f"Failed to check execution records for service {service_id}: {e}")
        
        # 1. 删除服务记录（跳过执行记录检查）
        try:
            result = self.service_service.services_collection.delete_one({"service_id": service_id})
            if result.deleted_count > 0:
                logger.info(f"Deleted service record: {service_id}")
            else:
                logger.warning(f"Service record not found: {service_id}")
        except Exception as e:
            logger.error(f"Failed to delete service record {service_id}: {e}")
            raise
        
        # 2. 从项目配置中移除服务引用
        try:
            from textmsa.services.data.user_data_manager_mongodb import get_user_data_manager
            user_data_manager = get_user_data_manager()
            stats = user_data_manager.remove_service_from_project_configs(service_id)
            logger.info(f"Removed service {service_id} from project configs: {stats}")
        except Exception as e:
            logger.warning(f"Failed to update project configs after force deleting service {service_id}: {e}")

