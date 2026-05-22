"""NicheNet 数据导入脚本"""
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

# NicheNet 数据源说明：
# NicheNet 数据主要通过 R 包提供，需要从 R 环境中导出。
# 使用方法：
# 1. 在 R 中运行：
#    library(nichenetr)
#    # 方法1：从在线资源加载
#    ligand_target_matrix <- readRDS(url("https://zenodo.org/record/3260758/files/ligand_target_matrix.rds"))
#    lr_network <- readRDS(url("https://zenodo.org/record/3260758/files/lr_network.rds"))
#    # 方法2：从已安装的包中加载
#    # data("ligand_target_matrix")
#    # data("lr_network")
#    
#    # 导出配体-靶基因矩阵（矩阵格式，行为配体，列为靶基因）
#    write.table(ligand_target_matrix, "nichenet_ligand_target.txt", sep="\t", quote=FALSE)
#    
#    # 导出配体-受体网络
#    write.csv(lr_network, "nichenet_ligand_receptor.csv", row.names = FALSE)
# 2. 然后使用相应的参数导入生成的文件
#
# 数据格式要求：
# - 配体-靶基因矩阵：制表符分隔，第一列为配体，后续列为靶基因，值为权重
# - 配体-受体网络：CSV 格式，包含 'from' (配体) 和 'to' (受体) 列


def download_nichenet_data(
    output_dir: Path,
    url: Optional[str] = None,
    data_type: str = "ligand_target",
) -> Path:
    """
    下载 NicheNet 数据
    
    Args:
        output_dir: 输出目录
        url: 数据源 URL，如果为 None 则使用默认 URL
        data_type: 数据类型 ('ligand_target' 或 'ligand_receptor')
    
    Returns:
        下载的文件路径
    """
    if url is None:
        if data_type == "ligand_target":
            url = NICHENET_LIGAND_TARGET_URL
        else:
            url = NICHENET_LIGAND_RECEPTOR_URL
    
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"nichenet_{data_type}.txt"
    output_file = output_dir / filename
    
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


def parse_ligand_target_matrix(txt_path: Path) -> pd.DataFrame:
    """
    解析 NicheNet 配体-靶基因矩阵文件
    
    NicheNet 配体-靶基因矩阵格式：
    - 第一列是配体基因名
    - 后续列是靶基因，值为权重/置信度分数
    
    Args:
        txt_path: 文本文件路径
    
    Returns:
        解析后的 DataFrame，包含 ligand, target, weight 列
    """
    logger.info(f"正在解析配体-靶基因矩阵文件: {txt_path}")
    
    try:
        # 读取矩阵文件（可能是制表符分隔）
        df_matrix = pd.read_csv(txt_path, sep="\t", index_col=0, low_memory=False)
        
        logger.info(f"成功读取矩阵，形状: {df_matrix.shape}")
        logger.info(f"配体数量: {len(df_matrix.index)}")
        logger.info(f"靶基因数量: {len(df_matrix.columns)}")
        
        # 将矩阵转换为长格式
        records = []
        for ligand in df_matrix.index:
            for target in df_matrix.columns:
                weight = df_matrix.loc[ligand, target]
                # 只保留非零权重
                if pd.notna(weight) and float(weight) != 0:
                    records.append({
                        "ligand": str(ligand).strip().upper(),
                        "target": str(target).strip().upper(),
                        "weight": float(weight),
                    })
        
        df = pd.DataFrame(records)
        logger.info(f"转换后记录数: {len(df)}")
        
        return df
        
    except Exception as e:
        logger.error(f"解析配体-靶基因矩阵失败: {e}")
        raise


def parse_ligand_receptor_network(txt_path: Path) -> pd.DataFrame:
    """
    解析 NicheNet 配体-受体网络文件
    
    NicheNet 配体-受体网络格式：
    - 列：ligand, receptor, 可能还有权重或其他信息
    
    Args:
        txt_path: 文本文件路径
    
    Returns:
        解析后的 DataFrame
    """
    logger.info(f"正在解析配体-受体网络文件: {txt_path}")
    
    try:
        # 尝试不同的分隔符
        separators = ["\t", ",", ";"]
        df = None
        
        for sep in separators:
            try:
                df = pd.read_csv(txt_path, sep=sep, low_memory=False)
                if len(df.columns) >= 2:
                    logger.info(f"成功使用分隔符 '{sep}' 读取文件")
                    break
            except Exception:
                continue
        
        if df is None or len(df.columns) < 2:
            raise ValueError("无法解析配体-受体网络文件，请检查文件格式")
        
        logger.info(f"成功读取 {len(df)} 行数据")
        logger.info(f"列名: {list(df.columns)}")
        
        return df
        
    except Exception as e:
        logger.error(f"解析配体-受体网络失败: {e}")
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


def import_ligand_target_to_database(
    df: pd.DataFrame,
    source: str = "nichenet",
    config_path: Optional[Path] = None,
    batch_size: int = 1000,
) -> int:
    """
    导入配体-靶基因数据到 MongoDB 数据库
    
    注意：NicheNet 的靶基因不是受体，而是下游靶基因。
    为了兼容现有数据库结构，我们将靶基因作为受体存储，
    并在 evidence 字段中标记为 "target_gene"。
    
    Args:
        df: 包含配体-靶基因数据的 DataFrame，必须包含 'ligand' 和 'target' 列
        source: 数据源名称
        config_path: 配置文件路径
        batch_size: 批量插入大小
    
    Returns:
        导入的记录数
    """
    logger.info(f"开始导入配体-靶基因数据到数据库（源: {source}）...")
    
    try:
        collection = get_collection("ligand_receptor_pairs", config_path)
        
        # 检查必需的列
        if "ligand" not in df.columns or "target" not in df.columns:
            raise ValueError(
                f"DataFrame 必须包含 'ligand' 和 'target' 列。可用列: {list(df.columns)}"
            )
        
        weight_col = "weight" if "weight" in df.columns else None
        
        # 准备批量插入的数据
        documents: List[Dict] = []
        imported_count = 0
        
        for idx, row in tqdm(df.iterrows(), total=len(df), desc="导入数据"):
            try:
                ligand = str(row["ligand"]).strip().upper()
                target = str(row["target"]).strip().upper()
                
                # 跳过空值
                if pd.isna(ligand) or pd.isna(target) or not ligand or not target:
                    continue
                
                # 构建文档
                # 注意：将靶基因作为受体存储，但标记为靶基因关系
                doc = {
                    "ligand": ligand,
                    "receptor": target,  # 将靶基因作为受体存储
                    "species": "both",  # NicheNet 通常包含人类和小鼠数据
                    "pathway": "",
                    "annotation": "target_gene",  # 标记为靶基因关系
                    "family": "",
                    "evidence": f"weight={row[weight_col]:.4f}" if weight_col and pd.notna(row[weight_col]) else "nichenet",
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
        
        logger.info(f"成功导入 {imported_count} 条配体-靶基因记录")
        return imported_count
        
    except Exception as e:
        logger.error(f"导入数据失败: {e}")
        raise


def import_ligand_receptor_to_database(
    df: pd.DataFrame,
    source: str = "nichenet",
    config_path: Optional[Path] = None,
    batch_size: int = 1000,
) -> int:
    """
    导入配体-受体数据到 MongoDB 数据库
    
    Args:
        df: 包含配体-受体对数据的 DataFrame
        source: 数据源名称
        config_path: 配置文件路径
        batch_size: 批量插入大小
    
    Returns:
        导入的记录数
    """
    logger.info(f"开始导入配体-受体数据到数据库（源: {source}）...")
    
    try:
        collection = get_collection("ligand_receptor_pairs", config_path)
        
        # 确定列名
        ligand_cols = ["ligand", "from", "source"]
        receptor_cols = ["receptor", "to", "target"]
        
        ligand_col = next((col for col in ligand_cols if col in df.columns), None)
        receptor_col = next((col for col in receptor_cols if col in df.columns), None)
        
        if not ligand_col or not receptor_col:
            raise ValueError(
                f"无法找到配体或受体列。可用列: {list(df.columns)}"
            )
        
        logger.info(f"使用列: ligand={ligand_col}, receptor={receptor_col}")
        
        # 准备批量插入的数据
        documents: List[Dict] = []
        imported_count = 0
        
        for idx, row in tqdm(df.iterrows(), total=len(df), desc="导入数据"):
            try:
                ligand = str(row[ligand_col]).strip().upper()
                receptor = str(row[receptor_col]).strip().upper()
                
                # 跳过空值
                if pd.isna(ligand) or pd.isna(receptor) or not ligand or not receptor:
                    continue
                
                # 构建文档
                doc = {
                    "ligand": ligand,
                    "receptor": receptor,
                    "species": "both",  # NicheNet 通常包含人类和小鼠数据
                    "pathway": "",
                    "annotation": "",
                    "family": "",
                    "evidence": "nichenet_lr_network",
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
        
        logger.info(f"成功导入 {imported_count} 条配体-受体记录")
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
        
        # NicheNet 特定统计
        nichenet_count = collection.count_documents({"source": "nichenet"})
        nichenet_target_count = collection.count_documents({"source": "nichenet", "annotation": "target_gene"})
        
        result = {
            "total_count": total_count,
            "species_counts": species_counts,
            "source_counts": source_counts,
            "unique_ligands": unique_ligands,
            "unique_receptors": unique_receptors,
            "nichenet_count": nichenet_count,
            "nichenet_target_count": nichenet_target_count,
        }
        
        logger.info(f"验证结果: {result}")
        return result
        
    except Exception as e:
        logger.error(f"验证数据失败: {e}")
        raise


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="NicheNet 数据导入工具")
    parser.add_argument(
        "--download",
        action="store_true",
        help="下载 NicheNet 数据",
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
        default="data/nichenet",
        help="数据存储目录（默认: data/nichenet）",
    )
    parser.add_argument(
        "--ligand-target-file",
        type=str,
        help="配体-靶基因矩阵文件路径（如果已下载）",
    )
    parser.add_argument(
        "--ligand-receptor-file",
        type=str,
        help="配体-受体网络文件路径（如果已下载）",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="配置文件路径",
    )
    parser.add_argument(
        "--data-type",
        type=str,
        choices=["ligand_target", "ligand_receptor", "both"],
        default="both",
        help="要导入的数据类型（默认: both）",
    )
    
    args = parser.parse_args()
    
    data_dir = Path(args.data_dir)
    config_path = Path(args.config) if args.config else None
    
    try:
        # 初始化数据库
        logger.info("初始化数据库...")
        init_database(config_path)
        
        ligand_target_file = None
        ligand_receptor_file = None
        
        # 下载数据
        if args.download:
            if args.data_type in ["ligand_target", "both"]:
                ligand_target_file = download_nichenet_data(data_dir, data_type="ligand_target")
            if args.data_type in ["ligand_receptor", "both"]:
                ligand_receptor_file = download_nichenet_data(data_dir, data_type="ligand_receptor")
        else:
            # 使用提供的文件路径或默认路径
            if args.ligand_target_file:
                ligand_target_file = Path(args.ligand_target_file)
                if not ligand_target_file.exists():
                    logger.error(f"配体-靶基因文件不存在: {ligand_target_file}")
                    sys.exit(1)
            elif args.data_type in ["ligand_target", "both"]:
                default_file = data_dir / "nichenet_ligand_target.txt"
                if default_file.exists():
                    ligand_target_file = default_file
                    logger.info(f"使用现有文件: {ligand_target_file}")
            
            if args.ligand_receptor_file:
                ligand_receptor_file = Path(args.ligand_receptor_file)
                if not ligand_receptor_file.exists():
                    logger.error(f"配体-受体文件不存在: {ligand_receptor_file}")
                    sys.exit(1)
            elif args.data_type in ["ligand_receptor", "both"]:
                default_file = data_dir / "nichenet_ligand_receptor.txt"
                if default_file.exists():
                    ligand_receptor_file = default_file
                    logger.info(f"使用现有文件: {ligand_receptor_file}")
        
        # 导入数据
        if args.do_import:
            if ligand_target_file and args.data_type in ["ligand_target", "both"]:
                df = parse_ligand_target_matrix(ligand_target_file)
                import_ligand_target_to_database(df, source="nichenet", config_path=config_path)
            
            if ligand_receptor_file and args.data_type in ["ligand_receptor", "both"]:
                df = parse_ligand_receptor_network(ligand_receptor_file)
                import_ligand_receptor_to_database(df, source="nichenet", config_path=config_path)
        
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

