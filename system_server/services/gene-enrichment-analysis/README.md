# 通用基因富集分析服务

## 服务概述

通用基因富集分析服务是一个整合了原 `single-cell-enrichment` 和 `spatial-enrichment` 两个服务的统一富集分析服务。该服务支持单细胞、空间转录组、差异基因列表等多种输入类型，提供全面的富集分析功能和丰富的可视化结果。

## 主要特性

### 1. 多数据类型支持
- 单细胞转录组数据的差异基因列表
- 空间转录组数据的差异基因列表
- 任意基因列表（CSV/TSV格式）

### 2. 丰富的富集分析功能
- 支持多种富集库（GO、KEGG等）
- 支持多种物种（Human、Mouse等）
- 支持Enrichr和KEGG两种引擎

### 3. 全面的统计指标
- 总富集项数、显著富集项数
- P值分布统计（最小值、最大值、平均值、中位数）
- 调整后P值分布统计
- Combined Score分布统计
- 重叠基因数统计
- 每个通路的基因数分布统计
- Odds Ratio分布统计

### 4. 多种可视化图表
- **Top富集项柱状图**：展示前20个最显著富集项的-Log10 P值
- **富集散点图**：展示Combined Score与-Log10 P值的关系
- **基因比例图**：展示每个富集项的重叠基因数与总基因数的比例
- **P值分布直方图**：展示所有通路的P值分布特征
- **富集分析Volcano图**：展示通路的显著性与效应量的关系

## API接口

### 富集分析接口

**POST** `/api/enrich`

**参数**：
- `file`: 包含 'gene' 列的 CSV/TSV 基因列表文件（必需）
- `sep`: 分隔符（',' 或 '\t'，默认：','）
- `library`: 富集库名称（默认：'GO_Biological_Process_2021'）
- `organism`: 物种（默认：'Human'）
- `engine`: 富集引擎（'enrichr' 或 'kegg'，默认：'enrichr'）

**返回**：
```json
{
  "success": true,
  "message": "富集分析完成",
  "data": {
    "富集分析结果.csv": "文件ID",
    "富集分析统计信息": "统计文本",
    "enrichment_bar.png": "图片ID",
    "enrichment_dot.png": "图片ID",
    "enrichment_ratio.png": "图片ID",
    "enrichment_pval_distribution.png": "图片ID",
    "enrichment_volcano.png": "图片ID"
  }
}
```

### 文件下载接口

**GET** `/api/download/{file_id}`

下载富集分析结果文件（CSV或PNG格式）。

## 部署

### 使用Docker Compose

```bash
cd gene-enrichment-analysis
docker-compose up -d
```

### 使用Docker

```bash
docker build -t gene-enrichment-analysis .
docker run -d -p 8086:8086 -v $(pwd)/outputs:/app/outputs gene-enrichment-analysis
```

### 直接运行

```bash
pip install -r requirements.txt
python main.py
```

## 服务合并说明

本服务合并了以下两个服务：
- `single-cell-enrichment`：单细胞基因富集分析服务
- `spatial-enrichment`：空间基因富集分析服务

**合并优势**：
1. 减少维护成本：只需维护一个服务
2. 统一接口和参数：提供一致的API接口
3. 功能更全面：整合了两个服务的所有功能
4. 支持更多输入类型：不仅限于单细胞或空间数据

**迁移建议**：
- 原有的 `single-cell-enrichment` 和 `spatial-enrichment` 服务可以逐步废弃
- 新项目应使用 `gene-enrichment-analysis` 服务
- API接口保持兼容，迁移成本低

## 配置

服务配置文件：`service_config.json`

主要配置项：
- `service_id`: `gene-enrichment-analysis`
- `port`: `8086`
- `baseurl`: `http://localhost:8086`

## 健康检查

**GET** `/health`

返回服务健康状态。

## 依赖

- Python 3.9+
- FastAPI
- gseapy
- pandas
- matplotlib
- seaborn

详见 `requirements.txt`。

## 许可证

与系统服务器其他服务保持一致。

