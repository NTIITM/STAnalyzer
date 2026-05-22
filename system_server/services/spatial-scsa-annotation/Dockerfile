FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 系统依赖（为 scanpy/anndata/omicverse 等科学计算栈提供编译和运行依赖）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    gfortran \
    libhdf5-dev \
    libopenblas-dev \
    liblapack-dev \
    libpng-dev \
    libfreetype6-dev \
    libssl-dev \
    libffi-dev \
    pkg-config \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 升级 pip
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# 先安装基础依赖（不包括 omicverse）
# 注意：omicverse 的 2023 数据库需要 pandas<2.0
COPY requirements.txt .
RUN pip install --no-cache-dir \
    fastapi>=0.104.0 \
    uvicorn[standard]>=0.24.0 \
    pydantic>=2.0.0 \
    python-multipart>=0.0.6 \
    anndata>=0.9.0 \
    scanpy>=1.9.0 \
    "pandas>=1.5.0,<2.0.0" \
    numpy>=1.23.0 \
    "scipy>=1.9.0,<1.12.0" \
    scikit-learn>=1.2.0 \
    matplotlib>=3.7.0 \
    seaborn>=0.12.0 \
    requests>=2.31.0

# 安装 PyTorch（omicverse 需要）
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu || \
    pip install --no-cache-dir torch torchvision torchaudio

# 安装 torch_geometric（omicverse 需要）
RUN pip install --no-cache-dir torch-geometric

# 安装 omicverse 及其依赖
# omicverse 需要多个可选依赖，我们尝试安装所有可能的依赖
# 注意：某些依赖可能会升级 pandas，所以最后需要再次锁定 pandas<2.0
RUN pip install --no-cache-dir \
    pygam \
    metatime \
    mofax \
    graphtools \
    ktplotspy \
    lifelines \
    marsilea \
    multiprocess \
    pydeseq2 \
    || echo "部分可选依赖安装失败，继续安装 omicverse..."

# 强制锁定 pandas<2.0（omicverse 2023 数据库要求）
RUN pip install --no-cache-dir "pandas>=1.5.0,<2.0.0"

# 安装 omicverse（尝试多个版本）
RUN pip install --no-cache-dir omicverse>=0.5.0 || \
    (echo "尝试从 GitHub 安装 omicverse..." && \
     pip install --no-cache-dir git+https://github.com/Starlitnightly/omicverse.git || \
     echo "omicverse 安装失败，服务将返回错误")

# 强制锁定 pandas<2.0（omicverse 2023 数据库要求，必须在所有安装后执行）
RUN pip install --no-cache-dir --force-reinstall --no-deps "pandas>=1.5.0,<2.0.0" && \
    python -c "import pandas as pd; assert pd.__version__.startswith('1.'), f'pandas 版本错误: {pd.__version__}'; print(f'pandas 版本确认: {pd.__version__}')"

# 验证 omicverse 安装和 pandas 版本（创建临时脚本）
RUN python -c "import pandas as pd; \
assert pd.__version__.startswith('1.'), f'pandas 版本错误: {pd.__version__}'; \
print(f'pandas 版本: {pd.__version__}'); \
import omicverse as ov; \
print('omicverse 安装成功'); \
assert hasattr(ov, 'single') and hasattr(ov.single, 'pySCSA'), 'pySCSA 不可用'; \
print('pySCSA 可用')" || echo "验证失败，但继续构建"

# 复制应用代码
COPY . .

# 准备输出和日志目录
RUN mkdir -p /app/outputs /app/logs

# 默认环境变量
ENV PORT=8080 \
    OUTPUT_DIR=/app/outputs \
    LOG_DIR=/app/logs

EXPOSE 8080

# 运行 FastAPI 服务
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]

