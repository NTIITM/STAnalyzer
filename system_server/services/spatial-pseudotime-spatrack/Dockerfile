FROM python:3.10-slim

# 设置非交互式安装
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# 升级 pip、setuptools、wheel
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# 复制依赖文件
COPY requirements.txt .

# 先安装 spaTrack（让它决定依赖版本，避免后续冲突）
RUN pip install --no-cache-dir git+https://github.com/ZJUFanLab/spaTrack.git || \
    pip install --no-cache-dir spaTrack || \
    echo "Note: spaTrack may need manual installation"

# 安装其他依赖（使用宽松的版本约束，避免与 spaTrack 冲突）
RUN pip install --no-cache-dir \
    fastapi>=0.104.0 \
    uvicorn[standard]>=0.24.0 \
    python-multipart>=0.0.6 \
    pot>=0.9.0 \
    scvelo>=0.3.0 \
    seaborn>=0.12.0

# 复制应用代码
COPY . .

# 创建输出目录
RUN mkdir -p /app/outputs

# 暴露端口
EXPOSE 8080

# 设置环境变量
ENV PORT=8080
ENV OUTPUT_DIR=/app/outputs

# 启动命令
CMD ["python3", "main.py"]


