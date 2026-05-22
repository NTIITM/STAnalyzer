"""
文件服务
整合file_manager和user_data_manager，提供统一的文件管理API
"""
import json
import os
import uuid
import zipfile
import tarfile
import tempfile
import shutil
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Set
from pathlib import Path
from datetime import datetime
from fastapi import UploadFile, HTTPException, status

from textmsa.logging_config import get_logger
from textmsa.services.analysis.cascade_deletion_service import get_cascade_deletion_service
from textmsa.services.file.file_manager import get_file_manager
from textmsa.services.file.file_type_service import get_file_type_service
from textmsa.services.data.user_data_manager_mongodb import get_user_data_manager

logger = get_logger(__name__)

# 尝试导入生物信息学库
try:
    import scanpy as sc
    import anndata as ad
    BIO_AVAILABLE = True
except ImportError:
    BIO_AVAILABLE = False
    logger.warning("scanpy/anndata库未安装，10x格式转换功能受限")


class FileService:
    """文件服务类"""
    
    def __init__(self):
        """初始化文件服务"""
        self.file_manager = get_file_manager()
        self.user_data_manager = get_user_data_manager()
        self.file_type_service = get_file_type_service()
        self.cascade_service = get_cascade_deletion_service()
        self._file_reader_tool = None
    
    @property
    def file_reader_tool(self):
        """延迟加载 FileReaderTool，避免循环导入"""
        if self._file_reader_tool is None:
            from textmsa.services.agent.tools.file_reader_tool import FileReaderTool
            self._file_reader_tool = FileReaderTool()
        return self._file_reader_tool

    def get_file_preview(
        self,
        file_id: str,
        user_id: str,
        max_length: int = 2000,
    ) -> str:
        """
        获取单个文件的预览内容（字符串）。

        预览逻辑与 get_project_files_tree_list 中 include_preview=True 时保持一致：
        - 优先使用 MongoDB 中保存的 file_path
        - 若不存在，则通过 file_manager.get_file_path 获取
        - 使用 file_reader_tool._read_preview 读取预览
        - 将预览字典转换为 JSON 字符串

        Args:
            file_id: 文件ID
            user_id: 用户ID（用于权限/租户隔离）
            max_length: 预览字符串的最大长度（字符数），超过则截断

        Returns:
            预览内容字符串（可能为空字符串）
        """
        try:
            # 开发模式：如果user_id是test_user_id，尝试从数据库获取test_user的实际ID
            from textmsa.services.auth.auth_service import resolve_test_user_id

            user_id = resolve_test_user_id(user_id)

            # 先从 MongoDB 获取文件信息，拿到 file_path / filename
            file_info = self.user_data_manager.get_file_info(user_id, file_id)
            if not file_info:
                logger.warning(
                    "get_file_preview: 文件不存在",
                    extra={"user_id": user_id, "file_id": file_id},
                )
                return ""

            saved_path = file_info.get("file_path")
            filename = file_info.get("filename", "")

            # 如果 DB 里没有路径，再尝试通过 file_manager 获取
            if not saved_path:
                try:
                    saved_path = self.file_manager.get_file_path(file_id)
                except Exception as e:
                    logger.warning(
                        "get_file_preview: 通过 file_manager 获取路径失败",
                        extra={
                            "user_id": user_id,
                            "file_id": file_id,
                            "error": str(e),
                        },
                    )
                    saved_path = None

            if not saved_path or not os.path.exists(saved_path):
                logger.warning(
                    "get_file_preview: 文件路径不存在或为空",
                    extra={
                        "user_id": user_id,
                        "file_id": file_id,
                        "filename": filename,
                        "file_path": file_info.get("file_path"),
                        "saved_path": saved_path,
                        "path_exists": os.path.exists(saved_path) if saved_path else False,
                    },
                )
                return ""

            # 从文件名中推断文件类型（与 get_project_files_tree_list 中逻辑一致）
            file_ext = os.path.splitext(filename)[1].lower()
            file_type_name = file_ext[1:] if file_ext else "unknown"

            logger.debug(
                "get_file_preview: 开始读取文件预览",
                extra={
                    "user_id": user_id,
                    "file_id": file_id,
                    "filename": filename,
                    "file_path": saved_path,
                    "file_type": file_type_name,
                },
            )

            preview_dict = self.file_reader_tool._read_preview(
                file_path=saved_path,
                file_type=file_type_name,
                filename=filename,
            )

            logger.debug(
                "get_file_preview: 文件预览读取完成",
                extra={
                    "user_id": user_id,
                    "file_id": file_id,
                    "filename": filename,
                    "preview_dict_type": type(preview_dict).__name__,
                    "preview_dict_keys": list(preview_dict.keys())
                    if isinstance(preview_dict, dict)
                    else None,
                    "preview_dict_empty": not preview_dict if preview_dict else True,
                },
            )

            if not preview_dict:
                return ""

            try:
                preview_str = json.dumps(preview_dict, ensure_ascii=False, indent=2)
            except Exception as json_err:
                logger.error(
                    "get_file_preview: 预览JSON序列化失败",
                    extra={
                        "user_id": user_id,
                        "file_id": file_id,
                        "filename": filename,
                        "error": str(json_err),
                        "preview_dict_snippet": str(preview_dict)[:200],
                    },
                    exc_info=True,
                )
                return ""

            if max_length > 0 and len(preview_str) > max_length:
                return preview_str[:max_length]
            return preview_str

        except Exception as e:
            logger.error(
                "get_file_preview: 获取文件预览失败",
                extra={"user_id": user_id, "file_id": file_id, "error": str(e)},
                exc_info=True,
            )
            return ""
    
    def upload_file(
        self,
        file: UploadFile,
        user_id: str,
        project_id: Optional[str] = None,
        file_type_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        上传文件
        
        Args:
            file: FastAPI UploadFile对象
            user_id: 用户ID
            project_id: 项目ID（可选，如果提供，上传后自动添加到项目）
        
        Returns:
            包含文件信息的字典
        """
        try:
            # 开发模式：如果user_id是test_user_id，尝试从数据库获取test_user的实际ID
            from textmsa.services.auth.auth_service import resolve_test_user_id
            user_id = resolve_test_user_id(user_id)
            
            # 验证文件名不能为空（符合需求 2）
            if not file.filename or not file.filename.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="文件名不能为空"
                )
            
            # 先解析文件类型，以便后续判断是否需要转换
            resolved_file_type = self.file_type_service.resolve_type(
                file_type_id=file_type_id,
                user_id=user_id,
            )
            
            # 保存文件
            file_info = self.file_manager.save_uploaded_file(
                file_obj=file,
                filename=file.filename.strip(),
                user_id=user_id
            )
            
            # 检查是否需要处理 10x 格式的数据（zip 或 gz/tar.gz）
            filename_lower = file_info["original_filename"].lower()
            
            # 调试日志：检查转换条件
            file_type_id_value = resolved_file_type.get("file_type_id")
            is_spatial_type = file_type_id_value == "spatial_rna_seq_data"
            is_archive = filename_lower.endswith('.zip') or filename_lower.endswith('.gz')
            
            logger.info(
                f"文件类型检查: file_type_id={file_type_id_value}, "
                f"is_spatial_type={is_spatial_type}, "
                f"filename={file_info['original_filename']}, "
                f"is_archive={is_archive}"
            )
            
            is_spatial_archive = is_spatial_type and is_archive
            
            # 如果是 spatial_rna_seq_data 类型的压缩文件，进行转换
            if is_spatial_archive:
                archive_type = "gz" if filename_lower.endswith('.gz') else "zip"
                logger.info(f"检测到 spatial_rna_seq_data 类型的 {archive_type} 文件，开始转换为 h5ad: {file_info['original_filename']}")
                try:
                    file_info = self._convert_10x_archive_to_h5ad(file_info, user_id)
                    logger.info(f"10x {archive_type} 文件转换成功: {file_info['original_filename']}")
                    # 转换后重新计算 filename_lower
                    filename_lower = file_info["original_filename"].lower()
                except Exception as e:
                    logger.error(f"10x {archive_type} 文件转换失败: {e}", exc_info=True)
                    # 删除已保存的压缩文件
                    try:
                        if os.path.exists(file_info["saved_path"]):
                            os.remove(file_info["saved_path"])
                    except Exception:
                        pass
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"10x 格式转换失败: {str(e)}"
                    )
            
            # 提取文件元信息（如果是h5ad文件）
            file_metadata = {
                "size": file_info["size"],
                "upload_time": file_info["upload_time"]
            }
            
            # 如果是h5ad文件，提取元信息
            if filename_lower.endswith('.h5ad'):
                logger.info(f"检测到h5ad文件，开始提取元信息: {file_info['original_filename']}")
                h5ad_metadata = self.file_reader_tool.extract_h5ad_metadata(file_info["saved_path"])
                # 合并元信息（排除 error 和 note 字段）
                h5ad_metadata_clean = {k: v for k, v in h5ad_metadata.items() if k not in ("error", "note")}
                file_metadata.update(h5ad_metadata_clean)
            file_type_block = self.file_type_service.build_metadata_block(resolved_file_type)
            file_metadata["file_type"] = file_type_block
            
            # MongoDB保存
            file_id = file_info["file_id"]  # 统一使用 file_id
            try:
                # 保存用户上传的文件记录到MongoDB
                # 注意：只有用户直接上传的文件才保存到MongoDB
                mongo_success = self.user_data_manager.add_user_file(
                    user_id=user_id,
                    file_id=file_id,
                    filename=file_info["original_filename"],
                    file_type_id=resolved_file_type["file_type_id"],
                    file_type_name=resolved_file_type["name"],
                    file_type_display_name=resolved_file_type["display_name"],
                    file_path=file_info["saved_path"],
                    file_info=file_metadata
                )
                
                if not mongo_success:
                    raise Exception("MongoDB保存失败")
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"文件上传失败: {e}", exc_info=True)
                # 如果MongoDB保存失败，也需要删除物理文件
                if file_id:
                    try:
                        self.user_data_manager.delete_file(user_id, file_id)
                    except Exception:
                        pass
                    try:
                        self.file_manager.delete_file(file_id)
                    except Exception:
                        pass
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"文件上传失败: {str(e)}"
                )
            
            file_id = file_info["file_id"]  # 统一使用 file_id
            logger.info(f"文件上传成功: {file_id} ({file_info['original_filename']})")
            
            # 如果提供了 project_id，自动添加到项目
            if project_id:
                try:
                    from textmsa.services.project.project_service import get_project_service
                    project_service = get_project_service()
                    project_service.add_file_to_project(
                        project_id=project_id,
                        file_id=file_id,
                        user_id=user_id
                    )
                    logger.info(f"文件已自动添加到项目: project_id={project_id}, file_id={file_id}")
                except Exception as e:
                    logger.warning(f"自动添加文件到项目失败: {e}，文件上传成功但未关联到项目")
            
            # 构建返回数据，包含元信息（如果是h5ad文件）
            result = {
                "file_id": file_id,  # 统一使用 file_id 字段
                "filename": file_info["original_filename"],
                "size": file_info["size"],
                "upload_time": file_info["upload_time"],
                "file_type": file_type_block,
            }
            
            # 如果是h5ad文件，添加元信息到返回结果
            if filename_lower.endswith('.h5ad'):
                result.update({
                    "n_spots": file_metadata.get("n_spots"),
                    "n_genes": file_metadata.get("n_genes"),
                    "has_spatial": file_metadata.get("has_spatial")
                })
            
            return result
        
        except HTTPException:
            # 重新抛出 HTTPException，不进行包装
            raise
        except Exception as e:
            logger.error(f"文件上传失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"文件上传失败: {str(e)}"
            )
    
    def _convert_10x_archive_to_h5ad(self, file_info: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        将 10x 格式的压缩文件（zip 或 tar.gz）转换为 h5ad 格式
        
        Args:
            file_info: 文件信息字典（包含 saved_path, original_filename 等）
            user_id: 用户ID
            
        Returns:
            更新后的文件信息字典（saved_path 指向新的 h5ad 文件）
            
        Raises:
            HTTPException: 如果转换失败
        """
        if not BIO_AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="生物信息学库未安装，无法进行格式转换"
            )
        
        archive_path = Path(file_info["saved_path"])
        original_filename = file_info["original_filename"]
        filename_lower = original_filename.lower()
        
        # 创建临时目录用于解压
        temp_dir = None
        try:
            temp_dir = tempfile.mkdtemp(prefix="10x_convert_")
            logger.debug(f"创建临时目录用于解压: {temp_dir}")
            
            # 根据文件扩展名选择解压方式
            if filename_lower.endswith('.gz'):
                # 处理 tar.gz 文件
                logger.info(f"开始解压 tar.gz 文件: {archive_path}")
                with tarfile.open(archive_path, 'r:gz') as tar_ref:
                    # 记录压缩文件中的内容
                    members = tar_ref.getmembers()
                    logger.info(f"压缩文件包含 {len(members)} 个文件/目录")
                    if members:
                        logger.info(f"压缩文件内容示例（前10个）: {[m.name for m in members[:10]]}")
                    tar_ref.extractall(temp_dir)
                    logger.info(f"tar.gz 文件解压完成: {archive_path} -> {temp_dir}")
            elif filename_lower.endswith('.zip'):
                # 处理 zip 文件
                logger.info(f"开始解压 zip 文件: {archive_path}")
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    # 记录压缩文件中的内容
                    members = zip_ref.namelist()
                    logger.info(f"压缩文件包含 {len(members)} 个文件/目录")
                    if members:
                        logger.info(f"压缩文件内容示例（前10个）: {[m for m in members[:10]]}")
                    zip_ref.extractall(temp_dir)
                    logger.info(f"zip 文件解压完成: {archive_path} -> {temp_dir}")
            else:
                raise ValueError(f"不支持的文件格式: {original_filename}")
            
            # 记录解压后的目录结构
            extracted_dir = Path(temp_dir)
            logger.info(f"解压后的根目录内容: {list(extracted_dir.iterdir())}")
            
            # 递归查找所有目录和文件（用于调试）
            def list_all_paths(path, max_depth=3, current_depth=0):
                """递归列出目录结构"""
                if current_depth >= max_depth:
                    return []
                paths = []
                try:
                    for item in path.iterdir():
                        if item.is_dir():
                            paths.append(f"{'  ' * current_depth}{item.name}/")
                            paths.extend(list_all_paths(item, max_depth, current_depth + 1))
                        else:
                            paths.append(f"{'  ' * current_depth}{item.name}")
                except PermissionError:
                    pass
                return paths
            
            all_paths = list_all_paths(extracted_dir, max_depth=3)
            logger.info(f"解压后的目录结构（前30项）:\n" + "\n".join(all_paths[:30]))
            
            # 查找 10x 数据目录（通常包含 filtered_feature_bc_matrix 或 raw_feature_bc_matrix）
            # 同时查找 spatial/ 目录以获取空间坐标和组织图像信息
            matrix_dir = None
            visium_dir = None  # 包含 matrix 和 spatial 目录的父目录
            
            # 递归查找包含 10x 数据文件的目录
            def find_10x_matrix_dir(root_dir, max_depth=5, current_depth=0):
                """递归查找包含 matrix.mtx, features.tsv 和 barcodes.tsv 的目录"""
                if current_depth >= max_depth:
                    return None
                
                root_path = Path(root_dir)
                if not root_path.exists() or not root_path.is_dir():
                    return None
                
                # 检查当前目录是否包含 10x 文件（支持压缩和非压缩版本）
                matrix_file = root_path / "matrix.mtx"
                matrix_file_gz = root_path / "matrix.mtx.gz"
                features_file = root_path / "features.tsv"
                features_file_gz = root_path / "features.tsv.gz"
                barcodes_file = root_path / "barcodes.tsv"
                barcodes_file_gz = root_path / "barcodes.tsv.gz"
                
                has_matrix = matrix_file.exists() or matrix_file_gz.exists()
                has_features = features_file.exists() or features_file_gz.exists()
                has_barcodes = barcodes_file.exists() or barcodes_file_gz.exists()
                
                if has_matrix and has_features and has_barcodes:
                    # 记录找到的文件格式
                    matrix_format = "matrix.mtx.gz" if matrix_file_gz.exists() else "matrix.mtx"
                    features_format = "features.tsv.gz" if features_file_gz.exists() else "features.tsv"
                    barcodes_format = "barcodes.tsv.gz" if barcodes_file_gz.exists() else "barcodes.tsv"
                    logger.info(f"在深度 {current_depth} 找到 10x 数据目录: {root_path}")
                    logger.info(f"  文件格式: {matrix_format}, {features_format}, {barcodes_format}")
                    return root_path
                
                # 递归搜索子目录
                try:
                    for item in root_path.iterdir():
                        if item.is_dir():
                            result = find_10x_matrix_dir(item, max_depth, current_depth + 1)
                            if result:
                                return result
                except PermissionError:
                    pass
                
                return None
            
            # 首先尝试标准位置
            possible_dirs = [
                extracted_dir / "filtered_feature_bc_matrix",
                extracted_dir / "raw_feature_bc_matrix",
                extracted_dir,
            ]
            
            matrix_dir = None
            for possible_dir in possible_dirs:
                if possible_dir.exists() and possible_dir.is_dir():
                    result = find_10x_matrix_dir(possible_dir, max_depth=3)
                    if result:
                        matrix_dir = result
                        break
            
            # 如果标准位置没找到，递归搜索整个解压目录
            if not matrix_dir:
                logger.info("在标准位置未找到 10x 数据，开始递归搜索整个解压目录...")
                matrix_dir = find_10x_matrix_dir(extracted_dir, max_depth=5)
            
            if matrix_dir:
                logger.info(f"找到 10x 矩阵数据目录: {matrix_dir}")
                
                # 检查父目录是否包含 spatial/ 目录（10x Visium 标准结构）
                parent_dir = matrix_dir.parent
                spatial_dir = parent_dir / "spatial"
                
                if spatial_dir.exists() and spatial_dir.is_dir():
                    # 检查 spatial 目录是否包含必要的文件
                    spatial_files = [
                        spatial_dir / "tissue_positions_list.csv",
                        spatial_dir / "tissue_positions.csv",
                    ]
                    has_spatial_coords = any(f.exists() for f in spatial_files)
                    
                    if has_spatial_coords:
                        visium_dir = parent_dir
                        logger.info(f"找到 10x Visium 空间数据目录: {spatial_dir}")
                        logger.info(f"使用 Visium 目录读取（包含空间坐标和组织图像）: {visium_dir}")
                    else:
                        logger.warning(f"找到 spatial/ 目录但缺少空间坐标文件: {spatial_dir}")
                else:
                    logger.warning(f"未找到 spatial/ 目录，将仅读取表达矩阵数据: {parent_dir}")
            
            if not matrix_dir:
                raise ValueError(
                    "无法在压缩文件中找到 10x 格式数据。"
                    "请确保压缩文件包含 matrix.mtx (或 matrix.mtx.gz), "
                    "features.tsv (或 features.tsv.gz) 和 barcodes.tsv (或 barcodes.tsv.gz) 文件。"
                )
            
            # 记录实际检测到的文件格式（用于日志和调试）
            matrix_file = matrix_dir / "matrix.mtx"
            matrix_file_gz = matrix_dir / "matrix.mtx.gz"
            features_file = matrix_dir / "features.tsv"
            features_file_gz = matrix_dir / "features.tsv.gz"
            barcodes_file = matrix_dir / "barcodes.tsv"
            barcodes_file_gz = matrix_dir / "barcodes.tsv.gz"
            
            # 确定实际使用的文件格式
            actual_matrix_format = "matrix.mtx.gz" if matrix_file_gz.exists() else "matrix.mtx"
            actual_features_format = "features.tsv.gz" if features_file_gz.exists() else "features.tsv"
            actual_barcodes_format = "barcodes.tsv.gz" if barcodes_file_gz.exists() else "barcodes.tsv"
            
            logger.info(f"检测到的实际文件格式: {actual_matrix_format}, {actual_features_format}, {actual_barcodes_format}")
            logger.info(f"注意: scanpy 的 read_10x_mtx() 和 read_visium() 会自动处理 .gz 压缩文件")
            
            # 使用 scanpy 读取 10x 数据
            # scanpy 的 read_10x_mtx() 和 read_visium() 会自动检测并处理 .gz 压缩文件
            # 如果找到 visium_dir（包含 spatial/ 目录），使用 read_visium；否则使用 read_10x_mtx
            if visium_dir:
                logger.info(f"开始读取 10x Visium 数据（包含空间信息）: {visium_dir}")
                logger.info(f"  将自动处理压缩文件格式: {actual_matrix_format}, {actual_features_format}, {actual_barcodes_format}")
                adata = sc.read_visium(str(visium_dir))
            else:
                logger.info(f"开始读取标准 10x 数据（无空间信息）: {matrix_dir}")
                logger.info(f"  将自动处理压缩文件格式: {actual_matrix_format}, {actual_features_format}, {actual_barcodes_format}")
                adata = sc.read_10x_mtx(str(matrix_dir))
            logger.info(f"10x 数据读取成功: {adata.shape}")
            
            # 验证空间坐标是否被正确读取
            if 'spatial' in adata.obsm:
                spatial_coords = adata.obsm['spatial']
                logger.info(f"空间坐标已加载: shape={spatial_coords.shape}, dtype={spatial_coords.dtype}")
                if spatial_coords.shape[1] != 2:
                    logger.warning(f"空间坐标维度异常: 期望2维，实际{spatial_coords.shape[1]}维")
            else:
                logger.warning("未找到空间坐标信息 (obsm['spatial'])，数据可能不包含空间信息")
            
            # 验证组织图像是否被正确读取
            if 'spatial' in adata.uns:
                spatial_info = adata.uns['spatial']
                if isinstance(spatial_info, dict):
                    for slice_id, slice_data in spatial_info.items():
                        if isinstance(slice_data, dict):
                            if 'images' in slice_data:
                                images = slice_data['images']
                                logger.info(f"组织图像已加载 (slice: {slice_id}): {list(images.keys())}")
                            if 'scalefactors' in slice_data:
                                scalefactors = slice_data['scalefactors']
                                logger.info(f"缩放因子已加载 (slice: {slice_id}): {list(scalefactors.keys()) if isinstance(scalefactors, dict) else 'present'}")
                else:
                    logger.info(f"空间信息已加载 (uns['spatial']): {type(spatial_info)}")
            else:
                logger.warning("未找到组织图像信息 (uns['spatial'])，数据可能不包含图像信息")
            
            # 生成新的 h5ad 文件名（处理 .tar.gz 的情况）
            original_stem = Path(original_filename).stem
            # 如果原始文件名是 .tar.gz，需要再次提取 stem
            if original_stem.endswith('.tar'):
                original_stem = Path(original_stem).stem
            h5ad_filename = f"{original_stem}.h5ad"
            
            # 确定保存路径（与原始压缩文件在同一目录）
            archive_dir = archive_path.parent
            h5ad_path = archive_dir / f"{original_stem}_{file_info['file_id'][:8]}.h5ad"
            
            # 保存为 h5ad 格式
            logger.info(f"开始保存 h5ad 文件: {h5ad_path}")
            adata.write_h5ad(str(h5ad_path))
            logger.info(f"h5ad 文件保存成功: {h5ad_path} ({h5ad_path.stat().st_size} bytes)")
            
            # 删除原始压缩文件
            try:
                if archive_path.exists():
                    archive_path.unlink()
                    logger.info(f"已删除原始压缩文件: {archive_path}")
            except Exception as e:
                logger.warning(f"删除原始压缩文件失败: {e}")
            
            # 更新文件信息
            file_info["saved_path"] = str(h5ad_path)
            file_info["original_filename"] = h5ad_filename
            file_info["size"] = h5ad_path.stat().st_size
            
            return file_info
            
        except (zipfile.BadZipFile, tarfile.TarError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的压缩文件格式: {str(e)}"
            )
        except Exception as e:
            logger.error(f"10x 格式转换失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"10x 格式转换失败: {str(e)}"
            )
        finally:
            # 清理临时目录
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                    logger.debug(f"已清理临时目录: {temp_dir}")
                except Exception as e:
                    logger.warning(f"清理临时目录失败: {e}")
    
    def get_file_list(self, user_id: str) -> List[Dict[str, Any]]:
        """
        获取用户文件列表
        
        Args:
            user_id: 用户ID
        
        Returns:
            文件信息列表
        """
        try:
            # 开发模式：如果user_id是test_user_id，尝试从数据库获取test_user的实际ID
            from textmsa.services.auth.auth_service import resolve_test_user_id
            user_id = resolve_test_user_id(user_id)
            
            logger.debug(f"查询文件列表，user_id: {user_id}")
            
            files = self.user_data_manager.get_user_uploaded_files(user_id)
            
            # 格式化返回数据（使用蛇形命名）
            result = []
            for file_info in files:
                metadata = file_info.get("metadata", {})
                file_type_payload = file_info.get("file_type")
                if not file_type_payload:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="FILE_TYPE_MISSING",
                    )
                file_item = {
                    "file_id": file_info.get("file_id"),
                    "name": file_info.get("filename") or file_info.get("name"),
                    "size": metadata.get("size", 0),
                    "status": file_info.get("analysis_status", "uploaded"),
                    "time": file_info.get("upload_time"),
                    "file_type": file_type_payload,
                    "file_type_id": file_type_payload.get("file_type_id"),

                    
                }
                
                # 如果是h5ad文件，添加元信息
                filename_lower = file_info.get("filename", "").lower()
                if filename_lower.endswith('.h5ad'):
                    file_item.update({
                        "n_spots": metadata.get("n_spots"),
                        "n_genes": metadata.get("n_genes"),
                        "has_spatial": metadata.get("has_spatial")
                    })
                
                result.append(file_item)
            
            return result
        
        except Exception as e:
            logger.error(f"获取文件列表失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="获取文件列表失败"
            )
    
    def get_file_info(self, file_id: str, user_id: str) -> Dict[str, Any]:
        """
        获取文件详情
        
        Args:
            file_id: 文件ID
            user_id: 用户ID
        
        Returns:
            文件详细信息
        
        Raises:
            HTTPException: 如果文件不存在或不属于该用户
        """
        try:
            # 开发模式：如果user_id是test_user_id，尝试从数据库获取test_user的实际ID
            from textmsa.services.auth.auth_service import resolve_test_user_id
            user_id = resolve_test_user_id(user_id)
            
            file_info = self.user_data_manager.get_file_info(user_id, file_id)
            
            if not file_info:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="文件不存在"
                )
            
            # 使用蛇形命名
            return {
                "user_id": user_id,  # 添加 user_id 字段，FileInfo 模型需要
                "file_id": file_info.get("file_id"),
                "filename": file_info.get("filename"),
                "file_path": file_info.get("file_path"),
                "upload_time": file_info.get("upload_time"),
                "last_viewed_time": file_info.get("last_viewed_time"),
                "analysis_status": file_info.get("analysis_status"),  # 使用 analysis_status 而不是 status，与 FileInfo 模型一致
                "status": file_info.get("analysis_status"),  # 保留 status 字段以保持向后兼容
                "description": file_info.get("description"),
                "metadata": file_info.get("metadata", {}),
                "conversations": file_info.get("conversations", []),
                "generated_by": file_info.get("generated_by"),
                "children": file_info.get("children", []),
                "file_type_id": file_info.get("file_type_id"),
                "file_type_name": file_info.get("file_type_name"),
                "file_type_display_name": file_info.get("file_type_display_name"),
            }
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取文件信息失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="获取文件信息失败"
            )
    
    def update_file_info(self, file_id: str, user_id: str, filename: Optional[str] = None, description: Optional[str] = None) -> Dict[str, Any]:
        """
        更新文件信息（文件名、描述）
        
        Args:
            file_id: 文件ID
            user_id: 用户ID
            filename: 新的文件名（可选）
            description: 新的文件描述（可选）
        
        Returns:
            更新后的文件信息
        
        Raises:
            HTTPException: 如果文件不存在或不属于该用户
        """
        try:
            # 开发模式：如果user_id是test_user_id，尝试从数据库获取test_user的实际ID
            from textmsa.services.auth.auth_service import resolve_test_user_id
            user_id = resolve_test_user_id(user_id)
            
            # 检查文件是否存在
            file_info = self.user_data_manager.get_file_info(user_id, file_id)
            
            if not file_info:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="文件不存在"
                )
            
            # 验证至少提供一个更新字段
            if filename is None and description is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="至少需要提供一个更新字段（name或description）"
                )
            
            # 更新MongoDB
            try:
                # 更新MongoDB
                update_result = self.user_data_manager.update_file_info(
                    user_id=user_id,
                    file_id=file_id,
                    filename=filename,
                    description=description
                )
                
                if not update_result.get("success", False):
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"文件更新失败：{update_result.get('message', 'MongoDB更新失败')}"
                    )
                
                # 根据实际更新情况记录日志
                if update_result.get("modified", False):
                    logger.info(f"文件信息更新成功: {file_id}")
                else:
                    logger.info(f"文件信息未变化: {file_id}（提供的值与现有值相同）")
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"文件更新失败: {e}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"文件更新失败: {str(e)}"
                )
            
            # 获取更新后的文件信息
            updated_file_info = self.user_data_manager.get_file_info(user_id, file_id)
            
            if not updated_file_info:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="文件不存在"
                )
            
            # 使用蛇形命名
            return {
                "file_id": updated_file_info.get("file_id", file_id),
                "name": updated_file_info.get("filename"),
                "description": updated_file_info.get("description")
            }
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"更新文件信息失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="更新文件信息失败"
            )
    
    def delete_file(self, file_id: str, user_id: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        """
        删除文件
        
        Args:
            file_id: 文件ID
            user_id: 用户ID
            project_id: 指定的项目ID（可选，用于限定删除范围）
        
        Returns:
            删除结果摘要
        
        Raises:
            HTTPException: 如果文件不存在或不属于该用户
        """
        try:
            # 开发模式：如果user_id是test_user_id，尝试从数据库获取test_user的实际ID
            from textmsa.services.auth.auth_service import resolve_test_user_id
            user_id = resolve_test_user_id(user_id)
            
            # 检查文件是否存在
            file_info = self.user_data_manager.get_file_info(user_id, file_id)
            
            if not file_info:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="文件不存在"
                )
            deletion_result = self.cascade_service.delete_files(
                user_id=user_id,
                root_file_ids=[file_id],
                project_ids=[project_id] if project_id else None,
            )

            if file_id not in deletion_result.get("deleted_file_ids", []):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="文件删除失败：未删除目标文件",
                )
            
            logger.info(f"文件及其衍生资源删除成功: {file_id}")
            return deletion_result
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"删除文件失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="删除文件失败"
            )
    
    def _collect_descendant_file_ids(
        self,
        *,
        root_file_id: str,
        project_id: Optional[str] = None,
    ) -> List[str]:
        """递归收集文件的所有子文件ID（不包含根文件）"""
        visited: Set[str] = set()
        descendants: List[str] = []
        queue: Deque[str] = deque([root_file_id])

        while queue:
            current_id = queue.popleft()
            relations = self.user_data_manager.get_file_children(
                parent_file_id=current_id,
                project_id=project_id,
            )

            for relation in relations:
                child_id = relation.get("child_file_id")
                if not child_id or child_id in visited:
                    continue
                visited.add(child_id)
                descendants.append(child_id)
                queue.append(child_id)

        return descendants

    def delete_file_children(
        self,
        file_id: str,
        user_id: str,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        递归删除指定文件的所有子文件（保留根文件）
        """
        try:
            from textmsa.services.auth.auth_service import resolve_test_user_id

            user_id = resolve_test_user_id(user_id)

            file_info = self.user_data_manager.get_file_info(user_id, file_id)
            if not file_info:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="文件不存在",
                )

            project_scope = (
                [project_id]
                if project_id
                else self.user_data_manager.find_project_ids_by_file(user_id, file_id)
            )

            child_file_ids = self._collect_descendant_file_ids(
                root_file_id=file_id,
                project_id=project_id,
            )

            if not child_file_ids:
                return {
                    "message": "没有子文件需要删除",
                    "deleted_file_ids": [],
                    "failed_file_ids": {},
                    "deleted_execution_ids": [],
                    "failed_execution_ids": {},
                    "project_scope": project_scope,
                }

            deletion_result = self.cascade_service.delete_files(
                user_id=user_id,
                root_file_ids=child_file_ids,
                project_ids=project_scope or None,
            )

            # 额外删除：以根文件作为输入的执行记录
            extra_deleted_execs, extra_failed_execs = self.cascade_service.delete_executions_by_input_file(
                user_id=user_id,
                input_file_id=file_id,
                project_ids=project_scope or None,
            )

            if extra_deleted_execs or extra_failed_execs:
                # 合并执行删除结果，避免重复 ID
                merged_deleted_execs = set(deletion_result.get("deleted_execution_ids") or [])
                merged_deleted_execs.update(extra_deleted_execs)

                merged_failed_execs = dict(deletion_result.get("failed_execution_ids") or {})
                merged_failed_execs.update(extra_failed_execs)

                deletion_result["deleted_execution_ids"] = sorted(merged_deleted_execs)
                deletion_result["failed_execution_ids"] = merged_failed_execs

            logger.info(
                "文件子文件递归删除完成: root=%s, deleted=%d",
                file_id,
                len(deletion_result.get("deleted_file_ids", [])),
            )
            return deletion_result

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"删除子文件失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="删除子文件失败"
            )
    
    def register_generated_file(
        self,
        file_path: str,
        filename: str,
        parent_file_ids: List[str],
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        注册生成的文件到数据库（类似 upload_file，但用于生成的文件）
        
        Args:
            file_path: 文件路径（已存在的文件）
            filename: 文件名
            parent_file_ids: 父文件ID列表（用于建立关系）
            description: 文件描述（可选）
            metadata: 文件元数据（可选）
        
        Returns:
            包含文件信息的字典，类似 upload_file 的返回格式
        
        Raises:
            FileNotFoundError: 如果文件不存在
            ValueError: 如果父文件不存在或未关联到项目
            HTTPException: 其他错误
        """
        try:
            # 1. 验证文件路径存在
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            if not path.is_file():
                raise ValueError(f"路径不是文件: {file_path}")
            
            # 2. 验证 parent_file_ids 非空
            if not parent_file_ids:
                raise ValueError("parent_file_ids 不能为空")
            
            # 3. 从第一个父文件获取 user_id 和 project_id
            first_parent_id = parent_file_ids[0]
            
            # 通过 file_id 直接查询父文件信息（file_id 是唯一索引）
            # 注意：直接访问 files_collection，因为 file_id 是唯一索引，不需要 user_id
            parent_file_doc = self.user_data_manager.files_collection.find_one(
                {"file_id": first_parent_id}
            )
            
            if not parent_file_doc:
                raise ValueError(f"父文件不存在: {first_parent_id}")
            
            # 获取 user_id
            user_id = parent_file_doc.get("user_id")
            if not user_id:
                raise ValueError(f"无法从父文件中获取 user_id: {first_parent_id}")
            
            # 开发模式：如果user_id是test_user_id，尝试从数据库获取test_user的实际ID
            from textmsa.services.auth.auth_service import resolve_test_user_id
            user_id = resolve_test_user_id(user_id)
            
            # 通过 find_project_ids_by_file 获取 project_id
            project_ids = self.user_data_manager.find_project_ids_by_file(
                user_id=user_id,
                file_id=first_parent_id
            )
            
            if not project_ids:
                raise ValueError(f"父文件 {first_parent_id} 未关联到任何项目")
            
            project_id = project_ids[0]
            
            # 4. 文件类型：对生成文件不再自动推测，优先使用显式提供的类型，否则使用 unknown
            file_type_id = "unknown"
            file_type_name = "Unknown"
            file_type_display_name = "Unknown"

            # 如果 metadata 提供了 file_type 信息，则使用之
            if metadata:
                provided_file_type = metadata.get("file_type")
                provided_file_type_id = metadata.get("file_type_id")

                if isinstance(provided_file_type, dict):
                    file_type_id = provided_file_type.get("file_type_id") or provided_file_type.get("id") or file_type_id
                    file_type_name = provided_file_type.get("name") or file_type_name
                    file_type_display_name = provided_file_type.get("display_name") or file_type_display_name
                elif isinstance(provided_file_type_id, str):
                    try:
                        resolved_type = self.file_type_service.resolve_type(
                            file_type_id=provided_file_type_id,
                            user_id=user_id,
                        )
                        file_type_id = resolved_type.get("file_type_id", file_type_id)
                        file_type_name = resolved_type.get("name", file_type_name)
                        file_type_display_name = resolved_type.get("display_name", file_type_display_name)
                    except HTTPException as e:
                        logger.warning(f"提供的 file_type_id 无法解析，使用 unknown: {provided_file_type_id}, {e}")
                    except Exception as e:
                        logger.warning(f"解析提供的 file_type_id 异常，使用 unknown: {provided_file_type_id}, {e}")
            
            # 5. 生成 file_id（使用 file_manager 的方式或类似方式）
            file_id = f"gen_{uuid.uuid4().hex}"
            
            # 6. 准备文件元数据
            file_metadata = {
                "size": path.stat().st_size,
                "upload_time": datetime.now().isoformat(),
            }
            
            # 添加用户提供的元数据
            if metadata:
                file_metadata.update(metadata)
            
            # 7. 保存文件记录到 MongoDB
            mongo_success = self.user_data_manager.add_user_file(
                user_id=user_id,
                file_id=file_id,
                filename=filename,
                file_type_id=file_type_id or "unknown",  # 如果无法推断，使用默认值
                file_type_name=file_type_name or "Unknown",
                file_type_display_name=file_type_display_name or "Unknown",
                description=description,
                file_path=str(path.absolute()),  # 使用绝对路径
                file_info=file_metadata
            )
            
            if not mongo_success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="MongoDB保存失败"
                )
            
            logger.info(f"生成文件已注册到数据库: {file_id} ({filename})")
            
            # 8. 将文件添加到项目
            try:
                self.user_data_manager.add_file_to_project(
                    user_id=user_id,
                    project_id=project_id,
                    file_id=file_id
                )
                logger.info(f"文件已添加到项目: project_id={project_id}, file_id={file_id}")
            except Exception as e:
                logger.warning(f"添加文件到项目失败: {file_id}, {project_id}, {e}")
                # 不抛出异常，允许继续
            
            # 9. 创建文件关系
            try:
                relation_result = self.user_data_manager.create_file_relations(
                    parent_file_ids=parent_file_ids,
                    child_file_id=file_id,
                    description=description,
                )
                logger.info(
                    f"成功创建文件关系: {file_id}, "
                    f"父文件: {parent_file_ids}, "
                    f"创建数量: {relation_result.get('created_count', 0)}"
                )
            except Exception as e:
                logger.error(f"创建文件关系失败: {file_id}, {e}", exc_info=True)
                # 不抛出异常，允许文件注册成功，但关系创建失败
            
            # 10. 构建返回数据
            result = {
                "file_id": file_id,
                "filename": filename,
                "file_path": str(path.absolute()),
                "size": file_metadata["size"],
                "upload_time": file_metadata["upload_time"],
                "user_id": user_id,
                "project_id": project_id,
                "parent_file_ids": parent_file_ids,
            }
            
            # 添加文件类型信息（如果可用）
            if file_type_id:
                resolved_file_type = self.file_type_service.resolve_type(
                    file_type_id=file_type_id,
                    user_id=user_id,
                )
                file_type_block = self.file_type_service.build_metadata_block(resolved_file_type)
                result["file_type"] = file_type_block
            
            return result
        
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"注册生成文件失败: {file_path}, {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"注册生成文件失败: {file_path}, {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"注册生成文件失败: {str(e)}"
            )
    
    def get_project_files_tree_list(
        self,
        project_id: str,
        user_id: str,
        context_files: Optional[List[str]] = None,
        include_path: bool = False,
        include_preview: bool = False,
        include_description: bool = True,
        recursive: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        获取项目下的文件树列表结构（树形结构，类似 files_deep_read_agent 的 FileTreeNode）
        
        Args:
            project_id: 项目ID
            user_id: 用户ID（用于权限检查）
            context_files: 上下文文件ID列表（可选，为空时返回空列表，不获取项目任何文件）
            include_path: 是否在返回结果中包含 file_path 字段（默认 False）
            include_preview: 是否在返回结果中包含 preview 字段（默认 False）
            include_description: 是否在返回结果中包含 description 字段（默认 True）
            recursive: 是否递归查找子文件（默认 True）。如果为 False，仅查找 context_files 中的文件及其关系，不递归查找子文件
        
        Returns:
            文件树列表，格式为 FileTreeNode 列表（如果多个根节点，会创建虚拟根节点）
        """
        try:
            # 开发模式：如果user_id是test_user_id，尝试从数据库获取test_user的实际ID
            from textmsa.services.auth.auth_service import resolve_test_user_id
            user_id = resolve_test_user_id(user_id)
            
            # 确认项目存在且用户有权限
            from textmsa.services.project.project_service import get_project_service
            project_service = get_project_service()
            project_dict = project_service.get_project(project_id=project_id, user_id=user_id)
            
            # 确定要查询的文件ID列表
            if context_files:
                # 如果提供了 context_files，使用它（但需要验证这些文件属于该项目）
                file_ids = context_files
            else:
                # 如果没有提供 context_files，返回空列表（不获取项目任何文件）
                return []
            
            if not file_ids:
                return []
            
            # 1) 获取文件详细信息（参考 project_service.get_project_files_relations）
            files_map: Dict[str, Dict[str, Any]] = {}
            try:
                sanitized_user_id = self.user_data_manager._sanitize_user_id(user_id)
                
                file_docs = list(self.user_data_manager.files_collection.find({
                    "user_id": sanitized_user_id,
                    "file_id": {"$in": list(file_ids)}
                }))
                
                from textmsa.services.data.mongodb_models import file_info_from_dict
                for file_doc in file_docs:
                    try:
                        file_info = file_info_from_dict(file_doc)
                        files_map[file_info.file_id] = {
                            "file_id": file_info.file_id,
                            "filename": file_info.filename,
                            "file_path": file_info.file_path,
                            "file_type_id": file_info.file_type_id,
                            "description": file_info.description or "",
                        }
                    except Exception as e:
                        logger.warning(f"解析文件信息失败 {file_doc.get('file_id')}: {e}")
            except Exception as e:
                logger.warning(f"获取项目文件信息失败: {e}")
            
            if not files_map:
                return []
            
            # 2) 获取文件关系（参考 project_service.get_project_files_relations）
            relations: List[Dict[str, Any]] = []
            try:
                relations = self.user_data_manager.get_file_relations(project_id=project_id) or []
            except Exception as e:
                logger.warning(f"获取项目文件关系失败: {e}")
            
            # 3) 如果 recursive=True，递归查找所有子文件并添加到 files_map
            if recursive:
                # 构建完整的关系映射（不限制在 files_map 中）
                all_parent_to_children: Dict[str, List[str]] = {}
                for relation in relations:
                    parent_id = relation.get("parent_file_id")
                    child_id = relation.get("child_file_id")
                    if parent_id and child_id:
                        if parent_id not in all_parent_to_children:
                            all_parent_to_children[parent_id] = []
                        all_parent_to_children[parent_id].append(child_id)
                
                # 递归查找所有子文件ID
                def collect_all_children(file_id: str, visited: set[str]) -> set[str]:
                    """递归收集所有子文件ID"""
                    if file_id in visited:
                        return set()
                    visited.add(file_id)
                    children = set()
                    if file_id in all_parent_to_children:
                        for child_id in all_parent_to_children[file_id]:
                            children.add(child_id)
                            children.update(collect_all_children(child_id, visited))
                    return children
                
                # 收集所有需要查询的子文件ID
                all_child_ids = set()
                for file_id in files_map.keys():
                    all_child_ids.update(collect_all_children(file_id, set()))
                
                # 如果存在子文件，查询它们的详细信息并添加到 files_map
                if all_child_ids:
                    missing_child_ids = [cid for cid in all_child_ids if cid not in files_map]
                    if missing_child_ids:
                        try:
                            sanitized_user_id = self.user_data_manager._sanitize_user_id(user_id)
                            child_file_docs = list(self.user_data_manager.files_collection.find({
                                "user_id": sanitized_user_id,
                                "file_id": {"$in": list(missing_child_ids)}
                            }))
                            
                            from textmsa.services.data.mongodb_models import file_info_from_dict
                            for file_doc in child_file_docs:
                                try:
                                    file_info = file_info_from_dict(file_doc)
                                    files_map[file_info.file_id] = {
                                        "file_id": file_info.file_id,
                                        "filename": file_info.filename,
                                        "file_path": file_info.file_path,
                                        "file_type_id": file_info.file_type_id,
                                        "description": file_info.description or "",
                                    }
                                except Exception as e:
                                    logger.warning(f"解析子文件信息失败 {file_doc.get('file_id')}: {e}")
                        except Exception as e:
                            logger.warning(f"获取子文件信息失败: {e}")
            
            # 4) 构建关系映射：parent_file_id -> [child_file_id, ...]
            parent_to_children: Dict[str, List[str]] = {}
            child_to_parent: Dict[str, str] = {}
            for relation in relations:
                parent_id = relation.get("parent_file_id")
                child_id = relation.get("child_file_id")
                if parent_id and child_id:
                    # 如果 recursive=False，只保留 parent 和 child 都在 files_map（即 context_files）中的关系
                    # 如果 recursive=True，parent 和 child 都应该在 files_map 中（因为已经递归添加了子文件）
                    if parent_id not in files_map or child_id not in files_map:
                        continue
                    
                    if parent_id not in parent_to_children:
                        parent_to_children[parent_id] = []
                    parent_to_children[parent_id].append(child_id)
                    child_to_parent[child_id] = parent_id
            
            # 5) 找到所有根节点（没有父节点的文件）
            root_file_ids = [
                file_id for file_id in files_map.keys()
                if file_id not in child_to_parent
            ]
            
            # 6) 递归构建文件树节点
            def build_file_node(file_id: str, visited: set[str]) -> Dict[str, Any]:
                """构建文件树节点（FileTreeNode 格式）"""
                if file_id in visited:
                    # 防止循环引用
                    logger.warning(f"检测到循环引用，跳过文件: {file_id}")
                    return None
                
                if file_id not in files_map:
                    return None
                
                file_info = files_map[file_id]
                new_visited = visited | {file_id}
                
                # 构建子节点
                children: List[Dict[str, Any]] = []
                if file_id in parent_to_children:
                    for child_id in parent_to_children[file_id]:
                        # 如果 recursive=False，只添加在 files_map 中的子节点（关系已经过滤过了，这里主要是安全检查）
                        if not recursive and child_id not in files_map:
                            continue
                        child_node = build_file_node(child_id, new_visited)
                        if child_node:
                            children.append(child_node)
                
                # 构建节点（FileTreeNode 格式）
                node: Dict[str, Any] = {
                    "file_id": file_id,
                    "file_name": file_info.get("filename", "unknown"),
                    "file_type_id": file_info.get("file_type_id"),
                    "children": children,
                }
                
                # 根据参数决定是否包含 description
                if include_description:
                    node["description"] = file_info.get("description", "")
                
                # 根据参数决定是否包含 file_path
                if include_path:
                    node["file_path"] = file_info.get("file_path", "")
                
                # 根据参数决定是否包含 preview
                if include_preview:
                    try:
                        # 优先使用 file_info 中的 file_path（来自数据库）
                        # 如果不存在，再尝试从 file_manager 获取
                        saved_path = file_info.get("file_path")
                        if not saved_path:
                            saved_path = self.file_manager.get_file_path(file_id)
                        
                        if saved_path and os.path.exists(saved_path):
                            # 从文件名中提取文件类型
                            filename = file_info.get("filename", "")
                            file_ext = os.path.splitext(filename)[1].lower()
                            file_type_name = file_ext[1:] if file_ext else "unknown"
                            
                            logger.debug(
                                f"开始读取文件预览",
                                extra={
                                    "file_id": file_id,
                                    "filename": filename,
                                    "file_path": saved_path,
                                    "file_type": file_type_name,
                                    "file_exists": os.path.exists(saved_path),
                                }
                            )
                            
                            preview_dict = self.file_reader_tool._read_preview(
                                file_path=saved_path,
                                file_type=file_type_name,
                                filename=filename,
                            )
                            
                            logger.debug(
                                f"文件预览读取完成",
                                extra={
                                    "file_id": file_id,
                                    "filename": filename,
                                    "preview_dict_type": type(preview_dict).__name__,
                                    "preview_dict_keys": list(preview_dict.keys()) if isinstance(preview_dict, dict) else None,
                                    "preview_dict_empty": not preview_dict if preview_dict else True,
                                }
                            )
                            
                            # 将预览转换为字符串格式
                            if preview_dict:
                                try:
                                    preview_str = json.dumps(preview_dict, ensure_ascii=False, indent=2)
                                    node["preview"] = preview_str
                                    logger.debug(
                                        f"文件预览转换成功",
                                        extra={
                                            "file_id": file_id,
                                            "filename": filename,
                                            "preview_length": len(preview_str),
                                        }
                                    )
                                except Exception as json_err:
                                    logger.error(
                                        f"预览JSON序列化失败 {file_id}: {json_err}",
                                        extra={
                                            "file_id": file_id,
                                            "filename": filename,
                                            "preview_dict": str(preview_dict)[:200],
                                        },
                                        exc_info=True,
                                    )
                                    node["preview"] = ""
                            else:
                                logger.warning(
                                    f"文件预览返回空字典 {file_id}",
                                    extra={
                                        "file_id": file_id,
                                        "filename": filename,
                                        "file_path": saved_path,
                                        "file_type": file_type_name,
                                    }
                                )
                                node["preview"] = ""
                        else:
                            logger.warning(
                                f"文件路径不存在或为空 {file_id}",
                                extra={
                                    "file_id": file_id,
                                    "filename": file_info.get("filename", ""),
                                    "file_path_from_info": file_info.get("file_path"),
                                    "file_path_from_manager": self.file_manager.get_file_path(file_id),
                                    "saved_path": saved_path,
                                    "path_exists": os.path.exists(saved_path) if saved_path else False,
                                }
                            )
                            node["preview"] = ""
                    except Exception as e:
                        logger.error(
                            f"获取文件预览失败 {file_id}: {e}",
                            extra={
                                "file_id": file_id,
                                "filename": file_info.get("filename", ""),
                                "error_type": type(e).__name__,
                            },
                            exc_info=True,
                        )
                        node["preview"] = ""
                
                return node
            
            # 7) 构建根节点列表
            root_nodes: List[Dict[str, Any]] = []
            for root_file_id in root_file_ids:
                node = build_file_node(root_file_id, set())
                if node:
                    root_nodes.append(node)
            
            return root_nodes
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取项目文件树列表失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="获取项目文件树列表失败"
            )


# 全局文件服务实例
_file_service: Optional[FileService] = None


def get_file_service() -> FileService:
    """获取全局文件服务实例"""
    global _file_service
    if _file_service is None:
        _file_service = FileService()
    return _file_service


def upload_file(
    file: UploadFile,
    user_id: str,
    project_id: Optional[str] = None,
    file_type_id: Optional[str] = None,
) -> Dict[str, Any]:
    """便捷函数：上传文件"""
    return get_file_service().upload_file(
        file=file,
        user_id=user_id,
        project_id=project_id,
        file_type_id=file_type_id,
    )


def get_file_list(user_id: str) -> List[Dict[str, Any]]:
    """便捷函数：获取文件列表"""
    return get_file_service().get_file_list(user_id)


def get_file_info(file_id: str, user_id: str) -> Dict[str, Any]:
    """便捷函数：获取文件信息"""
    return get_file_service().get_file_info(file_id, user_id)


def get_file_preview(file_id: str, user_id: str, max_length: int = 2000) -> str:
    """便捷函数：获取文件预览"""
    return get_file_service().get_file_preview(
        file_id=file_id,
        user_id=user_id,
        max_length=max_length,
    )


def delete_file(file_id: str, user_id: str, project_id: Optional[str] = None) -> Dict[str, Any]:
    """便捷函数：删除文件"""
    return get_file_service().delete_file(file_id, user_id, project_id=project_id)


def delete_file_children(file_id: str, user_id: str, project_id: Optional[str] = None) -> Dict[str, Any]:
    """便捷函数：递归删除子文件"""
    return get_file_service().delete_file_children(file_id, user_id, project_id=project_id)

