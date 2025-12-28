#!/bin/bash
#
# Steelmaking Simulation 停止脚本
# 用法: ./stop.sh [force]
#

set -e

# 脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 项目根目录
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
# PID 文件
PID_FILE="$PROJECT_DIR/simulation.pid"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否运行中
is_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# 停止模拟
stop_simulation() {
    local force="$1"
    
    if [ ! -f "$PID_FILE" ]; then
        log_warn "PID file not found. Simulation may not be running."
        
        # 尝试查找并杀死进程
        PIDS=$(pgrep -f "steelmaking_simulation" 2>/dev/null || true)
        if [ -n "$PIDS" ]; then
            log_warn "Found running processes: $PIDS"
            if [ "$force" = "force" ]; then
                log_info "Force killing processes..."
                echo "$PIDS" | xargs kill -9 2>/dev/null || true
                log_info "Processes killed"
            else
                log_info "Use './stop.sh force' to kill these processes"
            fi
        fi
        exit 0
    fi
    
    PID=$(cat "$PID_FILE")
    
    if ! ps -p "$PID" > /dev/null 2>&1; then
        log_warn "Process $PID is not running. Cleaning up PID file."
        rm -f "$PID_FILE"
        exit 0
    fi
    
    log_info "Stopping Steelmaking Simulation (PID: $PID)..."
    
    if [ "$force" = "force" ]; then
        # 强制停止
        log_info "Force stopping..."
        kill -9 "$PID" 2>/dev/null || true
    else
        # 优雅停止 (SIGTERM)
        kill "$PID" 2>/dev/null || true
        
        # 等待进程结束
        TIMEOUT=30
        COUNTER=0
        while ps -p "$PID" > /dev/null 2>&1; do
            if [ $COUNTER -ge $TIMEOUT ]; then
                log_warn "Process did not stop gracefully. Force killing..."
                kill -9 "$PID" 2>/dev/null || true
                break
            fi
            sleep 1
            COUNTER=$((COUNTER + 1))
            echo -n "."
        done
        echo ""
    fi
    
    # 清理 PID 文件
    rm -f "$PID_FILE"
    
    # 验证停止
    if ps -p "$PID" > /dev/null 2>&1; then
        log_error "Failed to stop simulation!"
        exit 1
    else
        log_info "Simulation stopped successfully"
    fi
}

# 主逻辑
case "${1:-}" in
    force)
        stop_simulation "force"
        ;;
    *)
        stop_simulation
        ;;
esac
