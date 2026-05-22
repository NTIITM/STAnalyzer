# 性能比较测试总结

## 测试配置

- **测试数据**: `/home/common/hwluo/project/Data/ST/151507_hvg.h5ad`
- **数据维度**: 4226 spots × 2000 genes
- **Cluster 列**: `layer` (8 个 cluster)
- **测试时间**: 2026-01-04

## 测试结果

### Marker-Gene 服务 ✅

**状态**: 成功运行

**性能指标**:
- **处理时间**: 11.21 秒 (0.19 分钟)
- **识别细胞类型数**: 3 种
- **细胞类型分布**:
  - Mature astrocyte: 1893 spots (44.8%)
  - Myelinating schwann cell: 1520 spots (36.0%)
  - Fibrous astrocyte: 813 spots (19.2%)
- **Unknown 比例**: 0%
- **置信度统计**:
  - 平均置信度: 0.081
  - 中位数: 0.057
  - 标准差: 0.094
  - 范围: [0.000, 0.568]

**输出文件**:
- annotated_data.h5ad
- cluster_annotation_statistics.csv
- annotation_confidence.csv
- statistics.txt
- 多个可视化图表 (UMAP, spatial, composition, dotplot)

### SCSA 服务 ❌

**状态**: 服务不可用

**问题**: omicverse 依赖缺失导致服务返回 503 错误

**错误信息**: `503 Server Error: Service Unavailable - omicverse 未安装，SCSA 方法不可用`

**原因分析**:
- omicverse 包已安装，但缺少多个依赖包
- 主要缺失依赖: pygam, metatime, mofax, graphtools, ktplotspy, lifelines, marsilea, multiprocess, pydeseq2 等
- scipy 版本不兼容 (需要 <1.12, 当前 1.15.3)

## 性能比较（部分）

由于 SCSA 服务无法运行，目前只能提供 Marker-Gene 服务的性能数据：

| 指标 | Marker-Gene 方法 |
|------|------------------|
| 处理时间 | 11.21 秒 |
| 识别细胞类型数 | 3 |
| Unknown 比例 | 0% |
| 平均置信度 | 0.081 |

## 下一步建议

### 1. 修复 SCSA 服务依赖

**选项 A**: 安装所有 omicverse 依赖
```bash
pip install pygam metatime mofax graphtools ktplotspy lifelines marsilea multiprocess pydeseq2
pip install "scipy<1.12,>=1.8"  # 降级 scipy
```

**选项 B**: 使用 conda 环境安装 omicverse
```bash
conda create -n scsa python=3.10
conda activate scsa
conda install -c conda-forge omicverse
```

**选项 C**: 修改代码，使 omicverse 为可选依赖，提供更友好的错误提示

### 2. 完成完整性能比较

修复 SCSA 服务后，重新运行性能比较脚本：
```bash
cd /home/common/hwluo/project/system_server/services/spatial-scsa-annotation
python3 benchmark_comparison.py
```

### 3. 性能指标对比

修复后，将比较以下指标：
- **处理时间**: SCSA vs Marker-Gene
- **识别细胞类型数**: 两种方法识别的类型数量和分布
- **标注质量**: Unknown 比例、置信度/Z-score 分布
- **一致性**: 两种方法标注结果的一致性

## 当前测试脚本

性能比较脚本已创建并可用：
- **位置**: `benchmark_comparison.py`
- **功能**: 
  - 检查两个服务的健康状态
  - 使用相同测试数据运行两种标注方法
  - 下载和分析结果
  - 生成性能比较报告（JSON 和文本格式）

## 文件位置

- **测试脚本**: `system_server/services/spatial-scsa-annotation/benchmark_comparison.py`
- **测试结果**: `system_server/services/spatial-scsa-annotation/benchmark_results/`
- **比较报告**: `benchmark_results/{timestamp}/benchmark_report_{timestamp}.txt`
- **JSON 数据**: `benchmark_results/{timestamp}/benchmark_comparison_{timestamp}.json`

