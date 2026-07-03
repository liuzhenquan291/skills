# Usage Tracking Skill

Claude Code Token 使用量追踪与统计工具。

自动记录每次 Claude Code 会话的 token 消耗，支持 **Web 可视化界面** 查看统计。

## 功能特性

- **自动记录**：通过 Stop hook，每次会话结束时自动记录
- **详细统计**：记录每轮对话的 token 消耗、工具调用、响应长度
- **跨项目**：全局生效，所有项目的记录汇总到一个文件
- **跨设备**：提供安装脚本，新设备一键部署
- **Web 界面**：本地 Web 服务，可视化展示统计数据
- **增量缓存**：智能缓存机制，避免重复解析
- **隐私安全**：只记录关键信息（工具名、响应长度），不记录对话内容

## 快速开始

### 1. 安装

在新设备上，将 `usage-tracking` 目录复制到 `~/.claude/skills/`：

```bash
cp -r usage-tracking ~/.claude/skills/
```

运行安装脚本：

```bash
bash ~/.claude/skills/usage-tracking/scripts/install.sh
```

安装脚本会：
- 创建 `data/` 目录
- 安装 Python 依赖（FastAPI + uvicorn）
- 配置 Stop hook（会话结束时自动记录）
- 创建数据文件
- 验证安装结果

### 2. 使用

安装完成后，正常使用 Claude Code 即可。每次会话结束时，token 消耗会自动记录到 `data/usage.jsonl`。

### 3. 查看统计

#### Web 界面（推荐）

```bash
# 启动 Web 服务
python3 ~/.claude/skills/usage-tracking/scripts/usage_server.py
```

然后访问 http://localhost:8765

功能：
- **总体统计**：总 token、会话数、平均消耗、模型分布
- **时间趋势**：每日 token 消耗折线图（最近 30 天）
- **会话列表**：按时间排序，可展开查看每轮对话详情
- **实时刷新**：点击刷新按钮获取最新数据

#### 命令行查看

```bash
# 总体摘要
python3 ~/.claude/skills/usage-tracking/scripts/view_usage.py --summary

# 最近 5 条会话
python3 ~/.claude/skills/usage-tracking/scripts/view_usage.py --latest 5

# 所有会话的每轮详情
python3 ~/.claude/skills/usage-tracking/scripts/view_usage.py --all-turns

# 指定会话的详情
python3 ~/.claude/skills/usage-tracking/scripts/view_usage.py --session <session_id> --turns

# 查看帮助
python3 ~/.claude/skills/usage-tracking/scripts/view_usage.py --help
```

### 4. 在 Claude Code 中查看

也可以直接在 Claude Code 会话中说：

- "查看 usage"
- "统计 token 消耗"
- "打开 usage 页面"
- "最近用了多少 token"

Claude 会自动调用这个 skill 来查询和展示统计数据。

## 数据格式

`data/usage.jsonl` 每行是一条 JSON 记录，包含：

```json
{
  "session_id": "ae6f96ae-266a-4680-a879-fcc206e6c743",
  "timestamp": "2026-07-02T14:13:00",
  "model": "claude-opus-4-7",
  "turns": 50,
  "input_tokens": 125000,
  "output_tokens": 38000,
  "cache_creation": 0,
  "cache_read": 95000,
  "total_tokens": 258000,
  "start_time": "2026-07-02T10:00:00",
  "end_time": "2026-07-02T14:13:00",
  "turn_details": [
    {
      "turn": 1,
      "timestamp": "2026-07-02T10:00:05",
      "input_tokens": 2500,
      "output_tokens": 800,
      "cache_creation": 0,
      "cache_read": 1900,
      "total": 5200,
      "stop_reason": "end_turn",
      "has_tool_calls": true,
      "tool_names": ["Read", "Bash"],
      "response_length": 1200
    }
  ]
}
```

## 文件大小估算

基于实测数据（201 轮 ≈ 48KB）：

| 使用强度 | 每天轮次 | 每天大小 | 每年大小 |
|---------|---------|---------|---------|
| 轻度 | ~500 轮 | ~120 KB | ~44 MB |
| 中度 | ~2000 轮 | ~480 KB | ~175 MB |
| 重度 | ~5000 轮 | ~1.2 MB | ~430 MB |

JSONL 格式支持追加写入，几百 MB 内读写都很流畅。

如果文件过大（>500MB），可以：
1. 归档旧数据：`mv data/usage.jsonl data/usage-2026.jsonl`
2. 或修改 `usage_logger.py`，不记录 `turn_details`（体积缩小 90%+）

## 文件结构

所有文件都在 skill 目录下，自包含、易迁移：

```
~/.claude/skills/usage-tracking/
├── SKILL.md                 ← Skill 定义（Claude Code 读取）
├── README.md                ← 本说明文档
├── USAGE_README.md          ← 详细使用说明
├── data/
│   ├── usage.jsonl          ← 原始数据（所有项目）
│   └── usage_cache.json     ← 处理后的缓存
└── scripts/
    ├── install.sh           ← 安装脚本
    ├── usage_logger.py      ← Stop hook 脚本
    ├── usage_server.py      ← Web 服务（FastAPI）
    ├── view_usage.py        ← 命令行查看工具
    └── web/
        └── index.html       ← Web 前端页面
```

| 文件 | 用途 |
|------|------|
| `data/usage.jsonl` | 原始 token 使用记录（append-only，所有项目混在一起） |
| `data/usage_cache.json` | 处理后的缓存数据（可删除，会自动重建） |
| `scripts/usage_logger.py` | Stop hook 脚本，解析 transcript 并记录 |
| `scripts/usage_server.py` | Web 服务（FastAPI），端口 8765 |
| `scripts/view_usage.py` | 命令行统计查看工具 |
| `scripts/web/index.html` | Web 前端页面（Chart.js 图表） |

## 缓存机制

Web 服务使用增量处理机制，避免重复解析：

1. `usage.jsonl` 是原始数据（append-only）
2. `usage_cache.json` 存储：
   - `last_offset`：已处理到的文件偏移量
   - `sessions`：已处理的会话摘要（按 session_id 索引）
   - `daily_stats`：每日统计汇总
   - `model_stats`：模型使用统计
   - `total_*`：总计数据
3. 每次请求 API 时：
   - 检查 `usage.jsonl` 文件大小是否超过 `last_offset`
   - 只读取新增的行
   - 处理新会话并更新缓存
   - 返回统计数据

**优势：**
- 首次加载后，后续请求只处理增量数据
- 即使文件很大（几百 MB），响应也很快
- 缓存文件可随时删除，会自动重建

## Web 界面截图说明

启动 Web 服务后，访问 http://localhost:8765 可以看到：

**顶部统计卡片：**
- 总 Tokens（格式化显示，如 1.2M）
- 会话数 / 总轮次
- 平均每次会话消耗的 token
- 最后更新时间 / 使用的模型数

**趋势图表：**
- 折线图展示最近 30 天的 token 消耗
- 双 Y 轴：左侧 token 数，右侧会话数
- 鼠标悬停显示详细数值

**会话列表：**
- 按时间倒序排列
- 显示会话 ID（前 8 位）、时间、模型、轮次、总 token
- 点击展开查看：
  - 输入/输出 token 明细
  - 缓存创建/读取统计
  - 开始/结束时间
  - 每轮对话详情表格（轮次、时间、token、工具调用、响应长度）

## 故障排查

### Hook 没有触发

检查 `~/.claude/settings.json` 是否有正确的 Stop hook 配置：

```bash
python3 -c "import json; d=json.load(open('$HOME/.claude/settings.json')); print(json.dumps(d.get('hooks',{}), indent=2))"
```

应该看到类似：

```json
{
  "Stop": [
    {
      "matcher": "",
      "hooks": [
        {
          "type": "command",
          "command": "python3 ~/.claude/usage_logger.py"
        }
      ]
    }
  ]
}
```

### 找不到 transcript

脚本通过 cwd 查找 transcript，确保在正确的项目目录下运行。

### 手动记录

如果 hook 没有自动触发，可以手动运行：

```bash
python3 ~/.claude/usage_logger.py
```

### 文件权限

确保脚本可执行：

```bash
chmod +x ~/.claude/usage_logger.py ~/.claude/view_usage.py
```

## 跨设备同步

### 方式 1：Git 仓库（推荐）

将 `~/codebuddy/skills/cc/usage-tracking/` 放入 git 仓库，新设备 clone 后运行 install。

### 方式 2：云同步

用 iCloud/Dropbox/OneDrive 同步 `~/.claude/skills/usage-tracking/` 目录。

### 方式 3：手动复制

直接复制 `usage-tracking/` 目录到新设备的 `~/.claude/skills/`。

## 工作原理

1. Claude Code 的每次对话都会生成 transcript 文件（`~/.claude/projects/<hash>/<session-id>.jsonl`）
2. 会话结束时，Stop hook 触发 `usage_logger.py`
3. 脚本解析 transcript，提取每轮对话的 token 使用量
4. 追加到 `~/.claude/usage.jsonl`
5. 通过 session_id 去重，避免重复记录

## 隐私说明

- **不记录对话内容**：只记录工具名称、响应长度等元数据
- **本地存储**：所有数据保存在本地 `~/.claude/usage.jsonl`
- **不上传**：不会自动上传到任何服务器
- **可删除**：随时可以删除 `usage.jsonl` 清除所有记录

## 技术细节

- **数据来源**：Claude Code transcript JSONL 文件
- **记录时机**：会话结束时（Stop hook）
- **存储格式**：JSONL（每行一条 JSON）
- **去重机制**：通过 session_id 判断是否已记录
- **全局生效**：配置在 `~/.claude/settings.json`，所有项目共用

## 许可证

MIT License - 自由使用和修改

## 贡献

欢迎提交 Issue 和 Pull Request。

## 联系方式

如有问题或建议，欢迎反馈。
