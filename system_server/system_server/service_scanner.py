"""
服务扫描器
用于扫描和发现服务
"""
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from system_server.utils import collect_service_configs
from system_server.config import Config

logger = logging.getLogger(__name__)


class ServiceScanner:
    """服务扫描器"""
    
    def __init__(self, services_dir: Optional[Path] = None):
        """
        初始化服务扫描器
        
        Args:
            services_dir: 服务目录
        """
        if services_dir is None:
            services_dir = Config.SERVICES_DIR
        self.services_dir = Path(services_dir).resolve()
        self._cached_services: Optional[List[Dict[str, Any]]] = None
    
    def scan_services(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        扫描所有服务
        
        Args:
            use_cache: 是否使用缓存
            
        Returns:
            服务配置列表
        """
        if use_cache and self._cached_services is not None:
            return self._cached_services
        
        services = collect_service_configs(self.services_dir)
        self._cached_services = services
        return services
    
    def get_service(self, service_name: str) -> Optional[Dict[str, Any]]:
        """
        获取单个服务配置
        
        Args:
            service_name: 服务名称或 ID
            
        Returns:
            服务配置，如果未找到则返回 None
        """
        services = self.scan_services()
        for service in services:
            if (service.get('name') == service_name or 
                service.get('service_id') == service_name or
                service.get('service_dir') == service_name):
                return service
        return None
    
    def clear_cache(self):
        """清除缓存"""
        self._cached_services = None

