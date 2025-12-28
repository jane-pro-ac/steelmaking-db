# Steelmaking Simulation 部署指南

本文档提供三种部署方式：
1. **Wheel 包部署** (推荐) - 使用 Poetry 构建，pip 安装
2. **源代码部署** - 直接使用 Poetry 管理依赖
3. **Docker 部署** - 容器化部署

---

## 方式一：Wheel 包部署 (推荐)

### 优势
- Poetry 原生支持，构建简单
- 服务器只需 Python + pip，无需 Poetry
- 自动创建虚拟环境，隔离依赖
- 包含自动安装脚本

### 系统要求
- Ubuntu 20.04 LTS 或更高版本
- Python 3.10+ (安装脚本会自动检查)
- 可访问的 PostgreSQL 数据库

### 构建 Wheel 包 (在开发机器上)

```bash
# 在项目目录
cd steelmaking-simulation

# 运行构建脚本
./deploy/build_wheel.sh

# 构建完成后会生成：
# dist/steelmaking-simulation-wheel-YYYYMMDD.tar.gz
```

### 部署到服务器

```bash
# 1. 上传包到服务器
scp dist/steelmaking-simulation-wheel-*.tar.gz user@server:/tmp/

# 2. 在服务器上解压
ssh user@server
cd /opt
sudo tar -xzf /tmp/steelmaking-simulation-wheel-*.tar.gz
sudo chown -R $USER:$USER steelmaking-simulation-release
cd steelmaking-simulation-release

# 3. 运行安装脚本 (自动创建虚拟环境并安装)
./install.sh

# 4. 配置环境变量
nano .env  # 编辑数据库配置

# 5. 运行
./start.sh              # 后台启动
./start.sh foreground   # 前台启动（查看输出）
tail -f logs/simulation.log  # 查看日志

# 6. 停止
./stop.sh
```

### Wheel 版本文件结构

```
steelmaking-simulation-release/
├── steelmaking_simulation-0.1.0-py3-none-any.whl  # wheel 包
├── install.sh               # 自动安装脚本
├── start.sh                 # 启动脚本
├── stop.sh                  # 停止脚本
├── .env.example             # 环境配置模板
├── README.md                # 使用说明
├── .venv/                   # 虚拟环境（安装后创建）
└── logs/                    # 日志目录（自动创建）
```

---

## 方式二：源代码部署

### 系统要求
- Ubuntu 20.04 LTS 或更高版本
- Python 3.10+
- Poetry (Python 包管理器)
- PostgreSQL 客户端库 (libpq-dev)

## 安装步骤

### 1. 安装系统依赖

```bash
# 更新系统包
sudo apt update && sudo apt upgrade -y

# 安装 Python 3.10+ 和 pip
sudo apt install -y python3.10 python3.10-venv python3-pip

# 安装 PostgreSQL 客户端库 (psycopg2 编译需要)
sudo apt install -y libpq-dev python3-dev

# 安装 Poetry
curl -sSL https://install.python-poetry.org | python3 -
# 或者使用 pip
# pip3 install poetry

# 添加 Poetry 到 PATH (如果需要)
export PATH="$HOME/.local/bin:$PATH"
# 建议添加到 ~/.bashrc 或 ~/.profile
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### 2. 上传项目文件

需要上传的文件和目录：

```
steelmaking-simulation/
├── pyproject.toml          # 项目配置和依赖
├── poetry.lock             # 依赖锁定文件 (如果有)
├── .env                    # 环境变量配置 (需要创建)
├── deploy/                 # 部署脚本目录
│   ├── start.sh
│   └── stop.sh
└── steelmaking_simulation/ # 源代码目录
    ├── __init__.py
    ├── main.py
    ├── config/
    ├── core/
    ├── database/
    ├── events/
    ├── kpi_stats/
    ├── planning/
    ├── seeding/
    ├── utils/
    └── warnings/
```

上传命令示例 (从本地执行):
```bash
# 使用 rsync 上传 (推荐)
rsync -avz --exclude '__pycache__' --exclude '.venv' --exclude '*.pyc' \
  ./steelmaking-simulation/ user@server:/opt/steelmaking-simulation/

# 或使用 scp
scp -r ./steelmaking-simulation user@server:/opt/steelmaking-simulation/
```

### 3. 服务器上安装项目

```bash
# 进入项目目录
cd /opt/steelmaking-simulation

# 使用 Poetry 安装依赖
poetry install --no-dev

# 或者创建虚拟环境并安装 (不使用 Poetry)
python3 -m venv .venv
source .venv/bin/activate
pip install psycopg2-binary python-dotenv
```

### 4. 配置环境变量

创建 `.env` 文件：

```bash
cd /opt/steelmaking-simulation
nano .env
```

`.env` 文件内容：

```env
# 数据库配置
DB_HOST=your_postgres_host
DB_PORT=5432
DB_NAME=your_database_name
DB_USER=your_username
DB_PASSWORD=your_password

# 模拟配置
SIMULATION_INTERVAL=2
NEW_HEAT_PROBABILITY=0.3
MIN_OPERATION_DURATION_MINUTES=30
MAX_OPERATION_DURATION_MINUTES=50
MIN_TRANSFER_GAP_MINUTES=20
MAX_TRANSFER_GAP_MINUTES=30
MAX_REST_DURATION_MINUTES=20
MIN_REST_DURATION_MINUTES=3
ALIGNED_ROUTE_PROBABILITY=0.9

# 警告配置
MAX_WARNINGS_PER_OPERATION=10
WARNING_PROBABILITY_PER_TICK=0.2
SEED_WARNING_PROBABILITY_PER_COMPLETED_OPERATION=0.2

# Demo 种子数据配置
DEMO_SEED_PAST_HEATS=4
DEMO_SEED_ACTIVE_HEATS=2
DEMO_SEED_FUTURE_HEATS=4
```

### 5. 设置脚本权限

```bash
chmod +x deploy/start.sh
chmod +x deploy/stop.sh
```

## 运行模拟

### 手动运行

```bash
cd /opt/steelmaking-simulation

# 使用 Poetry
poetry run simulate

# 或者激活虚拟环境后运行
poetry shell
python -m steelmaking_simulation.main
```

### 使用脚本运行

```bash
# 启动 (后台运行)
./deploy/start.sh

# 停止
./deploy/stop.sh

# 查看状态
./deploy/start.sh status

# 查看日志
tail -f logs/simulation.log
```

## 使用 Systemd 服务 (可选)

创建 systemd 服务文件：

```bash
sudo nano /etc/systemd/system/steelmaking-simulation.service
```

内容：

```ini
[Unit]
Description=Steelmaking Simulation Service
After=network.target postgresql.service

[Service]
Type=simple
User=your_user
WorkingDirectory=/opt/steelmaking-simulation
ExecStart=/opt/steelmaking-simulation/deploy/start.sh foreground
ExecStop=/opt/steelmaking-simulation/deploy/stop.sh
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable steelmaking-simulation
sudo systemctl start steelmaking-simulation
sudo systemctl status steelmaking-simulation
```

## 故障排除

### 常见问题

1. **psycopg2 编译错误**
   ```bash
   sudo apt install -y libpq-dev python3-dev
   ```

2. **Poetry 命令找不到**
   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   ```

3. **数据库连接失败**
   - 检查 `.env` 文件中的数据库配置
   - 确保 PostgreSQL 服务运行中
   - 检查防火墙设置

4. **权限问题**
   ```bash
   sudo chown -R $USER:$USER /opt/steelmaking-simulation
   ```

### 查看日志

```bash
# 实时查看日志
tail -f /opt/steelmaking-simulation/logs/simulation.log

# 查看最近100行
tail -100 /opt/steelmaking-simulation/logs/simulation.log
```

## 目录结构说明

部署后的目录结构：

```
/opt/steelmaking-simulation/
├── .env                    # 环境配置
├── .venv/                  # Python 虚拟环境 (Poetry 自动创建)
├── pyproject.toml
├── logs/                   # 日志目录 (脚本自动创建)
│   └── simulation.log
├── deploy/
│   ├── start.sh
│   └── stop.sh
└── steelmaking_simulation/
    └── ...
```

---

## 方式三：Docker 部署

### 优势
- 完全隔离的运行环境
- 易于扩展和管理
- 可选内置 PostgreSQL 数据库

### 系统要求
- Ubuntu 20.04+
- Docker 20.10+
- Docker Compose 2.0+

### 安装 Docker

```bash
# 安装 Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 添加当前用户到 docker 组
sudo usermod -aG docker $USER

# 安装 Docker Compose
sudo apt install -y docker-compose-plugin
```

### 部署步骤

```bash
# 1. 上传项目到服务器
rsync -avz --exclude '__pycache__' --exclude '.venv' \
  ./steelmaking-simulation/ user@server:/opt/steelmaking-simulation/

# 2. 在服务器上配置
cd /opt/steelmaking-simulation
cp deploy/.env.example .env
nano .env  # 编辑配置

# 3. 构建并启动
docker compose -f deploy/docker-compose.yml up -d

# 4. 查看日志
docker compose -f deploy/docker-compose.yml logs -f steelmaking-simulation

# 5. 停止
docker compose -f deploy/docker-compose.yml down
```

### Docker 常用命令

```bash
# 查看运行状态
docker compose -f deploy/docker-compose.yml ps

# 重启服务
docker compose -f deploy/docker-compose.yml restart steelmaking-simulation

# 查看实时日志
docker compose -f deploy/docker-compose.yml logs -f

# 进入容器
docker compose -f deploy/docker-compose.yml exec steelmaking-simulation bash

# 重新构建镜像
docker compose -f deploy/docker-compose.yml build --no-cache

# 完全清理（包括数据）
docker compose -f deploy/docker-compose.yml down -v
```

### 仅部署应用（使用外部数据库）

编辑 `deploy/docker-compose.yml`，注释掉 postgres 服务：

```yaml
services:
  steelmaking-simulation:
    # ... 保持不变
    depends_on:  # 删除这一行
      - postgres  # 删除这一行

  # postgres:  # 注释掉整个 postgres 服务
  #   ...
```

然后在 `.env` 中配置外部数据库地址。

---

## 部署方式对比

| 特性 | Wheel 包部署 | 源代码部署 | Docker 部署 |
|------|-------------|-----------|------------|
| 部署难度 | ⭐ 简单 | ⭐⭐ 中等 | ⭐⭐ 中等 |
| 构建工具 | Poetry | Poetry | Docker |
| 服务器依赖 | Python + pip | Python + Poetry | Docker |
| 启动速度 | 快 | 中等 | 中等 |
| 资源占用 | 小 | 中 | 较大 |
| 升级难度 | 简单（替换 whl） | 中等 | 简单（重建镜像） |
| 适用场景 | 生产环境 | 开发/测试 | 生产/多实例 |
| 隔离性 | 中（虚拟环境） | 中 | 高 |

## 推荐方案

- **生产环境单实例**: Wheel 包部署
- **开发/测试环境**: 源代码部署
- **生产环境多实例/微服务**: Docker 部署
- **需要快速扩展**: Docker 部署
