#!/usr/bin/env python3
"""
数据迁移脚本：将旧格式（每条记录 = 一个 session）转换为新格式（每条记录 = 一轮对话）

旧格式:
{
  "session_id": "...",
  "turns": 201,
  "total_tokens": 10135354,
  "turn_details": [
    {"turn": 1, "input_tokens": 30812, ...},
    {"turn": 2, "input_tokens": 30812, ...},
    ...
  ],
  ...
}

新格式:
{
  "session_id": "...",
  "turn": 1,
  "input_tokens": 30812,
  "output_tokens": 0,
  "total_tokens": 30812,
  ...
}

用法:
  python3 migrate_data.py
"""

import json
from pathlib import Path

# 文件路径
SKILL_DIR = Path(__file__).parent.parent
DATA_DIR = SKILL_DIR / 'data'
BACKUP_FILE = DATA_DIR / 'usage.jsonl.bak'
NEW_FILE = DATA_DIR / 'usage.jsonl'


def migrate():
    """迁移数据"""
    if not BACKUP_FILE.exists():
        print("备份文件不存在:", BACKUP_FILE)
        print("请先手动备份 usage.jsonl")
        return

    # 读取旧数据
    old_records = []
    with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                record = json.loads(line.strip())
                old_records.append(record)
            except:
                continue

    print(f"读取到 {len(old_records)} 条旧记录")

    # 转换为新格式
    new_records = []
    for record in old_records:
        session_id = record.get('session_id', '')
        project_dir = record.get('project_dir', '')
        project_name = record.get('project_name', '')
        model = record.get('model', 'unknown')

        # 如果有 turn_details，展开为每轮一条记录
        turn_details = record.get('turn_details', [])
        if turn_details:
            for turn in turn_details:
                new_record = {
                    'session_id': session_id,
                    'turn': turn.get('turn', 0),
                    'timestamp': turn.get('timestamp', record.get('timestamp', '')),
                    'project_dir': project_dir,
                    'project_name': project_name,
                    'model': model,
                    'input_tokens': turn.get('input_tokens', 0),
                    'output_tokens': turn.get('output_tokens', 0),
                    'cache_creation': turn.get('cache_creation', 0),
                    'cache_read': turn.get('cache_read', 0),
                    'total_tokens': turn.get('total', 0),
                    'stop_reason': turn.get('stop_reason', ''),
                    'has_tool_calls': turn.get('has_tool_calls', False),
                    'tool_names': turn.get('tool_names'),
                    'response_length': turn.get('response_length', 0),
                    'response_summary': turn.get('response_summary'),
                }
                new_records.append(new_record)
        else:
            # 没有 turn_details，创建一条汇总记录
            new_record = {
                'session_id': session_id,
                'turn': 0,
                'timestamp': record.get('timestamp', ''),
                'project_dir': project_dir,
                'project_name': project_name,
                'model': model,
                'input_tokens': record.get('input_tokens', 0),
                'output_tokens': record.get('output_tokens', 0),
                'cache_creation': record.get('cache_creation', 0),
                'cache_read': record.get('cache_read', 0),
                'total_tokens': record.get('total_tokens', 0),
                'stop_reason': '',
                'has_tool_calls': False,
                'tool_names': None,
                'response_length': 0,
                'response_summary': None,
            }
            new_records.append(new_record)

    print(f"转换为 {len(new_records)} 条新记录")

    # 写入新文件
    with open(NEW_FILE, 'w', encoding='utf-8') as f:
        for record in new_records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    print(f"✓ 迁移完成")
    print(f"  旧文件：{BACKUP_FILE}")
    print(f"  新文件：{NEW_FILE}")
    print(f"  记录数：{len(new_records)}")


if __name__ == '__main__':
    migrate()
