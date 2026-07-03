#!/usr/bin/env python3
"""
查看 Claude Code Token 使用统计（每轮追加模式）

读取 data/usage.jsonl 文件并生成统计报告。
每条记录是一轮对话，支持多维度汇总。

用法：
  python3 view_usage.py              # 查看所有会话
  python3 view_usage.py --summary    # 查看摘要
  python3 view_usage.py --latest     # 查看最近一次会话
  python3 view_usage.py --turns      # 查看最近一次会话的每轮详情
  python3 view_usage.py --all-turns  # 查看所有会话的每轮详情
  python3 view_usage.py --by-date    # 按天查看统计
  python3 view_usage.py --by-project # 按项目查看统计
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict


def load_usage_data(usage_file):
    """加载 usage.jsonl 文件（每轮一条记录）"""
    if not usage_file.exists():
        return []

    records = []
    with open(usage_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                record = json.loads(line.strip())
                records.append(record)
            except:
                continue

    return records


def format_tokens(num):
    """格式化 token 数量（千分位分隔）"""
    return f"{num:,}"


def aggregate_by_session(records):
    """按 session 聚合"""
    sessions = defaultdict(lambda: {
        'session_id': '',
        'project_dir': '',
        'project_name': '',
        'model': '',
        'total_tokens': 0,
        'total_turns': 0,
        'input_tokens': 0,
        'output_tokens': 0,
        'cache_creation': 0,
        'cache_read': 0,
        'first_timestamp': '',
        'last_timestamp': '',
        'turn_details': []
    })

    for rec in records:
        sid = rec.get('session_id', '')
        if not sid:
            continue

        session = sessions[sid]
        session['session_id'] = sid
        session['project_dir'] = rec.get('project_dir', '')
        session['project_name'] = rec.get('project_name', '')
        session['model'] = rec.get('model', '')
        session['total_tokens'] += rec.get('total_tokens', 0)
        session['total_turns'] += 1
        session['input_tokens'] += rec.get('input_tokens', 0)
        session['output_tokens'] += rec.get('output_tokens', 0)
        session['cache_creation'] += rec.get('cache_creation', 0)
        session['cache_read'] += rec.get('cache_read', 0)

        timestamp = rec.get('timestamp', '')
        if timestamp:
            if not session['first_timestamp'] or timestamp < session['first_timestamp']:
                session['first_timestamp'] = timestamp
            if not session['last_timestamp'] or timestamp > session['last_timestamp']:
                session['last_timestamp'] = timestamp

        session['turn_details'].append(rec)

    return dict(sessions)


def aggregate_by_date(records):
    """按天聚合"""
    daily = defaultdict(lambda: {'date': '', 'sessions': set(), 'tokens': 0, 'turns': 0})

    for rec in records:
        timestamp = rec.get('timestamp', '')
        date = timestamp[:10] if timestamp else 'unknown'
        session_id = rec.get('session_id', '')

        daily[date]['date'] = date
        daily[date]['sessions'].add(session_id)
        daily[date]['tokens'] += rec.get('total_tokens', 0)
        daily[date]['turns'] += 1

    # 转换为列表并排序
    result = []
    for date, stats in sorted(daily.items()):
        result.append({
            'date': stats['date'],
            'sessions': len(stats['sessions']),
            'tokens': stats['tokens'],
            'turns': stats['turns']
        })

    return result


def aggregate_by_project(records):
    """按项目聚合"""
    projects = defaultdict(lambda: {
        'project_dir': '',
        'project_name': '',
        'total_tokens': 0,
        'total_sessions': set(),
        'total_turns': 0
    })

    for rec in records:
        pdir = rec.get('project_dir', 'unknown')
        pname = rec.get('project_name', 'unknown')
        session_id = rec.get('session_id', '')

        projects[pdir]['project_dir'] = pdir
        projects[pdir]['project_name'] = pname
        projects[pdir]['total_tokens'] += rec.get('total_tokens', 0)
        projects[pdir]['total_sessions'].add(session_id)
        projects[pdir]['total_turns'] += 1

    # 转换为列表
    result = []
    for pdir, stats in projects.items():
        result.append({
            'project_dir': stats['project_dir'],
            'project_name': stats['project_name'],
            'total_tokens': stats['total_tokens'],
            'total_sessions': len(stats['total_sessions']),
            'total_turns': stats['total_turns']
        })

    # 按 token 消耗降序排序
    result.sort(key=lambda x: x['total_tokens'], reverse=True)
    return result


def print_summary(records):
    """打印摘要统计"""
    if not records:
        print("暂无使用记录")
        return

    total_tokens = sum(r.get('total_tokens', 0) for r in records)
    total_turns = len(records)
    sessions = aggregate_by_session(records)
    total_sessions = len(sessions)

    # 按天统计
    daily = aggregate_by_date(records)
    active_days = len([d for d in daily if d['tokens'] > 0])
    daily_avg = round(total_tokens / active_days) if active_days > 0 else 0

    # 按项目统计
    projects = aggregate_by_project(records)

    print("=" * 80)
    print("Claude Code Token 使用统计摘要")
    print("=" * 80)
    print(f"\n总 Tokens 消耗:     {format_tokens(total_tokens)}")
    print(f"总会话数:           {total_sessions}")
    print(f"总轮次:             {format_tokens(total_turns)}")
    print(f"活跃天数:           {active_days}")
    print(f"日均 Tokens:        {format_tokens(daily_avg)}")
    print(f"\n项目数:             {len(projects)}")
    for p in projects[:5]:  # 显示前 5 个项目
        print(f"  - {p['project_name']}: {format_tokens(p['total_tokens'])} ({p['total_sessions']} 个会话)")

    if records:
        latest = max(records, key=lambda r: r.get('timestamp', ''))
        print(f"\n最近一轮:")
        print(f"  会话 ID:        {latest['session_id'][:8]}...")
        print(f"  项目:           {latest.get('project_name', 'unknown')}")
        print(f"  轮次:           {latest.get('turn', 0)}")
        print(f"  Tokens:         {format_tokens(latest.get('total_tokens', 0))}")
        print(f"  时间:           {latest.get('timestamp', '')}")


def print_by_date(records):
    """按天查看统计"""
    if not records:
        print("暂无使用记录")
        return

    daily = aggregate_by_date(records)

    print("=" * 80)
    print(f"每日 Token 消耗统计 (共 {len(daily)} 天)")
    print("=" * 80)

    for d in daily:
        print(f"\n【{d['date']}】")
        print(f"  Tokens:         {format_tokens(d['tokens'])}")
        print(f"  会话数:         {d['sessions']}")
        print(f"  轮次:           {d['turns']}")


def print_by_project(records):
    """按项目查看统计"""
    if not records:
        print("暂无使用记录")
        return

    projects = aggregate_by_project(records)

    print("=" * 80)
    print(f"项目 Token 消耗统计 (共 {len(projects)} 个项目)")
    print("=" * 80)

    for i, p in enumerate(projects, 1):
        print(f"\n【项目 {i}】{p['project_name']}")
        print(f"  路径:           {p['project_dir']}")
        print(f"  Tokens:         {format_tokens(p['total_tokens'])}")
        print(f"  会话数:         {p['total_sessions']}")
        print(f"  轮次:           {p['total_turns']}")


def print_all_sessions(records):
    """打印所有会话记录"""
    if not records:
        print("暂无使用记录")
        return

    sessions = aggregate_by_session(records)
    sorted_sessions = sorted(sessions.values(), key=lambda s: s.get('last_timestamp', ''), reverse=True)

    print("=" * 80)
    print(f"Claude Code Token 使用记录 (共 {len(sorted_sessions)} 个会话)")
    print("=" * 80)

    for i, session in enumerate(sorted_sessions, 1):
        print(f"\n【会话 {i}】")
        print(f"  会话 ID:        {session['session_id'][:8]}...")
        print(f"  项目:           {session['project_name']}")
        print(f"  模型:           {session['model']}")
        print(f"  轮次:           {session['total_turns']}")
        print(f"  Input Tokens:   {format_tokens(session['input_tokens'])}")
        print(f"  Output Tokens:  {format_tokens(session['output_tokens'])}")
        print(f"  Cache Creation: {format_tokens(session['cache_creation'])}")
        print(f"  Cache Read:     {format_tokens(session['cache_read'])}")
        print(f"  总 Tokens:      {format_tokens(session['total_tokens'])}")
        print(f"  开始时间:       {session['first_timestamp']}")
        print(f"  结束时间:       {session['last_timestamp']}")


def print_latest_session(records):
    """打印最近一次会话"""
    if not records:
        print("暂无使用记录")
        return

    sessions = aggregate_by_session(records)
    if not sessions:
        print("暂无会话数据")
        return

    latest = max(sessions.values(), key=lambda s: s.get('last_timestamp', ''))

    print("=" * 80)
    print("最近一次 Claude Code 会话")
    print("=" * 80)
    print(f"\n会话 ID:        {latest['session_id']}")
    print(f"项目:           {latest['project_name']}")
    print(f"模型:           {latest['model']}")
    print(f"轮次:           {latest['total_turns']}")
    print(f"\nToken 消耗:")
    print(f"  Input Tokens:   {format_tokens(latest['input_tokens'])}")
    print(f"  Output Tokens:  {format_tokens(latest['output_tokens'])}")
    print(f"  Cache Creation: {format_tokens(latest['cache_creation'])}")
    print(f"  Cache Read:     {format_tokens(latest['cache_read'])}")
    print(f"  总计:           {format_tokens(latest['total_tokens'])}")
    print(f"\n开始时间:       {latest['first_timestamp']}")
    print(f"结束时间:       {latest['last_timestamp']}")


def print_turn_details(session_records, show_all=False):
    """打印会话的每轮详情"""
    if not session_records:
        print("该会话没有轮次数据")
        return

    session_id = session_records[0].get('session_id', '')[:8]
    print("=" * 80)
    print(f"会话 {session_id}... 每轮 Token 消耗详情")
    print("=" * 80)

    # 按 turn 编号排序
    turns = sorted(session_records, key=lambda r: r.get('turn', 0))

    # 如果轮次太多，只显示前 20 轮和后 10 轮
    if not show_all and len(turns) > 30:
        print(f"\n显示前 20 轮和后 10 轮（共 {len(turns)} 轮）")
        print("-" * 80)

        for turn in turns[:20]:
            print_turn_line(turn)

        print(f"\n... 中间 {len(turns) - 30} 轮省略 ...\n")

        for turn in turns[-10:]:
            print_turn_line(turn)
    else:
        print(f"\n共 {len(turns)} 轮")
        print("-" * 80)

        for turn in turns:
            print_turn_line(turn)

    # 显示统计信息
    print_turn_statistics(turns)


def print_turn_line(turn):
    """打印单轮详情"""
    # 构建工具调用标记
    tool_indicator = ""
    if turn.get('has_tool_calls'):
        tool_names = turn.get('tool_names', [])
        if tool_names:
            tool_indicator = f"  {','.join(tool_names[:2])}"
    elif turn.get('response_length', 0) > 0:
        tool_indicator = f" 💬 {turn['response_length']}字符"

    print(f"第 {turn.get('turn', 0):3d} 轮 | "
          f"Input: {turn.get('input_tokens', 0):>8,} | "
          f"Output: {turn.get('output_tokens', 0):>6,} | "
          f"Cache Create: {turn.get('cache_creation', 0):>8,} | "
          f"Cache Read: {turn.get('cache_read', 0):>8,} | "
          f"Total: {turn.get('total_tokens', 0):>8,}{tool_indicator}")


def print_turn_statistics(turns):
    """打印轮次统计信息"""
    if not turns:
        return

    total_turns = len(turns)
    turns_with_tools = sum(1 for t in turns if t.get('has_tool_calls'))
    turns_with_text = sum(1 for t in turns if t.get('response_length', 0) > 0)

    print("\n" + "=" * 80)
    print("统计信息")
    print("=" * 80)
    print(f"  总轮次: {total_turns}")
    print(f"  有工具调用的轮次: {turns_with_tools} ({turns_with_tools/total_turns*100:.1f}%)")
    print(f"  有文本回复的轮次: {turns_with_text} ({turns_with_text/total_turns*100:.1f}%)")

    # 工具使用频率统计
    tool_usage = {}
    for turn in turns:
        if turn.get('has_tool_calls'):
            for tool in turn.get('tool_names', []) or []:
                tool_usage[tool] = tool_usage.get(tool, 0) + 1

    if tool_usage:
        print(f"\n工具使用频率（Top 5）:")
        sorted_tools = sorted(tool_usage.items(), key=lambda x: x[1], reverse=True)
        for tool, count in sorted_tools[:5]:
            print(f"  {tool}: {count} 次")


def main():
    skill_dir = Path(__file__).parent.parent
    usage_file = skill_dir / 'data' / 'usage.jsonl'
    records = load_usage_data(usage_file)

    if not records:
        print("暂无使用记录")
        return

    if len(sys.argv) > 1:
        option = sys.argv[1].lower()
        if option == '--summary' or option == '-s':
            print_summary(records)
        elif option == '--latest' or option == '-l':
            print_latest_session(records)
        elif option == '--turns' or option == '-t':
            # 查看最近一次会话的每轮详情
            sessions = aggregate_by_session(records)
            if sessions:
                latest = max(sessions.values(), key=lambda s: s.get('last_timestamp', ''))
                latest_records = [r for r in records if r.get('session_id') == latest['session_id']]
                print_turn_details(latest_records, show_all=False)
        elif option == '--all-turns':
            # 查看所有会话的每轮详情（只显示最新会话）
            sessions = aggregate_by_session(records)
            if sessions:
                latest = max(sessions.values(), key=lambda s: s.get('last_timestamp', ''))
                latest_records = [r for r in records if r.get('session_id') == latest['session_id']]
                print_turn_details(latest_records, show_all=True)
        elif option == '--by-date':
            print_by_date(records)
        elif option == '--by-project':
            print_by_project(records)
        elif option == '--help' or option == '-h':
            print(__doc__)
        else:
            print(f"未知选项：{option}")
            print("使用 --help 查看帮助")
    else:
        print_all_sessions(records)


if __name__ == '__main__':
    main()
