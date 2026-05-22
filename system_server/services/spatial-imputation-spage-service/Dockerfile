FROM python:3.10-slim

# 设置非交互式安装
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    gfortran \
    git \
    libopenblas-dev \
    liblapack-dev \
    libssl-dev \
    libffi-dev \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 升级 pip
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# 复制依赖文件
COPY requirements.txt .

# 先安装基础依赖（不包括 SpaGE）
RUN pip install --no-cache-dir \
    fastapi>=0.104.0 \
    uvicorn[standard]>=0.24.0 \
    python-multipart>=0.0.6 \
    anndata>=0.9.0 \
    scanpy>=1.9.0 \
    pandas>=1.5.0 \
    numpy>=1.23.0 \
    scipy>=1.9.0 \
    matplotlib>=3.7.0 \
    seaborn>=0.12.0 \
    scikit-learn>=1.2.0

# 尝试安装 SpaGE
# 方法1: 尝试从 PyPI 安装
# 方法2: 从 GitHub 克隆并手动安装
RUN (pip install --no-cache-dir SpaGE 2>&1 || \
     (echo "从 GitHub 安装 SpaGE..." && \
      cd /tmp && \
      git clone --depth 1 https://github.com/tabdelaal/SpaGE.git spage_repo && \
      cd spage_repo && \
      (python setup.py install 2>&1 || \
       pip install . 2>&1 || \
       (echo "尝试直接复制模块..." && \
        mkdir -p /usr/local/lib/python3.10/site-packages/SpaGE && \
        cp -r SpaGE/* /usr/local/lib/python3.10/site-packages/SpaGE/ 2>&1 || true)) && \
      cd / && rm -rf /tmp/spage_repo || true) || \
     echo "警告: SpaGE 安装失败，服务将使用 KNN 回退实现")

# 验证安装（创建临时 Python 脚本）
RUN echo 'try:\n    import SpaGE\n    print("SpaGE 安装成功")\nexcept ImportError as e:\n    print(f"SpaGE 未安装，将使用 KNN 实现: {e}")' > /tmp/check_spage.py && \
    python /tmp/check_spage.py && \
    rm /tmp/check_spage.py || true

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

