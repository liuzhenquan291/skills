# Claude Code Skills

Claude Code 技能集合，提供增强功能。

## 安装

### usage-tracking

自动记录 Claude Code 会话的 token 消耗，支持 Web 可视化界面查看统计。

**一键安装：**

```bash
curl -fsSL https://raw.githubusercontent.com/liuzhenquan291/skills/main/install-usage-tracking.sh | bash
```

**安装后使用：**

- **Web 界面**（安装时自动启动，开机自启）：访问 http://localhost:8765
- 在 Claude Code 会话中说："查看 usage"、"统计 token 消耗"、"打开 usage 页面"
- 命令行查看：`python3 ~/.claude/skills/usage-tracking/scripts/view_usage.py --summary`

**服务管理：**

```bash
# 查看服务状态
bash ~/.claude/skills/usage-tracking/scripts/service.sh status

# 重启服务
bash ~/.claude/skills/usage-tracking/scripts/service.sh restart

# 停止服务
bash ~/.claude/skills/usage-tracking/scripts/service.sh stop

# 启动服务
bash ~/.claude/skills/usage-tracking/scripts/service.sh start
```

**安全说明：**

- ✅ Web 服务仅绑定 `127.0.0.1`，只能本机访问
- ✅ 所有数据存储在本地 `~/.claude/skills/usage-tracking/data/`
- ✅ 不记录对话内容，只记录工具名、token 数等元数据

**平台支持：**

| 平台 | 后台服务 | 开机自启 | 备注 |
|------|---------|---------|------|
| macOS | ✅ | ✅ launchd | 完整支持 |
| Linux | ✅ | ✅ systemd | 完整支持 |
| Windows | ⚠️ | ❌ | 需要 WSL 或 Git Bash |

**功能特性：**

- ✅ 自动记录：通过 Stop hook，每次会话结束时自动记录
- ✅ 详细统计：记录每轮对话的 token 消耗、工具调用、响应长度
- ✅ 跨项目：全局生效，所有项目的记录汇总到一个文件
- ✅ Web 界面：本地 Web 服务，可视化展示统计数据（Chart.js 图表）
- ✅ 增量缓存：智能缓存机制，避免重复解析
- ✅ 隐私安全：只记录关键信息（工具名、响应长度），不记录对话内容

## 技能列表

| 技能 | 说明 | 安装命令 |
|------|------|----------|
| [usage-tracking](cc/usage-tracking/) | Token 使用量追踪与统计 | `curl -fsSL https://raw.githubusercontent.com/liuzhenquan291/skills/main/install-usage-tracking.sh \| bash` |

## 开发新 Skill

每个 skill 应该是自包含的目录，包含：

- `SKILL.md` - Skill 定义（触发词、描述）
- `README.md` - 用户文档
- `scripts/` - 脚本和工具
- `data/` - 数据目录（gitignore）

参考 `cc/usage-tracking/` 的结构。

## 许可证

MIT License
