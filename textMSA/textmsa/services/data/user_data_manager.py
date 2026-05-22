"""
用户数据管理器
负责管理用户相关的数据：上传的文件列表、对话记录、中间文件等
使用 JSON 文件存储，后续可迁移到 MySQL/NoSQL
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from threading import Lock

from textmsa.logging_config import get_logger

logger = get_logger(__name__)


class UserDataManager:
    """用户数据管理器，使用 JSON 文件存储用户数据"""
    
    def __init__(self, data_dir: Optional[str] = None):
        """
        初始化用户数据管理器
        
        Args:
            data_dir: 数据存储目录，默认为项目根目录下的 data/users/
        """
        # 默认使用项目根目录下的 data/users
        project_root = Path(__file__).parent.parent.parent
        
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = project_root / "data" / "users"
        
        # 创建目录
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 线程锁，确保并发安全
        self._lock = Lock()
        
        # 内存缓存 (user_id -> user_data)
        self._cache: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"UserDataManager 初始化完成:")
        logger.info(f"  数据目录: {self.data_dir}")
    
    def _get_user_file_path(self, user_id: str) -> Path:
        """获取用户数据文件路径"""
        safe_user_id = self._sanitize_user_id(user_id)
        return self.data_dir / f"{safe_user_id}.json"
    
    def _sanitize_user_id(self, user_id: str) -> str:
        """清理用户ID，确保文件名安全"""
        user_id = user_id.strip()[:100]
        safe = []
        for ch in user_id:
            if ch.isalnum() or ch in ("_", "-", "."):
                safe.append(ch)
            else:
                safe.append("_")
        return "".join(safe) or "anonymous"
    
    def _load_user_data(self, user_id: str) -> Dict[str, Any]:
        """从文件加载用户数据（带缓存）"""
        with self._lock:
            # 检查缓存
            if user_id in self._cache:
                return self._cache[user_id].copy()
            
            # 从文件加载
            user_file = self._get_user_file_path(user_id)
            
            if user_file.exists():
                try:
                    with open(user_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    # 更新缓存
                    self._cache[user_id] = data.copy()
                    return data
                except Exception as e:
                    logger.error(f"加载用户数据失败 {user_id}: {e}")
                    return self._get_default_user_data(user_id)
            else:
                # 创建默认数据
                default_data = self._get_default_user_data(user_id)
                self._save_user_data(user_id, default_data)
                return default_data
    
    def _save_user_data(self, user_id: str, data: Dict[str, Any]) -> bool:
        """保存用户数据到文件"""
        try:
            user_file = self._get_user_file_path(user_id)
            
            # 更新最后修改时间
            data["updated_at"] = datetime.now().isoformat()
            
            # 保存到文件
            with open(user_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # 更新缓存
            self._cache[user_id] = data.copy()
            
            logger.debug(f"用户数据已保存: {user_id}")
            return True
        except Exception as e:
            logger.error(f"保存用户数据失败 {user_id}: {e}")
            return False
    
    def _get_default_user_data(self, user_id: str) -> Dict[str, Any]:
        """获取默认用户数据结构"""
        return {
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "files": []
        }
    
    # ============= 用户文件管理 =============
    
    def add_file(self, user_id: str, file_id: str, filename: str, file_path: str, 
                 file_info: Optional[Dict[str, Any]] = None) -> bool:
        """
        添加用户上传的文件
        
        Args:
            user_id: 用户ID
            file_id: 文件ID
            filename: 文件名
            file_path: 文件路径
            file_info: 额外文件信息（如 n_spots, n_genes 等）
        
        Returns:
            是否成功
        """
        with self._lock:
            data = self._load_user_data(user_id)
            
            # 检查文件是否已存在
            for file_item in data["files"]:
                if file_item.get("file_id") == file_id:
                    logger.warning(f"文件已存在: {user_id}/{file_id}")
                    return False
            
            # 添加新文件
            file_item = {
                "file_id": file_id,
                "filename": filename,
                "file_path": file_path,
                "upload_time": datetime.now().isoformat(),
                "last_viewed_time": datetime.now().isoformat(),
                "analysis_status": "uploaded",  # uploaded, processing, completed, error
                "metadata": file_info or {}
            }
            
            data["files"].append(file_item)
            return self._save_user_data(user_id, data)
    
    def get_user_files(self, user_id: str) -> List[Dict[str, Any]]:
        """
        获取用户的所有文件列表
        
        Args:
            user_id: 用户ID
        
        Returns:
            文件列表
        """
        data = self._load_user_data(user_id)
        return data.get("files", [])
    
    def get_file_info(self, user_id: str, file_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定文件的信息
        
        Args:
            user_id: 用户ID
            file_id: 文件ID
        
        Returns:
            文件信息，如果不存在返回 None
        """
        files = self.get_user_files(user_id)
        for file_item in files:
            if file_item.get("file_id") == file_id:
                return file_item
        return None
    
    def delete_file(self, user_id: str, file_id: str) -> bool:
        """
        删除用户文件（从数据记录中删除，不删除物理文件）
        
        Args:
            user_id: 用户ID
            file_id: 文件ID
        
        Returns:
            是否成功
        """
        with self._lock:
            data = self._load_user_data(user_id)
            
            # 移除文件
            original_count = len(data["files"])
            data["files"] = [
                f for f in data["files"]
                if f.get("file_id") != file_id
            ]
            
            if len(data["files"]) < original_count:
                return self._save_user_data(user_id, data)
            return False
    
    def update_file_view_time(self, user_id: str, file_id: str) -> bool:
        """
        更新文件最后查看时间
        
        Args:
            user_id: 用户ID
            file_id: 文件ID
        
        Returns:
            是否成功
        """
        with self._lock:
            data = self._load_user_data(user_id)
            
            for file_item in data["files"]:
                if file_item.get("file_id") == file_id:
                    file_item["last_viewed_time"] = datetime.now().isoformat()
                    return self._save_user_data(user_id, data)
            return False
    
    def update_file_status(self, user_id: str, file_id: str, status: str) -> bool:
        """
        更新文件分析状态
        
        Args:
            user_id: 用户ID
            file_id: 文件ID
            status: 状态 (uploaded, processing, completed, error)
        
        Returns:
            是否成功
        """
        with self._lock:
            data = self._load_user_data(user_id)
            
            for file_item in data["files"]:
                if file_item.get("file_id") == file_id:
                    file_item["analysis_status"] = status
                    return self._save_user_data(user_id, data)
            return False
    
    def update_file_metadata(self, user_id: str, file_id: str, metadata: Dict[str, Any]) -> bool:
        """
        更新文件元数据
        
        Args:
            user_id: 用户ID
            file_id: 文件ID
            metadata: 元数据字典
        
        Returns:
            是否成功
        """
        with self._lock:
            data = self._load_user_data(user_id)
            
            for file_item in data["files"]:
                if file_item.get("file_id") == file_id:
                    file_item["metadata"].update(metadata)
                    return self._save_user_data(user_id, data)
            return False
    
    # ============= 用户数据清理 =============
    
    def clear_cache(self, user_id: Optional[str] = None):
        """清理缓存"""
        with self._lock:
            if user_id:
                self._cache.pop(user_id, None)
            else:
                self._cache.clear()


# 全局用户数据管理器实例
_user_data_manager: Optional[UserDataManager] = None


def get_user_data_manager() -> UserDataManager:
    """获取全局用户数据管理器实例"""
    global _user_data_manager
    if _user_data_manager is None:
        _user_data_manager = UserDataManager()
    return _user_data_manager

