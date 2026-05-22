"""配体-受体查询接口"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Set

import pandas as pd

logger = logging.getLogger(__name__)


def _load_ligands_from_file(path: Path, columns: List[str]) -> Set[str]:
    """
    从本地 CSV 文件中加载配体基因名（大写、去重）。

    Args:
        path: 文件路径
        columns: 需要读取的列名列表

    Returns:
        配体基因名集合（大写）
    """
    if not path.exists():
        logger.warning("配体数据文件不存在: %s", path)
        return set()
    try:
        df = pd.read_csv(path)
    except Exception as e:  # pragma: no cover - 防御性日志
        logger.error("读取配体数据文件失败 %s: %s", path, e)
        return set()

    ligands: Set[str] = set()
    for col in columns:
        if col not in df.columns:
            logger.warning("配体数据文件缺少列 %s: %s", col, path)
            continue
        values = {
            str(v).strip().upper()
            for v in df[col].dropna().tolist()
            if str(v).strip()
        }
        ligands.update(values)
    return ligands


def _get_ligand_set_from_files(base_dir: Optional[str] = None) -> List[str]:
    """
    直接从仓库自带的 data 目录加载配体集合（无需访问 MongoDB）。

    默认目录结构:
        data/
          ├─ nichenet/nichenet_ligand_receptor.csv
          ├─ cellchat/cellchat_interactions_human.csv
          └─ cellphonedb/interaction.csv
    """
    # 默认以当前文件为基准定位到 system_server/data
    data_root = (
        Path(base_dir)
        if base_dir
        else Path(__file__).resolve().parent.parent / "data"
    )

    ligands: Set[str] = set()

    # 1) NicheNet 配体-受体网络
    nichenet_lr = data_root / "nichenet" / "nichenet_ligand_receptor.csv"
    ligands.update(_load_ligands_from_file(nichenet_lr, ["ligand"]))

    # 2) CellChat 交互数据库
    cellchat_csv = data_root / "cellchat" / "cellchat_interactions_human.csv"
    ligands.update(_load_ligands_from_file(cellchat_csv, ["ligand"]))

    # 3) CellPhoneDB 交互数据库（两端都可能作为配体使用）
    cpdb_csv = data_root / "cellphonedb" / "interaction.csv"
    ligands.update(_load_ligands_from_file(cpdb_csv, ["partner_a", "partner_b"]))

    if not ligands:
        raise RuntimeError(
            f"未能从本地数据文件中加载任何配体，请确认数据目录是否存在: {data_root}"
        )

    result = sorted(ligands)
    logger.info("使用本地文件获取到 %d 个唯一配体", len(result))
    return result


def _normalize_species(species_str: Optional[str]) -> str:
    """标准化物种字符串为 human/mouse/both。"""
    if not species_str or pd.isna(species_str):
        return "both"
    lower = str(species_str).lower()
    if "human" in lower or "homo" in lower:
        if "mouse" in lower or "mus" in lower:
            return "both"
        return "human"
    if "mouse" in lower or "mus" in lower:
        return "mouse"
    return "both"


def _load_nichenet_pairs(data_root: Path) -> List[Dict]:
    """从 NicheNet 配体-受体 CSV 构建配体-受体对。"""
    csv_path = data_root / "nichenet" / "nichenet_ligand_receptor.csv"
    if not csv_path.exists():
        return []
    try:
        df = pd.read_csv(csv_path, low_memory=False)
    except Exception as exc:  # pragma: no cover
        logger.error("读取 NicheNet 配体-受体文件失败: %s", exc)
        return []

    ligand_cols = ["ligand", "from", "source"]
    receptor_cols = ["receptor", "to", "target"]
    ligand_col = next((c for c in ligand_cols if c in df.columns), None)
    receptor_col = next((c for c in receptor_cols if c in df.columns), None)
    if not ligand_col or not receptor_col:
        logger.warning("NicheNet 文件中找不到配体或受体列，跳过: %s", csv_path)
        return []

    records: List[Dict] = []
    for _, row in df.iterrows():
        ligand = str(row[ligand_col]).strip().upper()
        receptor = str(row[receptor_col]).strip().upper()
        if not ligand or not receptor or pd.isna(ligand) or pd.isna(receptor):
            continue
        records.append(
            {
                "ligand": ligand,
                "receptor": receptor,
                "species": "both",
                "pathway": "",
                "annotation": "",
                "family": "",
                "evidence": "nichenet_lr_network",
                "source": "nichenet",
            }
        )
    return records


def _parse_cellchat_receptor_complex(receptor_str: str) -> List[str]:
    """解析 CellChat 受体复合物字符串。"""
    if not receptor_str or pd.isna(receptor_str):
        return []
    receptor_str = str(receptor_str).strip()
    for sep in ["_", "+", "&", "|"]:
        if sep in receptor_str:
            parts = [p.strip().upper() for p in receptor_str.split(sep) if p.strip()]
            if parts:
                return parts
    return [receptor_str.upper()]


def _load_cellchat_pairs(data_root: Path) -> List[Dict]:
    """从 CellChat 导出的 CSV 构建配体-受体对。"""
    csv_path = data_root / "cellchat" / "cellchat_interactions_human.csv"
    if not csv_path.exists():
        return []
    try:
        df = pd.read_csv(csv_path, low_memory=False)
    except Exception as exc:  # pragma: no cover
        logger.error("读取 CellChat 文件失败: %s", exc)
        return []

    ligand_cols = ["ligand", "ligand_name", "gene_a", "partner_a"]
    receptor_cols = ["receptor", "receptor_name", "gene_b", "partner_b"]
    pathway_cols = ["pathway_name", "pathway", "category", "interaction_name"]
    annotation_cols = ["annotation", "annotation_strategy", "description"]
    species_cols = ["species", "organism"]

    ligand_col = next((c for c in ligand_cols if c in df.columns), None)
    receptor_col = next((c for c in receptor_cols if c in df.columns), None)
    pathway_col = next((c for c in pathway_cols if c in df.columns), None)
    annotation_col = next((c for c in annotation_cols if c in df.columns), None)
    species_col = next((c for c in species_cols if c in df.columns), None)

    if not ligand_col or not receptor_col:
        logger.warning("CellChat 文件中找不到配体或受体列，跳过: %s", csv_path)
        return []

    records: List[Dict] = []
    for _, row in df.iterrows():
        ligand = str(row[ligand_col]).strip().upper()
        receptor_raw = str(row[receptor_col]).strip()
        if not ligand or not receptor_raw or pd.isna(ligand) or pd.isna(receptor_raw):
            continue
        receptors = _parse_cellchat_receptor_complex(receptor_raw)
        if not receptors:
            continue
        species_val = (
            _normalize_species(row[species_col]) if species_col and species_col in row else "both"
        )
        pathway_val = (
            str(row[pathway_col]).strip()
            if pathway_col and pathway_col in row and not pd.isna(row[pathway_col])
            else ""
        )
        annotation_val = (
            str(row[annotation_col]).strip()
            if annotation_col and annotation_col in row and not pd.isna(row[annotation_col])
            else ""
        )
        for receptor in receptors:
            records.append(
                {
                    "ligand": ligand,
                    "receptor": receptor,
                    "species": species_val,
                    "pathway": pathway_val,
                    "annotation": annotation_val,
                    "family": "",
                    "evidence": "",
                    "source": "cellchat",
                }
            )
    return records


def _determine_cpdb_ligand_receptor(
    row: pd.Series,
    gene_a: str,
    gene_b: str,
    partner_a: Optional[str],
    partner_b: Optional[str],
) -> tuple[str, str]:
    """根据 CellPhoneDB 的 partner 列判断配体和受体。"""
    if partner_a and partner_b:
        a_val = str(row.get(partner_a, "")).lower()
        b_val = str(row.get(partner_b, "")).lower()
        if "ligand" in a_val:
            return str(row[gene_a]), str(row[gene_b])
        if "ligand" in b_val:
            return str(row[gene_b]), str(row[gene_a])
    # 默认 gene_a 是配体
    return str(row[gene_a]), str(row[gene_b])


def _load_cellphonedb_pairs(data_root: Path) -> List[Dict]:
    """从 CellPhoneDB interaction.csv 构建配体-受体对。"""
    csv_path = data_root / "cellphonedb" / "interaction.csv"
    if not csv_path.exists():
        return []
    try:
        df = pd.read_csv(csv_path, low_memory=False)
    except Exception as exc:  # pragma: no cover
        logger.error("读取 CellPhoneDB 文件失败: %s", exc)
        return []

    gene_a_cols = ["gene_name_a", "gene_a", "partner_a", "id_a"]
    gene_b_cols = ["gene_name_b", "gene_b", "partner_b", "id_b"]
    partner_a_cols = ["partner_a", "type_a", "role_a"]
    partner_b_cols = ["partner_b", "type_b", "role_b"]
    species_cols = ["species", "organism", "species_id"]
    pathway_cols = ["pathway_name", "pathway", "pathway_name_final"]
    annotation_cols = ["annotation", "annotation_strategy", "annotation_final"]

    gene_a = next((c for c in gene_a_cols if c in df.columns), None)
    gene_b = next((c for c in gene_b_cols if c in df.columns), None)
    partner_a = next((c for c in partner_a_cols if c in df.columns), None)
    partner_b = next((c for c in partner_b_cols if c in df.columns), None)
    species_col = next((c for c in species_cols if c in df.columns), None)
    pathway_col = next((c for c in pathway_cols if c in df.columns), None)
    annotation_col = next((c for c in annotation_cols if c in df.columns), None)

    if not gene_a or not gene_b:
        logger.warning("CellPhoneDB 文件中找不到基因名称列，跳过: %s", csv_path)
        return []

    records: List[Dict] = []
    for _, row in df.iterrows():
        ligand_raw, receptor_raw = _determine_cpdb_ligand_receptor(
            row, gene_a, gene_b, partner_a, partner_b
        )
        if not ligand_raw or not receptor_raw or pd.isna(ligand_raw) or pd.isna(receptor_raw):
            continue

        species_val = (
            _normalize_species(row[species_col]) if species_col and species_col in row else "both"
        )
        pathway_val = (
            str(row[pathway_col]).strip()
            if pathway_col and pathway_col in row and not pd.isna(row[pathway_col])
            else ""
        )
        annotation_val = (
            str(row[annotation_col]).strip()
            if annotation_col and annotation_col in row and not pd.isna(row[annotation_col])
            else ""
        )

        records.append(
            {
                "ligand": str(ligand_raw).strip().upper(),
                "receptor": str(receptor_raw).strip().upper(),
                "species": species_val,
                "pathway": pathway_val,
                "annotation": annotation_val,
                "family": "",
                "evidence": "",
                "source": "cellphonedb",
            }
        )
    return records


def _get_ligand_receptor_pairs_from_files(
    base_dir: Optional[str] = None,
) -> List[Dict]:
    """综合 NicheNet、CellChat、CellPhoneDB 本地文件构建配体-受体对列表。"""
    data_root = (
        Path(base_dir)
        if base_dir
        else Path(__file__).resolve().parent.parent / "data"
    )

    records: List[Dict] = []
    records.extend(_load_nichenet_pairs(data_root))
    records.extend(_load_cellchat_pairs(data_root))
    records.extend(_load_cellphonedb_pairs(data_root))

    if not records:
        raise RuntimeError(
            f"未能从本地数据文件中加载任何配体-受体对，请确认数据目录是否存在且包含有效文件: {data_root}"
        )

    logger.info("从本地文件加载到 %d 条配体-受体对", len(records))
    return records


def get_ligand_receptor_pairs(
    species: Optional[str] = None,
    source: Optional[str] = None,
    config_path: Optional[str] = None,
) -> List[Dict]:
    """
    查询配体-受体对
    
    Args:
        species: 物种过滤 ('human', 'mouse', 'both')，None 表示不过滤
        source: 数据源过滤，None 表示不过滤
        config_path: 配置文件路径
    
    Returns:
        配体-受体对列表，每个元素包含:
        {
            "ligand": str,
            "receptor": str,
            "species": str,
            "pathway": Optional[str],
            "annotation": Optional[str],
            "family": Optional[str],
            "evidence": Optional[str],
            "source": str
        }
    """
    try:
        base_dir = os.getenv("MISTY_LIGAND_DATA_DIR")  # 复用同一数据目录配置
        records = _get_ligand_receptor_pairs_from_files(base_dir)
        
        # 物种过滤
        if species:
            species = species.lower()
            records = [
                r for r in records if r.get("species", "both").lower() == species
            ]

        # 数据源过滤
        if source:
            records = [r for r in records if r.get("source") == source]
        
        logger.info("获取到 %d 条配体-受体对记录", len(records))
        return records
        
    except Exception as e:  # pragma: no cover
        logger.error("从本地文件获取配体-受体对失败: %s", e)
        return []


def filter_available_pairs(
    available_genes: List[str],
    species: Optional[str] = None,
    source: Optional[str] = None,
    config_path: Optional[str] = None,
) -> List[Dict]:
    """
    根据可用基因过滤配体-受体对
    
    Args:
        available_genes: 可用基因列表（大写）
        species: 物种过滤
        source: 数据源过滤
        config_path: 配置文件路径
    
    Returns:
        过滤后的配体-受体对列表
    """
    try:
        # 获取所有配体-受体对
        all_pairs = get_ligand_receptor_pairs(
            species=species,
            source=source,
            config_path=config_path,
        )
        
        # 转换为大写集合以便快速查找
        available_genes_set = {gene.upper() for gene in available_genes}
        
        # 过滤：配体和受体都必须在可用基因列表中
        filtered_pairs = [
            pair
            for pair in all_pairs
            if pair.get("ligand", "").upper() in available_genes_set
            and pair.get("receptor", "").upper() in available_genes_set
        ]
        
        logger.info(
            f"从 {len(all_pairs)} 条记录中过滤出 {len(filtered_pairs)} 条可用配体-受体对"
        )
        return filtered_pairs
        
    except Exception as e:
        logger.error(f"过滤配体-受体对失败: {e}")
        return []


def get_ligand_target_network(
    species: Optional[str] = None,
    source: Optional[str] = None,
    config_path: Optional[str] = None,
) -> Dict[str, List[str]]:
    """
    获取配体-靶基因网络（用于 NicheNet）
    
    注意：此函数基于配体-受体对构建网络，其中受体被视为靶基因
    
    Args:
        species: 物种过滤
        source: 数据源过滤
        config_path: 配置文件路径
    
    Returns:
        字典，键为配体基因名，值为靶基因（受体）列表
        {
            "CXCL12": ["CXCR4", "CXCR7"],
            "VEGFA": ["KDR", "FLT1"],
            ...
        }
    """
    try:
        pairs = get_ligand_receptor_pairs(
            species=species,
            source=source,
            config_path=config_path,
        )
        
        # 构建配体 -> 靶基因（受体）网络
        network: Dict[str, Set[str]] = {}
        for pair in pairs:
            ligand = pair.get("ligand", "").upper()
            receptor = pair.get("receptor", "").upper()
            
            if ligand and receptor:
                if ligand not in network:
                    network[ligand] = set()
                network[ligand].add(receptor)
        
        # 转换为列表格式
        result = {ligand: list(targets) for ligand, targets in network.items()}
        
        logger.info(f"构建配体-靶基因网络，包含 {len(result)} 个配体")
        return result
        
    except Exception as e:
        logger.error(f"构建配体-靶基因网络失败: {e}")
        return {}


def get_ligand_set(
    species: Optional[str] = None,
    source: Optional[str] = None,
    config_path: Optional[str] = None,
) -> List[str]:
    """
    获取配体列表（用于 MISTY 等服务），完全基于本地数据文件。
    """
    try:
        base_dir = os.getenv("MISTY_LIGAND_DATA_DIR")
        # 直接基于本地文件构建（不再依赖 MongoDB）
        pairs = _get_ligand_receptor_pairs_from_files(base_dir)
        
        ligands = {
            p.get("ligand", "").upper()
            for p in pairs
            if p.get("ligand")
        }
        result = sorted(ligands)
        logger.info("获取到 %d 个唯一配体", len(result))
        return result
        
    except Exception as e:  # pragma: no cover
        logger.error("获取配体列表失败: %s", e)
        return []

