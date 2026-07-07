#!/usr/bin/env bash
# Usage Tracking 服务管理脚本
# 用法: service.sh {start|stop|restart|status}

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
PID_FILE="$SKILL_DIR/data/server.pid"
LOG_FILE="$SKILL_DIR/data/server.log"
PORT=8765

start_service() {
    # 检查是否已运行
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "✓ 服务已在运行 (PID: $PID)"
            echo "  访问: http://localhost:$PORT"
            return 0
        else
            # PID 文件存在但进程不存在，清理
            rm -f "$PID_FILE"
        fi
    fi

    # 确保数据目录存在
    mkdir -p "$SKILL_DIR/data"

    # 启动后台服务
    echo "启动 Web 服务..."
    nohup python3 "$SCRIPT_DIR/usage_server.py" "$PORT" \
        > "$LOG_FILE" 2>&1 &
    PID=$!
    echo "$PID" > "$PID_FILE"

    # 等待服务启动
    sleep 1

    # 检查是否成功启动
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "✓ 服务已启动 (PID: $PID)"
        echo "  访问: http://localhost:$PORT"
        echo "  日志: $LOG_FILE"

        # macOS: 创建 launchd plist 实现开机自启
        if [[ "$OSTYPE" == "darwin"* ]]; then
            setup_launchd
        # Linux: 创建 systemd user service 实现开机自启
        elif [[ "$OSTYPE" == "linux"* ]]; then
            setup_systemd
        fi
    else
        echo "✗ 服务启动失败，请检查日志: $LOG_FILE"
        rm -f "$PID_FILE"
        return 1
    fi
}

stop_service() {
    if [ ! -f "$PID_FILE" ]; then
        echo "服务未运行（PID 文件不存在）"
        return 0
    fi

    PID=$(cat "$PID_FILE")

    if ps -p "$PID" > /dev/null 2>&1; then
        echo "停止服务 (PID: $PID)..."
        kill "$PID"
        sleep 1

        # 确认已停止
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "强制停止..."
            kill -9 "$PID"
        fi

        echo "✓ 服务已停止"
    else
        echo "服务未运行（进程不存在）"
    fi

    rm -f "$PID_FILE"

    # macOS: 卸载 launchd
    if [[ "$OSTYPE" == "darwin"* ]]; then
        unload_launchd
    # Linux: 停止 systemd user service
    elif [[ "$OSTYPE" == "linux"* ]]; then
        stop_systemd
    fi
}

restart_service() {
    stop_service
    sleep 1
    start_service
}

status_service() {
    if [ ! -f "$PID_FILE" ]; then
        echo "服务未运行"
        return 1
    fi

    PID=$(cat "$PID_FILE")

    if ps -p "$PID" > /dev/null 2>&1; then
        echo "✓ 服务运行中 (PID: $PID)"
        echo "  访问: http://localhost:$PORT"
        echo "  日志: $LOG_FILE"
        return 0
    else
        echo "✗ 服务未运行（PID 文件存在但进程不存在）"
        rm -f "$PID_FILE"
        return 1
    fi
}

# macOS launchd 配置
setup_launchd() {
    PLIST_NAME="com.claude.usage-tracking"
    PLIST_FILE="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"

    # 如果已存在，先卸载
    unload_launchd

    # 创建 LaunchAgents 目录
    mkdir -p "$HOME/Library/LaunchAgents"

    # 生成 plist
    cat > "$PLIST_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$SCRIPT_DIR/usage_server.py</string>
        <string>$PORT</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$SKILL_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>$LOG_FILE</string>
    <key>StandardErrorPath</key>
    <string>$LOG_FILE</string>
</dict>
</plist>
EOF

    # 加载 plist
    launchctl load "$PLIST_FILE" 2>/dev/null || true
    echo "  ✓ 已配置开机自启 (launchd)"
}

unload_launchd() {
    PLIST_NAME="com.claude.usage-tracking"
    PLIST_FILE="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"

    if [ -f "$PLIST_FILE" ]; then
        launchctl unload "$PLIST_FILE" 2>/dev/null || true
        rm -f "$PLIST_FILE"
    fi
}

# Linux systemd 配置
setup_systemd() {
    SERVICE_NAME="usage-tracking"
    SERVICE_DIR="$HOME/.config/systemd/user"
    SERVICE_FILE="$SERVICE_DIR/$SERVICE_NAME.service"

    # 创建 systemd user 目录
    mkdir -p "$SERVICE_DIR"

    # 生成 service 文件
    cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Claude Code Usage Tracking Web Server
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $SCRIPT_DIR/usage_server.py $PORT
WorkingDirectory=$SKILL_DIR
Restart=on-failure
RestartSec=5
StandardOutput=append:$LOG_FILE
StandardError=append:$LOG_FILE

[Install]
WantedBy=default.target
EOF

    # 重新加载 systemd
    systemctl --user daemon-reload

    # 启用并启动服务
    systemctl --user enable "$SERVICE_NAME" 2>/dev/null || true
    systemctl --user start "$SERVICE_NAME" 2>/dev/null || true

    # 启用 linger（让用户服务在未登录时也能运行）
    sudo loginctl enable-linger "$USER" 2>/dev/null || true

    echo "  ✓ 已配置开机自启 (systemd)"
    echo "  提示: 运行 'loginctl enable-linger $USER' 让服务在未登录时也运行"
}

stop_systemd() {
    SERVICE_NAME="usage-tracking"

    if systemctl --user is-active "$SERVICE_NAME" >/dev/null 2>&1; then
        systemctl --user stop "$SERVICE_NAME" 2>/dev/null || true
        systemctl --user disable "$SERVICE_NAME" 2>/dev/null || true
    fi

    # 删除 service 文件
    SERVICE_FILE="$HOME/.config/systemd/user/$SERVICE_NAME.service"
    if [ -f "$SERVICE_FILE" ]; then
        rm -f "$SERVICE_FILE"
        systemctl --user daemon-reload 2>/dev/null || true
    fi
}

# 主逻辑
case "${1:-}" in
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    status)
        status_service
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
