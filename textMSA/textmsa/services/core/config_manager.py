"""
统一配置管理
仅从config.json读取配置，不考虑环境变量
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional
from functools import lru_cache


class ConfigError(RuntimeError):
    """配置错误"""
    pass


class UnifiedConfig:
    """统一配置管理器"""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径（可选，默认使用textmsa/config/config.json）
        """
        self._config_cache: Optional[Dict[str, Any]] = None
        self._config_path = config_path or self._get_default_config_path()
        self._load_config()
    
    def _get_default_config_path(self) -> Path:
        """获取默认配置文件路径"""
        # 从textmsa/services/core/config_manager.py的位置计算
        # services/core -> services -> textmsa -> textmsa/config/config.json
        package_root = Path(__file__).resolve().parent.parent.parent
        config_file = package_root / "config" / "config.json"
        return config_file
    
    def _load_config(self):
        """从config.json加载配置"""
        if not self._config_path.exists():
            raise ConfigError(f"配置文件不存在: {self._config_path}")
        
        try:
            with self._config_path.open("r", encoding="utf-8") as f:
                self._config_cache = json.load(f)
            
            if not isinstance(self._config_cache, dict):
                raise ConfigError("config.json顶层必须为对象")
        except json.JSONDecodeError as e:
            raise ConfigError(f"JSON配置解析失败: {e}")
        except Exception as e:
            raise ConfigError(f"无法加载配置文件: {e}")
    
    def get(self, section: str, key: Optional[str] = None, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            section: 配置节名称
            key: 配置键名称（可选）
            default: 默认值
        
        Returns:
            配置值
        """
        if self._config_cache is None:
            self._load_config()
        
        if key is None:
            return self._config_cache.get(section, default)
        
        section_config = self._config_cache.get(section, {})
        if not isinstance(section_config, dict):
            return default
        
        return section_config.get(key, default)
    
    def reload(self):
        """重新加载配置"""
        self._config_cache = None
        self._load_config()


# 全局配置实例
_config_instance: Optional[UnifiedConfig] = None


@lru_cache(maxsize=1)
def get_config() -> UnifiedConfig:
    """获取全局配置实例"""
    global _config_instance
    if _config_instance is None:
        _config_instance = UnifiedConfig()
    return _config_instance


def reload_config():
    """重新加载配置"""
    global _config_instance
    if _config_instance:
        _config_instance.reload()
    else:
        _config_instance = UnifiedConfig()
    get_config.cache_clear()
