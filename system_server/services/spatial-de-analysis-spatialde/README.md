# SpatialDE 空间差异表达分析服务

基于 [SpatialDE](https://github.com/Teichlab/SpatialDE) 实现的空间差异表达分析服务，用于识别在空间上具有显著差异表达的基因。

## 功能特性

- 使用高斯过程模型检测空间差异表达基因
- 支持数据标准化和 log 变换
- 支持高变基因筛选
- 生成详细的统计报告
- 提供可视化图表（火山图、空间表达图）
- 完整的错误处理和错误信息返回

## 安装

### 使用 Docker

```bash
cd spatial-de-analysis-spatialde
docker-compose up --build
```

### 本地运行

```bash
pip install -r requirements.txt
python main.py
```

## API 使用

### 分析接口

**POST** `/api/analyze`

**参数：**
- `file`: 上传的空间转录组数据文件（h5ad 格式）
- `file_type`: 文件类型（auto, h5ad, 10x_h5, csv, tsv），默认 "auto"
- `normalize`: 是否标准化数据，默认 true
- `use_highly_variable`: 是否使用高变基因，默认 true
- `min_counts`: 基因最小总计数，默认 1
- `min_cells`: 基因必须在至少多少个细胞中表达，默认 10

**返回：**
```json
{
  "success": true,
  "message": "SpatialDE 空间差异表达分析完成",
  "data": {
    "spatial_de_results.csv": "结果文件ID",
    "spatial_de_data.h5ad": "数据文件ID",
    "statistics.txt": "统计报告ID",
    "volcano_plot.png": "火山图ID",
    "top_genes_spatial.png": "空间表达图ID"
  }
}
```

### 下载接口

**GET** `/api/download/{file_id}`

下载分析结果文件。

### 健康检查

**GET** `/health`

检查服务状态。

## 输出文件说明

1. **spatial_de_results.csv**: SpatialDE 分析结果，包含以下列：
   - `g`: 基因名
   - `l`: 最优长度尺度参数
   - `LLR`: 对数似然比
   - `pval`: p 值
   - `qval`: FDR 校正后的 p 值
   - `FSV`: 空间方差分数
   - `BIC`: 贝叶斯信息准则

2. **spatial_de_data.h5ad**: 处理后的 AnnData 对象，包含：
   - `uns['spatialde_results']`: SpatialDE 分析结果
   - `var['spatialde_analyzed']`: 标记哪些基因被分析

3. **statistics.txt**: 详细的统计报告，包括：
   - 分析参数
   - 数据统计
   - 结果摘要
   - Top 10 显著基因

4. **volcano_plot.png**: 火山图，显示 FSV vs -log10(q-value)

5. **top_genes_spatial.png**: Top 5 显著基因的空间表达图

## 错误处理

服务会返回详细的错误信息，包括：
- 数据格式错误（400）
- 依赖包缺失（500）
- 分析失败（500，包含错误堆栈）

## 参考

- [SpatialDE GitHub](https://github.com/Teichlab/SpatialDE)
- [SpatialDE 论文](https://www.nature.com/articles/nmeth.4636)

