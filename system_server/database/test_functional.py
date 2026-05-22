#!/usr/bin/env python3
"""功能测试脚本 - 测试实际查询功能"""
import sys
import logging
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_query_functions():
    """测试查询函数"""
    logger.info("=" * 60)
    logger.info("功能测试: 查询函数")
    logger.info("=" * 60)
    
    try:
        from database import (
            get_ligand_receptor_pairs,
            filter_available_pairs,
            get_ligand_target_network,
            get_ligand_set,
        )
        
        # 测试 1: 查询所有配体-受体对
        logger.info("\n测试 1: 查询所有配体-受体对...")
        pairs = get_ligand_receptor_pairs()
        logger.info(f"✓ 查询成功，返回 {len(pairs)} 条记录")
        
        if pairs:
            logger.info(f"示例记录: {pairs[0]}")
        
        # 测试 2: 按物种过滤
        logger.info("\n测试 2: 按物种过滤（human）...")
        human_pairs = get_ligand_receptor_pairs(species="human")
        logger.info(f"✓ 查询成功，返回 {len(human_pairs)} 条记录")
        
        # 测试 3: 按可用基因过滤
        logger.info("\n测试 3: 按可用基因过滤...")
        available_genes = ["CXCL12", "CXCR4", "VEGFA", "KDR"]
        filtered = filter_available_pairs(available_genes, species="human")
        logger.info(f"✓ 过滤成功，返回 {len(filtered)} 条记录")
        
        if filtered:
            logger.info(f"示例记录: {filtered[0]}")
        
        # 测试 4: 获取配体-靶基因网络
        logger.info("\n测试 4: 获取配体-靶基因网络...")
        network = get_ligand_target_network(species="human")
        logger.info(f"✓ 构建成功，包含 {len(network)} 个配体")
        
        if network:
            first_ligand = list(network.keys())[0]
            logger.info(f"示例: {first_ligand} -> {network[first_ligand][:3]}...")
        
        # 测试 5: 获取配体列表
        logger.info("\n测试 5: 获取配体列表...")
        ligands = get_ligand_set(species="human")
        logger.info(f"✓ 获取成功，包含 {len(ligands)} 个唯一配体")
        
        if ligands:
            logger.info(f"前5个配体: {ligands[:5]}")
        
        logger.info("\n✅ 所有查询功能测试通过！\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ 查询功能测试失败: {e}", exc_info=True)
        return False


def test_cache_functionality():
    """测试缓存功能"""
    logger.info("=" * 60)
    logger.info("功能测试: 缓存功能")
    logger.info("=" * 60)
    
    try:
        from database import LigandReceptorCache
        
        # 创建缓存实例
        logger.info("\n测试 1: 创建缓存实例...")
        cache = LigandReceptorCache(max_memory_gb=5.0)
        logger.info("✓ 缓存实例创建成功")
        
        # 检查缓存状态
        logger.info("\n测试 2: 检查缓存状态...")
        info = cache.get_cache_info()
        logger.info(f"✓ 缓存信息: {info}")
        
        # 尝试加载数据（如果数据库有数据）
        logger.info("\n测试 3: 尝试从数据库加载数据...")
        loaded = cache.load_from_database(species="human")
        if loaded:
            logger.info("✓ 数据成功加载到内存缓存")
            info = cache.get_cache_info()
            logger.info(f"缓存信息: {info}")
            
            # 测试从缓存获取数据
            logger.info("\n测试 4: 从缓存获取数据...")
            pairs = cache.get_pairs(species="human")
            logger.info(f"✓ 从缓存获取 {len(pairs)} 条记录")
            
            # 测试获取网络
            logger.info("\n测试 5: 从缓存获取配体-靶基因网络...")
            network = cache.get_ligand_target_network(species="human")
            logger.info(f"✓ 从缓存获取网络，包含 {len(network)} 个配体")
            
            # 测试获取配体列表
            logger.info("\n测试 6: 从缓存获取配体列表...")
            ligands = cache.get_ligand_set(species="human")
            logger.info(f"✓ 从缓存获取 {len(ligands)} 个配体")
        else:
            logger.info("⚠️  数据未加载到缓存（可能数据太大或数据库为空）")
        
        # 测试清空缓存
        logger.info("\n测试 7: 清空缓存...")
        cache.clear()
        logger.info("✓ 缓存已清空")
        
        logger.info("\n✅ 所有缓存功能测试通过！\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ 缓存功能测试失败: {e}", exc_info=True)
        return False


def test_database_connection():
    """测试数据库连接和初始化"""
    logger.info("=" * 60)
    logger.info("功能测试: 数据库连接和初始化")
    logger.info("=" * 60)
    
    try:
        from database import get_mongodb_client, init_database
        
        # 测试连接
        logger.info("\n测试 1: 连接数据库...")
        client, db_name = get_mongodb_client()
        logger.info(f"✓ 成功连接到数据库: {db_name}")
        
        # 测试初始化
        logger.info("\n测试 2: 初始化数据库（创建索引）...")
        init_database()
        logger.info("✓ 数据库初始化成功")
        
        # 检查集合
        logger.info("\n测试 3: 检查集合...")
        db = client[db_name]
        collections = db.list_collection_names()
        logger.info(f"✓ 数据库中的集合: {collections}")
        
        if "ligand_receptor_pairs" in collections:
            collection = db["ligand_receptor_pairs"]
            count = collection.count_documents({})
            logger.info(f"✓ ligand_receptor_pairs 集合包含 {count} 条记录")
            
            # 检查索引
            indexes = collection.list_indexes()
            logger.info("✓ 索引列表:")
            for idx in indexes:
                logger.info(f"  - {idx.get('name', 'unnamed')}: {idx.get('key', {})}")
        
        client.close()
        logger.info("\n✅ 数据库连接和初始化测试通过！\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ 数据库连接测试失败: {e}", exc_info=True)
        return False


def main():
    """运行所有功能测试"""
    logger.info("\n" + "=" * 60)
    logger.info("开始运行功能测试")
    logger.info("=" * 60 + "\n")
    
    results = []
    
    # 运行所有测试
    results.append(("数据库连接和初始化", test_database_connection()))
    results.append(("查询函数", test_query_functions()))
    results.append(("缓存功能", test_cache_functionality()))
    
    # 汇总结果
    logger.info("=" * 60)
    logger.info("测试结果汇总")
    logger.info("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
    
    logger.info("=" * 60)
    logger.info(f"总计: {passed}/{total} 测试通过")
    logger.info("=" * 60)
    
    if passed == total:
        logger.info("\n🎉 所有功能测试通过！代码运行正常。\n")
        return 0
    else:
        logger.error("\n❌ 部分测试失败，请检查错误信息。\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

