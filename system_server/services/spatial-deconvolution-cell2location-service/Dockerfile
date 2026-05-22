FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
# 先安装 PyTorch (CPU 版本，如果需要 GPU 可以改为 CUDA 版本)
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

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
ENV PYTHONUNBUFFERED=1

# 启动命令
CMD ["python", "main.py"]

