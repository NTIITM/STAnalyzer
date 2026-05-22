"""数据加载器（支持内存缓存）"""
from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

from database.db_connection import get_collection
from database.ligand_receptor import (
    get_ligand_receptor_pairs,
    filter_available_pairs,
    get_ligand_target_network as _get_ligand_target_network,
    get_ligand_set as _get_ligand_set,
)

logger = logging.getLogger(__name__)


def _estimate_memory_size_mb(data: List[Dict]) -> float:
    """
    估算数据在内存中的大小（MB）
    
    Args:
        data: 数据列表
    
    Returns:
        估算的内存大小（MB）
    """
    if not data:
        return 0.0
    
    # 简单估算：每个字典约 500 字节
    # 实际大小可能因字段数量和内容而异
    estimated_bytes = len(data) * 500
    return estimated_bytes / (1024 * 1024)  # 转换为 MB


class LigandReceptorCache:
    """配体-受体数据内存缓存"""
    
    def __init__(self, max_memory_gb: float = 5.0):
        """
        初始化缓存
        
        Args:
            max_memory_gb: 最大内存使用量（GB），默认 5.0 GB
        """
        self.max_memory_gb = max_memory_gb
        self._cache: Optional[List[Dict]] = None
        self._cache_size_mb: float = 0.0
        self._species_filter: Optional[str] = None
        self._source_filter: Optional[str] = None
        self._config_path: Optional[str] = None
    
    def load_from_database(
        self,
        species: Optional[str] = None,
        source: Optional[str] = None,
        config_path: Optional[str] = None,
    ) -> bool:
        """
        从数据库加载数据到内存
        
        Args:
            species: 物种过滤
            source: 数据源过滤
            config_path: 配置文件路径
        
        Returns:
            True 如果成功加载到内存，False 如果数据太大
        """
        try:
            # 先查询一次，估算数据大小
            logger.info("正在从数据库加载数据...")
            pairs = get_ligand_receptor_pairs(
                species=species,
                source=source,
                config_path=config_path,
            )
            
            # 估算内存大小
            estimated_size_mb = _estimate_memory_size_mb(pairs)
            estimated_size_gb = estimated_size_mb / 1024.0
            
            logger.info(f"估算数据大小: {estimated_size_mb:.2f} MB ({estimated_size_gb:.2f} GB)")
            
            # 检查是否超过限制
            if estimated_size_gb > self.max_memory_gb:
                logger.warning(
                    f"数据大小 ({estimated_size_gb:.2f} GB) 超过限制 ({self.max_memory_gb} GB)，"
                    "将使用数据库查询而非内存缓存"
                )
                return False
            
            # 加载到内存
            self._cache = pairs
            self._cache_size_mb = estimated_size_mb
            self._species_filter = species
            self._source_filter = source
            self._config_path = config_path
            
            logger.info(
                f"成功加载 {len(pairs)} 条记录到内存缓存 "
                f"({estimated_size_mb:.2f} MB)"
            )
            return True
            
        except Exception as e:
            logger.error(f"从数据库加载数据失败: {e}")
            return False
    
    def get_pairs(
        self,
        species: Optional[str] = None,
        available_genes: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        获取配体-受体对
        
        如果内存缓存可用且过滤条件匹配，从缓存获取；否则查询数据库
        
        Args:
            species: 物种过滤（如果与缓存时的过滤条件不同，会查询数据库）
            available_genes: 可用基因列表（用于过滤）
        
        Returns:
            配体-受体对列表
        """
        # 如果缓存可用且过滤条件匹配，使用缓存
        if (
            self._cache is not None
            and species == self._species_filter
        ):
            pairs = self._cache
        else:
            # 查询数据库
            pairs = get_ligand_receptor_pairs(
                species=species,
                source=self._source_filter,
                config_path=self._config_path,
            )
        
        # 如果提供了可用基因列表，进行过滤
        if available_genes:
            available_genes_set = {gene.upper() for gene in available_genes}
            pairs = [
                pair
                for pair in pairs
                if pair.get("ligand", "").upper() in available_genes_set
                and pair.get("receptor", "").upper() in available_genes_set
            ]
        
        return pairs
    
    def get_ligand_target_network(
        self,
        species: Optional[str] = None,
    ) -> Dict[str, List[str]]:
        """
        获取配体-靶基因网络（用于 NicheNet）
        
        如果内存缓存可用且过滤条件匹配，从缓存获取；否则查询数据库
        
        Args:
            species: 物种过滤（如果与缓存时的过滤条件不同，会查询数据库）
        
        Returns:
            字典，键为配体基因名，值为靶基因（受体）列表
        """
        # 如果缓存可用且过滤条件匹配，使用缓存
        if (
            self._cache is not None
            and species == self._species_filter
        ):
            # 从缓存构建网络
            network: Dict[str, List[str]] = {}
            for pair in self._cache:
                ligand = pair.get("ligand", "").upper()
                receptor = pair.get("receptor", "").upper()
                
                if ligand and receptor:
                    if ligand not in network:
                        network[ligand] = []
                    if receptor not in network[ligand]:
                        network[ligand].append(receptor)
            
            return network
        else:
            # 查询数据库
            return _get_ligand_target_network(
                species=species,
                source=self._source_filter,
                config_path=self._config_path,
            )
    
    def get_ligand_set(
        self,
        species: Optional[str] = None,
    ) -> List[str]:
        """
        获取配体列表（用于 MISTY）
        
        如果内存缓存可用且过滤条件匹配，从缓存获取；否则查询数据库
        
        Args:
            species: 物种过滤（如果与缓存时的过滤条件不同，会查询数据库）
        
        Returns:
            配体基因名列表（去重，大写）
        """
        # 如果缓存可用且过滤条件匹配，使用缓存
        if (
            self._cache is not None
            and species == self._species_filter
        ):
            # 从缓存提取配体
            ligands = {
                pair.get("ligand", "").upper()
                for pair in self._cache
                if pair.get("ligand")
            }
            return sorted(list(ligands))
        else:
            # 查询数据库
            return _get_ligand_set(
                species=species,
                source=self._source_filter,
                config_path=self._config_path,
            )
    
    def clear_cache(self) -> None:
        """清空内存缓存"""
        self._cache = None
        self._cache_size_mb = 0.0
        logger.info("内存缓存已清空")
    
    def clear(self) -> None:
        """清空内存缓存（别名方法）"""
        self.clear_cache()
    
    def is_cached(self) -> bool:
        """检查是否有内存缓存"""
        return self._cache is not None
    
    def get_cache_info(self) -> Dict:
        """
        获取缓存信息
        
        Returns:
            包含缓存状态的字典
        """
        return {
            "cached": self.is_cached(),
            "cache_size_mb": self._cache_size_mb,
            "cache_count": len(self._cache) if self._cache else 0,
            "max_memory_gb": self.max_memory_gb,
            "species_filter": self._species_filter,
            "source_filter": self._source_filter,
        }


# 全局缓存实例（可选）
_global_cache: Optional[LigandReceptorCache] = None


def get_global_cache(max_memory_gb: Optional[float] = None) -> LigandReceptorCache:
    """
    获取全局缓存实例（单例模式）
    
    Args:
        max_memory_gb: 最大内存使用量（GB），如果为 None 则从环境变量读取
    
    Returns:
        全局缓存实例
    """
    global _global_cache
    
    if _global_cache is None:
        if max_memory_gb is None:
            max_memory_gb = float(os.getenv("LR_MAX_MEMORY_GB", "5.0"))
        _global_cache = LigandReceptorCache(max_memory_gb=max_memory_gb)
    
    return _global_cache

