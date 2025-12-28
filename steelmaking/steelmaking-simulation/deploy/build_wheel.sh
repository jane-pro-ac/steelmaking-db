#!/bin/bash
#
# 使用 Poetry 构建 wheel 包
# 生成的包可以直接用 pip install 安装
#

set -e

# 脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 项目根目录
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
# 输出目录
DIST_DIR="$PROJECT_DIR/dist"

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

cd "$PROJECT_DIR"

log_info "Building Steelmaking Simulation wheel package..."
log_info "Project directory: $PROJECT_DIR"

# 清理之前的构建
log_info "Cleaning previous builds..."
rm -rf "$DIST_DIR"

# 使用 Poetry 构建 wheel
log_info "Running poetry build..."
poetry build

# 检查构建结果
WHEEL_FILE=$(ls "$DIST_DIR"/*.whl 2>/dev/null | head -1)

if [ -n "$WHEEL_FILE" ]; then
    log_info "Build successful!"
    log_info "Wheel file: $WHEEL_FILE"
    log_info "File size: $(du -h "$WHEEL_FILE" | cut -f1)"
    
    # 创建发布包
    log_info "Creating release package..."
    RELEASE_DIR="$DIST_DIR/steelmaking-simulation-release"
    mkdir -p "$RELEASE_DIR"
    
    # 复制 wheel 文件
    cp "$WHEEL_FILE" "$RELEASE_DIR/"
    
    # 创建启动脚本
    cat > "$RELEASE_DIR/start.sh" <<'STARTEOF'
#!/bin/bash
#
# Steelmaking Simulation 启动脚本 (Wheel 版本)
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/simulation.pid"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/simulation.log"

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查是否已运行
is_running() {
    [ -f "$PID_FILE" ] && ps -p "$(cat "$PID_FILE")" > /dev/null 2>&1
}

# 显示状态
show_status() {
    if is_running; then
        log_info "Simulation is running (PID: $(cat "$PID_FILE"))"
        ps -p "$(cat "$PID_FILE")" -o pid,ppid,user,%cpu,%mem,start,time --no-headers
    else
        log_warn "Simulation is not running"
    fi
}

# 启动
start_simulation() {
    local mode="$1"
    
    cd "$SCRIPT_DIR"
    mkdir -p "$LOG_DIR"
    
    if is_running; then
        log_warn "Already running (PID: $(cat "$PID_FILE"))"
        exit 1
    fi
    
    # 检查 .env 文件
    if [ ! -f "$SCRIPT_DIR/.env" ]; then
        log_error ".env file not found! Please create it from .env.example"
        exit 1
    fi
    
    # 查找 Python 和 simulate 命令
    SIMULATE_CMD=""
    
    # 方式1: 虚拟环境中的命令
    if [ -d "$SCRIPT_DIR/.venv" ]; then
        source "$SCRIPT_DIR/.venv/bin/activate"
        SIMULATE_CMD="simulate"
    # 方式2: 系统安装的命令
    elif command -v simulate &> /dev/null; then
        SIMULATE_CMD="simulate"
    # 方式3: Python 模块方式
    elif command -v python3 &> /dev/null; then
        SIMULATE_CMD="python3 -m steelmaking_simulation.main"
    else
        log_error "Cannot find simulate command or python3"
        exit 1
    fi
    
    log_info "Starting Steelmaking Simulation..."
    log_info "Command: $SIMULATE_CMD"
    log_info "Log file: $LOG_FILE"
    
    if [ "$mode" = "foreground" ]; then
        exec $SIMULATE_CMD 2>&1 | tee -a "$LOG_FILE"
    else
        nohup $SIMULATE_CMD >> "$LOG_FILE" 2>&1 &
        PID=$!
        echo "$PID" > "$PID_FILE"
        
        sleep 2
        if is_running; then
            log_info "Started successfully (PID: $PID)"
            log_info "Logs: tail -f $LOG_FILE"
        else
            log_error "Failed to start. Check logs: $LOG_FILE"
            rm -f "$PID_FILE"
            exit 1
        fi
    fi
}

case "${1:-}" in
    foreground) start_simulation "foreground" ;;
    status) show_status ;;
    *) start_simulation "background" ;;
esac
STARTEOF

    # 创建停止脚本
    cat > "$RELEASE_DIR/stop.sh" <<'STOPEOF'
#!/bin/bash
#
# Steelmaking Simulation 停止脚本
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/simulation.pid"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

if [ ! -f "$PID_FILE" ]; then
    log_warn "PID file not found. Not running."
    exit 0
fi

PID=$(cat "$PID_FILE")

if ! ps -p "$PID" > /dev/null 2>&1; then
    log_warn "Process $PID not found. Cleaning up."
    rm -f "$PID_FILE"
    exit 0
fi

log_info "Stopping simulation (PID: $PID)..."

if [ "${1:-}" = "force" ]; then
    kill -9 "$PID" 2>/dev/null || true
else
    kill "$PID" 2>/dev/null || true
    # 等待进程结束
    for i in {1..30}; do
        if ! ps -p "$PID" > /dev/null 2>&1; then
            break
        fi
        sleep 1
    done
    # 强制终止
    if ps -p "$PID" > /dev/null 2>&1; then
        log_warn "Force killing..."
        kill -9 "$PID" 2>/dev/null || true
    fi
fi

rm -f "$PID_FILE"
log_info "Stopped"
STOPEOF

    # 创建安装脚本
    cat > "$RELEASE_DIR/install.sh" <<'INSTALLEOF'
#!/bin/bash
#
# Steelmaking Simulation 安装脚本
# 自动创建虚拟环境并安装 wheel 包
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

cd "$SCRIPT_DIR"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    log_warn "Python3 not found. Installing..."
    sudo apt update && sudo apt install -y python3 python3-venv python3-pip
fi

# 检查 Python 版本
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
log_info "Python version: $PYTHON_VERSION"

if [[ "$PYTHON_VERSION" < "3.10" ]]; then
    log_warn "Python 3.10+ required. Current: $PYTHON_VERSION"
    log_warn "Installing Python 3.10..."
    sudo apt install -y python3.10 python3.10-venv
    PYTHON_CMD="python3.10"
else
    PYTHON_CMD="python3"
fi

# 创建虚拟环境
if [ ! -d "$VENV_DIR" ]; then
    log_info "Creating virtual environment..."
    $PYTHON_CMD -m venv "$VENV_DIR"
fi

# 激活虚拟环境
source "$VENV_DIR/bin/activate"

# 安装 wheel 包
log_info "Installing steelmaking-simulation..."
WHEEL_FILE=$(ls "$SCRIPT_DIR"/*.whl 2>/dev/null | head -1)

if [ -z "$WHEEL_FILE" ]; then
    log_warn "No wheel file found!"
    exit 1
fi

pip install --upgrade pip
pip install "$WHEEL_FILE"

# 检查配置文件
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    if [ -f "$SCRIPT_DIR/.env.example" ]; then
        cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
        log_warn "Created .env from .env.example. Please edit it!"
    fi
fi

log_info "Installation complete!"
log_info ""
log_info "Next steps:"
log_info "1. Edit .env file with your database settings"
log_info "2. Run: ./start.sh"
INSTALLEOF

    # 复制环境配置示例
    cp "$SCRIPT_DIR/.env.example" "$RELEASE_DIR/"
    
    # 创建 README
    cat > "$RELEASE_DIR/README.md" <<'READMEEOF'
# Steelmaking Simulation - Wheel Release

## 快速安装

```bash
# 1. 运行安装脚本 (自动创建虚拟环境并安装)
./install.sh

# 2. 配置数据库连接
nano .env

# 3. 启动
./start.sh
```

## 系统要求

- Ubuntu 20.04+ / Debian 10+
- Python 3.10+ (安装脚本会自动检查/安装)

## 手动安装

如果不想使用安装脚本，可以手动安装：

```bash
# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装 wheel 包
pip install steelmaking_simulation-*.whl

# 配置并运行
cp .env.example .env
nano .env
./start.sh
```

## 文件说明

- `steelmaking_simulation-*.whl` - Python wheel 包
- `install.sh` - 自动安装脚本
- `start.sh` - 启动脚本
- `stop.sh` - 停止脚本
- `.env.example` - 环境配置模板

## 运行命令

```bash
./start.sh              # 后台启动
./start.sh foreground   # 前台启动
./start.sh status       # 查看状态
./stop.sh               # 停止
./stop.sh force         # 强制停止
tail -f logs/simulation.log  # 查看日志
```
READMEEOF

    chmod +x "$RELEASE_DIR"/*.sh
    
    # 打包
    cd "$DIST_DIR"
    ARCHIVE_NAME="steelmaking-simulation-wheel-$(date +%Y%m%d).tar.gz"
    tar -czf "$ARCHIVE_NAME" steelmaking-simulation-release/
    
    log_info ""
    log_info "=========================================="
    log_info "Release package created: $DIST_DIR/$ARCHIVE_NAME"
    log_info "=========================================="
    log_info ""
    log_info "部署到 Ubuntu 服务器:"
    log_info "1. 上传: scp dist/$ARCHIVE_NAME user@server:/tmp/"
    log_info "2. 解压: cd /opt && sudo tar -xzf /tmp/$ARCHIVE_NAME"
    log_info "3. 安装: cd steelmaking-simulation-release && ./install.sh"
    log_info "4. 配置: nano .env"
    log_info "5. 运行: ./start.sh"
else
    log_warn "Build failed!"
    exit 1
fi
