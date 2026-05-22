# 查看 Docker 容器日志指南

## 概述

当服务以 Docker 模式运行时，可以通过多种方式查看容器的日志信息。本文档介绍所有可用的方法。

## 方法一：使用 Docker 命令（推荐用于调试）

### 基本命令

```bash
# 查看容器的最后 100 行日志
docker logs <container_name>

# 查看最后 N 行日志
docker logs --tail 100 <container_name>

# 实时跟踪日志（类似 tail -f）
docker logs -f <container_name>

# 查看最近 30 分钟的日志
docker logs --since 30m <container_name>

# 查看指定时间之后的日志
docker logs --since 2023-12-13T14:00:00 <container_name>

# 查看所有日志
docker logs --tail 0 <container_name>
```

### 查找容器名称

根据你的服务，容器名称通常是服务名称。例如：
- `spatialde` 服务的容器名可能是 `spatialde`
- `single-cell-dge` 服务的容器名可能是 `single-cell-dge`

**查看所有运行中的容器：**
```bash
docker ps
```

**查看所有容器（包括已停止的）：**
```bash
docker ps -a
```

### 实际示例

根据你的日志输出，可以看到以下容器正在运行：
- `single-cell-dge` (端口: 39947)
- `spatialde` (镜像: spatialde:latest)

查看这些容器的日志：

```bash
# 查看 single-cell-dge 的最后 100 行日志
docker logs --tail 100 single-cell-dge

# 实时跟踪 spatialde 的日志
docker logs -f spatialde

# 查看最近 1 小时的日志
docker logs --since 1h spatialde
```

## 方法二：使用 API 端点（推荐用于集成）

### 基本用法

```bash
# 查看服务的最后 100 行日志
curl http://localhost:9000/api/v1/services/<service_name>/logs

# 查看最后 50 行日志
curl "http://localhost:9000/api/v1/services/<service_name>/logs?tail=50"

# 查看最近 30 分钟的日志
curl "http://localhost:9000/api/v1/services/<service_name>/logs?since=30m"

# 查看所有日志（可能很大，谨慎使用）
curl "http://localhost:9000/api/v1/services/<service_name>/logs?tail=0"
```

### 实际示例

```bash
# 查看 spatialde 服务的日志
curl http://localhost:9000/api/v1/services/spatialde/logs

# 查看 single-cell-dge 的最后 200 行日志
curl "http://localhost:9000/api/v1/services/single-cell-dge/logs?tail=200"

# 查看最近 1 小时的日志
curl "http://localhost:9000/api/v1/services/spatialde/logs?since=1h"
```

### API 响应格式

```json
{
  "success": true,
  "service_name": "spatialde",
  "container_name": "spatialde",
  "logs": "2025-12-13 14:53:54,125 - INFO - 服务启动成功\n...",
  "tail": 100,
  "follow": false
}
```

### 使用 Python 客户端

```python
import requests

# 获取服务日志
response = requests.get(
    "http://localhost:9000/api/v1/services/spatialde/logs",
    params={"tail": 100, "since": "30m"}
)

if response.status_code == 200:
    data = response.json()
    if data["success"]:
        print(data["logs"])
    else:
        print(f"错误: {data.get('error')}")
else:
    print(f"请求失败: {response.status_code}")
```

## 方法三：使用 Swagger UI（可视化界面）

1. 打开浏览器访问：http://localhost:9000/docs
2. 找到 `/api/v1/services/{service_name}/logs` 端点
3. 点击 "Try it out"
4. 输入服务名称（如 `spatialde`）
5. 设置参数：
   - `tail`: 日志行数（默认 100）
   - `since`: 时间范围（如 `30m`, `1h`, `2023-12-13T14:00:00`）
6. 点击 "Execute" 查看结果

## 常见场景

### 1. 查看服务启动日志

```bash
# 查看最后 50 行，通常包含启动信息
docker logs --tail 50 <container_name>
```

### 2. 实时监控服务运行

```bash
# 实时跟踪日志输出
docker logs -f <container_name>
```

### 3. 查看错误日志

```bash
# 查看最近 1 小时的日志，过滤错误
docker logs --since 1h <container_name> | grep -i error

# 或者使用 API
curl "http://localhost:9000/api/v1/services/<service_name>/logs?since=1h" | grep -i error
```

### 4. 查看特定时间段的日志

```bash
# 查看今天 14:00 之后的日志
docker logs --since 2025-12-13T14:00:00 <container_name>

# 查看最近 2 小时的日志
docker logs --since 2h <container_name>
```

### 5. 导出日志到文件

```bash
# 导出所有日志
docker logs <container_name> > service.log 2>&1

# 导出最近 1000 行
docker logs --tail 1000 <container_name> > service.log 2>&1

# 导出最近 1 小时的日志
docker logs --since 1h <container_name> > service.log 2>&1
```

## 时间格式说明

`--since` 参数支持以下格式：

- **相对时间**：
  - `30m` - 30 分钟前
  - `1h` - 1 小时前
  - `2h30m` - 2 小时 30 分钟前
  - `1d` - 1 天前

- **绝对时间**：
  - `2025-12-13T14:00:00` - ISO 8601 格式
  - `2025-12-13T14:00:00Z` - UTC 时间
  - `2025-12-13T14:00:00+08:00` - 带时区的时间

## 故障排查

### 问题 1：容器不存在

**错误信息：** `容器 <name> 不存在`

**解决方法：**
```bash
# 检查容器是否存在
docker ps -a | grep <container_name>

# 如果容器不存在，检查服务是否已启动
curl http://localhost:9000/api/v1/services/<service_name>/status
```

### 问题 2：无法连接到 Docker

**错误信息：** `未找到 docker 命令` 或 `Cannot connect to the Docker daemon`

**解决方法：**
```bash
# 检查 Docker 是否运行
docker ps

# 如果失败，启动 Docker 服务
sudo systemctl start docker
```

### 问题 3：日志为空

**可能原因：**
- 容器刚启动，还没有日志输出
- 服务没有输出日志到 stdout/stderr
- 日志被重定向到文件

**解决方法：**
```bash
# 检查容器是否在运行
docker ps | grep <container_name>

# 检查容器内的日志文件（如果服务写入文件）
docker exec <container_name> ls -la /app/logs
docker exec <container_name> cat /app/logs/*.log
```

### 问题 4：日志太多，查看困难

**解决方法：**
```bash
# 只查看最后 50 行
docker logs --tail 50 <container_name>

# 过滤特定关键词
docker logs <container_name> | grep -i error
docker logs <container_name> | grep -i "启动成功"

# 使用 less 分页查看
docker logs <container_name> | less
```

## 最佳实践

1. **定期查看日志**：使用 `--since` 参数查看最近的日志，而不是所有日志
2. **实时监控**：使用 `-f` 参数实时跟踪关键服务的日志
3. **日志导出**：定期导出日志到文件进行备份和分析
4. **错误过滤**：使用 `grep` 过滤错误和警告信息
5. **API 集成**：在监控系统中使用 API 端点定期获取日志

## 相关命令参考

```bash
# 查看容器状态
docker ps

# 查看容器详细信息
docker inspect <container_name>

# 进入容器（调试用）
docker exec -it <container_name> /bin/bash

# 查看容器资源使用情况
docker stats <container_name>

# 停止容器
docker stop <container_name>

# 重启容器
docker restart <container_name>
```

## 总结

- **快速查看**：使用 `docker logs --tail 100 <container_name>`
- **实时监控**：使用 `docker logs -f <container_name>`
- **API 集成**：使用 `GET /api/v1/services/<service_name>/logs`
- **可视化**：使用 Swagger UI (http://localhost:9000/docs)

选择最适合你场景的方法！

