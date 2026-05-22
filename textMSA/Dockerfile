# textMSA API Server Dockerfile
# 支持连接外部 MongoDB 和挂载存储卷

FROM python:3.11-slim as builder

# 设置工作目录
WORKDIR /build

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY server/requirements.txt /build/requirements.txt

# 安装 Python 依赖
RUN pip install --no-cache-dir --user -r requirements.txt

# 运行时镜像
FROM python:3.11-slim

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 安装运行时依赖（如果需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制 Python 依赖
COPY --from=builder /root/.local /root/.local

# 确保本地 bin 目录在 PATH 中
ENV PATH=/root/.local/bin:$PATH

# 设置工作目录
WORKDIR /app

# 复制项目文件
COPY server/ /app/server/
COPY textmsa/ /app/textmsa/

# 创建必要的目录
RUN mkdir -p /app/logs /app/data /app/uploads /app/outputs

# 设置权限
RUN chmod +x /app/server/app.py

# 暴露端口（默认 8000，可通过配置文件修改）
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动命令
# app.py 会自动检测项目根目录，所以从 /app 运行即可
CMD ["python", "server/app.py"]

