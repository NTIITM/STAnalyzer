"""MongoDB 连接管理"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional, Tuple

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, ConfigurationError

logger = logging.getLogger(__name__)


def get_mongodb_client(
    config_path: Optional[Path] = None,
) -> Tuple[MongoClient, str]:
    """
    创建 MongoDB 客户端
    
    Args:
        config_path: 配置文件路径，如果为 None 则使用默认配置或环境变量
    
    Returns:
        (MongoClient 实例, 数据库名称)
    
    Raises:
        ConnectionError: 无法连接到 MongoDB 服务器
    """
    # 尝试从配置文件读取
    mongodb_config = {}
    
    if config_path and config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
                mongodb_config = config.get("mongodb", {})
        except Exception as e:
            logger.warning(f"无法读取配置文件 {config_path}: {e}")
    
    # 如果配置文件中没有，尝试从环境变量读取
    if not mongodb_config:
        mongodb_config = {
            "uri": os.getenv("MONGODB_URI", "mongodb://localhost:27017/"),
            "database": os.getenv("MONGODB_DATABASE", "ligand_receptor_db"),
            "server_selection_timeout_ms": int(
                os.getenv("MONGODB_SERVER_SELECTION_TIMEOUT_MS", "5000")
            ),
            "connect_timeout_ms": int(
                os.getenv("MONGODB_CONNECT_TIMEOUT_MS", "5000")
            ),
            "socket_timeout_ms": int(
                os.getenv("MONGODB_SOCKET_TIMEOUT_MS", "30000")
            ),
            "max_pool_size": int(os.getenv("MONGODB_MAX_POOL_SIZE", "50")),
            "min_pool_size": int(os.getenv("MONGODB_MIN_POOL_SIZE", "10")),
        }
    else:
        # 使用配置文件中的值，但允许环境变量覆盖
        mongodb_config = {
            "uri": os.getenv("MONGODB_URI", mongodb_config.get("uri", "mongodb://localhost:27017/")),
            "database": os.getenv("MONGODB_DATABASE", mongodb_config.get("database", "ligand_receptor_db")),
            "server_selection_timeout_ms": int(
                os.getenv("MONGODB_SERVER_SELECTION_TIMEOUT_MS", mongodb_config.get("server_selection_timeout_ms", 5000))
            ),
            "connect_timeout_ms": int(
                os.getenv("MONGODB_CONNECT_TIMEOUT_MS", mongodb_config.get("connect_timeout_ms", 5000))
            ),
            "socket_timeout_ms": int(
                os.getenv("MONGODB_SOCKET_TIMEOUT_MS", mongodb_config.get("socket_timeout_ms", 30000))
            ),
            "max_pool_size": int(
                os.getenv("MONGODB_MAX_POOL_SIZE", mongodb_config.get("max_pool_size", 50))
            ),
            "min_pool_size": int(
                os.getenv("MONGODB_MIN_POOL_SIZE", mongodb_config.get("min_pool_size", 10))
            ),
        }
    
    try:
        client = MongoClient(
            mongodb_config["uri"],
            serverSelectionTimeoutMS=mongodb_config["server_selection_timeout_ms"],
            connectTimeoutMS=mongodb_config["connect_timeout_ms"],
            socketTimeoutMS=mongodb_config["socket_timeout_ms"],
            maxPoolSize=mongodb_config["max_pool_size"],
            minPoolSize=mongodb_config["min_pool_size"],
        )
        
        # 测试连接
        client.admin.command('ping')
        logger.info(f"成功连接到 MongoDB: {mongodb_config['uri']}")
        
        return client, mongodb_config["database"]
        
    except ConnectionFailure as e:
        logger.error(f"无法连接到 MongoDB 服务器: {e}")
        raise ConnectionError(f"无法连接到 MongoDB 服务器: {e}") from e
    except ConfigurationError as e:
        logger.error(f"MongoDB 配置错误: {e}")
        raise ConnectionError(f"MongoDB 配置错误: {e}") from e


def get_collection(
    collection_name: str = "ligand_receptor_pairs",
    config_path: Optional[Path] = None,
) -> Collection:
    """
    获取 MongoDB 集合
    
    Args:
        collection_name: 集合名称
        config_path: 配置文件路径
    
    Returns:
        MongoDB Collection 对象
    """
    client, database_name = get_mongodb_client(config_path)
    db: Database = client[database_name]
    return db[collection_name]


def init_database(config_path: Optional[Path] = None) -> None:
    """
    初始化数据库（创建集合和索引）
    
    Args:
        config_path: 配置文件路径
    """
    try:
        collection = get_collection("ligand_receptor_pairs", config_path)
        
        # 创建唯一索引（防止重复）
        try:
            collection.create_index(
                [("ligand", 1), ("receptor", 1), ("species", 1)],
                unique=True,
                name="unique_ligand_receptor_species",
            )
            logger.info("创建唯一索引: unique_ligand_receptor_species")
        except Exception as e:
            logger.warning(f"创建唯一索引失败（可能已存在）: {e}")
        
        # 创建单字段索引（提升查询性能）
        indexes = [
            ("ligand", "idx_ligand"),
            ("receptor", "idx_receptor"),
            ("species", "idx_species"),
            ("source", "idx_source"),
        ]
        
        for field, index_name in indexes:
            try:
                collection.create_index(field, name=index_name)
                logger.info(f"创建索引: {index_name}")
            except Exception as e:
                logger.warning(f"创建索引 {index_name} 失败（可能已存在）: {e}")
        
        logger.info("数据库初始化完成")
        
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise

