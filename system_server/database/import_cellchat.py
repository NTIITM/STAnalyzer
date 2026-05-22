"""CellChat 数据导入脚本"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import requests
from tqdm import tqdm

from database.db_connection import get_collection, init_database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# CellChat 数据源说明：
# CellChat 数据主要通过 R 包提供，需要从 R 环境中导出。
# 使用方法：
# 1. 在 R 中运行：
#    library(CellChat)
#    CellChatDB <- CellChatDB.human  # 或 CellChatDB.mouse
#    interactions <- CellChatDB$interaction
#    write.csv(interactions, "cellchat_interactions.csv", row.names = FALSE)
# 2. 然后使用 --csv-file 参数导入生成的 CSV 文件
#
# 数据格式要求：
# CSV 文件应包含以下列（至少需要 ligand 和 receptor）：
# - ligand: 配体基因名
# - receptor: 受体基因名（可以是复合物，用 _ 或 + 分隔）
# - pathway_name: 信号通路名称（可选）
# - annotation: 功能注释（可选）
# - species: 物种信息（可选）


def download_cellchat_data(
    output_dir: Path,
    url: Optional[str] = None,
) -> Path:
    """
    下载 CellChat 数据（如果提供了 URL）
    
    注意：CellChat 数据主要通过 R 包提供，建议用户从 R 环境中导出 CSV 文件。
    如果提供了 URL，此函数会尝试下载。
    
    Args:
        output_dir: 输出目录
        url: 数据源 URL（如果提供）
    
    Returns:
        下载的文件路径
    """
    if url is None:
        raise ValueError(
            "CellChat 数据需要从 R 包中导出。\n"
            "请使用以下 R 代码导出数据：\n"
            "  library(CellChat)\n"
            "  CellChatDB <- CellChatDB.human\n"
            "  interactions <- CellChatDB$interaction\n"
            "  write.csv(interactions, 'cellchat_interactions.csv', row.names = FALSE)\n"
            "然后使用 --csv-file 参数导入生成的 CSV 文件。"
        )
    
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "CellChatDB.csv"
    
    # 如果文件已存在，询问是否覆盖
    if output_file.exists():
        logger.info(f"文件已存在: {output_file}")
        response = input("是否重新下载？(y/n): ").strip().lower()
        if response != "y":
            logger.info("跳过下载，使用现有文件")
            return output_file
    
    logger.info(f"正在从 {url} 下载数据...")
    
    # 增加超时时间并添加重试机制
    max_retries = 3
    timeout = 300  # 5 分钟超时
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, stream=True, timeout=timeout)
            response.raise_for_status()
            
            total_size = int(response.headers.get("content-length", 0))
            
            with open(output_file, "wb") as f:
                if total_size == 0:
                    f.write(response.content)
                else:
                    with tqdm(total=total_size, unit="B", unit_scale=True, desc="下载") as pbar:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                pbar.update(len(chunk))
            
            logger.info(f"下载完成: {output_file}")
            return output_file
            
        except requests.exceptions.Timeout as e:
            if attempt < max_retries - 1:
                logger.warning(f"下载超时，正在重试 ({attempt + 1}/{max_retries})...")
                continue
            else:
                logger.error(f"下载失败（超时）: {e}")
                raise
        except Exception as e:
            logger.error(f"下载失败: {e}")
            raise


def parse_cellchat_csv(csv_path: Path) -> pd.DataFrame:
    """
    解析 CellChat CSV 文件
    
    CellChat 数据格式通常包含：
    - ligand: 配体基因名
    - receptor: 受体基因名（可能是复合物，用 _ 分隔）
    - pathway_name: 信号通路名称
    - annotation: 功能注释
    - interaction_name: 相互作用名称
    
    Args:
        csv_path: CSV 文件路径
    
    Returns:
        解析后的 DataFrame
    """
    logger.info(f"正在解析 CSV 文件: {csv_path}")
    
    try:
        # 尝试不同的分隔符和编码
        encodings = ["utf-8", "latin-1", "iso-8859-1"]
        separators = [",", "\t", ";"]
        
        df = None
        for encoding in encodings:
            for sep in separators:
                try:
                    df = pd.read_csv(csv_path, encoding=encoding, sep=sep, low_memory=False)
                    if len(df.columns) > 1:
                        logger.info(f"成功使用编码 {encoding} 和分隔符 '{sep}' 读取文件")
                        break
                except Exception:
                    continue
            if df is not None and len(df.columns) > 1:
                break
        
        if df is None or len(df.columns) <= 1:
            raise ValueError("无法解析 CSV 文件，请检查文件格式")
        
        logger.info(f"成功读取 {len(df)} 行数据")
        logger.info(f"列名: {list(df.columns)}")
        
        return df
        
    except Exception as e:
        logger.error(f"解析 CSV 文件失败: {e}")
        raise


def normalize_species(species_str: Optional[str]) -> str:
    """
    标准化物种信息
    
    Args:
        species_str: 原始物种字符串
    
    Returns:
        标准化后的物种 ('human', 'mouse', 'both')
    """
    if not species_str or pd.isna(species_str):
        return "both"
    
    species_lower = str(species_str).lower()
    
    if "human" in species_lower and "mouse" in species_lower:
        return "both"
    elif "human" in species_lower or "homo" in species_lower:
        return "human"
    elif "mouse" in species_lower or "mus" in species_lower:
        return "mouse"
    else:
        return "both"


def parse_receptor_complex(receptor_str: str) -> List[str]:
    """
    解析受体复合物（可能包含多个亚基，用 _ 或 + 分隔）
    
    Args:
        receptor_str: 受体字符串，可能包含多个亚基
    
    Returns:
        受体列表（如果只有一个受体，返回单元素列表）
    """
    if not receptor_str or pd.isna(receptor_str):
        return []
    
    receptor_str = str(receptor_str).strip()
    
    # 尝试不同的分隔符
    for sep in ["_", "+", "&", "|"]:
        if sep in receptor_str:
            receptors = [r.strip().upper() for r in receptor_str.split(sep) if r.strip()]
            if receptors:
                return receptors
    
    # 如果没有分隔符，返回单个受体
    return [receptor_str.upper()]


def import_to_database(
    df: pd.DataFrame,
    source: str = "cellchat",
    config_path: Optional[Path] = None,
    batch_size: int = 1000,
) -> int:
    """
    导入数据到 MongoDB 数据库
    
    Args:
        df: 包含配体-受体对数据的 DataFrame
        source: 数据源名称
        config_path: 配置文件路径
        batch_size: 批量插入大小
    
    Returns:
        导入的记录数
    """
    logger.info(f"开始导入数据到数据库（源: {source}）...")
    
    try:
        collection = get_collection("ligand_receptor_pairs", config_path)
        
        # 确定列名（CellChat 可能有不同的列名）
        ligand_cols = ["ligand", "ligand_name", "gene_a", "partner_a"]
        receptor_cols = ["receptor", "receptor_name", "gene_b", "partner_b"]
        pathway_cols = ["pathway_name", "pathway", "category", "interaction_name"]
        annotation_cols = ["annotation", "annotation_strategy", "description"]
        species_cols = ["species", "organism"]
        
        # 查找实际存在的列
        ligand_col = next((col for col in ligand_cols if col in df.columns), None)
        receptor_col = next((col for col in receptor_cols if col in df.columns), None)
        pathway_col = next((col for col in pathway_cols if col in df.columns), None)
        annotation_col = next((col for col in annotation_cols if col in df.columns), None)
        species_col = next((col for col in species_cols if col in df.columns), None)
        
        if not ligand_col or not receptor_col:
            raise ValueError(
                f"无法找到配体或受体列。可用列: {list(df.columns)}"
            )
        
        logger.info(f"使用列: ligand={ligand_col}, receptor={receptor_col}")
        if pathway_col:
            logger.info(f"使用列: pathway={pathway_col}")
        if annotation_col:
            logger.info(f"使用列: annotation={annotation_col}")
        
        # 准备批量插入的数据
        documents: List[Dict] = []
        imported_count = 0
        
        for idx, row in tqdm(df.iterrows(), total=len(df), desc="导入数据"):
            try:
                ligand = str(row[ligand_col]).strip().upper()
                receptor_str = str(row[receptor_col]).strip()
                
                # 跳过空值
                if pd.isna(ligand) or pd.isna(receptor_str) or not ligand or not receptor_str:
                    continue
                
                # 解析受体复合物
                receptors = parse_receptor_complex(receptor_str)
                if not receptors:
                    continue
                
                # 为每个受体创建一条记录
                for receptor in receptors:
                    # 构建文档
                    doc = {
                        "ligand": ligand,
                        "receptor": receptor,
                        "species": normalize_species(
                            row[species_col] if species_col and species_col in row else None
                        ),
                        "pathway": str(row[pathway_col]).strip() if pathway_col and pathway_col in row and not pd.isna(row[pathway_col]) else "",
                        "annotation": str(row[annotation_col]).strip() if annotation_col and annotation_col in row and not pd.isna(row[annotation_col]) else "",
                        "family": "",  # CellChat 可能没有这个字段
                        "evidence": "",  # CellChat 可能没有这个字段
                        "source": source,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                    }
                    
                    documents.append(doc)
                
                # 批量插入
                if len(documents) >= batch_size:
                    try:
                        collection.insert_many(documents, ordered=False)
                        imported_count += len(documents)
                        documents = []
                    except Exception as e:
                        # 忽略重复键错误（由于唯一索引）
                        if "duplicate key" not in str(e).lower() and "E11000" not in str(e):
                            logger.warning(f"批量插入部分失败: {e}")
                        # 尝试逐个插入
                        for doc in documents:
                            try:
                                collection.insert_one(doc)
                                imported_count += 1
                            except Exception as e2:
                                if "duplicate key" not in str(e2).lower() and "E11000" not in str(e2):
                                    logger.warning(f"插入失败: {doc.get('ligand')}-{doc.get('receptor')}: {e2}")
                        documents = []
                        
            except Exception as e:
                logger.warning(f"处理第 {idx} 行时出错: {e}")
                continue
        
        # 插入剩余数据
        if documents:
            try:
                collection.insert_many(documents, ordered=False)
                imported_count += len(documents)
            except Exception as e:
                if "duplicate key" not in str(e).lower() and "E11000" not in str(e):
                    logger.warning(f"批量插入剩余数据失败: {e}")
                # 尝试逐个插入
                for doc in documents:
                    try:
                        collection.insert_one(doc)
                        imported_count += 1
                    except Exception as e2:
                        if "duplicate key" not in str(e2).lower() and "E11000" not in str(e2):
                            logger.warning(f"插入失败: {doc.get('ligand')}-{doc.get('receptor')}: {e2}")
        
        logger.info(f"成功导入 {imported_count} 条记录")
        return imported_count
        
    except Exception as e:
        logger.error(f"导入数据失败: {e}")
        raise


def validate_imported_data(config_path: Optional[Path] = None) -> Dict:
    """
    验证导入的数据
    
    Args:
        config_path: 配置文件路径
    
    Returns:
        验证结果字典
    """
    logger.info("正在验证导入的数据...")
    
    try:
        collection = get_collection("ligand_receptor_pairs", config_path)
        
        # 统计总数
        total_count = collection.count_documents({})
        
        # 按物种统计
        species_counts = {}
        for species in ["human", "mouse", "both"]:
            count = collection.count_documents({"species": species})
            species_counts[species] = count
        
        # 按数据源统计
        source_counts = {}
        pipeline = [
            {"$group": {"_id": "$source", "count": {"$sum": 1}}}
        ]
        for result in collection.aggregate(pipeline):
            source_counts[result["_id"]] = result["count"]
        
        # 统计唯一配体和受体数量
        unique_ligands = len(collection.distinct("ligand"))
        unique_receptors = len(collection.distinct("receptor"))
        
        # CellChat 特定统计
        cellchat_count = collection.count_documents({"source": "cellchat"})
        
        result = {
            "total_count": total_count,
            "species_counts": species_counts,
            "source_counts": source_counts,
            "unique_ligands": unique_ligands,
            "unique_receptors": unique_receptors,
            "cellchat_count": cellchat_count,
        }
        
        logger.info(f"验证结果: {result}")
        return result
        
    except Exception as e:
        logger.error(f"验证数据失败: {e}")
        raise


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="CellChat 数据导入工具")
    parser.add_argument(
        "--download",
        action="store_true",
        help="下载 CellChat 数据",
    )
    parser.add_argument(
        "--import",
        dest="do_import",
        action="store_true",
        help="导入数据到数据库",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="验证导入的数据",
    )
    parser.add_argument(
        "--cache-memory",
        action="store_true",
        help="加载数据到内存缓存（如果数据 < 5GB）",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/cellchat",
        help="数据存储目录（默认: data/cellchat）",
    )
    parser.add_argument(
        "--csv-file",
        type=str,
        help="CSV 文件路径（如果已下载）",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="配置文件路径",
    )
    parser.add_argument(
        "--url",
        type=str,
        help="CellChat 数据源 URL（如果要从网络下载）",
    )
    
    args = parser.parse_args()
    
    data_dir = Path(args.data_dir)
    config_path = Path(args.config) if args.config else None
    
    try:
        # 初始化数据库
        logger.info("初始化数据库...")
        init_database(config_path)
        
        csv_file = None
        
        # 下载数据
        if args.download:
            if args.url:
                csv_file = download_cellchat_data(data_dir, args.url)
            else:
                logger.error(
                    "CellChat 数据需要从 R 包中导出。\n"
                    "请使用以下 R 代码导出数据：\n"
                    "  library(CellChat)\n"
                    "  CellChatDB <- CellChatDB.human\n"
                    "  interactions <- CellChatDB$interaction\n"
                    "  write.csv(interactions, 'cellchat_interactions.csv', row.names = FALSE)\n"
                    "然后使用 --csv-file 参数导入生成的 CSV 文件。"
                )
                sys.exit(1)
        elif args.csv_file:
            csv_file = Path(args.csv_file)
            if not csv_file.exists():
                logger.error(f"CSV 文件不存在: {csv_file}")
                sys.exit(1)
        else:
            # 尝试使用默认路径
            default_csv = data_dir / "CellChatDB.csv"
            if default_csv.exists():
                csv_file = default_csv
                logger.info(f"使用现有文件: {csv_file}")
            else:
                logger.warning("未指定 CSV 文件，且默认文件不存在。使用 --download 下载数据。")
        
        # 导入数据
        if args.do_import and csv_file:
            df = parse_cellchat_csv(csv_file)
            import_to_database(df, source="cellchat", config_path=config_path)
        
        # 验证数据
        if args.validate:
            validate_imported_data(config_path)
        
        # 加载到内存缓存
        if args.cache_memory:
            from database.data_loader import get_global_cache
            
            cache = get_global_cache()
            cache.load_from_database(config_path=str(config_path) if config_path else None)
            logger.info(f"缓存信息: {cache.get_cache_info()}")
        
        logger.info("完成！")
        
    except Exception as e:
        logger.error(f"执行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

