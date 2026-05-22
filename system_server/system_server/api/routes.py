"""
API 路由
"""
from fastapi import APIRouter, HTTPException, status
from typing import List
import logging

from system_server.api.models import (
    ServiceInfo,
    ServiceListResponse,
    ServiceStatusResponse,
    ServiceActionResponse,
    ServiceLogsResponse
)
from system_server.service_manager import ServiceManager
from system_server.service_scanner import ServiceScanner
from system_server.config import Config

logger = logging.getLogger(__name__)

router = APIRouter(tags=["services"])

# 初始化服务管理器和扫描器
service_manager = ServiceManager(
    services_base_dir=Config.SERVICES_DIR,
    project_root=Config.PROJECT_ROOT,
    services_config_path=Config.SERVICES_CONFIG_PATH,
)
service_scanner = ServiceScanner(
    services_dir=Config.SERVICES_DIR
)


@router.get("/services", response_model=ServiceListResponse)
async def get_services():
    """
    获取所有服务列表
    
    返回所有已扫描到的系统服务及其配置信息。
    """
    try:
        import socket as _socket
        # 清除缓存并重新扫描，确保获取最新的服务配置
        service_scanner.clear_cache()
        services = service_scanner.scan_services(use_cache=False)
        
        # 转换为 ServiceInfo 模型
        service_infos = []
        for service in services:
            # 获取服务状态：直接检查扫描到的端口是否响应
            service_id = service.get("service_id") or service.get("name") or service.get("service_dir", "")
            scanned_port = service.get("port", 0)
            
            # 直接用 scanned_port 做 TCP connect 判断，避免 service_manager 内存为空时误报 stopped
            svc_status = "stopped"
            if scanned_port:
                try:
                    with _socket.create_connection(("127.0.0.1", scanned_port), timeout=0.5):
                        svc_status = "running"
                except (OSError, ConnectionRefusedError):
                    # 端口不可达，保持 stopped
                    pass
            
            # 如果直接连接失败，还是回退到 service_manager 的检测（通过进程）
            if svc_status == "stopped":
                status_info = service_manager.get_service_status(service_id)
                svc_status = status_info.get("status", "stopped")
            
            service_info = ServiceInfo(
                service_id=service_id,
                name=service.get("name", service_id),
                description=service.get("description"),
                version=service.get("version", "1.0.0"),
                baseurl=service.get("baseurl", ""),
                port=scanned_port,
                service_suffix=service.get("service_suffix"),
                download_suffix=service.get("download_suffix"),
                parameter_template=service.get("parameter_template"),
                parameter_schema=service.get("parameter_schema"),
                accepted_files=service.get("accepted_files"),
                output_config=service.get("output_config"),
                status=svc_status,
                docker=service.get("docker", False)
            )
            service_infos.append(service_info)
        
        return ServiceListResponse(
            services=service_infos,
            total=len(service_infos)
        )
    except Exception as e:
        logger.error(f"Failed to get services: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get services: {str(e)}"
        )



@router.get("/services/{service_name}", response_model=ServiceInfo)
async def get_service(service_name: str):
    """
    获取单个服务信息
    
    Args:
        service_name: 服务名称或 ID
    """
    try:
        service = service_scanner.get_service(service_name)
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_name}' not found"
            )
        
        # 获取服务状态
        status_info = service_manager.get_service_status(service_name)
        
        service_id = service.get("service_id") or service.get("name") or service.get("service_dir", "")
        
        return ServiceInfo(
            service_id=service_id,
            name=service.get("name", service_id),
            description=service.get("description"),
            version=service.get("version", "1.0.0"),
            baseurl=service.get("baseurl", ""),
            port=service.get("port", 0),
            service_suffix=service.get("service_suffix"),
            download_suffix=service.get("download_suffix"),
            parameter_template=service.get("parameter_template"),
            parameter_schema=service.get("parameter_schema"),
            accepted_files=service.get("accepted_files"),
            output_config=service.get("output_config"),
            status=status_info.get("status", "stopped"),
            docker=service.get("docker", False)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get service {service_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get service: {str(e)}"
        )


@router.get("/services/{service_name}/status", response_model=ServiceStatusResponse)
async def get_service_status(service_name: str):
    """
    获取服务状态
    
    Args:
        service_name: 服务名称或 ID
    """
    try:
        # 检查服务是否存在
        service = service_scanner.get_service(service_name)
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_name}' not found"
            )
        
        status_info = service_manager.get_service_status(service_name)
        
        return ServiceStatusResponse(
            service_id=service_name,
            status=status_info.get("status", "stopped"),
            message=status_info.get("message")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get service status {service_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get service status: {str(e)}"
        )


@router.post("/services/{service_name}/start", response_model=ServiceActionResponse)
async def start_service(service_name: str):
    """
    启动服务
    
    Args:
        service_name: 服务名称或 ID
    """
    try:
        # 检查服务是否存在
        service = service_scanner.get_service(service_name)
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_name}' not found"
            )
        
        success = service_manager.start_service(service_name)
        
        if success:
            return ServiceActionResponse(
                service_id=service_name,
                action="start",
                success=True,
                message=f"Service '{service_name}' started successfully"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to start service '{service_name}'"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start service {service_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start service: {str(e)}"
        )


@router.post("/services/{service_name}/stop", response_model=ServiceActionResponse)
async def stop_service(service_name: str, force: bool = False):
    """
    停止服务
    
    Args:
        service_name: 服务名称或 ID
        force: 是否强制停止
    """
    try:
        # 检查服务是否存在
        service = service_scanner.get_service(service_name)
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_name}' not found"
            )
        
        success = service_manager.stop_service(service_name, force=force)
        
        if success:
            return ServiceActionResponse(
                service_id=service_name,
                action="stop",
                success=True,
                message=f"Service '{service_name}' stopped successfully"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to stop service '{service_name}'"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop service {service_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop service: {str(e)}"
        )


@router.get("/services/{service_name}/logs", response_model=ServiceLogsResponse)
async def get_service_logs(
    service_name: str,
    tail: int = 100,
    since: str = None,
):
    """
    获取服务容器的日志（仅 Docker 模式）
    
    Args:
        service_name: 服务名称或 ID
        tail: 返回最后 N 行日志（默认 100，0 表示返回所有日志）
        since: 只显示指定时间之后的日志（格式：2023-01-01T00:00:00 或 30m、1h 等）
    
    示例：
    - 查看最后 100 行：GET /api/v1/services/spatialde/logs?tail=100
    - 查看最近 30 分钟的日志：GET /api/v1/services/spatialde/logs?since=30m
    - 查看所有日志：GET /api/v1/services/spatialde/logs?tail=0
    """
    try:
        # 检查服务是否存在
        service = service_scanner.get_service(service_name)
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_name}' not found"
            )
        
        # 获取容器日志
        logs_result = service_manager.get_container_logs(
            service_name=service_name,
            tail=tail,
            follow=False,  # API 不支持实时跟踪，使用 WebSocket 可以实现
            since=since,
        )
        
        if logs_result.get("success"):
            return ServiceLogsResponse(
                success=True,
                service_name=logs_result.get("service_name"),
                container_name=logs_result.get("container_name"),
                logs=logs_result.get("logs", ""),
                tail=logs_result.get("tail"),
                follow=logs_result.get("follow")
            )
        else:
            # 如果获取失败，返回错误信息
            error_msg = logs_result.get("error", "Unknown error")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get logs: {error_msg}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get service logs {service_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get service logs: {str(e)}"
        )

