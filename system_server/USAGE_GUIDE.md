# System Server 使用指南

## 项目概述

`system_server` 是一个系统服务管理和 API 服务器，支持：
- **自动扫描** `services/` 目录下的所有服务
- **自动查找** Docker 镜像（从 `docker-compose.yml` 中提取）
- **自动分配** 可用端口（避免端口冲突）
- **一键启动** 所有服务（支持进程模式和 Docker 模式）

## 核心功能

### 1. 服务发现
- 自动扫描 `services/` 目录下所有包含 `main.py` 的子目录
- 解析每个服务的 `service_config.json` 配置文件
- 提取服务名称、描述、端口等信息

### 2. 镜像查找
- 从服务的 `docker-compose.yml` 文件中提取镜像名称
- 检查镜像是否已存在于本地 Docker 环境
- 如果镜像存在，直接使用；如果不存在，使用 Docker Compose 构建

### 3. 端口分配
- 自动为每个服务分配可用端口（从 50000 开始查找）
- 避免端口冲突
- 自动更新 `service_config.json` 中的端口和 `baseurl`

### 4. 服务启动
- **进程模式**：直接运行服务的 `main.py`
- **Docker 模式**：使用 Docker Compose 或 `docker run` 启动容器

## 快速开始

### 前置要求

1. **Python 环境**
   ```bash
   # 确保已安装 Python 3.8+
   python --version
   ```

2. **依赖安装**
   ```bash
   cd /home/common/hwluo/project/system_server
   pip install -r requirements.txt
   # 或使用开发模式安装
   pip install -e .
   ```

3. **Docker（可选，仅 Docker 模式需要）**
   ```bash
   docker --version
   docker compose version  # 或 docker-compose --version
   ```

### 基本使用

#### 方式一：使用启动脚本（推荐）

```bash
cd /home/common/hwluo/project/system_server
bash start_server.sh
```

这个脚本会：
1. 激活 conda 环境 `STppMCP`
2. 启动 system_server API 服务器（端口 9000）
3. 自动扫描并启动所有服务

#### 方式二：直接使用 uvicorn

```bash
cd /home/common/hwluo/project/system_server
conda activate STppMCP  # 或使用其他 Python 环境
uvicorn system_server.main:app --host 0.0.0.0 --port 9000
```

#### 方式三：使用 Python 模块

```bash
cd /home/common/hwluo/project/system_server
python -m system_server.main
```

## 配置说明

### 环境变量配置

创建 `.env` 文件（可选，用于自定义配置）：

```bash
# API 服务器配置
API_HOST=0.0.0.0
API_PORT=9000

# 服务目录
SERVICES_DIR=services

# 服务运行模式：process（进程模式）或 docker（Docker 模式）
SERVICE_RUN_MODE=process

# 自动启动配置
AUTO_START_SERVICES=true          # 启动 API 时是否自动扫描/启动服务
AUTO_START_BACKGROUND=true        # 服务是否以后台进程方式启动

# Docker 模式配置（仅当 SERVICE_RUN_MODE=docker 时生效）
DOCKER_BUILD_ON_START=false       # 启动时是否构建镜像
DOCKER_DETACH=true                # 是否在后台运行容器
DOCKER_INCLUDE_SERVER=false       # 是否同时启动 API Server 容器

# 日志配置
LOG_LEVEL=INFO
```

### 服务配置

每个服务目录需要包含：

1. **`main.py`**：服务入口文件（必需）
2. **`service_config.json`**：服务配置文件（推荐）
   ```json
   {
     "name": "服务名称",
     "description": "服务描述",
     "port": 8080,
     "baseurl": "http://localhost:8080",
     "accepted_files": {...},
     "output_config": {...}
   }
   ```
3. **`docker-compose.yml`**：Docker Compose 配置（Docker 模式需要）
4. **`Dockerfile`**：Docker 镜像构建文件（Docker 模式需要）

## 运行模式详解

### 进程模式（默认）

**特点：**
- 直接运行服务的 `main.py` 文件
- 使用系统 Python 或指定的 conda 环境
- 适合开发和调试

**启动流程：**
1. 扫描 `services/` 目录
2. 为每个服务分配端口
3. 使用 `python main.py` 启动服务（设置 `PORT` 环境变量）

**示例：**
```bash
# 设置运行模式为进程模式
export SERVICE_RUN_MODE=process
uvicorn system_server.main:app --host 0.0.0.0 --port 9000
```

### Docker 模式

**特点：**
- 使用 Docker 容器运行服务
- 自动检查镜像是否存在
- 支持 Docker Compose 和 `docker run`

**启动流程：**
1. 扫描 `services/` 目录
2. 从 `docker-compose.yml` 提取镜像名称
3. 检查镜像是否存在：
   - **存在**：使用 `docker run` 直接启动容器
   - **不存在**：使用 `docker compose up` 构建并启动
4. 为每个服务分配端口并映射到容器

**示例：**
```bash
# 设置运行模式为 Docker 模式
export SERVICE_RUN_MODE=docker
export DOCKER_BUILD_ON_START=true  # 如果镜像不存在，自动构建
uvicorn system_server.main:app --host 0.0.0.0 --port 9000
```

## API 使用

启动 system_server 后，可以通过 REST API 管理服务：

### 健康检查
```bash
curl http://localhost:9000/health
```

### 查看所有服务
```bash
curl http://localhost:9000/api/v1/services | jq
```

### 启动单个服务
```bash
curl -X POST http://localhost:9000/api/v1/services/<service_id>/start
```

### 停止单个服务
```bash
curl -X POST http://localhost:9000/api/v1/services/<service_id>/stop
```

### 查看服务状态
```bash
curl http://localhost:9000/api/v1/services/<service_id>/status | jq
```

### 查看容器日志（Docker 模式）
```bash
# 查看最后 100 行日志
curl http://localhost:9000/api/v1/services/<service_id>/logs

# 查看最后 50 行日志
curl "http://localhost:9000/api/v1/services/<service_id>/logs?tail=50"

# 查看最近 30 分钟的日志
curl "http://localhost:9000/api/v1/services/<service_id>/logs?since=30m"
```

**或者直接使用 Docker 命令：**
```bash
# 查看容器日志
docker logs <container_name>

# 实时跟踪日志
docker logs -f <container_name>

# 查看最后 100 行
docker logs --tail 100 <container_name>
```

详细说明请参考 [VIEW_CONTAINER_LOGS.md](VIEW_CONTAINER_LOGS.md)

### API 文档
- Swagger UI: http://localhost:9000/docs
- ReDoc: http://localhost:9000/redoc

## 工作流程

### 启动时的自动流程

1. **服务扫描**
   - 扫描 `services/` 目录
   - 发现所有包含 `main.py` 的子目录
   - 解析 `service_config.json` 配置

2. **配置生成**
   - 生成/更新 `services_config.json`（汇总所有服务配置）
   - 为每个服务分配可用端口
   - 更新服务的 `service_config.json` 中的端口信息

3. **服务启动**
   - 根据 `SERVICE_RUN_MODE` 选择启动方式：
     - `process`：使用 `start_all_services()` 启动进程
     - `docker`：使用 `start_all_services_docker()` 启动容器

### 端口分配机制

1. 从端口 50000 开始查找可用端口
2. 检查端口是否被占用（使用 `socket` 模块）
3. 如果端口已分配过，复用之前的端口
4. 更新 `service_config.json` 和 `services_config.json`

### 镜像查找机制

1. 读取服务的 `docker-compose.yml` 文件
2. 提取 `services.<service_name>.image` 或 `services.<service_name>.build` 信息
3. 使用 `docker images -q <image_name>` 检查镜像是否存在
4. 根据结果选择启动方式：
   - 镜像存在 → `docker run`
   - 镜像不存在 → `docker compose up --build`

## 常见问题

### 1. 端口冲突

**问题**：服务启动失败，提示端口被占用

**解决**：
```bash
# 查看端口占用
lsof -i :9000

# 修改 API 端口
export API_PORT=9100
uvicorn system_server.main:app --host 0.0.0.0 --port 9100
```

### 2. 服务未自动启动

**检查项**：
- 确认 `AUTO_START_SERVICES=true`
- 确认服务目录包含 `main.py`
- 查看日志：`tail -f system_server.log`

### 3. Docker 模式问题

**检查项**：
- 确认 Docker 已安装：`docker --version`
- 确认 Docker Compose 可用：`docker compose version`
- 确认服务目录包含 `docker-compose.yml`
- 查看 Docker 日志：`docker logs <container_name>`

### 4. 镜像不存在

**解决**：
```bash
# 方式一：设置自动构建
export DOCKER_BUILD_ON_START=true
export SERVICE_RUN_MODE=docker

# 方式二：手动构建镜像
cd services/<service_name>
docker compose build
```

## 目录结构

```
system_server/
├── services/                    # 服务目录
│   ├── gene-enrichment-analysis/
│   │   ├── main.py             # 服务入口（必需）
│   │   ├── service_config.json # 服务配置（推荐）
│   │   ├── docker-compose.yml  # Docker 配置（Docker 模式需要）
│   │   └── Dockerfile          # Docker 镜像定义（Docker 模式需要）
│   └── ...
├── system_server/               # 核心代码
│   ├── main.py                 # FastAPI 应用入口
│   ├── service_manager.py     # 服务管理器（核心逻辑）
│   ├── service_scanner.py     # 服务扫描器
│   ├── config.py              # 配置管理
│   └── ...
├── services_config.json        # 所有服务的汇总配置（自动生成）
├── start_server.sh             # 启动脚本
├── requirements.txt            # Python 依赖
└── README.md                   # 项目说明
```

## 高级用法

### 仅扫描服务，不启动

```python
from system_server.service_manager import ServiceManager

manager = ServiceManager()
manager.process_all_services(generate_docker=False)
# 服务已扫描并配置，但未启动
```

### 手动启动特定服务

```python
from system_server.service_manager import ServiceManager

manager = ServiceManager()
manager.process_all_services(generate_docker=False)

# 启动单个服务（进程模式）
manager.start_service("gene-enrichment-analysis", background=True)

# 启动单个服务（Docker 模式）
manager.start_service_docker("gene-enrichment-analysis", build=False, detach=True)
```

### 查看端口映射

```python
from system_server.service_manager import ServiceManager

manager = ServiceManager()
manager.process_all_services(generate_docker=False)
port_mapping = manager.get_port_mapping()
print(port_mapping)  # {51023: ['gene-enrichment-analysis'], ...}
```

## 总结

`system_server` 提供了完整的服务管理解决方案：

1. **自动化**：自动扫描、配置、启动所有服务
2. **灵活性**：支持进程模式和 Docker 模式
3. **智能端口分配**：避免端口冲突，自动分配可用端口
4. **镜像管理**：自动查找镜像，支持构建和运行
5. **REST API**：提供完整的服务管理 API

通过简单的配置和启动命令，即可管理整个服务生态系统。

