FROM python:3.10-slim

WORKDIR /app

# 基础依赖（与其它服务保持一致，便于复用）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    r-base \
    r-base-dev \
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev \
    && rm -rf /var/lib/apt/lists/*

# 仅安装当前服务的依赖
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 拷贝当前服务代码
COPY . /app

RUN mkdir -p /app/outputs

ENV PORT=8080
ENV OUTPUT_DIR=/app/outputs

EXPOSE 8080

WORKDIR /app

CMD ["python", "main.py"]


