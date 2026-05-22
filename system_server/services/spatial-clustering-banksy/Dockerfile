FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（包括 R 和 rpy2 所需的库）
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    r-base \
    r-base-dev \
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 安装 R 包 mclust（供 banksy 使用）
RUN Rscript -e "install.packages('mclust', repos='https://cloud.r-project.org')"

# 复制应用代码（包括本地的 banksy 目录）
COPY . .

# 创建输出目录
RUN mkdir -p /app/outputs

# 设置环境变量
ENV PORT=8080
ENV OUTPUT_DIR=/app/outputs
ENV PYTHONPATH=/app/banksy/src

# 启动命令
CMD ["python", "main.py"]

