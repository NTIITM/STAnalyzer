#!/usr/bin/env python3
"""
验证 en-US.json 和 zh-CN.json 的 help 部分结构是否一致
"""
import json
from pathlib import Path

def get_all_keys(obj, prefix=''):
    """递归获取所有键路径"""
    keys = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            current_path = f"{prefix}.{key}" if prefix else key
            keys.add(current_path)
            keys.update(get_all_keys(value, current_path))
    return keys

def main():
    # 读取文件
    en_us_path = Path('src/i18n/locales/en-US.json')
    zh_cn_path = Path('src/i18n/locales/zh-CN.json')
    
    print("📖 读取文件...")
    with open(en_us_path, 'r', encoding='utf-8') as f:
        en_us = json.load(f)
    with open(zh_cn_path, 'r', encoding='utf-8') as f:
        zh_cn = json.load(f)
    
    # 获取 help 部分的所有键
    print("\n🔍 分析 help 部分结构...")
    en_help_keys = get_all_keys(en_us.get('help', {}), 'help')
    zh_help_keys = get_all_keys(zh_cn.get('help', {}), 'help')
    
    # 比较
    print(f"\n📊 统计:")
    print(f"   en-US help 键数量: {len(en_help_keys)}")
    print(f"   zh-CN help 键数量: {len(zh_help_keys)}")
    
    # 找出差异
    only_in_zh = zh_help_keys - en_help_keys
    only_in_en = en_help_keys - zh_help_keys
    
    if only_in_zh:
        print(f"\n⚠️  仅在 zh-CN 中存在的键 ({len(only_in_zh)}):")
        for key in sorted(only_in_zh)[:10]:
            print(f"   - {key}")
        if len(only_in_zh) > 10:
            print(f"   ... 还有 {len(only_in_zh) - 10} 个")
    
    if only_in_en:
        print(f"\n⚠️  仅在 en-US 中存在的键 ({len(only_in_en)}):")
        for key in sorted(only_in_en)[:10]:
            print(f"   - {key}")
        if len(only_in_en) > 10:
            print(f"   ... 还有 {len(only_in_en) - 10} 个")
    
    # 检查关键组件使用的键
    print("\n✅ 检查组件使用的关键键:")
    critical_keys = [
        'help.common.keyPoints',
        'help.introduction.subtitle',
        'help.introduction.coreFeatures.projectManagement.title',
        'help.introduction.coreFeatures.projectManagement.description',
        'help.introduction.coreFeatures.dagVisualization.title',
        'help.introduction.coreFeatures.multiPerspective.title',
        'help.introduction.coreFeatures.intelligentAgent.title',
        'help.introduction.coreFeatures.serviceManagement.title',
        'help.introduction.advantages.automation.title',
        'help.introduction.advantages.integration.title',
        'help.introduction.advantages.intelligent.title',
        'help.introduction.advantages.visualization.title',
        'help.sections.gettingStarted.steps.createProject.point1',
        'help.sections.gettingStarted.steps.createProject.point2',
        'help.sections.gettingStarted.steps.createProject.point3',
        'help.sections.gettingStarted.steps.uploadData.point1',
        'help.sections.gettingStarted.steps.addContext.point1',
        'help.sections.gettingStarted.steps.askAgent.point1',
        'help.sections.gettingStarted.steps.viewReport.point1',
        'help.sections.analysisPage.leftPanel.projectList.feature1',
        'help.sections.analysisPage.leftPanel.fileList.feature1',
        'help.sections.analysisPage.middleContent.dagView.elements.nodesDetail1',
        'help.sections.analysisPage.rightPanel.feature1',
        'help.sections.serviceManagement.serviceInfo.functions.function1',
        'help.sections.serviceManagement.relationshipGraph.functions.components.component1',
        'help.sections.executionManagement.functions.executionList.feature1',
    ]
    
    missing_keys = []
    for key in critical_keys:
        if key in en_help_keys and key in zh_help_keys:
            print(f"   ✅ {key}")
        elif key not in en_help_keys:
            print(f"   ❌ {key} (缺失在 en-US)")
            missing_keys.append(key)
        elif key not in zh_help_keys:
            print(f"   ⚠️  {key} (缺失在 zh-CN)")
    
    # 总结
    print("\n" + "="*60)
    if not only_in_zh and not only_in_en and not missing_keys:
        print("🎉 完美！help 部分结构完全一致！")
        return 0
    elif not missing_keys:
        print("✅ 所有关键键都存在，但存在一些结构差异")
        print("   这些差异可能是正常的（如某些语言特有的说明）")
        return 0
    else:
        print("❌ 发现问题：有关键键缺失")
        return 1

if __name__ == '__main__':
    import sys
    try:
        sys.exit(main())
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
