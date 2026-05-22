#!/usr/bin/env python3
"""
修复 en-US.json 中的 help 部分，使其结构与 zh-CN.json 保持一致
"""
import json
import sys
from pathlib import Path

def main():
    # 文件路径
    en_us_path = Path('src/i18n/locales/en-US.json')
    help_fixed_path = Path('help-en-fixed.json')
    output_path = Path('src/i18n/locales/en-US-fixed.json')
    
    # 读取原始 en-US.json
    print(f"读取 {en_us_path}...")
    with open(en_us_path, 'r', encoding='utf-8') as f:
        en_us_data = json.load(f)
    
    # 读取修复后的 help 部分
    print(f"读取 {help_fixed_path}...")
    with open(help_fixed_path, 'r', encoding='utf-8') as f:
        help_fixed_data = json.load(f)
    
    # 替换 help 部分
    print("替换 help 部分...")
    en_us_data['help'] = help_fixed_data['help']
    
    # 写入新文件
    print(f"写入 {output_path}...")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(en_us_data, f, ensure_ascii=False, indent=2)
    
    print("✅ 修复完成！")
    print(f"   新文件已保存到: {output_path}")
    print(f"   请检查文件内容，确认无误后执行:")
    print(f"   mv {output_path} {en_us_path}")
    
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
