# scDGRN 服务 Docker 部署指南

## 概述

本文档介绍如何使用 Docker 构建、部署和测试 scDGRN 服务。

## 前置要求

1. **Docker** - 已安装 Docker Engine
2. **NVIDIA GPU** (可选) - 如需使用 GPU 加速，需要：
   - NVIDIA GPU 驱动
   - nvidia-container-toolkit

## 快速开始

### 方法 1: 使用自动化脚本（推荐）

```bash
cd /home/common/hwluo/project/system_server/services/scdgrn-service

# 完整流程：构建 -> 运行 -> 测试
bash docker_test.sh
```

### 方法 2: 分步执行

#### 1. 构建 Docker 镜像

```bash
bash docker_build.sh
```

#### 2. 运行容器并测试

```bash
bash docker_run.sh
```

#### 3. 使用 docker-compose

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止
docker-compose down
```

## 手动操作

### 构建镜像

```bash
docker build -t scdgrn-service:latest .
```

### 运行容器

**使用 GPU（推荐）：**
```bash
docker run -d \
  --name scdgrn-service \
  -p 8080:8080 \
  --gpus all \
  -v $(pwd)/outputs:/app/outputs \
  -v $(pwd)/test_data:/app/test_data:ro \
  -e PORT=8080 \
  -e OUTPUT_DIR=/app/outputs \
  scdgrn-service:latest
```

**仅使用 CPU：**
```bash
docker run -d \
  --name scdgrn-service \
  -p 8080:8080 \
  -v $(pwd)/outputs:/app/outputs \
  -v $(pwd)/test_data:/app/test_data:ro \
  -e PORT=8080 \
  -e OUTPUT_DIR=/app/outputs \
  scdgrn-service:latest
```

### 检查服务状态

```bash
# 健康检查
curl http://localhost:8080/health

# 查看容器日志
docker logs -f scdgrn-service

# 查看容器状态
docker ps | grep scdgrn-service
```

### 运行测试

```bash
# 确保服务正在运行
curl http://localhost:8080/health

# 运行测试脚本
python3 test_api.py
```

### 停止和清理

```bash
# 停止容器
docker stop scdgrn-service

# 删除容器
docker rm scdgrn-service

# 删除镜像（可选）
docker rmi scdgrn-service:latest
```

## 文件说明

### Docker 相关文件

- `Dockerfile` - Docker 镜像构建文件
- `docker-compose.yml` - Docker Compose 配置文件
- `.dockerignore` - Docker 构建忽略文件列表
- `docker_build.sh` - 构建脚本
- `docker_run.sh` - 运行和测试脚本
- `docker_test.sh` - 完整测试流程脚本

### 测试文件

- `test_api.py` - API 测试脚本
- `test_data/network_human.h5ad` - 测试数据文件

## 配置说明

### 环境变量

- `PORT` - 服务端口（默认: 8080）
- `OUTPUT_DIR` - 输出目录（默认: /app/outputs）
- `NVIDIA_VISIBLE_DEVICES` - GPU 设备（默认: all）

### 端口映射

- 主机端口 `8080` 映射到容器端口 `8080`

### 数据卷挂载

- `./outputs:/app/outputs` - 输出目录（读写）
- `./test_data:/app/test_data:ro` - 测试数据（只读）

## 服务端点

- **健康检查**: `GET http://localhost:8080/health`
- **GRN 发现**: `POST http://localhost:8080/api/grn-discovery`
- **文件下载**: `GET http://localhost:8080/api/download/{file_id}`

## 故障排除

### 端口被占用

```bash
# 查找占用端口的进程
lsof -ti:8080

# 停止占用端口的进程
lsof -ti:8080 | xargs kill -9
```

### GPU 不可用

如果遇到 GPU 相关错误，可以：
1. 检查 NVIDIA 驱动是否安装
2. 检查 nvidia-container-toolkit 是否安装
3. 使用 CPU 模式运行（移除 `--gpus all` 参数）

### 容器无法启动

```bash
# 查看详细错误信息
docker logs scdgrn-service

# 检查容器状态
docker ps -a | grep scdgrn-service
```

### 测试数据问题

确保测试数据文件存在：
```bash
ls -lh test_data/network_human.h5ad
```

## 性能优化

1. **使用 GPU**: 确保使用 `--gpus all` 参数以启用 GPU 加速
2. **资源限制**: 可以根据需要设置 CPU 和内存限制
3. **数据卷**: 使用数据卷挂载避免数据丢失

## 更新镜像

当代码或依赖更新后：

```bash
# 停止并删除旧容器
docker stop scdgrn-service
docker rm scdgrn-service

# 重新构建镜像
bash docker_build.sh

# 启动新容器
bash docker_run.sh
```

## 注意事项

1. 确保 `outputs` 目录有写权限
2. 测试数据文件需要存在且可读
3. GPU 模式需要 NVIDIA 驱动和 nvidia-container-toolkit
4. 首次构建可能需要较长时间（下载依赖）

## 验证部署

部署成功后，应该看到：

```json
{
    "status": "healthy",
    "output_dir": "/app/outputs",
    "device": "cuda:0",
    "cuda_available": true
}
```

服务地址: `http://localhost:8080`

