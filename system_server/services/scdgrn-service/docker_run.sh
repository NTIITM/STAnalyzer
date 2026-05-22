#!/bin/bash
# Docker 运行和测试脚本

set -e

cd "$(dirname "$0")"

echo "=========================================="
echo "scDGRN 服务 Docker 部署和测试"
echo "=========================================="
echo ""

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "✗ Docker 未安装，请先安装 Docker"
    exit 1
fi

# 检查镜像是否存在
IMAGE_NAME="scdgrn-service:latest"
if ! docker images | grep -q "scdgrn-service"; then
    echo "⚠ 镜像不存在，正在构建..."
    bash docker_build.sh
    echo ""
fi

# 停止并删除旧容器（如果存在）
if docker ps -a | grep -q "scdgrn-service"; then
    echo "停止并删除旧容器..."
    docker stop scdgrn-service 2>/dev/null || true
    docker rm scdgrn-service 2>/dev/null || true
    echo ""
fi

# 检查是否有 GPU
GPU_FLAG=""
if command -v nvidia-smi &> /dev/null; then
    GPU_FLAG="--gpus all"
    echo "✓ 使用 GPU 模式"
else
    echo "⚠ 使用 CPU 模式（性能较慢）"
fi
echo ""

# 启动容器
echo "启动 Docker 容器..."
docker run -d \
    --name scdgrn-service \
    -p 8080:8080 \
    ${GPU_FLAG} \
    -v "$(pwd)/outputs:/app/outputs" \
    -v "$(pwd)/test_data:/app/test_data:ro" \
    -e PORT=8080 \
    -e OUTPUT_DIR=/app/outputs \
    ${IMAGE_NAME}

if [ $? -ne 0 ]; then
    echo "✗ 容器启动失败"
    exit 1
fi

echo "✓ 容器已启动"
echo ""

# 等待服务启动
echo "等待服务启动..."
for i in {1..30}; do
    if curl -s http://localhost:8080/health > /dev/null 2>&1; then
        echo "✓ 服务已就绪"
        break
    fi
    sleep 1
    echo -n "."
done
echo ""

# 检查服务健康状态
echo "检查服务健康状态..."
HEALTH_RESPONSE=$(curl -s http://localhost:8080/health)
if [ $? -eq 0 ]; then
    echo "$HEALTH_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$HEALTH_RESPONSE"
    echo ""
else
    echo "✗ 服务健康检查失败"
    echo "查看容器日志："
    echo "  docker logs scdgrn-service"
    exit 1
fi

# 运行测试
echo "=========================================="
echo "运行 API 测试"
echo "=========================================="
echo ""

if [ -f "test_api.py" ]; then
    python3 test_api.py
    TEST_RESULT=$?
    echo ""
    
    if [ $TEST_RESULT -eq 0 ]; then
        echo "=========================================="
        echo "✓ 所有测试通过！"
        echo "=========================================="
    else
        echo "=========================================="
        echo "✗ 部分测试失败"
        echo "=========================================="
    fi
else
    echo "⚠ 测试脚本不存在: test_api.py"
fi

echo ""
echo "=========================================="
echo "服务信息"
echo "=========================================="
echo "容器名称: scdgrn-service"
echo "服务地址: http://localhost:8080"
echo "健康检查: http://localhost:8080/health"
echo ""
echo "常用命令："
echo "  查看日志: docker logs -f scdgrn-service"
echo "  停止服务: docker stop scdgrn-service"
echo "  启动服务: docker start scdgrn-service"
echo "  删除容器: docker rm -f scdgrn-service"
echo ""

