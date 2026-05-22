FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# 设置工作目录
WORKDIR /app

# 安装 Python 3.10 和系统依赖
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3.10-dev \
    python3-pip \
    gcc \
    g++ \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 创建符号链接（覆盖已有的 pip/python 链接以避免构建失败）
RUN ln -sf /usr/bin/python3.10 /usr/bin/python && \
    ln -sf /usr/bin/pip3 /usr/bin/pip

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
# 安装 PyTorch（CUDA 11.8 版本）
RUN pip install --no-cache-dir torch==2.0.1 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# 安装其他依赖
RUN pip install --no-cache-dir -r requirements.txt

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
CMD ["python", "main.py"]

