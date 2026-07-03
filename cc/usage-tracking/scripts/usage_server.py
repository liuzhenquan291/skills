#!/usr/bin/env python3
"""
Usage Tracking Web Server（每轮追加模式）

提供本地 Web 服务，展示 Claude Code token 使用统计。
支持增量处理、按项目/会话/天等多维度汇总统计。

启动: python3 usage_server.py [port]
访问: http://localhost:8765
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
from collections import defaultdict

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    import uvicorn
except ImportError:
    print("错误：缺少依赖包")
    print("请运行：pip3 install fastapi uvicorn")
    sys.exit(1)


# 配置
SKILL_DIR = Path(__file__).parent.parent
DATA_DIR = SKILL_DIR / 'data'
USAGE_FILE = DATA_DIR / 'usage.jsonl'
CACHE_FILE = DATA_DIR / 'usage_cache.json'
WEB_DIR = Path(__file__).parent / 'web'

DEFAULT_PORT = 8765


class UsageCache:
    """增量处理的缓存管理器（每轮记录模式）"""

    def __init__(self):
        self.cache_file = CACHE_FILE
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict:
        """加载缓存文件"""
        default_cache = {
            'last_offset': 0,
            'sessions': {},  # session_id -> 聚合统计
            'projects': {},  # project_dir -> 聚合统计
            'daily_stats': {},  # date -> 聚合统计
            'model_stats': {},  # model -> 聚合统计
            'total_tokens': 0,
            'total_sessions': 0,
            'total_turns': 0,
            'updated_at': None
        }

        if not self.cache_file.exists():
            return default_cache

        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache = json.load(f)
                # 确保字段存在
                if 'projects' not in cache:
                    cache['projects'] = {}
                if 'sessions' not in cache:
                    cache['sessions'] = {}
                return cache
        except (json.JSONDecodeError, IOError):
            return default_cache

    def save_cache(self):
        """保存缓存到文件"""
        self.cache['updated_at'] = datetime.now().isoformat()
        # 序列化：将 set 转换为 list
        serializable = json.loads(json.dumps(self.cache, default=lambda o: list(o) if isinstance(o, set) else o))
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(serializable, f, indent=2, ensure_ascii=False)

    def check_and_update(self) -> bool:
        """检查并增量更新缓存"""
        if not USAGE_FILE.exists():
            return False

        current_size = USAGE_FILE.stat().st_size
        last_offset = self.cache.get('last_offset', 0)

        # 没有新数据
        if current_size <= last_offset:
            return False

        # 增量读取新数据
        new_turns = []
        with open(USAGE_FILE, 'r', encoding='utf-8') as f:
            f.seek(last_offset)
            for line in f:
                try:
                    turn = json.loads(line.strip())
                    new_turns.append(turn)
                except json.JSONDecodeError:
                    continue

        # 处理新轮次
        for turn in new_turns:
            self._process_turn(turn)

        # 更新偏移量
        self.cache['last_offset'] = current_size
        self.save_cache()

        return len(new_turns) > 0

    def _process_turn(self, turn: Dict):
        """处理单个轮次记录"""
        session_id = turn.get('session_id', '')
        if not session_id:
            return

        # 获取维度信息
        project_dir = turn.get('project_dir', 'unknown')
        project_name = turn.get('project_name', 'unknown')
        model = turn.get('model', 'unknown')
        timestamp = turn.get('timestamp', '')
        date = timestamp[:10] if timestamp else 'unknown'

        total_tokens = turn.get('total_tokens', 0)
        input_tokens = turn.get('input_tokens', 0)
        output_tokens = turn.get('output_tokens', 0)
        cache_creation = turn.get('cache_creation', 0)
        cache_read = turn.get('cache_read', 0)

        # 更新全局总计
        self.cache['total_tokens'] += total_tokens
        self.cache['total_turns'] += 1

        # 更新会话统计
        if session_id not in self.cache['sessions']:
            self.cache['sessions'][session_id] = {
                'session_id': session_id,
                'project_dir': project_dir,
                'project_name': project_name,
                'model': model,
                'total_tokens': 0,
                'total_turns': 0,
                'input_tokens': 0,
                'output_tokens': 0,
                'cache_creation': 0,
                'cache_read': 0,
                'first_timestamp': timestamp,
                'last_timestamp': timestamp,
                'turn_details': []  # 存储轮次详情（用于 session 详情 API）
            }

        session = self.cache['sessions'][session_id]
        session['total_tokens'] += total_tokens
        session['total_turns'] += 1
        session['input_tokens'] += input_tokens
        session['output_tokens'] += output_tokens
        session['cache_creation'] += cache_creation
        session['cache_read'] += cache_read
        if timestamp < session['first_timestamp']:
            session['first_timestamp'] = timestamp
        if timestamp > session['last_timestamp']:
            session['last_timestamp'] = timestamp

        # 添加轮次详情（用于 session 详情 API）
        session['turn_details'].append({
            'turn': turn.get('turn', 0),
            'timestamp': timestamp,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'cache_creation': cache_creation,
            'cache_read': cache_read,
            'total': total_tokens,
            'stop_reason': turn.get('stop_reason', ''),
            'has_tool_calls': turn.get('has_tool_calls', False),
            'tool_names': turn.get('tool_names'),
            'response_length': turn.get('response_length', 0),
            'response_summary': turn.get('response_summary'),
        })

        # 更新项目统计
        if project_dir not in self.cache['projects']:
            self.cache['projects'][project_dir] = {
                'project_dir': project_dir,
                'project_name': project_name,
                'total_tokens': 0,
                'total_sessions': 0,
                'total_turns': 0,
                'daily_stats': {},
                'model_stats': {}
            }

        project = self.cache['projects'][project_dir]
        project['total_tokens'] += total_tokens
        project['total_turns'] += 1

        # 更新模型统计（全局）
        if model not in self.cache['model_stats']:
            self.cache['model_stats'][model] = {'sessions': set(), 'tokens': 0, 'turns': 0}
        self.cache['model_stats'][model]['sessions'].add(session_id)
        self.cache['model_stats'][model]['tokens'] += total_tokens
        self.cache['model_stats'][model]['turns'] += 1

        # 更新模型统计（项目）
        if model not in project['model_stats']:
            project['model_stats'][model] = {'sessions': set(), 'tokens': 0, 'turns': 0}
        project['model_stats'][model]['sessions'].add(session_id)
        project['model_stats'][model]['tokens'] += total_tokens
        project['model_stats'][model]['turns'] += 1

        # 更新每日统计（全局）
        if date not in self.cache['daily_stats']:
            self.cache['daily_stats'][date] = {'date': date, 'sessions': set(), 'tokens': 0, 'turns': 0}
        self.cache['daily_stats'][date]['sessions'].add(session_id)
        self.cache['daily_stats'][date]['tokens'] += total_tokens
        self.cache['daily_stats'][date]['turns'] += 1

        # 更新每日统计（项目）
        if date not in project['daily_stats']:
            project['daily_stats'][date] = {'date': date, 'sessions': set(), 'tokens': 0, 'turns': 0}
        project['daily_stats'][date]['sessions'].add(session_id)
        project['daily_stats'][date]['tokens'] += total_tokens
        project['daily_stats'][date]['turns'] += 1

    def _serialize_cache(self) -> Dict:
        """序列化缓存（将 set 转为可 JSON 序列化的格式）"""
        serialized = json.loads(json.dumps(self.cache, default=lambda o: list(o) if isinstance(o, set) else o))
        return serialized


# 全局缓存实例
cache = UsageCache()

# FastAPI 应用
app = FastAPI(title="Usage Tracking API", version="3.0.0")


@app.on_event("startup")
async def startup_event():
    """启动时初始化缓存"""
    cache.check_and_update()


@app.get("/", response_class=HTMLResponse)
async def root():
    """返回前端页面"""
    html_file = WEB_DIR / 'index.html'
    if not html_file.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")

    with open(html_file, 'r', encoding='utf-8') as f:
        return f.read()


@app.get("/api/summary")
async def get_summary():
    """获取总体统计"""
    cache.check_and_update()

    # 计算 session 数（从 sessions 字典的键数量）
    total_sessions = len(cache.cache['sessions'])

    # 序列化 model_stats（将 sessions set 转为列表长度）
    model_stats = {}
    for model, stats in cache.cache['model_stats'].items():
        model_stats[model] = {
            'sessions': len(stats['sessions']) if isinstance(stats['sessions'], set) else stats['sessions'],
            'tokens': stats['tokens'],
            'turns': stats['turns']
        }

    return {
        'total_tokens': cache.cache['total_tokens'],
        'total_sessions': total_sessions,
        'total_turns': cache.cache['total_turns'],
        'model_stats': model_stats,
        'project_count': len(cache.cache['projects']),
        'updated_at': cache.cache.get('updated_at')
    }


@app.get("/api/trends")
async def get_trends(days: Optional[int] = 30):
    """获取全局时间趋势"""
    cache.check_and_update()

    daily_stats = cache.cache.get('daily_stats', {})
    sorted_dates = sorted(daily_stats.keys(), reverse=True)[:days]
    sorted_dates.reverse()

    # 序列化（将 sessions set 转为长度）
    data = []
    for date in sorted_dates:
        stats = daily_stats[date]
        data.append({
            'date': stats['date'],
            'sessions': len(stats['sessions']) if isinstance(stats['sessions'], set) else stats['sessions'],
            'tokens': stats['tokens'],
            'turns': stats['turns']
        })

    return {
        'days': days,
        'data': data
    }


@app.get("/api/projects")
async def get_projects():
    """获取所有项目列表"""
    cache.check_and_update()

    projects = []
    for proj_dir, proj in cache.cache['projects'].items():
        # 序列化
        serialized_proj = {
            'project_dir': proj['project_dir'],
            'project_name': proj['project_name'],
            'total_tokens': proj['total_tokens'],
            'total_sessions': len(set(
                sid for sid, s in cache.cache['sessions'].items()
                if s['project_dir'] == proj_dir
            )),
            'total_turns': proj['total_turns'],
        }
        projects.append(serialized_proj)

    # 按 token 消耗降序排序
    projects.sort(key=lambda x: x.get('total_tokens', 0), reverse=True)

    return {
        'total': len(projects),
        'projects': projects
    }


@app.get("/api/project")
async def get_project_detail(project_dir: Optional[str] = None):
    """获取单个项目详情"""
    cache.check_and_update()

    if not project_dir:
        raise HTTPException(status_code=400, detail="Missing project_dir parameter")

    project = cache.cache['projects'].get(project_dir)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # 序列化
    serialized_proj = {
        'project_dir': project['project_dir'],
        'project_name': project['project_name'],
        'total_tokens': project['total_tokens'],
        'total_sessions': len(set(
            sid for sid, s in cache.cache['sessions'].items()
            if s['project_dir'] == project_dir
        )),
        'total_turns': project['total_turns'],
        'model_stats': {}
    }

    # 序列化 model_stats
    for model, stats in project.get('model_stats', {}).items():
        serialized_proj['model_stats'][model] = {
            'sessions': len(stats['sessions']) if isinstance(stats['sessions'], set) else stats['sessions'],
            'tokens': stats['tokens'],
            'turns': stats['turns']
        }

    return serialized_proj


@app.get("/api/project/trends")
async def get_project_trends(project_dir: Optional[str] = None, days: Optional[int] = 30):
    """获取单个项目的时间趋势"""
    cache.check_and_update()

    if not project_dir:
        raise HTTPException(status_code=400, detail="Missing project_dir parameter")

    project = cache.cache['projects'].get(project_dir)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    daily_stats = project.get('daily_stats', {})
    sorted_dates = sorted(daily_stats.keys(), reverse=True)[:days]
    sorted_dates.reverse()

    # 序列化
    data = []
    for date in sorted_dates:
        stats = daily_stats[date]
        data.append({
            'date': stats['date'],
            'sessions': len(stats['sessions']) if isinstance(stats['sessions'], set) else stats['sessions'],
            'tokens': stats['tokens'],
            'turns': stats['turns']
        })

    return {
        'project_dir': project_dir,
        'project_name': project.get('project_name', 'unknown'),
        'days': days,
        'data': data
    }


@app.get("/api/sessions")
async def get_sessions(
    project_dir: Optional[str] = None,
    limit: Optional[int] = 50,
    offset: Optional[int] = 0
):
    """获取会话列表（可按项目筛选）"""
    cache.check_and_update()

    sessions = []
    for session_id, session in cache.cache['sessions'].items():
        if project_dir and session.get('project_dir') != project_dir:
            continue

        sessions.append({
            'session_id': session_id,
            'project_dir': session.get('project_dir', ''),
            'project_name': session.get('project_name', ''),
            'model': session.get('model', ''),
            'total_tokens': session.get('total_tokens', 0),
            'total_turns': session.get('total_turns', 0),
            'timestamp': session.get('last_timestamp', ''),
            'start_time': session.get('first_timestamp', ''),
            'end_time': session.get('last_timestamp', ''),
        })

    # 按时间倒序排序
    sessions.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

    # 分页
    total = len(sessions)
    sessions_page = sessions[offset:offset + limit]

    return {
        'total': total,
        'limit': limit,
        'offset': offset,
        'project_dir': project_dir,
        'sessions': sessions_page
    }


@app.get("/api/session/{session_id}")
async def get_session_detail(session_id: str):
    """获取单个会话详情（包含每轮概述）"""
    cache.check_and_update()

    session = cache.cache['sessions'].get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 序列化 turn_details（按 turn 编号排序）
    turn_details = sorted(session.get('turn_details', []), key=lambda x: x.get('turn', 0))

    return {
        'session_id': session_id,
        'project_dir': session.get('project_dir', ''),
        'project_name': session.get('project_name', ''),
        'model': session.get('model', ''),
        'total_tokens': session.get('total_tokens', 0),
        'total_turns': session.get('total_turns', 0),
        'input_tokens': session.get('input_tokens', 0),
        'output_tokens': session.get('output_tokens', 0),
        'cache_creation': session.get('cache_creation', 0),
        'cache_read': session.get('cache_read', 0),
        'start_time': session.get('first_timestamp', ''),
        'end_time': session.get('last_timestamp', ''),
        'turn_details': turn_details
    }


@app.get("/api/refresh")
async def refresh_cache():
    """手动刷新缓存"""
    updated = cache.check_and_update()
    return {
        'updated': updated,
        'message': 'Cache refreshed' if updated else 'No new data'
    }


def main():
    """主函数"""
    port = DEFAULT_PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"无效的端口号: {sys.argv[1]}")
            sys.exit(1)

    print(f"=== Usage Tracking Web Server ===")
    print(f"启动服务：http://localhost:{port}")
    print(f"数据文件：{USAGE_FILE}")
    print(f"缓存文件：{CACHE_FILE}")
    print(f"按 Ctrl+C 停止服务\n")

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
