"""
文件管理服务
负责处理上传文件的存储和管理
使用配置文件管理存储路径
"""
import os
import shutil
import uuid
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from textmsa.logging_config import get_logger
from textmsa.settings import get_storage_config

logger = get_logger(__name__)


class FileManager:
    """文件管理器，处理上传文件和结果文件的存储"""
    
    def __init__(self, upload_dir: Optional[str] = None, output_dir: Optional[str] = None):
        """
        初始化文件管理器
        
        Args:
            upload_dir: 上传文件存储目录（可选，优先使用配置）
            output_dir: 结果文件存储目录（可选，优先使用配置）
        """
        # 从配置文件读取存储路径
        storage_config = get_storage_config()
        
        # 优先使用传入参数，然后使用配置文件
        if upload_dir:
            self.upload_dir = Path(upload_dir)
        else:
            self.upload_dir = Path(storage_config["upload_dir"])
        
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path(storage_config["output_dir"])
        
        # 创建目录（如果不存在）
        try:
            self.upload_dir.mkdir(parents=True, exist_ok=True)
            self.output_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"存储目录已创建或已存在")
        except PermissionError as e:
            logger.error(f"创建存储目录失败（权限不足）: {e}")
            raise
        except Exception as e:
            logger.error(f"创建存储目录失败: {e}")
            raise
        
        # 存储文件信息 (file_id -> file_info)
        self.uploaded_files: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"FileManager 初始化完成:")
        logger.info(f"  上传目录: {self.upload_dir}")
        logger.info(f"  输出目录: {self.output_dir}")
    
    def save_uploaded_file(self, file_obj, filename: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        保存上传的文件
        
        Args:
            file_obj: 文件对象（FastAPI的UploadFile或其他类型）
            filename: 原始文件名
            user_id: 用户ID（可选）
            
        Returns:
            dict: 包含保存路径和文件信息
        """
        # 生成唯一ID和文件名（不使用时间戳前缀）
        file_id = str(uuid.uuid4())
        ext = Path(filename).suffix
        
        # 如果提供了 user_id，保存到用户子目录
        if user_id:
            save_dir = self.upload_dir / user_id
            save_dir.mkdir(parents=True, exist_ok=True)
        else:
            save_dir = self.upload_dir
        
        # 保存文件（使用原始文件名，如果冲突则添加UUID后缀）
        original_stem = Path(filename).stem
        saved_filename = f"{original_stem}_{file_id[:8]}{ext}"
        saved_path = save_dir / saved_filename
        
        # 根据文件对象类型选择保存方式
        saved = False
        error_msg = None
        
        try:
            # FastAPI/Starlette UploadFile对象
            if hasattr(file_obj, 'file') and hasattr(file_obj, 'filename'):
                logger.debug(f"使用 UploadFile 方式保存: {filename}")
                with open(saved_path, 'wb') as f:
                    content = file_obj.file.read()
                    f.write(content)
                    try:
                        file_obj.file.seek(0)
                    except:
                        pass
                saved = True
            # 类文件对象（有read方法）
            elif hasattr(file_obj, 'read') and callable(file_obj.read):
                logger.debug(f"使用 read 方式保存: {filename}")
                with open(saved_path, 'wb') as f:
                    content = file_obj.read()
                    f.write(content)
                    try:
                        if hasattr(file_obj, 'seek'):
                            file_obj.seek(0)
                    except:
                        pass
                saved = True
            # 文件路径对象
            elif hasattr(file_obj, 'name') and os.path.exists(file_obj.name):
                logger.debug(f"使用 copy 方式保存 (from name): {filename}")
                shutil.copy2(file_obj.name, saved_path)
                saved = True
            # 字符串或Path路径
            elif isinstance(file_obj, (str, Path)) and os.path.exists(str(file_obj)):
                logger.debug(f"使用 copy 方式保存 (from path): {filename}")
                shutil.copy2(str(file_obj), saved_path)
                saved = True
            else:
                error_msg = f"不支持的文件对象类型: {type(file_obj)}"
                logger.error(error_msg)
        
        except Exception as e:
            error_msg = f"保存文件时发生错误: {str(e)}"
            logger.error(error_msg, exc_info=True)
        
        # 检查是否保存成功
        if not saved or error_msg:
            if saved_path.exists():
                saved_path.unlink()
            raise ValueError(error_msg or "文件保存失败")
        
        # 验证文件
        if not saved_path.exists() or saved_path.stat().st_size == 0:
            raise ValueError("文件保存后验证失败：文件不存在或为空")
        
        logger.info(f"文件保存成功: {saved_path} ({saved_path.stat().st_size} bytes)")
        
        # 记录文件信息
        file_info = {
            "file_id": file_id,  # 统一使用 file_id 字段
            "original_filename": filename,
            "saved_path": str(saved_path),
            "saved_filename": saved_filename,
            "size": saved_path.stat().st_size,
            "upload_time": datetime.now().isoformat(),
            "user_id": user_id,
        }
        
        self.uploaded_files[file_id] = file_info
        
        return file_info
    
    def get_file_path(self, file_id: str) -> Optional[str]:
        """
        根据文件ID获取文件路径
        
        Args:
            file_id: 文件ID
            
        Returns:
            文件路径，如果不存在则返回 None
        """
        if file_id in self.uploaded_files:
            path = self.uploaded_files[file_id]["saved_path"]
            if os.path.exists(path):
                return path
        return None
    
    def get_output_path(self, file_id: str, suffix: str = "_processed.h5ad") -> str:
        """
        获取结果文件路径
        
        Args:
            file_id: 原始文件ID
            suffix: 文件名后缀
            
        Returns:
            结果文件路径
        """
        if file_id in self.uploaded_files:
            original_name = Path(self.uploaded_files[file_id]["original_filename"]).stem
            output_filename = f"{original_name}{suffix}"
        else:
            # 如果找不到原始文件，使用UUID生成文件名（不添加时间戳）
            output_filename = f"{uuid.uuid4().hex[:8]}{suffix}"
        
        return str(self.output_dir / output_filename)
    
    def list_uploaded_files(self, user_id: Optional[str] = None) -> list:
        """
        列出所有上传的文件
        
        Args:
            user_id: 可选，筛选特定用户的文件
            
        Returns:
            文件信息列表
        """
        if user_id:
            return [f for f in self.uploaded_files.values() if f.get("user_id") == user_id]
        return list(self.uploaded_files.values())
    
    def delete_file(self, file_id: str) -> bool:
        """
        删除文件
        
        Args:
            file_id: 文件ID
            
        Returns:
            是否成功删除
        """
        if file_id in self.uploaded_files:
            file_info = self.uploaded_files[file_id]
            file_path = file_info["saved_path"]
            
            # 删除物理文件
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # 从记录中删除
            del self.uploaded_files[file_id]
            
            logger.info(f"文件已删除: {file_id}")
            return True
        return False


# 全局文件管理器实例
_file_manager: Optional[FileManager] = None


def get_file_manager() -> FileManager:
    """获取全局文件管理器实例"""
    global _file_manager
    if _file_manager is None:
        _file_manager = FileManager()
    return _file_manager

