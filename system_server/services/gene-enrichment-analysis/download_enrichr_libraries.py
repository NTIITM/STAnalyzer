#!/usr/bin/env python3
"""
下载 Enrichr 基因集库到本地
用于离线环境下的富集分析，避免网络请求失败
"""
import os
import sys
import requests
import json
from pathlib import Path
from typing import List, Dict
import time

# Enrichr API 端点
ENRICHR_API_URL = "https://maayanlab.cloud/Enrichr"
ENRICHR_LIBRARY_LIST_URL = f"{ENRICHR_API_URL}/datasetStatistics"
ENRICHR_GENE_SET_URL = f"{ENRICHR_API_URL}/geneSetLibrary"

# 常用的基因集库列表（可以根据需要扩展）
COMMON_LIBRARIES = [
    # GO 数据库
    "GO_Biological_Process_2021",
    "GO_Cellular_Component_2021",
    "GO_Molecular_Function_2021",
    "GO_Biological_Process_2023",
    "GO_Cellular_Component_2023",
    "GO_Molecular_Function_2023",
    
    # KEGG 数据库
    "KEGG_2021_Human",
    "KEGG_2021_Mouse",
    "KEGG_2019_Human",
    "KEGG_2019_Mouse",
    
    # Reactome 数据库
    "Reactome_2022",
    
    # WikiPathways
    "WikiPathways_2021_Human",
    "WikiPathways_2021_Mouse",
    
    # MSigDB
    "MSigDB_Hallmark_2020",
    "MSigDB_Oncogenic_Signatures",
    
    # 其他常用库
    "ChEA_2022",
    "ENCODE_and_ChEA_Consensus_TFs_from_ChIP-X",
    "Transcription_Factor_PPIs",
    "ARCHS4_TFs_Coexp",
    "ENCODE_TF_ChIP-seq_2015",
    "TF_Perturbations_Followed_by_Expression",
    "TF-LOF_Expression_from_GEO",
    "Virus_Perturbations_from_GEO_up",
    "Virus_Perturbations_from_GEO_down",
    "Disease_Perturbations_from_GEO_up",
    "Disease_Perturbations_from_GEO_down",
    "Drug_Perturbations_from_GEO_2014",
    "Drug_Perturbations_from_GEO_up",
    "Drug_Perturbations_from_GEO_down",
    "DrugMatrix",
    "LINCS_L1000_Chem_Pert_up",
    "LINCS_L1000_Chem_Pert_down",
    "LINCS_L1000_Chem_Pert_Consensus_Sigs",
    "LINCS_L1000_Ligand_Perturbations_up",
    "LINCS_L1000_Ligand_Perturbations_down",
    "MGI_Mammalian_Phenotype_Level_4_2021",
    "Human_Phenotype_Ontology",
    "GWAS_Catalog_2019",
    "DisGeNET",
    "Jensen_DISEASES",
    "Jensen_COMPARTMENTS",
    "Jensen_TISSUES",
    "Human_Gene_Atlas",
    "Mouse_Gene_Atlas",
    "ARCHS4_Tissues",
    "GTEx_Tissue_Sample_Gene_Expression_Profiles_up",
    "GTEx_Tissue_Sample_Gene_Expression_Profiles_down",
    "ARCHS4_Cell-lines",
    "ARCHS4_IDG_Coexp",
    "ARCHS4_Kinases_Coexp",
    "Cancer_Cell_Line_Encyclopedia",
    "NCI-60_Cancer_Cell_Lines",
    "Achilles_fitness_decrease",
    "Achilles_fitness_increase",
    "Achilles_Common_Essential",
    "Achilles_Nonessential",
    "CRISPR-Cas9_KO",
    "CRISPR-Cas9_KO_Repurposing_Hub",
    "DepMap_WG_CRISPR_Genetic_Dependencies_2020",
    "DepMap_WG_CRISPR_KO_Screens_2020",
    "DepMap_WG_RNAi_Genetic_Dependencies_2020",
    "DepMap_WG_RNAi_KO_Screens_2020",
    "BioPlanet_2019",
    "Elsevier_Pathway_Collection",
    "Genome_Browser_PWMs",
    "TRANSFAC_and_JASPAR_PWMs",
    "JASPAR_2022",
    "miRTarBase_2017",
    "TargetScan_microRNA_2017",
    "TargetScan_microRNA",
    "miRDB_2022",
    "miRNA_Targets_2017",
    "miRNA_Targets",
    "MGI_Mammalian_Phenotype_2017",
    "MGI_Mammalian_Phenotype_Level_3",
    "MGI_Mammalian_Phenotype_Level_4",
    "Human_Phenotype_Ontology",
    "OMIM_Disease",
    "OMIM_Expanded",
    "Jensen_DISEASES",
    "Jensen_COMPARTMENTS",
    "Jensen_TISSUES",
    "Human_Gene_Atlas",
    "Mouse_Gene_Atlas",
    "ARCHS4_Tissues",
    "GTEx_Tissue_Sample_Gene_Expression_Profiles_up",
    "GTEx_Tissue_Sample_Gene_Expression_Profiles_down",
    "ARCHS4_Cell-lines",
    "ARCHS4_IDG_Coexp",
    "ARCHS4_Kinases_Coexp",
    "Cancer_Cell_Line_Encyclopedia",
    "NCI-60_Cancer_Cell_Lines",
    "Achilles_fitness_decrease",
    "Achilles_fitness_increase",
    "Achilles_Common_Essential",
    "Achilles_Nonessential",
    "CRISPR-Cas9_KO",
    "CRISPR-Cas9_KO_Repurposing_Hub",
    "DepMap_WG_CRISPR_Genetic_Dependencies_2020",
    "DepMap_WG_CRISPR_KO_Screens_2020",
    "DepMap_WG_RNAi_Genetic_Dependencies_2020",
    "DepMap_WG_RNAi_KO_Screens_2020",
    "BioPlanet_2019",
    "Elsevier_Pathway_Collection",
    "Genome_Browser_PWMs",
    "TRANSFAC_and_JASPAR_PWMs",
    "JASPAR_2022",
    "miRTarBase_2017",
    "TargetScan_microRNA_2017",
    "TargetScan_microRNA",
    "miRDB_2022",
    "miRNA_Targets_2017",
    "miRNA_Targets",
]

def get_all_libraries() -> List[str]:
    """获取 Enrichr 所有可用的基因集库列表"""
    try:
        response = requests.get(ENRICHR_LIBRARY_LIST_URL, timeout=30)
        response.raise_for_status()
        data = response.json()
        libraries = [lib["libraryName"] for lib in data.get("statistics", [])]
        return libraries
    except Exception as e:
        print(f"警告: 无法获取库列表，将使用预定义的常用库列表: {e}")
        return COMMON_LIBRARIES

def download_gene_set(library_name: str, output_dir: str, mode: str = "text") -> bool:
    """
    下载单个基因集库
    
    Args:
        library_name: 库名称
        output_dir: 输出目录
        mode: 下载模式 ('text' 或 'json')
    
    Returns:
        是否成功下载
    """
    try:
        params = {
            "mode": mode,
            "libraryName": library_name
        }
        
        print(f"正在下载: {library_name}...")
        response = requests.get(ENRICHR_GENE_SET_URL, params=params, timeout=60)
        response.raise_for_status()
        
        # 保存文件
        if mode == "text":
            # GMT 格式
            filename = f"{library_name}.gmt"
            filepath = os.path.join(output_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(response.text)
            print(f"  ✓ 已保存: {filepath}")
        else:
            # JSON 格式
            filename = f"{library_name}.json"
            filepath = os.path.join(output_dir, filename)
            data = response.json()
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"  ✓ 已保存: {filepath}")
        
        return True
    except requests.exceptions.RequestException as e:
        print(f"  ✗ 下载失败: {library_name} - {e}")
        return False
    except Exception as e:
        print(f"  ✗ 保存失败: {library_name} - {e}")
        return False

def download_all_libraries(
    output_dir: str = "./gmt",
    libraries: List[str] = None,
    mode: str = "text",
    delay: float = 0.5
) -> Dict[str, bool]:
    """
    下载所有指定的基因集库
    
    Args:
        output_dir: 输出目录
        libraries: 要下载的库列表，如果为 None 则下载所有可用库
        mode: 下载模式 ('text' 或 'json')
        delay: 每次请求之间的延迟（秒），避免请求过快
    
    Returns:
        下载结果字典 {库名: 是否成功}
    """
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 获取库列表
    if libraries is None:
        print("获取 Enrichr 所有可用基因集库...")
        libraries = get_all_libraries()
        print(f"找到 {len(libraries)} 个库")
    else:
        print(f"将下载 {len(libraries)} 个指定的库")
    
    # 下载每个库
    results = {}
    success_count = 0
    fail_count = 0
    
    for i, library in enumerate(libraries, 1):
        print(f"[{i}/{len(libraries)}] ", end="")
        success = download_gene_set(library, output_dir, mode)
        results[library] = success
        
        if success:
            success_count += 1
        else:
            fail_count += 1
        
        # 延迟，避免请求过快
        if i < len(libraries):
            time.sleep(delay)
    
    # 打印总结
    print("\n" + "=" * 60)
    print("下载完成!")
    print(f"成功: {success_count}/{len(libraries)}")
    print(f"失败: {fail_count}/{len(libraries)}")
    print(f"文件保存在: {os.path.abspath(output_dir)}")
    print("=" * 60)
    
    return results

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="下载 Enrichr 基因集库到本地",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 下载所有常用库
  python download_enrichr_libraries.py
  
  # 下载指定的库
  python download_enrichr_libraries.py --libraries GO_Biological_Process_2021 KEGG_2021_Human
  
  # 下载所有可用库
  python download_enrichr_libraries.py --all
  
  # 使用 JSON 格式
  python download_enrichr_libraries.py --mode json
        """
    )
    
    parser.add_argument(
        "--output-dir",
        "-o",
        default="./gmt",
        help="输出目录（默认: ./gmt）"
    )
    
    parser.add_argument(
        "--libraries",
        "-l",
        nargs="+",
        help="要下载的库名称列表（默认: 使用预定义的常用库）"
    )
    
    parser.add_argument(
        "--all",
        action="store_true",
        help="下载所有可用的库（从 Enrichr API 获取）"
    )
    
    parser.add_argument(
        "--mode",
        choices=["text", "json"],
        default="text",
        help="下载格式: text (GMT格式) 或 json (默认: text)"
    )
    
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="每次请求之间的延迟（秒，默认: 0.5）"
    )
    
    args = parser.parse_args()
    
    # 确定要下载的库列表
    if args.all:
        libraries = None  # None 表示下载所有库
    elif args.libraries:
        libraries = args.libraries
    else:
        libraries = COMMON_LIBRARIES
    
    # 执行下载
    results = download_all_libraries(
        output_dir=args.output_dir,
        libraries=libraries,
        mode=args.mode,
        delay=args.delay
    )
    
    # 如果有失败的，打印失败列表
    failed = [lib for lib, success in results.items() if not success]
    if failed:
        print("\n失败的库:")
        for lib in failed:
            print(f"  - {lib}")
        sys.exit(1)
    else:
        print("\n所有库下载成功!")
        sys.exit(0)

if __name__ == "__main__":
    main()

