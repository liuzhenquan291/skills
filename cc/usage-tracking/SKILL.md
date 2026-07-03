---
name: usage-tracking
description: |
  Claude Code Token 使用量追踪与统计工具。

  TRIGGER: 当用户提到以下场景时使用此 skill：
  - "统计 token 消耗"、"查看 token 用量"、"token 使用记录"
  - "安装 token 追踪"、"配置 usage hook"
  - "查看 usage"、"usage 统计"、"消耗了多少 token"
  - "打开 usage 页面"、"web 界面"、"可视化统计"
  - 在新设备上想要启用 token 追踪功能
---

# Usage Tracking Skill

自动记录每次 Claude Code 会话的 token 消耗，支持 Web 可视化界面查看统计。

## 功能

- **自动记录**：通过 Stop hook，每次会话结束时自动记录到 `data/usage.jsonl`
- **详细统计**：记录每轮对话的 token 消耗、工具调用、响应长度
- **跨项目**：全局生效，所有项目的记录汇总到一个文件
- **跨设备**：提供安装脚本，新设备一键部署
- **Web 界面**：本地 Web 服务，可视化展示统计数据

## 命令

### 安装（新设备首次使用）

当用户要求安装或配置 token 追踪时，运行安装脚本：

```bash
bash ~/.claude/skills/usage-tracking/scripts/install.sh
```

安装脚本会：
1. 创建 `data/` 目录
2. 安装 Python 依赖（FastAPI + uvicorn）
3. 在 `~/.claude/settings.json` 中配置 Stop hook
4. 验证安装结果

### 启动 Web 界面

当用户想要查看可视化统计时：

```bash
python3 ~/.claude/skills/usage-tracking/scripts/usage_server.py
```

然后访问 http://localhost:8765

功能：
- 总体统计：总 token、会话数、平均消耗
- 时间趋势：每日 token 消耗折线图
- 会话列表：按时间排序，可展开查看详情

### 查看统计（命令行）

当用户想快速查看 token 使用情况时：

```bash
# 总体摘要
python3 ~/.claude/skills/usage-tracking/scripts/view_usage.py --summary

# 最近 N 条会话
python3 ~/.claude/skills/usage-tracking/scripts/view_usage.py --latest 5

# 所有会话的每轮详情
python3 ~/.claude/skills/usage-tracking/scripts/view_usage.py --all-turns

# 指定会话的详情
python3 ~/.claude/skills/usage-tracking/scripts/view_usage.py --session <session_id> --turns
```

### 手动记录当前会话

如果 hook 没有触发，可以手动运行：

```bash
python3 ~/.claude/skills/usage-tracking/scripts/usage_logger.py
```

## 文件结构

所有文件都在 skill 目录下，自包含、易迁移：

```
~/.claude/skills/usage-tracking/
├── SKILL.md                 ← Skill 定义
├── README.md                ← 说明文档
├── data/
│   ├── usage.jsonl          ← 原始数据（所有项目）
│   └── usage_cache.json     ← 处理后的缓存
└── scripts/
    ├── install.sh           ← 安装脚本
    ├── usage_logger.py      ← Stop hook 脚本
    ├── usage_server.py      ← Web 服务
    ├── view_usage.py        ← 命令行工具
    └── web/
        └── index.html       ← Web 前端
```

## 缓存机制

Web 服务使用增量处理机制：
- `usage.jsonl` 是原始数据（append-only）
- `usage_cache.json` 存储处理后的统计数据和文件偏移量
- 每次请求时只处理新增的会话数据
- 避免重复解析，提高性能

## 故障排查

### Web 服务无法启动
检查依赖是否安装：
```bash
pip3 install fastapi uvicorn
```

### Hook 没有触发
检查 `~/.claude/settings.json` 是否有正确的 Stop hook 配置：
```bash
python3 -c "import json; d=json.load(open('$HOME/.claude/settings.json')); print(json.dumps(d.get('hooks',{}), indent=2))"
```

### 找不到 transcript
脚本通过 cwd 查找 transcript，确保在正确的项目目录下运行。

### 文件权限
确保脚本可执行：
```bash
chmod +x ~/.claude/usage_logger.py ~/.claude/view_usage.py ~/.claude/usage_server.py
```
