# Spatial Pseudotime (SpaTrack) Service

基于 SpaTrack 的空间转录组轨迹推断服务。使用最优传输理论（Optimal Transport）结合基因表达和空间信息来推断细胞动态轨迹。

## 功能特点

- **空间感知的轨迹推断**：直接利用空间坐标信息，与 Monocle 不同，SpaTrack 专门为空间转录组数据设计
- **基于最优传输理论**：使用 OT 理论计算细胞间的转移概率
- **自动识别轨迹起点**：基于信息熵方法自动识别起始集群
- **速度矢量场**：计算并可视化细胞状态变化的方向和速度
- **流线图可视化**：直观展示细胞轨迹的流向

## 参考教程

本服务基于以下教程实现：
- [探索细胞轨迹：SpaTrack如何利用最优传输理论解析细胞动态](https://cloud.tencent.com/developer/article/2518546)

## 安装和运行

### 使用 Docker Compose

```bash
cd system_server/services/spatial-pseudotime-spatrack
docker-compose up --build
```

服务将在 `http://localhost:44988` 启动。

### API 端点

#### 健康检查
```bash
GET /health
```

#### 轨迹推断
```bash
POST /api/spatrack-pseudotime
```

**参数**：
- `file`: 上传的 AnnData 文件（h5ad格式，必须包含空间坐标）
- `file_type`: 文件类型（auto/h5ad/10x_h5/csv/tsv），默认 "auto"
- `cluster_key`: 聚类列名（如 "leiden", "louvain"），用于识别轨迹起点，默认 "leiden"
- `n_neigh_pos`: 计算速度场时的空间邻居数量，默认 50
- `entropy_method`: 熵计算方法（auto/shannon/renyi），默认 "auto"
- `start_cluster`: 手动指定起始集群（如果为 null，则自动基于熵选择）

**响应**：
```json
{
  "success": true,
  "message": "SpaTrack pseudotime analysis completed successfully",
  "result_id": "xxx.h5ad",
  "outputs": {
    "h5ad": "xxx.h5ad",
    "report": "xxx.txt",
    "spatial_pseudotime": "xxx.png",
    "streamplot": "xxx.png",
    "pseudotime_distribution": "xxx.png"
  },
  "pseudotime_stats": {
    "min": 0.0,
    "max": 1.0,
    "mean": 0.5,
    "median": 0.5,
    "std": 0.2
  }
}
```

#### 下载文件
```bash
GET /api/download/{file_id}
```

## 输入要求

### 必需
- **空间坐标**：数据必须包含空间坐标，存储在 `adata.obsm['spatial']` 或 `adata.obsm['X_spatial']` 中
- **表达矩阵**：标准的 AnnData 格式，基因在行，细胞在列

### 可选
- **聚类信息**：如果提供 `cluster_key`，将使用熵方法自动识别轨迹起点
- **原始计数**：建议在 `adata.layers['counts']` 中保存原始计数

## 输出说明

1. **h5ad 文件**：包含伪时间结果
   - `adata.obs['spatrack_pseudotime']`: 伪时间值
   - `adata.uns['E_grid']`, `adata.uns['V_grid']`: 速度矢量场（如果计算成功）

2. **空间伪时间图**：在空间坐标上展示伪时间值

3. **流线图**：展示速度矢量场和细胞轨迹流向（如果速度场可用）

4. **伪时间分布图**：伪时间的直方图和按聚类的箱线图

5. **文本报告**：包含参数、统计信息和解释说明

## 与 Monocle 服务的对比

| 特性 | SpaTrack | Monocle |
|------|----------|---------|
| 空间信息利用 | ✅ 直接使用空间坐标 | ❌ 仅基于表达矩阵 |
| 理论基础 | 最优传输理论 | DDRTree 降维 |
| 轨迹起点识别 | 基于信息熵 | 自动或手动指定 |
| 速度场计算 | ✅ 支持 | ❌ 不支持 |
| 流线图 | ✅ 支持 | ❌ 不支持 |
| 适用场景 | 空间转录组数据 | 单细胞/空间数据 |

## 注意事项

1. **空间坐标必需**：SpaTrack 需要空间坐标信息，如果数据中没有空间坐标，服务会报错
2. **内存使用**：对于大型数据集，最优传输矩阵的计算可能占用较多内存
3. **速度场计算**：速度场计算是可选的，如果失败不会影响伪时间计算
4. **聚类信息**：虽然聚类信息是可选的，但提供聚类信息可以更好地识别轨迹起点

## 故障排除

### 错误：spaTrack package is not available
- **原因**：spaTrack 包未安装
- **解决**：检查 Dockerfile 中的安装步骤，或手动安装：`pip install spaTrack`

### 错误：Spatial coordinates not found
- **原因**：输入数据缺少空间坐标
- **解决**：确保数据包含 `adata.obsm['spatial']` 或 `adata.obsm['X_spatial']`

### 错误：内存不足
- **原因**：数据量过大
- **解决**：减少基因数量（筛选高变基因）或减少细胞数量

## 开发

### 本地开发（不使用 Docker）

```bash
pip install -r requirements.txt
python main.py
```

### 测试

```bash
# 使用 curl 测试
curl -X POST "http://localhost:44988/api/spatrack-pseudotime" \
  -F "file=@your_data.h5ad" \
  -F "cluster_key=leiden" \
  -F "n_neigh_pos=50"
```

## 许可证

与项目主许可证一致。




