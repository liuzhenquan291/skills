#!/usr/bin/env python3
"""
Claude Code Token 使用记录器（每轮追加模式）

在 Claude Code 每轮对话结束时（通过 Stop hook）运行，
读取当前会话的 transcript 文件，提取最新一轮的 token 使用量，
追加到 skill 目录下的 data/usage.jsonl 文件。

每轮对话一条记录，支持多维度汇总统计。

数据来源：~/.claude/projects/<project-hash>/<session-id>.jsonl
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime

# Skill 目录（脚本在 scripts/ 下，数据在 data/ 下）
SKILL_DIR = Path(__file__).parent.parent
DATA_DIR = SKILL_DIR / 'data'
USAGE_FILE = DATA_DIR / 'usage.jsonl'


def find_git_root(path):
    """从 path 向上查找 git 根目录，找不到则返回 path 本身"""
    p = Path(path).resolve()
    while p != p.parent:
        if (p / '.git').exists():
            return p
        p = p.parent
    return path


def find_transcript_by_cwd(project_dir):
    """通过 cwd 查找当前项目的最新 transcript 文件"""
    project_path = Path(project_dir).resolve()
    claude_projects = Path.home() / '.claude' / 'projects'

    if not claude_projects.exists():
        return None, None

    latest_file = None
    latest_time = 0
    latest_session = None

    for proj_dir in claude_projects.iterdir():
        if not proj_dir.is_dir():
            continue
        for jsonl in proj_dir.glob('*.jsonl'):
            try:
                mtime = jsonl.stat().st_mtime
                if mtime > latest_time:
                    # 验证 transcript 是否属于当前项目（精确匹配或 cwd 在项目目录下）
                    with open(jsonl, 'r') as f:
                        for line in f:
                            try:
                                data = json.loads(line.strip())
                                transcript_cwd = data.get('cwd', '')
                                # 精确匹配，或者 transcript 的 cwd 是当前项目目录的子目录
                                if transcript_cwd == str(project_path) or \
                                   str(transcript_cwd).startswith(str(project_path) + '/'):
                                    latest_time = mtime
                                    latest_file = jsonl
                                    latest_session = jsonl.stem
                                    break
                            except:
                                continue
            except Exception:
                continue

    return latest_session, latest_file


def get_recorded_turns(session_id, usage_file):
    """获取已记录的轮次编号"""
    recorded_turns = set()
    if not usage_file.exists():
        return recorded_turns

    with open(usage_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                rec = json.loads(line.strip())
                if rec.get('session_id') == session_id and 'turn' in rec:
                    recorded_turns.add(rec['turn'])
            except:
                continue

    return recorded_turns


def parse_latest_turn(transcript_path, recorded_turns):
    """解析 transcript 文件，提取未记录的轮次"""
    turns_to_record = []
    model = 'unknown'

    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            turn_number = 0
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except:
                    continue

                # 只处理 assistant 消息
                if data.get('type') != 'assistant':
                    continue

                msg = data.get('message', {})
                model = msg.get('model', model)
                usage = msg.get('usage', {})
                timestamp = data.get('timestamp', '')
                content = msg.get('content', [])

                # 只处理有 usage 的消息
                if not usage:
                    continue

                turn_number += 1

                # 跳过已记录的轮次
                if turn_number in recorded_turns:
                    continue

                input_tokens = usage.get('input_tokens', 0)
                output_tokens = usage.get('output_tokens', 0)
                cache_creation = usage.get('cache_creation_input_tokens', 0)
                cache_read = usage.get('cache_read_input_tokens', 0)

                # 提取关键信息
                tool_names = []
                has_tool_calls = False
                response_text_length = 0
                response_summary = ""

                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            item_type = item.get('type', '')

                            # 工具调用
                            if item_type == 'tool_use':
                                has_tool_calls = True
                                tool_name = item.get('name', 'unknown')
                                tool_names.append(tool_name)

                            # 文本回复
                            elif item_type == 'text':
                                text = item.get('text', '')
                                response_text_length += len(text)
                                # 提取第一行作为概述（最多 200 字符）
                                if not response_summary and text.strip():
                                    first_line = text.strip().split('\n')[0][:200]
                                    response_summary = first_line

                turns_to_record.append({
                    'turn': turn_number,
                    'timestamp': timestamp,
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                    'cache_creation': cache_creation,
                    'cache_read': cache_read,
                    'total_tokens': input_tokens + output_tokens + cache_creation + cache_read,
                    'stop_reason': msg.get('stop_reason', ''),
                    'has_tool_calls': has_tool_calls,
                    'tool_names': tool_names if tool_names else None,
                    'response_length': response_text_length,
                    'response_summary': response_summary if response_summary else None,
                })

    except FileNotFoundError:
        print(f"Transcript 文件不存在：{transcript_path}", file=sys.stderr)
        return None, model

    return turns_to_record, model


def main():
    # 获取项目目录（从 cwd 向上查找 git 根目录）
    if len(sys.argv) > 1:
        project_dir = sys.argv[1]
    else:
        project_dir = os.getcwd()

    project_path = Path(project_dir).resolve()
    # 使用 git 根目录作为项目标识
    git_root = find_git_root(project_path)
    project_name = Path(git_root).name

    # 查找 transcript 文件
    session_id, transcript_path = find_transcript_by_cwd(git_root)

    if not transcript_path:
        print("未找到当前项目的 transcript 文件", file=sys.stderr)
        sys.exit(0)

    # 获取已记录的轮次
    recorded_turns = get_recorded_turns(session_id, USAGE_FILE)

    # 解析未记录的轮次
    turns_to_record, model = parse_latest_turn(transcript_path, recorded_turns)

    if not turns_to_record:
        print("没有新的轮次需要记录", file=sys.stderr)
        sys.exit(0)

    # 确保数据目录存在
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 追加每轮记录
    with open(USAGE_FILE, 'a', encoding='utf-8') as f:
        for turn in turns_to_record:
            record = {
                'session_id': session_id,
                'turn': turn['turn'],
                'timestamp': turn['timestamp'],
                'project_dir': str(git_root),
                'project_name': project_name,
                'model': model,
                'input_tokens': turn['input_tokens'],
                'output_tokens': turn['output_tokens'],
                'cache_creation': turn['cache_creation'],
                'cache_read': turn['cache_read'],
                'total_tokens': turn['total_tokens'],
                'stop_reason': turn['stop_reason'],
                'has_tool_calls': turn['has_tool_calls'],
                'tool_names': turn['tool_names'],
                'response_length': turn['response_length'],
                'response_summary': turn['response_summary'],
            }
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    # 输出摘要
    print(f"✓ 记录 {len(turns_to_record)} 轮对话")
    print(f"  项目：{project_name}")
    print(f"  会话：{session_id[:8]}...")
    print(f"  轮次：{[t['turn'] for t in turns_to_record]}")
    print(f"  -> {USAGE_FILE}")


if __name__ == '__main__':
    main()
