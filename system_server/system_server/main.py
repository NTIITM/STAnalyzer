"""
system_server 主应用
"""
import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from system_server.api.routes import router, service_manager, service_scanner
from system_server.config import Config

# 配置日志
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="System Server",
    description="系统服务管理和 API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(router, prefix="/api/v1")


def _prepare_services_sync() -> None:
    """同步执行服务扫描、端口分配和启动流程"""
    generate_docker_files = Config.GENERATE_DOCKER_FILES or Config.USE_DOCKER
    logger.info(
        "Preparing services (generate_docker=%s, run_mode=%s)",
        generate_docker_files,
        Config.SERVICE_RUN_MODE,
    )

    service_manager.process_all_services(
        generate_docker=generate_docker_files,
        output_config_path=Config.SERVICES_CONFIG_PATH,
    )
    service_scanner.clear_cache()

    if Config.USE_DOCKER:
        logger.info("Starting services via Docker Compose")
        service_manager.start_all_services_docker(
            build=Config.DOCKER_BUILD_ON_START,
            detach=Config.DOCKER_DETACH,
            extra_args=None,
            include_server=Config.DOCKER_INCLUDE_SERVER,
        )
    else:
        logger.info(
            "Starting services as local processes (background=%s)",
            Config.AUTO_START_BACKGROUND,
        )
        service_manager.start_all_services(background=Config.AUTO_START_BACKGROUND)


def _stop_services_sync(force: bool = False) -> None:
    """同步执行服务停止流程"""
    if Config.USE_DOCKER:
        logger.info("Stopping services via docker stop")
        service_manager.stop_all_services_docker(
            remove_volumes=False,
            extra_args=None,
            include_server=Config.DOCKER_INCLUDE_SERVER,
        )
    else:
        logger.info("Stopping local service processes (force=%s)", force)
        service_manager.stop_all_services(force=force)


@app.on_event("startup")
async def startup_event():
    """应用启动时自动启动所有服务"""
    if not Config.AUTO_START_SERVICES:
        logger.info("AUTO_START_SERVICES disabled, skipping auto-start")
        return

    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, _prepare_services_sync)
        logger.info("All services prepared and started successfully")
    except Exception as exc:  # pragma: no cover - startup should keep running
        logger.error("Failed to auto-start services: %s", exc, exc_info=True)


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时可选地停止所有服务"""
    if not Config.STOP_SERVICES_ON_SHUTDOWN:
        logger.info("STOP_SERVICES_ON_SHUTDOWN disabled, skipping service stop")
        return

    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, _stop_services_sync)
        logger.info("All services stopped successfully")
    except Exception as exc:  # pragma: no cover - shutdown best-effort
        logger.error("Failed to stop services gracefully: %s", exc, exc_info=True)

@app.get("/health")
async def health():
    """健康检查"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "service": "system-server"
    }

@app.get("/")
async def root():
    """根端点"""
    return {
        "message": "System Server API",
        "version": "1.0.0",
        "docs": "/docs",
        "api": "/api/v1"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=Config.API_HOST,
        port=Config.API_PORT
    )

