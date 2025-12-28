#!/bin/bash
#
# Steelmaking Simulation 启动脚本
# 用法: ./start.sh [foreground|status]
#

set -e

# 脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 项目根目录
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
# PID 文件
PID_FILE="$PROJECT_DIR/simulation.pid"
# 日志目录
LOG_DIR="$PROJECT_DIR/logs"
# 日志文件
LOG_FILE="$LOG_DIR/simulation.log"

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

# 检查是否已运行
is_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# 显示状态
show_status() {
    if is_running; then
        PID=$(cat "$PID_FILE")
        log_info "Simulation is running (PID: $PID)"
        # 显示进程信息
        ps -p "$PID" -o pid,ppid,user,%cpu,%mem,start,time,cmd --no-headers 2>/dev/null || true
        return 0
    else
        log_warn "Simulation is not running"
        return 1
    fi
}

# 启动模拟
start_simulation() {
    local mode="$1"
    
    cd "$PROJECT_DIR"
    
    # 检查是否已运行
    if is_running; then
        PID=$(cat "$PID_FILE")
        log_warn "Simulation is already running (PID: $PID)"
        exit 1
    fi
    
    # 创建日志目录
    mkdir -p "$LOG_DIR"
    
    # 检查 .env 文件
    if [ ! -f "$PROJECT_DIR/.env" ]; then
        log_error ".env file not found! Please create it from .env.example"
        exit 1
    fi
    
    log_info "Starting Steelmaking Simulation..."
    log_info "Project directory: $PROJECT_DIR"
    log_info "Log file: $LOG_FILE"
    
    # 检测 Poetry 或使用 Python
    if command -v poetry &> /dev/null; then
        # 使用 Poetry
        log_info "Using Poetry to run simulation"
        
        if [ "$mode" = "foreground" ]; then
            # 前台运行 (用于 systemd)
            exec poetry run simulate 2>&1 | tee -a "$LOG_FILE"
        else
            # 后台运行
            nohup poetry run simulate >> "$LOG_FILE" 2>&1 &
            PID=$!
        fi
    else
        # 使用虚拟环境中的 Python
        if [ -d "$PROJECT_DIR/.venv" ]; then
            source "$PROJECT_DIR/.venv/bin/activate"
        fi
        
        log_info "Using Python to run simulation"
        
        if [ "$mode" = "foreground" ]; then
            exec python -m steelmaking_simulation.main 2>&1 | tee -a "$LOG_FILE"
        else
            nohup python -m steelmaking_simulation.main >> "$LOG_FILE" 2>&1 &
            PID=$!
        fi
    fi
    
    # 保存 PID (仅后台模式)
    if [ "$mode" != "foreground" ]; then
        echo "$PID" > "$PID_FILE"
        
        # 等待一小段时间检查进程是否成功启动
        sleep 2
        
        if is_running; then
            log_info "Simulation started successfully (PID: $PID)"
            log_info "Logs: tail -f $LOG_FILE"
        else
            log_error "Simulation failed to start. Check logs: $LOG_FILE"
            rm -f "$PID_FILE"
            exit 1
        fi
    fi
}

# 主逻辑
case "${1:-}" in
    foreground)
        start_simulation "foreground"
        ;;
    status)
        show_status
        ;;
    *)
        start_simulation "background"
        ;;
esac
