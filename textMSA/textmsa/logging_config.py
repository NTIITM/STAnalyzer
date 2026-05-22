"""
Centralized logging configuration for the textMSA project.

This module exposes a `setup_logging` helper that either consumes a JSON/YAML
configuration file (when provided) or falls back to a sensible default format.
It also offers a lightweight `get_logger` wrapper to keep logger creation
consistent across modules.
"""

from __future__ import annotations

import json
import logging
import logging.config
import os
from pathlib import Path
from typing import Any, Dict, Optional

_LOGGING_INITIALIZED = False
DEFAULT_LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)


class ExtraFormatter(logging.Formatter):
    """
    自定义 Formatter，支持显示 extra 字段的内容。
    
    如果 LogRecord 中有 extra 字段（通过 logger.info(..., extra={...}) 传入），
    会在消息后面追加这些字段的内容。
    """
    
    def format(self, record: logging.LogRecord) -> str:
        # 先格式化基本消息
        message = super().format(record)
        
        # 检查是否有 extra 字段（除了标准字段外的自定义字段）
        # 标准字段列表
        standard_fields = {
            'name', 'msg', 'args', 'created', 'filename', 'funcName',
            'levelname', 'levelno', 'lineno', 'module', 'msecs',
            'message', 'pathname', 'process', 'processName', 'relativeCreated',
            'thread', 'threadName', 'exc_info', 'exc_text', 'stack_info',
            'asctime', 'taskName'
        }
        
        # 获取所有非标准字段
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in standard_fields:
                extra_fields[key] = value
        
        # 如果有 extra 字段，追加到消息后面
        if extra_fields:
            # 格式化 extra 字段
            extra_parts = []
            for key, value in sorted(extra_fields.items()):
                if isinstance(value, str) and (value.startswith('{') or value.startswith('[')):
                    # 如果已经是 JSON 字符串（由 format_log_extra 格式化），换行显示更易读
                    # 对于多行 JSON，使用换行和缩进
                    if '\n' in value:
                        # 多行 JSON，使用换行显示
                        extra_parts.append(f"{key}=\n{value}")
                    else:
                        # 单行 JSON，直接追加
                        extra_parts.append(f"{key}={value}")
                else:
                    # 简单类型，直接转换为字符串
                    extra_parts.append(f"{key}={value}")
            
            if extra_parts:
                # 使用换行符分隔，使多行 JSON 更易读
                message += "\n" + "\n".join(extra_parts)
        
        return message


def _get_log_level_from_env() -> int:
    """
    从环境变量获取日志级别
    
    支持的环境变量：
    - LOG_LEVEL: DEBUG/INFO/WARNING/ERROR/CRITICAL (默认: INFO)
    
    Returns:
        日志级别常量
    """
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "WARN": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    return level_map.get(level_name, logging.INFO)


def setup_logging(
    config_path: Optional[str] = None,
    default_level: Optional[int] = None,
    log_file: Optional[str] = None,
    force_reinit: bool = False,
) -> None:
    """
    Configure global logging.

    Parameters
    ----------
    config_path:
        Optional path to a JSON logging configuration file. When present and
        valid it overrides the default configuration.
    default_level:
        Fallback log level when no configuration file is provided.
        If None, will try to get from LOG_LEVEL environment variable.
        If environment variable is not set, defaults to INFO.
    log_file:
        Optional path to log file. If provided, logs will be written to this file
        in addition to console output. If not provided, will try to get from
        LOG_FILE environment variable.
    force_reinit:
        If True, force re-initialization even if logging was already configured.
        Useful when you need to update the log file path after initial setup.
    """
    global _LOGGING_INITIALIZED

    if _LOGGING_INITIALIZED and not force_reinit:
        # 如果已经初始化且没有强制重新初始化，只检查是否需要添加文件 handler
        # 同时更新所有现有 handler 的 Formatter 为 ExtraFormatter（如果还不是的话）
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            if not isinstance(handler.formatter, ExtraFormatter):
                handler.setFormatter(ExtraFormatter(DEFAULT_LOG_FORMAT))
        
        if log_file:
            # 检查是否已经有文件 handler
            has_file_handler = any(
                isinstance(h, logging.FileHandler) and h.baseFilename == str(Path(log_file).resolve())
                for h in root_logger.handlers
            )
            if not has_file_handler:
                # 添加文件 handler
                log_path = Path(log_file)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                file_handler = logging.FileHandler(log_file, encoding="utf-8")
                file_handler.setLevel(root_logger.level)
                file_handler.setFormatter(ExtraFormatter(DEFAULT_LOG_FORMAT))
                root_logger.addHandler(file_handler)
        return

    if config_path:
        config_file = Path(config_path)
        if config_file.is_file():
            with config_file.open("r", encoding="utf-8") as fh:
                config_data: Dict[str, Any] = json.load(fh)
            logging.config.dictConfig(config_data)
            _LOGGING_INITIALIZED = True
            return

    # 确定日志级别：优先使用环境变量，其次使用传入的default_level，最后使用INFO
    if default_level is None:
        log_level = _get_log_level_from_env()
    else:
        log_level = default_level

    # 确定日志文件路径：优先使用传入参数，其次使用环境变量
    if log_file is None:
        log_file = os.getenv("LOG_FILE")
    
    # 配置 handlers
    handlers = []
    
    # 控制台输出 handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(ExtraFormatter(DEFAULT_LOG_FORMAT))
    handlers.append(console_handler)
    
    # 文件输出 handler（如果指定了日志文件）
    if log_file:
        log_path = Path(log_file)
        # 确保日志目录存在
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(ExtraFormatter(DEFAULT_LOG_FORMAT))
        handlers.append(file_handler)
    
    # 配置根 logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    # 清除现有的 handlers（避免重复）
    root_logger.handlers.clear()
    for handler in handlers:
        root_logger.addHandler(handler)
    
    _LOGGING_INITIALIZED = True


def get_logger(name: str) -> logging.Logger:
    """
    Fetch a module-scoped logger, lazily ensuring logging is configured.
    """
    if not _LOGGING_INITIALIZED:
        setup_logging()
    return logging.getLogger(name)

