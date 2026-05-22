#!/usr/bin/env python3
"""
textMSA API 服务器主应用
使用统一配置管理（.env + config.json）
"""
from __future__ import annotations

import os
import sys
import warnings
import fcntl
import time
from contextlib import asynccontextmanager
from pathlib import Path

# 过滤 anndata 库的 FutureWarning（已弃用的导入方式）
# 这些警告来自 anndata 库内部，不影响功能，但会在启动时显示
warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    module="anndata.utils"
)

# 添加项目根目录到 Python 路径
APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
except Exception as e:
    raise SystemExit("FastAPI is required: pip install fastapi uvicorn")

# 导入统一配置
from textmsa.settings import get_server_config, get_system_server_config
from textmsa.logging_config import setup_logging, get_logger

# 导入 httpx 用于 ping 检查
import httpx

# 导入中间件
try:
    from textmsa.services.api.middleware import RequestLoggingMiddleware
except ImportError as e:
    print(f"Warning: Request logging middleware not available: {e}")
    RequestLoggingMiddleware = None

# 导入API路由模块
try:
    from textmsa.services.api.routers import (
        user_router,
        file_router,
        file_type_router,
        analysis_router,
        spatial_router,
        service_router,
        knowledge_router,
        project_router,
        visualization_router,
        agent_router,
    )
    HAS_API_ROUTES = True
except ImportError as e:
    print(f"Warning: API routes not available: {e}")
    HAS_API_ROUTES = False
    from fastapi import APIRouter
    user_router = APIRouter()
    file_router = APIRouter()
    file_type_router = APIRouter()
    analysis_router = APIRouter()
    spatial_router = APIRouter()
    service_router = APIRouter()
    knowledge_router = APIRouter()
    project_router = APIRouter()
    visualization_router = APIRouter()
    agent_router = APIRouter()

# 项目信息
VERSION = "2.0.0"
TITLE = "textMSA API"
DESCRIPTION = """
textMSA 多组学分析系统 API

## 功能模块

### 1. 用户管理 (`/api/user`)
用户注册、登录和信息管理
- 用户注册
- 用户登录（JWT认证）
- 获取用户信息

### 2. 文件管理 (`/api/file`)
文件上传、下载和管理
- 文件上传（支持用户隔离）
- 文件列表查询
- 文件详情查看
- 文件删除

### 3. 分析流程 (`/api/analysis`)
文件分析流程树形结构管理
- 获取文件分析流程树
- 获取文件节点详情
- 获取算法详情
- 更新算法执行状态

## 配置

配置优先级：
1. 环境变量（最高优先级）
2. .env 文件（项目根目录）
3. config.json（textmsa/config/config.json）

## 架构

- **前端**: Vue 3 + Vite
- **API**: FastAPI + Uvicorn
- **数据库**: MongoDB
- **存储**: 可配置的存储路径

## 文档

- OpenAPI 文档: `/docs`
- ReDoc: `/redoc`
"""

# 初始化日志（import 阶段也写入文件，适配 uvicorn 直接加载 app 对象的场景）
_env_log_file = os.getenv("LOG_FILE")
if not _env_log_file:
    _env_log_file = str(APP_ROOT / "logs" / "api_server.log")
# force_reinit 确保在重复 import 时也能补充文件 handler
setup_logging(log_file=_env_log_file, force_reinit=True)

# 获取 logger（用于启动事件）
logger = get_logger(__name__)


async def ping_system_server(system_server_url: str, timeout: float = 5.0) -> bool:
    """
    检查 system_server 是否可连接
    
    Args:
        system_server_url: system_server 的 URL
        timeout: 超时时间（秒）
    
    Returns:
        True 如果连接成功，False 如果连接失败
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # 尝试访问健康检查端点或根端点
            health_url = f"{system_server_url.rstrip('/')}/health"
            response = await client.get(health_url)
            response.raise_for_status()
            return True
    except httpx.TimeoutException:
        logger.error(f"Timeout while pinging system_server: {system_server_url}")
        return False
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error while pinging system_server: {e.response.status_code} - {system_server_url}")
        return False
    except httpx.ConnectError as e:
        logger.error(f"Connection error while pinging system_server: {system_server_url} - {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error while pinging system_server: {system_server_url} - {e}")
        return False


async def register_system_services():
    """
    从 system_server 注册系统服务到数据库
    
    使用文件锁确保多个 worker 中只有一个执行注册操作
    """
    lock_file_path = APP_ROOT / "logs" / ".system_service_registration.lock"
    lock_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 尝试获取文件锁（非阻塞）
    try:
        lock_file = open(lock_file_path, 'w')
        try:
            # 尝试获取排他锁（非阻塞）
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            logger.info("Acquired lock for system service registration")
        except IOError:
            # 锁已被其他进程持有，跳过注册
            lock_file.close()
            logger.info("Another worker is already registering system services, skipping...")
            return
    except Exception as e:
        logger.warning(f"Failed to acquire lock for system service registration: {e}")
        # 如果获取锁失败，仍然尝试注册（向后兼容）
        lock_file = None
    
    try:
        # 从配置获取 system_server 配置
        config = get_system_server_config()
        system_server_url = config.get("url", "http://localhost:9000")
        
        # 检查是否启用服务注册
        enable_registration = config.get("enable_registration", True)
        if not enable_registration:
            logger.info("System service registration is disabled")
            return
        
        # 在注册前先 ping 检查连接
        ping_timeout = min(config.get("timeout", 10.0), 5.0)  # ping 使用较短的超时时间
        logger.info(f"Pinging system_server at {system_server_url}...")
        if not await ping_system_server(system_server_url, timeout=ping_timeout):
            logger.error(f"Failed to connect to system_server at {system_server_url}. Skipping service registration.")
            logger.warning("Server will continue to start without system services. They can be registered manually later.")
            return
        
        logger.info(f"Successfully connected to system_server. Registering system services from {system_server_url}...")
        
        # 创建注册器并同步服务
        from textmsa.services.system_service_registrar import SystemServiceRegistrar
        registrar = SystemServiceRegistrar(
            system_server_url=system_server_url,
            timeout=config.get("timeout", 10.0)
        )
        created_services = await registrar.synchronise_services()
        
        logger.info(f"Successfully registered {len(created_services)} system services: {created_services}")
        
    except Exception as e:
        # 服务注册失败不应阻止服务器启动
        logger.error(f"Failed to register system services: {e}", exc_info=True)
        logger.warning("Server will continue to start without system services. They can be registered manually later.")
    finally:
        # 释放锁
        if lock_file:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                lock_file.close()
                logger.info("Released lock for system service registration")
            except Exception as e:
                logger.warning(f"Failed to release lock: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    替代已弃用的 on_event 装饰器
    """
    # 启动时执行
    logger.info("Starting textMSA server...")
    await register_system_services()
    yield
    # 关闭时执行（如果需要）
    logger.info("Shutting down textMSA server...")


# 创建应用
app = FastAPI(
    title=TITLE,
    description=DESCRIPTION,
    version=VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS 中间件（暂时禁用）
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # 生产环境应限制
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# 请求日志中间件（暂时禁用）
# if RequestLoggingMiddleware is not None:
#     app.add_middleware(RequestLoggingMiddleware)

# 注册API路由
if HAS_API_ROUTES:
    app.include_router(user_router)
    app.include_router(file_router)
    app.include_router(file_type_router)
    app.include_router(analysis_router)
    app.include_router(spatial_router)
    app.include_router(service_router)
    app.include_router(knowledge_router)
    app.include_router(project_router)
    app.include_router(visualization_router)
    app.include_router(agent_router)


@app.get("/", tags=["Root"])
async def root():
    """
    根端点 - 返回 API 基本信息
    """
    return {
        "message": "textMSA API Server",
        "version": VERSION,
        "status": "running",
        "docs": "/docs",
        "modules": {
            "user": "/api/user",
            "file": "/api/file",
            "file_type": "/api/file-types",
            "analysis": "/api/analysis",
            "spatial": "/api/spatial",
            "service": "/api/service",
            "knowledge": "/api/knowledge",
            "project": "/api/project",
            "visualization": "/api/visualization",
            "agent": "/api/agent",
        }
    }


@app.get("/health", tags=["Root"])
async def health_check():
    """
    健康检查端点
    """
    return {
        "status": "healthy",
        "version": VERSION,
        "service": "textmsa-api"
    }


@app.get("/api/system-services/status", tags=["System Services"])
async def system_services_status():
    """
    检查系统服务注册状态
    """
    try:
        config = get_system_server_config()
        system_server_url = config.get("url", "http://localhost:9000")
        
        from textmsa.services.system_service_registrar import SystemServiceRegistrar
        registrar = SystemServiceRegistrar(
            system_server_url=system_server_url,
            timeout=config.get("timeout", 10.0)
        )
        services = await registrar.fetch_services()
        
        # 检查数据库中的系统服务数量
        from textmsa.services.service.service_service import get_service_service
        from textmsa.services.data.mongodb_models import ServiceVisibility
        
        service_service = get_service_service()
        db_services = list(service_service.services_collection.find(
            {"visibility": ServiceVisibility.SYSTEM.value}
        ))
        
        return {
            "system_server_url": system_server_url,
            "system_server_available": True,
            "services_in_system_server": len(services),
            "services_in_database": len(db_services),
            "synchronised": len(services) == len(db_services),
            "db_service_ids": [s["service_id"] for s in db_services]
        }
    except Exception as e:
        logger.error(f"Failed to check system services status: {e}", exc_info=True)
        system_server_url = get_system_server_config().get("url", "unknown")
        return {
            "system_server_url": system_server_url,
            "system_server_available": False,
            "error": str(e)
        }


@app.get("/api/system-services/diagnose", tags=["System Services"])
async def diagnose_system_server():
    """
    诊断 system_server 的健康状态和响应能力
    
    检查：
    - 端口是否在监听
    - 连接是否可建立
    - 健康检查端点是否可用
    - /api/v1/services 端点是否响应
    """
    try:
        config = get_system_server_config()
        system_server_url = config.get("url", "http://localhost:9000")
        
        from textmsa.services.system_service_registrar import SystemServiceRegistrar
        registrar = SystemServiceRegistrar(
            system_server_url=system_server_url,
            timeout=config.get("timeout", 10.0)
        )
        diagnosis = await registrar.diagnose_system_server()
        
        return {
            "success": True,
            "diagnosis": diagnosis
        }
    except Exception as e:
        logger.error(f"Failed to diagnose system_server: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "diagnosis": {
                "system_server_url": get_system_server_config().get("url", "unknown"),
                "error": str(e)
            }
        }


@app.post("/api/system-services/sync", tags=["System Services"])
async def sync_system_services():
    """
    手动触发系统服务同步
    """
    try:
        from fastapi import HTTPException
        config = get_system_server_config()
        system_server_url = config.get("url", "http://localhost:9000")
        
        logger.info(f"Manual system service sync triggered from {system_server_url}...")
        
        from textmsa.services.system_service_registrar import SystemServiceRegistrar
        registrar = SystemServiceRegistrar(
            system_server_url=system_server_url,
            timeout=config.get("timeout", 10.0)
        )
        created_services = await registrar.synchronise_services()
        
        return {
            "success": True,
            "message": f"Successfully synchronised {len(created_services)} services",
            "services": created_services
        }
    except Exception as e:
        logger.error(f"Failed to sync system services: {e}", exc_info=True)
        from fastapi import HTTPException
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync system services: {str(e)}"
        )


def main():
    """主函数 - 启动服务器"""
    import uvicorn
    
    # 从统一配置获取服务器设置
    server_config = get_server_config()
    host = server_config["host"]
    port = server_config["port"]
    workers = server_config.get("workers")
    reload = server_config.get("reload", True)
    dev_mode = server_config.get("dev_mode", False)
    
    # 配置日志文件（环境变量优先，默认写入项目 logs/api_server.log）
    log_file = os.getenv("LOG_FILE")
    if not log_file:
        log_file = str(APP_ROOT / "logs" / "api_server.log")
    
    # 重新配置日志（控制台 + 文件）
    setup_logging(log_file=log_file)
    
    # 获取 logger 并记录启动信息
    logger = get_logger(__name__)
    logger.info("=" * 60)
    logger.info("textMSA API Server 正在启动...")
    logger.info(f"版本: {VERSION}")
    logger.info(f"主机: {host}")
    logger.info(f"端口: {port}")
    logger.info(f"开发模式: {'是' if dev_mode else '否'}")
    if workers:
        logger.info(f"工作进程数: {workers} (多进程模式)")
    else:
        logger.info("工作进程数: 1 (单进程模式)")
    logger.info(f"热更新: {'启用' if reload else '禁用'}")
    logger.info(f"日志文件: {log_file}")
    logger.info("=" * 60)

    mode_str = f"{workers} workers" if workers else "Single process"
    dev_str = "Development" if dev_mode else "Production"
    reload_str = "Enabled" if reload else "Disabled"
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║                    textMSA API Server                     ║
╠═══════════════════════════════════════════════════════════╣
║  Version: {VERSION:<48}║
║  Host:    {host:<48}║
║  Port:    {port:<48}║
║  Mode:    {mode_str:<48}║
║  Dev Mode: {dev_str:<46}║
║  Reload:   {reload_str:<46}║
╠═══════════════════════════════════════════════════════════╣
║  API Docs:  http://{host}:{port}/docs{' ':<28}║
║  Health:    http://{host}:{port}/health{' ':<26}║
║  Log File:  {"Disabled (Console only)":<43}║
╚═══════════════════════════════════════════════════════════╝
    """)
    
    # 配置 uvicorn 日志（只输出到控制台，不写入文件）
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "root": {
            "level": "INFO",
            "handlers": ["default"],
        },
        "loggers": {
            "uvicorn": {
                "level": "INFO",
                "handlers": ["default"],
                "propagate": False,
            },
            "uvicorn.error": {
                "level": "INFO",
                "handlers": ["default"],
                "propagate": False,
            },
            "uvicorn.access": {
                "level": "INFO",
                "handlers": ["default"],
                "propagate": False,
            },
        },
    }
    
    logger.info("启动 Uvicorn 服务器...")
    
    # 构建 uvicorn.run 参数
    uvicorn_kwargs = {
        "app": "server.app:app",
        "host": host,
        "port": port,
        "reload": reload,  # 根据 dev_mode 自动设置
        "log_config": log_config,
    }
    
    # 如果配置了 workers，则添加 workers 参数（多进程模式）
    if workers:
        uvicorn_kwargs["workers"] = workers
        logger.info(f"使用多进程模式，启动 {workers} 个工作进程")
    else:
        logger.info("使用单进程模式")
        # 开发模式下，配置热更新相关参数
        if reload:
            # 设置热更新监控的目录
            uvicorn_kwargs["reload_dirs"] = [
                str(APP_ROOT / "server"),
                str(APP_ROOT / "textmsa"),
            ]
            # 排除不需要监控的目录
            uvicorn_kwargs["reload_excludes"] = [
                "*.pyc",
                "*.pyo",
                "__pycache__",
                "*.log",
                ".git",
                "node_modules",
            ]
            logger.info("热更新已启用，监控代码变更")
    
    uvicorn.run(**uvicorn_kwargs)


if __name__ == "__main__":
    main()
