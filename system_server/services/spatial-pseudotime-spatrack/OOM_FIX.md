# 容器停止问题诊断和修复

## 问题诊断

### 根本原因
容器 `spatial-pseudotime-spatrack` 在处理大型数据集（112,155 个细胞）时，因**内存不足（OOM - Out of Memory）**被系统强制终止。

### 证据
1. **容器状态**：`"OOMKilled": true`，退出码 137
2. **日志显示**：容器在处理数据时，在计算最优传输矩阵（optimal transport matrix）阶段停止
3. **时间线**：
   - 启动时间：2026-01-29 11:41:17
   - 停止时间：2026-01-29 12:12:56
   - 运行时长：约 31 分钟

### 问题分析
- **数据规模**：112,155 个细胞，63 个基因
- **内存瓶颈**：最优传输矩阵的计算需要 O(n²) 的内存空间，对于 112K 细胞的数据集，需要大量内存
- **原配置问题**：
  - `restart: "no"` - 容器崩溃后不会自动重启
  - 没有内存限制配置，容器可以使用所有可用内存，但系统 OOM killer 会在系统内存不足时杀死容器

## 修复方案

### 1. 添加内存限制
在 `docker-compose.yml` 中添加了内存限制配置：
- `mem_limit: 64g` - 最大内存限制为 64GB
- `mem_reservation: 32g` - 预留内存为 32GB

### 2. 修改重启策略
将 `restart: "no"` 改为 `restart: unless-stopped`，使容器在异常退出时自动重启。

### 3. 增加共享内存
添加 `shm_size: 2gb`，为某些计算提供足够的共享内存空间。

## 使用建议

### 对于不同规模的数据集

1. **小型数据集（< 10K 细胞）**
   - 当前配置（64GB）足够
   
2. **中型数据集（10K - 50K 细胞）**
   - 当前配置（64GB）足够
   
3. **大型数据集（50K - 100K 细胞）**
   - 当前配置（64GB）应该足够，但可能需要监控内存使用
   
4. **超大型数据集（> 100K 细胞）**
   - 建议增加 `mem_limit` 到 128GB 或更高
   - 或者考虑数据预处理，减少细胞数量（例如采样或过滤）

### 如果仍然遇到 OOM

1. **增加内存限制**：
   ```yaml
   mem_limit: 128g
   mem_reservation: 64g
   ```

2. **优化数据处理**：
   - 在计算前对数据进行降维或采样
   - 使用批处理方式计算最优传输矩阵
   - 考虑使用稀疏矩阵存储

3. **检查系统资源**：
   ```bash
   # 检查系统内存使用
   free -h
   
   # 检查容器内存使用
   docker stats spatial-pseudotime-spatrack
   ```

## 重启容器

修复配置后，需要重启容器：

```bash
cd /home/common/hwluo/project/system_server/services/spatial-pseudotime-spatrack
docker-compose down
docker-compose up -d
```

或者如果容器已经停止，直接启动：

```bash
docker-compose up -d
```

## 监控建议

建议在运行大型任务时监控容器资源使用：

```bash
# 实时监控容器资源
docker stats spatial-pseudotime-spatrack

# 查看容器日志
docker logs -f spatial-pseudotime-spatrack
```

## 相关文件

- `docker-compose.yml` - Docker Compose 配置文件（已修复）
- `main.py` - 主程序文件（包含错误处理逻辑）
- `README.md` - 服务文档
