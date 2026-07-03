#!/usr/bin/env bash
# Usage Tracking 安装脚本
# 在新设备上运行，自动配置 token 追踪功能

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$SKILL_DIR/data"
CLAUDE_DIR="$HOME/.claude"

echo "=== Usage Tracking 安装 ==="
echo ""

# 1. 确保 data 目录存在
mkdir -p "$DATA_DIR"
echo "✓ 数据目录已就绪: $DATA_DIR"

# 2. 创建空的 usage.jsonl（如果不存在）
USAGE_FILE="$DATA_DIR/usage.jsonl"
if [ ! -f "$USAGE_FILE" ]; then
    touch "$USAGE_FILE"
    echo "✓ 已创建 $USAGE_FILE"
else
    echo "✓ $USAGE_FILE 已存在"
fi

# 3. 设置脚本权限
chmod +x "$SCRIPT_DIR/usage_logger.py"
chmod +x "$SCRIPT_DIR/view_usage.py"
chmod +x "$SCRIPT_DIR/usage_server.py"
echo "✓ 脚本权限已设置"

# 4. 安装 Python 依赖（FastAPI + uvicorn）
echo ""
echo "=== 安装 Python 依赖 ==="
if pip3 install --quiet fastapi uvicorn 2>/dev/null; then
    echo "✓ FastAPI 和 uvicorn 已安装"
else
    echo "⚠ 自动安装失败，请手动运行: pip3 install fastapi uvicorn"
fi

# 5. 配置 Stop hook（如果尚未配置）
SETTINGS_FILE="$CLAUDE_DIR/settings.json"

if [ ! -f "$SETTINGS_FILE" ]; then
    # settings.json 不存在，创建新的
    mkdir -p "$CLAUDE_DIR"
    cat > "$SETTINGS_FILE" <<EOF
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 $SCRIPT_DIR/usage_logger.py"
          }
        ]
      }
    ]
  }
}
EOF
    echo "✓ 已创建 $SETTINGS_FILE 并配置 Stop hook"
else
    # settings.json 已存在，用 Python 安全地添加 hooks
    python3 - "$SETTINGS_FILE" "$SCRIPT_DIR" <<'PYEOF'
import json
import sys

settings_file = sys.argv[1]
script_dir = sys.argv[2]

# 读取现有配置
try:
    with open(settings_file, 'r') as f:
        settings = json.load(f)
except (json.JSONDecodeError, FileNotFoundError):
    settings = {}

# 检查是否已有 Stop hook
hooks = settings.get('hooks', {})
stop_hooks = hooks.get('Stop', [])

already_configured = False
for entry in stop_hooks:
    for h in entry.get('hooks', []):
        if 'usage_logger.py' in h.get('command', ''):
            already_configured = True
            break

if already_configured:
    print("✓ Stop hook 已配置，无需重复添加")
else:
    # 添加 Stop hook
    if 'hooks' not in settings:
        settings['hooks'] = {}
    if 'Stop' not in settings['hooks']:
        settings['hooks']['Stop'] = []

    settings['hooks']['Stop'].append({
        "matcher": "",
        "hooks": [
            {
                "type": "command",
                "command": f"python3 {script_dir}/usage_logger.py"
            }
        ]
    })

    with open(settings_file, 'w') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

    print("✓ 已将 Stop hook 添加到 settings.json")
PYEOF
fi

# 6. 验证安装
echo ""
echo "=== 安装验证 ==="
echo ""

# 验证脚本存在
if [ -f "$SCRIPT_DIR/usage_logger.py" ] && [ -f "$SCRIPT_DIR/view_usage.py" ] && [ -f "$SCRIPT_DIR/usage_server.py" ]; then
    echo "✓ 脚本文件就绪"
else
    echo "✗ 脚本文件缺失"
    exit 1
fi

# 验证 web 目录
if [ -d "$SCRIPT_DIR/web" ] && [ -f "$SCRIPT_DIR/web/index.html" ]; then
    echo "✓ Web 前端就绪"
else
    echo "✗ Web 前端缺失"
    exit 1
fi

# 验证数据目录
if [ -d "$DATA_DIR" ]; then
    echo "✓ 数据目录就绪"
else
    echo "✗ 数据目录缺失"
    exit 1
fi

# 验证 hook 配置
if python3 -c "import json; d=json.load(open('$SETTINGS_FILE')); assert 'usage_logger.py' in str(d.get('hooks',{}))" 2>/dev/null; then
    echo "✓ Stop hook 已配置"
else
    echo "✗ Stop hook 未配置"
    exit 1
fi

# 验证 FastAPI
if python3 -c "import fastapi" 2>/dev/null; then
    echo "✓ FastAPI 已安装"
else
    echo "✗ FastAPI 未安装，Web 服务无法启动"
    echo "  请手动运行: pip3 install fastapi uvicorn"
fi

echo ""
echo "=== 安装完成 ==="
echo ""
echo "使用方式："
echo ""
echo "1. 命令行查看："
echo "   python3 $SCRIPT_DIR/view_usage.py --summary"
echo "   python3 $SCRIPT_DIR/view_usage.py --latest 5"
echo ""
echo "2. Web 界面（推荐）："
echo "   python3 $SCRIPT_DIR/usage_server.py"
echo "   然后访问: http://localhost:8765"
echo ""
echo "下次启动 Claude Code 会话时，token 消耗将自动记录。"
