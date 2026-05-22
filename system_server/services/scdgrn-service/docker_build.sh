#!/bin/bash
# Docker 构建脚本

set -e

cd "$(dirname "$0")"

echo "=========================================="
echo "构建 scDGRN 服务 Docker 镜像"
echo "=========================================="
echo ""

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "✗ Docker 未安装，请先安装 Docker"
    exit 1
fi

# 检查是否有 NVIDIA GPU（可选）
if command -v nvidia-smi &> /dev/null; then
    echo "✓ 检测到 NVIDIA GPU"
    nvidia-smi --query-gpu=name --format=csv,noheader | head -1
    echo ""
else
    echo "⚠ 未检测到 NVIDIA GPU，将使用 CPU 模式"
    echo ""
fi

# 构建镜像
echo "开始构建 Docker 镜像..."
echo ""

IMAGE_NAME="scdgrn-service"
IMAGE_TAG="latest"

docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✓ Docker 镜像构建成功！"
    echo "=========================================="
    echo ""
    echo "镜像名称: ${IMAGE_NAME}:${IMAGE_TAG}"
    echo ""
    echo "运行以下命令启动服务："
    echo "  docker-compose up -d"
    echo "  或"
    echo "  docker run -d -p 8080:8080 --gpus all ${IMAGE_NAME}:${IMAGE_TAG}"
    echo ""
else
    echo ""
    echo "✗ Docker 镜像构建失败"
    exit 1
fi

