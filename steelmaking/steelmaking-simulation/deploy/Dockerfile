# Steelmaking Simulation Docker Image
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 安装 Poetry
RUN pip install --no-cache-dir poetry

# 复制项目文件
COPY pyproject.toml poetry.lock* ./
COPY steelmaking_simulation/ ./steelmaking_simulation/

# 安装 Python 依赖
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# 创建日志目录
RUN mkdir -p /app/logs

# 暴露端口（如果需要）
# EXPOSE 8000

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 运行程序
CMD ["python", "-m", "steelmaking_simulation.main"]
