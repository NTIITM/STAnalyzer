"""
配置管理
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


def _bool_env(name: str, default: bool = False) -> bool:
    """读取布尔环境变量"""
    value = os.getenv(name, str(default))
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _path_env(name: str, default: Path) -> Path:
    """读取路径环境变量"""
    return Path(os.getenv(name, str(default))).expanduser().resolve()


class Config:
    """系统服务器配置"""

    BASE_DIR = Path(__file__).resolve().parent.parent
    ROOT_DIR = BASE_DIR.parent

    # 服务目录
    SERVICES_DIR = _path_env("SERVICES_DIR", BASE_DIR / "services")
    SERVICES_CONFIG_PATH = _path_env("SERVICES_CONFIG_PATH", BASE_DIR / "services_config.json")

    # API 配置
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", "9000"))

    # 日志配置
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE")

    # textMSA 项目路径 / API Server
    PROJECT_ROOT = _path_env("TEXTMSA_PROJECT_ROOT", ROOT_DIR / "textMSA")
    API_SERVER_DIR = _path_env("TEXTMSA_API_SERVER_DIR", PROJECT_ROOT / "server")
    API_SERVER_PORT = int(os.getenv("TEXTMSA_API_SERVER_PORT", os.getenv("API_SERVER_PORT", "8000")))

    # 服务运行配置
    AUTO_START_SERVICES = _bool_env("AUTO_START_SERVICES", True)
    AUTO_START_BACKGROUND = _bool_env("AUTO_START_BACKGROUND", True)
    SERVICE_RUN_MODE = os.getenv("SERVICE_RUN_MODE", os.getenv("RUN_MODE", "process")).strip().lower()
    USE_DOCKER = SERVICE_RUN_MODE == "docker"
    GENERATE_DOCKER_FILES = _bool_env("GENERATE_DOCKER_FILES", True)
    DOCKER_BUILD_ON_START = _bool_env("DOCKER_BUILD_ON_START", False)
    DOCKER_DETACH = _bool_env("DOCKER_DETACH", True)
    DOCKER_INCLUDE_SERVER = _bool_env("DOCKER_INCLUDE_SERVER", False)
    SERVICE_WAIT_READY_SECONDS = float(os.getenv("SERVICE_WAIT_READY_SECONDS", "2.0"))
    STOP_SERVICES_ON_SHUTDOWN = _bool_env("STOP_SERVICES_ON_SHUTDOWN", True)
