#!/bin/bash

# 批量构建所有服务的Docker镜像
# 用法: ./build_all_services.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICES_DIR="${SERVICES_DIR:-$SCRIPT_DIR/services}"
LOG_FILE="${LOG_FILE:-$SCRIPT_DIR/build_log_$(date +%Y%m%d_%H%M%S).txt}"
ORIGINAL_DIR=$(pwd)

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 统计变量
SUCCESS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

echo "========================================="
echo "开始批量构建Docker镜像"
echo "日志文件: $LOG_FILE"
echo "========================================="
echo ""

# 记录日志函数
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# 构建单个服务
build_service() {
    local service_dir=$1
    local service_name=$(basename "$service_dir")
    local original_pwd=$(pwd)
    
    log "========================================="
    log "构建服务: $service_name"
    log "目录: $service_dir"
    
    if [ ! -f "$service_dir/Dockerfile" ]; then
        log "跳过: 未找到Dockerfile"
        echo -e "${YELLOW}跳过: $service_name (无Dockerfile)${NC}"
        ((SKIP_COUNT++))
        cd "$original_pwd" 2>/dev/null || true
        return 0
    fi
    
    if ! cd "$service_dir" 2>/dev/null; then
        log "错误: 无法进入目录 $service_dir"
        echo -e "${RED}错误: $service_name (无法进入目录)${NC}"
        ((FAIL_COUNT++))
        cd "$original_pwd" 2>/dev/null || true
        return 0
    fi
    
    # 构建镜像，镜像名格式: service-name:latest
    local image_name="${service_name}:latest"
    
    log "开始构建镜像: $image_name"
    echo -e "${YELLOW}构建中: $service_name...${NC}"
    
    if docker build -t "$image_name" . >> "$LOG_FILE" 2>&1; then
        log "成功: $service_name 构建完成"
        echo -e "${GREEN}✓ 成功: $service_name${NC}"
        ((SUCCESS_COUNT++))
    else
        log "失败: $service_name 构建失败"
        echo -e "${RED}✗ 失败: $service_name${NC}"
        ((FAIL_COUNT++))
    fi
    
    # 确保返回到原始目录
    cd "$original_pwd" 2>/dev/null || cd "$SERVICES_DIR" 2>/dev/null || true
    return 0
}

# 主循环：遍历所有服务目录
if ! cd "$SERVICES_DIR" 2>/dev/null; then
    echo "错误: 无法进入服务目录 $SERVICES_DIR"
    exit 1
fi

for service_dir in */; do
    service_path="$SERVICES_DIR/$service_dir"
    if [ -d "$service_path" ]; then
        build_service "$service_path"
        echo ""
    fi
done

# 返回到原始目录
cd "$ORIGINAL_DIR" 2>/dev/null || true

# 输出统计信息
echo ""
echo "========================================="
echo "构建完成统计"
echo "========================================="
echo -e "${GREEN}成功: $SUCCESS_COUNT${NC}"
echo -e "${RED}失败: $FAIL_COUNT${NC}"
echo -e "${YELLOW}跳过: $SKIP_COUNT${NC}"
echo ""
echo "详细日志请查看: $LOG_FILE"
echo "========================================="

# 如果有失败的构建，返回非零退出码
if [ $FAIL_COUNT -gt 0 ]; then
    exit 1
fi

exit 0
