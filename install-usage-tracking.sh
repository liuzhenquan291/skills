#!/usr/bin/env bash
# Usage Tracking Skill 安装脚本
# 一键安装到 ~/.claude/skills/usage-tracking/
#
# 用法:
#   curl -fsSL https://raw.githubusercontent.com/liuzhenquan291/skills/main/install-usage-tracking.sh | bash

set -e

echo "=== Claude Code Usage Tracking Skill 安装 ==="
echo ""

# 目标目录
SKILL_DIR="$HOME/.claude/skills/usage-tracking"
TEMP_DIR=$(mktemp -d)

# 清理临时目录
trap "rm -rf $TEMP_DIR" EXIT

echo "1. 下载 skill 文件..."
REPO_URL="https://github.com/liuzhenquan291/skills/archive/refs/heads/main.tar.gz"

if curl -fsSL "$REPO_URL" -o "$TEMP_DIR/skills.tar.gz" 2>/dev/null; then
    tar -xzf "$TEMP_DIR/skills.tar.gz" -C "$TEMP_DIR"
    SOURCE_DIR="$TEMP_DIR/skills-main/cc/usage-tracking"
else
    echo "  下载失败，尝试使用 zip 格式..."
    REPO_URL="https://github.com/liuzhenquan291/skills/archive/refs/heads/main.zip"
    curl -fsSL "$REPO_URL" -o "$TEMP_DIR/skills.zip"
    unzip -q "$TEMP_DIR/skills.zip" -d "$TEMP_DIR"
    SOURCE_DIR="$TEMP_DIR/skills-main/cc/usage-tracking"
fi

if [ ! -d "$SOURCE_DIR" ]; then
    echo "  错误：找不到 usage-tracking 目录"
    exit 1
fi

echo "2. 创建目录结构..."
mkdir -p "$SKILL_DIR"
mkdir -p "$SKILL_DIR/scripts"
mkdir -p "$SKILL_DIR/data"

echo "3. 复制文件..."
cp -r "$SOURCE_DIR/scripts"/* "$SKILL_DIR/scripts/"
cp "$SOURCE_DIR/README.md" "$SKILL_DIR/" 2>/dev/null || true
cp "$SOURCE_DIR/SKILL.md" "$SKILL_DIR/" 2>/dev/null || true

echo "4. 设置权限..."
chmod +x "$SKILL_DIR/scripts/install.sh"
chmod +x "$SKILL_DIR/scripts/usage_logger.py"
chmod +x "$SKILL_DIR/scripts/view_usage.py"
chmod +x "$SKILL_DIR/scripts/usage_server.py"

echo "5. 创建数据文件..."
if [ ! -f "$SKILL_DIR/data/usage.jsonl" ]; then
    touch "$SKILL_DIR/data/usage.jsonl"
fi

echo "6. 配置 Stop hook..."
SETTINGS_FILE="$HOME/.claude/settings.json"

if [ ! -f "$SETTINGS_FILE" ]; then
    mkdir -p "$HOME/.claude"
    cat > "$SETTINGS_FILE" <<EOF
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 $SKILL_DIR/scripts/usage_logger.py"
          }
        ]
      }
    ]
  }
}
EOF
    echo "  已创建 settings.json"
else
    python3 - "$SETTINGS_FILE" "$SKILL_DIR" <<'PYEOF'
import json
import sys

settings_file = sys.argv[1]
skill_dir = sys.argv[2]

try:
    with open(settings_file, 'r') as f:
        settings = json.load(f)
except (json.JSONDecodeError, FileNotFoundError):
    settings = {}

hooks = settings.get('hooks', {})
stop_hooks = hooks.get('Stop', [])

already_configured = False
for entry in stop_hooks:
    for h in entry.get('hooks', []):
        if 'usage_logger.py' in h.get('command', ''):
            already_configured = True
            break

if already_configured:
    print("  Stop hook 已配置")
else:
    if 'hooks' not in settings:
        settings['hooks'] = {}
    if 'Stop' not in settings['hooks']:
        settings['hooks']['Stop'] = []

    settings['hooks']['Stop'].append({
        "matcher": "",
        "hooks": [
            {
                "type": "command",
                "command": f"python3 {skill_dir}/scripts/usage_logger.py"
            }
        ]
    })

    with open(settings_file, 'w') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

    print("  已添加 Stop hook")
PYEOF
fi

echo ""
echo "7. 安装依赖..."
if pip3 install --quiet fastapi uvicorn 2>/dev/null; then
    echo "  ✓ FastAPI 和 uvicorn 已安装"
else
    echo "  ⚠ 自动安装失败，请手动运行: pip3 install fastapi uvicorn"
fi

echo ""
echo "8. 启动 Web 服务..."
# 检查是否已有服务在运行
if lsof -i :8765 > /dev/null 2>&1; then
    echo "  服务已在运行（端口 8765）"
else
    # 后台启动服务
    nohup python3 "$SKILL_DIR/scripts/usage_server.py" > "$SKILL_DIR/data/usage_server.log" 2>&1 &
    echo "  ✓ 服务已启动（PID: $!）"
fi

echo ""
echo "=== 安装完成 ==="
echo ""
echo "Web 界面：http://localhost:8765"
echo ""
echo "命令行查看："
echo "  python3 $SKILL_DIR/scripts/view_usage.py --summary"
echo ""
echo "服务管理："
echo "  查看日志：cat $SKILL_DIR/data/usage_server.log"
echo "  重启服务：pkill -f usage_server.py && python3 $SKILL_DIR/scripts/usage_server.py &"
echo ""
echo "下次启动 Claude Code 会话时，token 消耗将自动记录。"
