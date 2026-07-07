#!/usr/bin/env python3
"""
数据升级脚本

功能：
1. 重新分析现有JSONL数据，确保所有字段完整
2. 修复项目目录名称（使用git根目录）
3. 删除旧缓存，让服务端重新生成汇总数据

在安装skill时自动运行。
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime


# Skill 目录
SKILL_DIR = Path(__file__).parent.parent
DATA_DIR = SKILL_DIR / 'data'
USAGE_FILE = DATA_DIR / 'usage.jsonl'
CACHE_FILE = DATA_DIR / 'usage_cache.json'


def find_git_root(path):
    """从 path 向上查找 git 根目录，找不到则返回 path 本身"""
    p = Path(path).resolve()
    while p != p.parent:
        if (p / '.git').exists():
            return p
        p = p.parent
    return path


def upgrade_data():
    """升级JSONL数据"""
    if not USAGE_FILE.exists():
        print("✓ 没有数据文件需要升级")
        return 0

    print(f"📂 数据文件：{USAGE_FILE}")

    # 备份原文件
    backup_file = USAGE_FILE.with_suffix('.jsonl.backup')
    if not backup_file.exists():
        import shutil
        shutil.copy(USAGE_FILE, backup_file)
        print(f"✓ 已备份到：{backup_file}")

    # 读取所有记录
    records = []
    fixed_count = 0

    with open(USAGE_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                rec = json.loads(line.strip())
                records.append(rec)
            except:
                continue

    print(f"📊 读取 {len(records)} 条记录")

    # 修复每条记录
    upgraded_records = []
    for rec in records:
        original_dir = rec.get('project_dir', '')
        original_name = rec.get('project_name', '')

        # 修复项目目录（使用git根目录）
        if original_dir:
            git_root = find_git_root(original_dir)
            if str(git_root) != original_dir:
                fixed_count += 1
                rec['project_dir'] = str(git_root)
                rec['project_name'] = Path(git_root).name
                print(f"  🔧 修复：{original_name}({original_dir}) -> {rec['project_name']}({git_root})")

        # 确保4类token字段存在
        if 'input_tokens' not in rec:
            rec['input_tokens'] = 0
        if 'output_tokens' not in rec:
            rec['output_tokens'] = 0
        if 'cache_creation' not in rec:
            rec['cache_creation'] = 0
        if 'cache_read' not in rec:
            rec['cache_read'] = 0

        # 确保total_tokens正确
        expected_total = rec['input_tokens'] + rec['output_tokens'] + rec['cache_creation'] + rec['cache_read']
        if rec.get('total_tokens', 0) != expected_total and expected_total > 0:
            rec['total_tokens'] = expected_total

        upgraded_records.append(rec)

    if fixed_count > 0:
        print(f"\n✓ 修复了 {fixed_count} 条记录的项目目录")

    # 写回文件
    with open(USAGE_FILE, 'w', encoding='utf-8') as f:
        for rec in upgraded_records:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')

    print(f"✓ 数据升级完成")

    return fixed_count


def clear_cache():
    """删除缓存文件，让服务端重新生成"""
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()
        print(f"✓ 已删除缓存：{CACHE_FILE}")
        return True
    return False


def main():
    print("=" * 50)
    print("🔄 Usage Tracking 数据升级")
    print("=" * 50)
    print()

    # 升级数据
    fixed = upgrade_data()

    # 清除缓存
    print()
    if clear_cache():
        print("✓ 缓存已清除，服务端将重新生成汇总数据")
    else:
        print("✓ 无缓存需要清除")

    print()
    print("=" * 50)
    if fixed > 0:
        print(f"✅ 升级完成！修复了 {fixed} 条记录")
    else:
        print("✅ 升级完成！数据格式正常")
    print("=" * 50)


if __name__ == '__main__':
    main()
