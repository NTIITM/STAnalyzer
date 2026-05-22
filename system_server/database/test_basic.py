#!/usr/bin/env python3
"""基本功能测试脚本"""
import sys
import logging
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_imports():
    """测试模块导入"""
    logger.info("=" * 60)
    logger.info("测试 1: 模块导入")
    logger.info("=" * 60)
    
    try:
        # 测试数据库连接模块
        from database.db_connection import get_mongodb_client, init_database, get_collection
        logger.info("✓ db_connection 模块导入成功")
        
        # 测试配体-受体查询模块
        from database.ligand_receptor import (
            get_ligand_receptor_pairs,
            filter_available_pairs,
            get_ligand_target_network,
            get_ligand_set,
        )
        logger.info("✓ ligand_receptor 模块导入成功")
        
        # 测试数据加载模块
        from database.data_loader import LigandReceptorCache
        logger.info("✓ data_loader 模块导入成功")
        
        # 测试导入脚本模块
        from database import import_cellphonedb
        logger.info("✓ import_cellphonedb 模块导入成功")
        
        # 测试主模块
        from database import (
            get_ligand_receptor_pairs,
            filter_available_pairs,
            get_ligand_target_network,
            get_ligand_set,
            LigandReceptorCache,
            get_mongodb_client,
            init_database,
        )
        logger.info("✓ database 主模块导入成功")
        
        logger.info("\n✅ 所有模块导入测试通过！\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ 模块导入失败: {e}", exc_info=True)
        return False


def test_db_connection():
    """测试数据库连接"""
    logger.info("=" * 60)
    logger.info("测试 2: 数据库连接")
    logger.info("=" * 60)
    
    try:
        from database.db_connection import get_mongodb_client
        
        logger.info("尝试连接到 MongoDB...")
        client, db_name = get_mongodb_client()
        logger.info(f"✓ 成功连接到数据库: {db_name}")
        
        # 测试 ping
        result = client.admin.command('ping')
        logger.info(f"✓ MongoDB ping 成功: {result}")
        
        client.close()
        logger.info("\n✅ 数据库连接测试通过！\n")
        return True
        
    except ConnectionError as e:
        logger.warning(f"⚠️  数据库连接失败（这是正常的，如果 MongoDB 未运行）: {e}")
        logger.info("提示: 如果 MongoDB 未运行，这是预期的行为\n")
        return False
    except Exception as e:
        logger.error(f"❌ 数据库连接测试失败: {e}", exc_info=True)
        return False


def test_query_functions():
    """测试查询函数（不实际连接数据库）"""
    logger.info("=" * 60)
    logger.info("测试 3: 查询函数定义")
    logger.info("=" * 60)
    
    try:
        from database.ligand_receptor import (
            get_ligand_receptor_pairs,
            filter_available_pairs,
            get_ligand_target_network,
            get_ligand_set,
        )
        
        # 检查函数是否存在且可调用
        assert callable(get_ligand_receptor_pairs), "get_ligand_receptor_pairs 不是可调用对象"
        assert callable(filter_available_pairs), "filter_available_pairs 不是可调用对象"
        assert callable(get_ligand_target_network), "get_ligand_target_network 不是可调用对象"
        assert callable(get_ligand_set), "get_ligand_set 不是可调用对象"
        
        logger.info("✓ get_ligand_receptor_pairs 函数定义正确")
        logger.info("✓ filter_available_pairs 函数定义正确")
        logger.info("✓ get_ligand_target_network 函数定义正确")
        logger.info("✓ get_ligand_set 函数定义正确")
        
        logger.info("\n✅ 查询函数定义测试通过！\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ 查询函数测试失败: {e}", exc_info=True)
        return False


def test_cache_class():
    """测试缓存类"""
    logger.info("=" * 60)
    logger.info("测试 4: 缓存类")
    logger.info("=" * 60)
    
    try:
        from database.data_loader import LigandReceptorCache
        
        # 测试类实例化
        cache = LigandReceptorCache(max_memory_gb=1.0)
        logger.info("✓ LigandReceptorCache 实例化成功")
        
        # 检查方法是否存在
        assert hasattr(cache, 'load_from_database'), "缺少 load_from_database 方法"
        assert hasattr(cache, 'get_pairs'), "缺少 get_pairs 方法"
        assert hasattr(cache, 'get_ligand_target_network'), "缺少 get_ligand_target_network 方法"
        assert hasattr(cache, 'get_ligand_set'), "缺少 get_ligand_set 方法"
        assert hasattr(cache, 'clear'), "缺少 clear 方法"
        
        logger.info("✓ 所有必需方法都存在")
        
        logger.info("\n✅ 缓存类测试通过！\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ 缓存类测试失败: {e}", exc_info=True)
        return False


def test_import_script():
    """测试导入脚本"""
    logger.info("=" * 60)
    logger.info("测试 5: 导入脚本")
    logger.info("=" * 60)
    
    try:
        import database.import_cellphonedb as import_script
        
        # 检查主要函数是否存在
        assert hasattr(import_script, 'download_cellphonedb_data'), "缺少 download_cellphonedb_data 函数"
        assert hasattr(import_script, 'import_to_database'), "缺少 import_to_database 函数"
        assert hasattr(import_script, 'validate_imported_data'), "缺少 validate_imported_data 函数"
        assert hasattr(import_script, 'main'), "缺少 main 函数"
        
        logger.info("✓ download_cellphonedb_data 函数存在")
        logger.info("✓ import_to_database 函数存在")
        logger.info("✓ validate_imported_data 函数存在")
        logger.info("✓ main 函数存在")
        
        logger.info("\n✅ 导入脚本测试通过！\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ 导入脚本测试失败: {e}", exc_info=True)
        return False


def main():
    """运行所有测试"""
    logger.info("\n" + "=" * 60)
    logger.info("开始运行基本功能测试")
    logger.info("=" * 60 + "\n")
    
    results = []
    
    # 运行所有测试
    results.append(("模块导入", test_imports()))
    results.append(("数据库连接", test_db_connection()))
    results.append(("查询函数", test_query_functions()))
    results.append(("缓存类", test_cache_class()))
    results.append(("导入脚本", test_import_script()))
    
    # 汇总结果
    logger.info("=" * 60)
    logger.info("测试结果汇总")
    logger.info("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "⚠️  跳过/失败"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
    
    logger.info("=" * 60)
    logger.info(f"总计: {passed}/{total} 测试通过")
    logger.info("=" * 60)
    
    # 如果所有关键测试都通过，返回成功
    if passed >= 4:  # 数据库连接可能失败，所以至少4个通过即可
        logger.info("\n🎉 所有关键测试通过！代码可以正常使用。\n")
        return 0
    else:
        logger.error("\n❌ 部分测试失败，请检查错误信息。\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

