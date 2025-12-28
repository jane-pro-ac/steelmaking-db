#!/bin/bash
#
# 构建 Steelmaking Simulation 二进制可执行文件
# 使用 PyInstaller 打包
#

set -e

# 脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 项目根目录
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
# 输出目录
DIST_DIR="$PROJECT_DIR/dist"
BUILD_DIR="$PROJECT_DIR/build"

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

log_info "Building Steelmaking Simulation binary..."
log_info "Project directory: $PROJECT_DIR"

# 检查并安装 PyInstaller
if ! poetry run pyinstaller --version &> /dev/null; then
    log_warn "PyInstaller not found, installing..."
    poetry add --group dev pyinstaller
fi

# 清理之前的构建
log_info "Cleaning previous builds..."
rm -rf "$BUILD_DIR" "$DIST_DIR" *.spec

# 创建 PyInstaller spec 文件
log_info "Creating PyInstaller spec file..."

cat > steelmaking_simulation.spec <<'EOF'
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['steelmaking_simulation/main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'psycopg2',
        'psycopg2._psycopg',
        'dotenv',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='steelmaking-simulation',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
EOF

# 使用 PyInstaller 构建
log_info "Running PyInstaller..."
poetry run pyinstaller steelmaking_simulation.spec --clean

# 检查构建结果
if [ -f "$DIST_DIR/steelmaking-simulation" ]; then
    log_info "Build successful!"
    log_info "Binary location: $DIST_DIR/steelmaking-simulation"
    log_info "Binary size: $(du -h "$DIST_DIR/steelmaking-simulation" | cut -f1)"
    
    # 创建发布包
    log_info "Creating release package..."
    RELEASE_DIR="$DIST_DIR/steelmaking-simulation-release"
    mkdir -p "$RELEASE_DIR"
    
    # 复制二进制文件
    cp "$DIST_DIR/steelmaking-simulation" "$RELEASE_DIR/"
    
    # 复制部署脚本（修改为二进制版本）
    cp "$SCRIPT_DIR/start_binary.sh" "$RELEASE_DIR/start.sh" 2>/dev/null || cat > "$RELEASE_DIR/start.sh" <<'STARTEOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/simulation.pid"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/simulation.log"

mkdir -p "$LOG_DIR"

if [ -f "$PID_FILE" ] && ps -p "$(cat "$PID_FILE")" > /dev/null 2>&1; then
    echo "Already running (PID: $(cat "$PID_FILE"))"
    exit 1
fi

if [ "${1:-}" = "foreground" ]; then
    exec "$SCRIPT_DIR/steelmaking-simulation" 2>&1 | tee -a "$LOG_FILE"
else
    nohup "$SCRIPT_DIR/steelmaking-simulation" >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "Started (PID: $!)"
    echo "Logs: tail -f $LOG_FILE"
fi
STARTEOF
    
    cp "$SCRIPT_DIR/stop.sh" "$RELEASE_DIR/" 2>/dev/null || cat > "$RELEASE_DIR/stop.sh" <<'STOPEOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/simulation.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "Not running"
    exit 0
fi

PID=$(cat "$PID_FILE")
if ps -p "$PID" > /dev/null 2>&1; then
    echo "Stopping (PID: $PID)..."
    kill "$PID"
    sleep 2
    if ps -p "$PID" > /dev/null 2>&1; then
        kill -9 "$PID"
    fi
    rm -f "$PID_FILE"
    echo "Stopped"
else
    rm -f "$PID_FILE"
    echo "Not running"
fi
STOPEOF
    
    # 复制环境配置示例
    cp "$SCRIPT_DIR/.env.example" "$RELEASE_DIR/"
    
    # 创建 README
    cat > "$RELEASE_DIR/README.md" <<'READMEEOF'
# Steelmaking Simulation Binary Release

## 快速开始

1. 配置环境变量：
```bash
cp .env.example .env
nano .env  # 编辑数据库配置
```

2. 设置可执行权限：
```bash
chmod +x steelmaking-simulation start.sh stop.sh
```

3. 运行：
```bash
# 启动
./start.sh

# 停止
./stop.sh

# 前台运行（查看实时输出）
./start.sh foreground

# 查看日志
tail -f logs/simulation.log
```

## 系统要求

- Ubuntu 20.04+ / Debian 10+
- 无需安装 Python 或其他依赖
- 需要可访问的 PostgreSQL 数据库

## 文件说明

- `steelmaking-simulation` - 主程序二进制文件
- `start.sh` - 启动脚本
- `stop.sh` - 停止脚本
- `.env.example` - 环境配置模板
- `logs/` - 日志目录（自动创建）
READMEEOF
    
    chmod +x "$RELEASE_DIR"/*.sh
    chmod +x "$RELEASE_DIR/steelmaking-simulation"
    
    # 打包
    cd "$DIST_DIR"
    tar -czf steelmaking-simulation-$(uname -m).tar.gz steelmaking-simulation-release/
    
    log_info "Release package created: $DIST_DIR/steelmaking-simulation-$(uname -m).tar.gz"
    log_info ""
    log_info "To deploy on Ubuntu server:"
    log_info "1. Upload: scp dist/steelmaking-simulation-$(uname -m).tar.gz user@server:/tmp/"
    log_info "2. Extract: tar -xzf /tmp/steelmaking-simulation-$(uname -m).tar.gz -C /opt/"
    log_info "3. Configure: cd /opt/steelmaking-simulation-release && cp .env.example .env && nano .env"
    log_info "4. Run: ./start.sh"
else
    log_warn "Build failed!"
    exit 1
fi
