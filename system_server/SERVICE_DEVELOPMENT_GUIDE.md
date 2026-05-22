# 服务构建开发指南

本文档详细说明如何为系统构建新的服务，包括配置文件编写、服务代码实现、Docker配置等完整流程。

---

## 目录

1. [服务架构概述](#服务架构概述)
2. [服务目录结构](#服务目录结构)
3. [配置文件编写 (service_config.json)](#配置文件编写-service_configjson)
4. [服务代码实现 (main.py)](#服务代码实现-mainpy)
5. [依赖管理 (requirements.txt)](#依赖管理-requirementstxt)
6. [Docker 配置](#docker-配置)
7. [服务部署与运行](#服务部署与运行)
8. [最佳实践](#最佳实践)

---

## 服务架构概述

系统采用微服务架构，每个服务都是独立的 FastAPI 应用：

- **服务发现**：系统通过扫描 `services/` 目录下的 `service_config.json` 文件自动发现服务
- **端口管理**：每个服务在配置文件中指定端口，系统会自动分配和管理
- **API 规范**：服务必须实现标准的 API 端点（处理接口 + 下载接口）
- **输出管理**：服务将结果文件保存到 `outputs/` 目录，通过 UUID 命名

---

## 服务目录结构

每个服务应遵循以下目录结构：

```
service-name/
├── main.py                 # 服务主代码（必需）
├── service_config.json     # 服务配置文件（必需）
├── requirements.txt        # Python 依赖（必需）
├── Dockerfile              # Docker 构建文件（可选）
├── docker-compose.yml      # Docker Compose 配置（可选）
├── outputs/                # 输出目录（自动创建）
└── README.md               # 服务说明文档（可选）
```

---

## 配置文件编写 (service_config.json)

`service_config.json` 是服务的核心配置文件，定义了服务的元数据、参数、输入输出等。

### 完整配置模板

```json
{
  "service_id": "service-name",
  "name": "Service Display Name",
  "description": "详细的服务描述，说明服务功能、算法、适用场景等",
  "version": "1.0.0",
  "baseurl": "http://localhost:PORT",
  "port": PORT,
  "service_suffix": "/api/service-endpoint",
  "download_suffix": "/api/download",
  "parameter_template": {
    "param1": "default_value",
    "param2": 10
  },
  "parameter_schema": {
    "param1": {
      "type": "enum",
      "default_value": "value1",
      "enum_values": ["value1", "value2"],
      "description": "参数描述",
      "required": false
    },
    "param2": {
      "type": "discrete",
      "default_value": 10,
      "min_value": 1,
      "max_value": 100,
      "description": "参数描述",
      "required": false
    }
  },
  "accepted_files": {
    "file": {
      "file_type_ids": ["file_type_id"],
      "description": "输入文件描述"
    }
  },
  "output_config": {
    "collection_description": "输出文件集合描述",
    "items": [
      {
        "type": "file",
        "filename": "output_file.h5ad",
        "description": "输出文件描述",
        "file_type_id": "output_file_type_id"
      }
    ]
  }
}
```

### 配置字段详解

#### 1. 基础信息

- **service_id** (string, 必需): 服务的唯一标识符，通常与目录名一致，使用小写字母和连字符
- **name** (string, 必需): 服务的显示名称
- **description** (string, 必需): 服务的详细描述，用于文档和UI展示
- **version** (string, 必需): 服务版本号，遵循语义化版本规范
- **baseurl** (string, 必需): 服务的基础URL，格式：`http://localhost:PORT`
- **port** (integer, 必需): 服务监听的端口号，确保与其他服务不冲突
- **service_suffix** (string, 必需): 服务处理接口的路径后缀，如 `/api/spatial-cluster`
- **download_suffix** (string, 必需): 文件下载接口的路径后缀，通常为 `/api/download`

#### 2. 参数模板 (parameter_template)

定义所有参数的默认值，这些值会在用户未提供参数时使用。

```json
"parameter_template": {
  "file_type": "auto",
  "n_neighbors": 15,
  "resolution": 1.0,
  "algorithm": "leiden",
  "random_state": 0,
  "use_expression_fallback": true
}
```

#### 3. 参数模式 (parameter_schema)

定义每个参数的详细模式，包括类型、约束、描述等。

**参数类型 (type)**:
- `enum`: 枚举类型，从预定义列表中选择
- `discrete`: 整数类型，有最小值和最大值
- `continuous`: 浮点数类型，有最小值和最大值
- `boolean`: 布尔类型
- `string`: 字符串类型

**示例**:

```json
"parameter_schema": {
  "file_type": {
    "type": "enum",
    "default_value": "auto",
    "enum_values": ["auto", "h5ad", "10x_h5", "csv", "tsv"],
    "description": "输入文件类型",
    "required": false
  },
  "n_neighbors": {
    "type": "discrete",
    "default_value": 15,
    "min_value": 2,
    "max_value": 100,
    "description": "近邻数量",
    "required": false
  },
  "resolution": {
    "type": "continuous",
    "default_value": 1.0,
    "min_value": 0.1,
    "max_value": 5.0,
    "description": "聚类分辨率",
    "required": false
  },
  "use_expression_fallback": {
    "type": "boolean",
    "default_value": true,
    "description": "是否使用表达回退",
    "required": false
  }
}
```

#### 4. 接受文件 (accepted_files)

定义服务接受的输入文件类型。

```json
"accepted_files": {
  "file": {
    "file_type_ids": ["preprocessed_spatial_data"],
    "description": "预处理后的空间转录组数据 (h5ad格式)，包含表达矩阵和空间坐标"
  }
}
```

- **file**: 文件参数的键名（在API中使用）
- **file_type_ids**: 文件类型标识符列表，用于类型匹配
- **description**: 文件描述

#### 5. 输出配置 (output_config)

定义服务产生的输出文件。

**⚠️ 重要：输出文件描述必须尽可能详细！**

输出文件的 `description` 字段是用户了解输出内容的主要途径，应该包含足够的信息，让用户能够：
- 理解文件的结构和格式
- 知道文件中包含哪些数据/信息
- 了解如何解析和使用这些文件
- 理解数据的含义和用途

##### 输出配置结构

```json
"output_config": {
  "collection_description": "输出聚类后的空间数据和可视化图表",
  "items": [
    {
      "type": "file",
      "filename": "spatial_cluster_data.h5ad",
      "description": "详细的文件描述...",
      "file_type_id": "clustered_spatial_rna_seq_data"
    }
  ]
}
```

- **collection_description**: 输出集合的整体描述，简要说明所有输出文件的用途
- **items**: 输出文件列表
  - **type**: 文件类型，通常为 `"file"`
  - **filename**: 输出文件名（用于返回给客户端）
  - **description**: **文件详细描述（必须尽可能详细，见下方要求）**
  - **file_type_id**: 文件类型标识符

##### 输出文件描述详细要求

根据实际服务的输出描述，以下是不同类型文件的详细描述要求：

###### 1. AnnData 文件 (h5ad 格式)

**必须描述的内容**：
- 文件格式：明确说明是 AnnData 对象 (h5ad 格式)
- 数据结构：详细说明 AnnData 对象的所有主要属性（X, obs, var, obsm, uns）
- 每个属性的具体内容：
  - **X**: 表达矩阵的维度（spots/cells x genes）、数据类型、是否归一化
  - **obs**: 列名列表，每列的含义和数据类型（如聚类标签、置信度分数等）
  - **var**: 列名列表，每列的含义（如基因统计信息、空间变异指标等）
  - **obsm**: 包含的键名和内容（如空间坐标、降维结果等）
  - **uns**: 包含的键名和内容（如分析参数、统计信息、元数据等）

**示例（优秀）**：
```json
{
  "type": "file",
  "filename": "spatial_variation_data.h5ad",
  "description": "AnnData object (h5ad format) containing spatial transcriptomics data with spatial variation analysis results. Attributes: 'X' (expression matrix, spots/cells x genes), 'obs' (spot/cell metadata with 'hotspot' (boolean indicating hotspot status), 'coldspot' (boolean indicating coldspot status), and spatial coordinates), 'var' (gene metadata with spatial variation statistics), 'obsm' (spatial coordinates in 'spatial' or 'X_spatial' key), 'uns' (unsupervised annotations including 'spatial_autocorr' (autocorrelation statistics per gene), 'spatial_variable_genes' (list of spatially variable genes), and analysis parameters)",
  "file_type_id": "spatial_rna_seq_data"
}
```

**示例（较差）**：
```json
{
  "type": "file",
  "filename": "spatial_variation_data.h5ad",
  "description": "AnnData对象，包含空间变异分析结果",
  "file_type_id": "spatial_rna_seq_data"
}
```

###### 2. CSV/TSV 文件

**必须描述的内容**：
- 文件格式：CSV 或 TSV，分隔符
- 列名列表：所有列的名称
- 每列的含义：详细说明每列的数据类型、取值范围、含义
- 数据说明：特殊值、缺失值处理、单位等

**示例（优秀）**：
```json
{
  "type": "file",
  "filename": "spatial_autocorr_results.csv",
  "description": "CSV file containing spatial autocorrelation analysis results. Columns: 'gene' (gene identifier), 'morans_i' (Moran's I statistic, positive indicates positive spatial autocorrelation), 'morans_pvalue' (p-value for Moran's I), 'morans_fdr' (FDR-adjusted p-value for Moran's I), 'gearys_c' (Geary's C statistic if computed, lower indicates positive spatial autocorrelation), 'gearys_pvalue' (p-value for Geary's C), 'gearys_fdr' (FDR-adjusted p-value for Geary's C), 'mean_expression' (mean expression level of the gene), 'spatially_variable' (boolean indicating if gene is spatially variable based on thresholds)",
  "file_type_id": "spatial_autocorr_results_csv"
}
```

**示例（较差）**：
```json
{
  "type": "file",
  "filename": "spatial_autocorr_results.csv",
  "description": "空间自相关分析结果CSV文件",
  "file_type_id": "spatial_autocorr_results_csv"
}
```

**另一个优秀示例**：
```json
{
  "type": "file",
  "filename": "enrichment_results.csv",
  "description": "CSV file containing functional enrichment analysis results from gseapy Enrichr. Columns: 'Term' (pathway/term name), 'Overlap' (overlap between input genes and term genes, e.g., '50/200'), 'P-value' (statistical p-value for enrichment), 'Adjusted P-value' (adjusted p-value using multiple testing correction), 'Odds Ratio' (odds ratio for enrichment), 'Combined Score' (combined score combining p-value and odds ratio), 'Genes' (comma-separated list of overlapping genes), 'gene_count' (number of overlapping genes), 'total_genes' (total genes in the term)",
  "file_type_id": "pathway_enrichment_csv"
}
```

###### 3. 图像文件 (PNG/JPG 等)

**必须描述的内容**：
- 图像格式：PNG、JPG 等
- 分辨率：DPI（通常为 300 DPI）
- 图表类型：明确说明是什么类型的图表（如 UMAP、热图、散点图等）
- 图表内容：说明图表展示的内容、颜色编码、坐标轴含义等
- 生成条件：说明在什么条件下会生成此图表（如果适用）

**示例（优秀）**：
```json
{
  "type": "file",
  "filename": "spatial_variation_heatmap.png",
  "description": "Heatmap of top spatially variable genes (PNG, 300 DPI)",
  "file_type_id": "heatmap_png"
}
```

```json
{
  "type": "file",
  "filename": "annotation_umap.png",
  "description": "UMAP plot (PNG, 300 DPI) colored by annotated cell types to assess separation",
  "file_type_id": "umap_plot_png"
}
```

```json
{
  "type": "file",
  "filename": "hotspot_coldspot_map.png",
  "description": "Spatial map of hotspots and coldspots (PNG, 300 DPI) when detection is enabled",
  "file_type_id": "spatial_plot_png"
}
```

**示例（较差）**：
```json
{
  "type": "file",
  "filename": "heatmap.png",
  "description": "热图",
  "file_type_id": "heatmap_png"
}
```

###### 4. JSON 文件

**必须描述的内容**：
- 文件格式：JSON 格式
- 数据结构：说明 JSON 的结构（对象、数组等）
- 键名和含义：列出主要键名及其含义
- 数据类型：说明值的类型和格式

**示例（优秀）**：
```json
{
  "type": "file",
  "filename": "imputation_stats.json",
  "description": "Run statistics (parameters, gene intersections, distance summaries, etc.)",
  "file_type_id": "qc_summary_json"
}
```

**更详细的示例**：
```json
{
  "type": "file",
  "filename": "analysis_stats.json",
  "description": "JSON file containing analysis statistics and metadata. Structure: object with keys 'parameters' (analysis parameters used), 'gene_intersection' (number of genes in intersection), 'distance_summary' (statistics of distances: mean, median, min, max), 'processing_time' (time taken in seconds), 'n_spots' (number of spots/cells processed), 'n_genes' (number of genes analyzed)",
  "file_type_id": "qc_summary_json"
}
```

###### 5. 文本文件 (TXT)

**必须描述的内容**：
- 文件格式：纯文本格式
- 内容类型：说明文件包含什么类型的信息（统计报告、日志、摘要等）
- 内容结构：如果有多部分，说明各部分的内容

**示例（优秀）**：
```json
{
  "type": "file",
  "filename": "statistics.txt",
  "description": "Text report containing service statistics and summary information",
  "file_type_id": "txt_report"
}
```

**更详细的示例**：
```json
{
  "type": "file",
  "filename": "analysis_report.txt",
  "description": "Text report containing detailed analysis statistics. Sections include: 'Input Summary' (input file information, number of spots/cells, genes), 'Processing Parameters' (all parameters used in analysis), 'Results Summary' (key findings, number of clusters/annotations, etc.), 'Quality Metrics' (quality scores, confidence metrics), 'Output Files' (list of generated output files)",
  "file_type_id": "txt_report"
}
```

##### 描述编写检查清单

在编写输出文件描述时，请确保：

- ✅ **格式明确**：说明文件格式（h5ad、CSV、PNG 等）
- ✅ **结构详细**：对于结构化文件（h5ad、CSV、JSON），详细说明数据结构
- ✅ **列名完整**：对于表格文件（CSV），列出所有列名和含义
- ✅ **属性说明**：对于 AnnData 文件，说明所有主要属性（X, obs, var, obsm, uns）及其内容
- ✅ **数据类型**：说明关键字段的数据类型（boolean、float、string 等）
- ✅ **取值范围**：如果适用，说明值的取值范围或含义（如 "positive indicates..."）
- ✅ **图表信息**：对于图像文件，说明图表类型、DPI、内容、颜色编码等
- ✅ **生成条件**：如果文件在某些条件下才生成，说明这些条件
- ✅ **单位说明**：如果涉及数值，说明单位（如距离、时间等）
- ✅ **特殊值处理**：说明缺失值、特殊值的表示方式

##### 描述长度建议

- **最小长度**：至少 50 个字符，包含基本格式和内容说明
- **推荐长度**：100-300 个字符，包含详细的结构和内容说明
- **复杂文件**：对于包含多个列/属性的文件，可以更长（300-500 字符）

**原则**：宁可详细也不要简略，用户需要足够的信息来理解和使用输出文件。

---

## 服务代码实现 (main.py)

服务代码必须实现以下核心功能：

### 1. FastAPI 应用初始化

```python
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse

app = FastAPI(
    title="服务名称",
    description="服务描述",
    version="1.0.0",
)
```

### 2. 输出目录配置

```python
import os

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)
```

### 3. 主处理接口

接口路径必须与 `service_config.json` 中的 `service_suffix` 一致。

**接口规范**:
- 方法: `POST`
- 参数: 文件上传 + 表单参数
- 返回: JSON 响应，包含成功状态和文件ID映射

**示例**:

```python
@app.post("/api/spatial-cluster")
async def spatial_cluster(
    file: UploadFile = File(...),
    file_type: str = Form("auto"),
    n_neighbors: int = Form(15),
    resolution: float = Form(1.0),
    algorithm: str = Form("leiden"),
    random_state: int = Form(0),
    use_expression_fallback: bool = Form(True),
) -> JSONResponse:
    """空间聚类接口"""
    temp_input_path = None
    try:
        # 1. 保存上传文件
        file_id = str(uuid.uuid4())
        temp_input_path = os.path.join(tempfile.gettempdir(), f"input_{file_id}_{file.filename}")
        with open(temp_input_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # 2. 读取和处理数据
        adata = read_adata(temp_input_path, file_type)
        # ... 处理逻辑 ...
        
        # 3. 保存结果文件（使用UUID命名）
        h5ad_id = f"{uuid.uuid4()}.h5ad"
        output_file_path = os.path.join(OUTPUT_DIR, h5ad_id)
        adata.write_h5ad(output_file_path)
        
        # 4. 生成其他输出文件（如图表、统计报告等）
        # ...
        
        # 5. 构建返回数据（文件名 -> UUID映射）
        data_dict = {
            "spatial_cluster_data.h5ad": h5ad_id,
            "statistics.txt": statistics_id,
            # ... 其他文件
        }
        
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "处理完成", "data": data_dict},
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"处理失败: {str(e)}"},
        )
    finally:
        # 清理临时文件
        if temp_input_path and os.path.exists(temp_input_path):
            try:
                os.remove(temp_input_path)
            except:
                pass
```

**关键要点**:
- 使用 `UploadFile` 接收文件上传
- 使用 `Form()` 接收表单参数，默认值应与 `parameter_template` 一致
- 临时文件保存在系统临时目录，处理完成后删除
- 输出文件使用 UUID 命名，避免冲突
- 返回的 `data` 字典键为配置中的 `filename`，值为实际的文件ID（UUID）

### 4. 文件下载接口

接口路径必须与 `service_config.json` 中的 `download_suffix` 一致。

```python
@app.get("/api/download/{file_id}")
async def download_file(file_id: str) -> FileResponse:
    """下载文件"""
    file_path = os.path.join(OUTPUT_DIR, file_id)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"文件不存在: {file_id}")
    
    # 根据文件类型设置媒体类型
    if file_path.endswith(".png"):
        media_type = "image/png"
    elif file_path.endswith(".h5ad"):
        media_type = "application/octet-stream"
    else:
        media_type = "application/octet-stream"
    
    return FileResponse(path=file_path, filename=file_id, media_type=media_type)
```

### 5. 健康检查接口

```python
@app.get("/health")
async def health():
    return {"status": "healthy", "output_dir": OUTPUT_DIR}
```

### 6. 主程序入口

```python
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
```

**注意**: 端口应从环境变量 `PORT` 读取，而不是硬编码。

### 7. 错误处理

- 使用 try-except 捕获异常
- 返回适当的 HTTP 状态码
- 提供清晰的错误消息
- 确保资源清理（临时文件、连接等）

**错误响应格式要求**:

所有错误响应必须使用英文，并包含详细的错误信息和参数建议。错误响应格式如下：

```python
return JSONResponse(
    status_code=500,  # 或适当的 HTTP 状态码
    content={
        "success": False,
        "message": "Detailed error message with parameter suggestions",
        "error": {
            "error_type": "ValueError",
            "error_message": "Original error message",
            "suggestions": [
                "Suggestion 1",
                "Suggestion 2",
                ...
            ]
        }
    }
)
```

**错误消息要求**:

1. **必须使用英文**: 所有返回给用户的错误消息必须使用英文，包括：
   - `message` 字段中的错误描述
   - `error.suggestions` 中的参数建议
   - HTTPException 的 `detail` 字段

2. **详细的错误信息**: `message` 字段应包含：
   - 错误发生的步骤/操作
   - 具体的错误原因
   - 参数建议（如果有）

3. **参数建议格式**: 建议应清晰、具体，格式如下：
   ```
   Error description: [specific error message]
   
   Parameter suggestions:
     • Suggestion 1
     • Suggestion 2
     • ...
   ```

4. **常见错误类型处理**:
   - **文件格式错误**: 提供文件类型建议（file_type 参数）
   - **坐标缺失错误**: 提供坐标键建议（coord_key 参数）和可用的 obsm 键列表
   - **参数验证错误**: 提供参数取值范围建议
   - **数据维度错误**: 提供数据要求说明
   - **依赖包错误**: 提供安装命令

**示例**:

```python
def format_error_info_to_message(error_info: Dict[str, Any]) -> str:
    """Format error_info dictionary into a readable string message"""
    parts = []
    
    # Basic information
    parts.append(f"Error Type: {error_info.get('error_type', 'Unknown')}")
    parts.append(f"Error Message: {error_info.get('error_message', 'Unknown error')}")
    
    # Diagnosis information
    if "diagnosis" in error_info:
        parts.append(f"\nDiagnosis: {error_info['diagnosis']}")
    
    # Suggestions information
    if "suggestions" in error_info and error_info["suggestions"]:
        parts.append("\nSuggestions:")
        for idx, suggestion in enumerate(error_info["suggestions"], 1):
            if isinstance(suggestion, dict):
                issue = suggestion.get("issue", "Unknown issue")
                recommendations = suggestion.get("recommendations", [])
                parts.append(f"\n  {idx}. {issue}:")
                for rec in recommendations:
                    parts.append(f"     - {rec}")
    
    return "\n".join(parts)


def handle_error(step: str, error: Exception, include_traceback: bool = True,
                 context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Unified error handling function that provides detailed error messages and parameter suggestions"""
    error_info = {
        "error": True,
        "step": step,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "suggestions": []
    }
    
    # Generate suggestions based on error type and context
    error_msg_lower = str(error).lower()
    
    if "file" in error_msg_lower or "read" in error_msg_lower:
        error_info["diagnosis"] = "File reading or format issue"
        error_info["suggestions"].extend([
            {
                "issue": "File format mismatch or file corrupted",
                "recommendations": [
                    "Check if file format is correct (supported formats: h5ad, 10x_h5, csv, tsv)",
                    "Try explicitly specifying the file_type parameter"
                ]
            }
        ])
    
    # ... more error handling logic ...
    
    return error_info

# 在接口中使用
try:
    # ... processing ...
except Exception as e:
    error_info = handle_error("processing_step", e, context={"param1": value1})
    error_message = format_error_info_to_message(error_info)
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": error_message  # 只包含 message 字段，不包含 error 字段
        }
    )
```

### 8. 服务响应格式要求

**成功响应格式**:

```python
return JSONResponse(
    status_code=200,
    content={
        "success": True,
        "message": "Operation completed successfully",  # 英文消息
        "data": {
            "output_file.h5ad": "uuid-here.h5ad",
            "statistics.txt": "uuid-here.txt"
        }
    }
)
```

**响应字段说明**:

- `success` (boolean): 操作是否成功
- `message` (string): **必须使用英文**，简要描述操作结果或状态
- `data` (dict): 输出文件映射，键为配置中的 `filename`，值为实际的文件ID（UUID+扩展名）

**错误响应格式**:

```python
# 使用 format_error_info_to_message 格式化错误信息
error_info = handle_error("step_name", e, context=context)
error_message = format_error_info_to_message(error_info)

return JSONResponse(
    status_code=400,  # 或 500 等
    content={
        "success": False,
        "message": error_message  # 只包含 message 字段，不包含 error 字段
    }
)
```

**注意**: 错误响应只包含 `success` 和 `message` 字段，不包含 `error` 字段。所有错误信息（包括错误类型、错误消息、诊断信息、建议等）都通过 `format_error_info_to_message` 函数格式化为字符串，放在 `message` 字段中。

**重要要求**:

1. ✅ **所有用户可见的消息必须使用英文**:
   - API 响应中的 `message` 字段
   - 错误消息和参数建议
   - HTTPException 的 `detail` 字段
   - Form 参数的 `description` 字段
   - 函数文档字符串（docstrings）

2. ✅ **错误消息必须详细且包含建议**:
   - 说明错误发生的具体步骤
   - 提供具体的错误原因
   - 包含参数建议，帮助用户修正问题
   - 列出可用的选项或取值范围

3. ✅ **日志信息必须使用英文**:
   - `logger.info()`, `logger.warning()`, `logger.error()` 等所有日志信息必须使用英文
   - 日志信息会被记录到日志文件中，可能被用户查看，因此应使用英文以保持一致性

4. ✅ **统计报告必须使用英文**:
   - 输出到文件的统计报告（如 `statistics.txt`）必须使用英文
   - 报告内容会被用户直接查看，应使用英文以确保国际化兼容性
   - 包括报告标题、章节标题、统计项描述、数值说明等所有文本内容

### 9. 数据处理函数

将复杂的数据处理逻辑封装为独立函数，提高代码可维护性。

```python
def read_adata(file_path: str, file_type: str) -> ad.AnnData:
    """读取AnnData文件"""
    # 实现文件读取逻辑
    pass

def process_data(adata: ad.AnnData, **params) -> ad.AnnData:
    """处理数据"""
    # 实现数据处理逻辑
    pass

def generate_plots(adata: ad.AnnData, output_dir: str) -> Dict[str, str]:
    """生成可视化图表"""
    # 实现图表生成逻辑
    # 返回: {配置中的filename: 实际文件ID}
    pass
```

---

## 依赖管理 (requirements.txt)

列出服务所需的所有 Python 包及其版本。

### 格式规范

```
package_name>=version
package_name==version
package_name~=version
```

### 示例

```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
python-multipart>=0.0.6
anndata>=0.9.0
scanpy>=1.9.0
pandas>=1.5.0
numpy>=1.23.0
scipy>=1.9.0
matplotlib>=3.7.0
seaborn>=0.12.0
scikit-learn>=1.3.0
igraph>=0.10.0
leidenalg>=0.9.0
```

### 注意事项

- 使用 `>=` 指定最低版本，允许兼容更新
- 使用 `==` 固定版本，确保一致性（谨慎使用）
- 包含所有直接依赖，不要遗漏
- 定期更新依赖以修复安全漏洞

---

## Docker 配置

### Dockerfile

```dockerfile
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DEFAULT_TIMEOUT=100

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 配置 pip 镜像源（可选，加速国内构建）
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn

# 升级 pip 和安装构建工具
RUN pip install --upgrade pip setuptools wheel

# 安装 Python 依赖
RUN pip install -r requirements.txt

# 复制应用代码
COPY . .

# 创建输出目录
RUN mkdir -p /app/outputs

# 暴露端口
EXPOSE 8080

# 设置环境变量
ENV PORT=8080
ENV OUTPUT_DIR=/app/outputs

# 启动命令
CMD ["python", "main.py"]
```

**关键要点**:
- 使用合适的基础镜像（如 `python:3.10-slim`）
- 安装系统依赖（如编译工具）
- 配置 pip 镜像源以加速构建（可选）
- 设置环境变量 `PORT` 和 `OUTPUT_DIR`
- 暴露端口（与配置中的端口一致）

### docker-compose.yml

```yaml
version: '3.8'

services:
  service-name:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: service-name
    ports:
      - "PORT:PORT"
    environment:
      - PORT=PORT
      - OUTPUT_DIR=/app/outputs
    volumes:
      - ./outputs:/app/outputs
    networks:
      - services-network
    restart: unless-stopped

networks:
  services-network:
    driver: bridge
```

**关键要点**:
- 端口映射：`HOST_PORT:CONTAINER_PORT`
- 环境变量与 Dockerfile 一致
- 挂载 `outputs` 目录以持久化输出
- 使用共享网络以便服务间通信

---

## 服务部署与运行

### 1. 本地开发运行

```bash
# 安装依赖
pip install -r requirements.txt

# 设置环境变量
export PORT=54889
export OUTPUT_DIR=./outputs

# 运行服务
python main.py
```

### 2. Docker 运行

```bash
# 构建镜像
docker build -t service-name .

# 运行容器
docker run -d \
  -p 54889:8080 \
  -v $(pwd)/outputs:/app/outputs \
  -e PORT=8080 \
  -e OUTPUT_DIR=/app/outputs \
  service-name
```

### 3. Docker Compose 运行

```bash
# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 4. 通过系统服务管理器运行

系统会自动扫描服务目录，读取配置，并启动服务。

```bash
# 在 system_server 目录下
python -m system_server.main
```

---

## 最佳实践

### 1. 配置文件

- ✅ 使用有意义的 `service_id`，与目录名一致
- ✅ 提供详细的 `description`，说明功能、算法、适用场景
- ✅ 参数默认值合理，符合常见使用场景
- ✅ 参数约束清晰（最小值、最大值、枚举值）
- ✅ **输出文件描述尽可能详细**（⚠️ 最重要）
  - 这是用户理解输出内容的主要途径
  - 必须包含文件结构、列名/属性、数据类型、含义等详细信息
  - 参考本文档"输出配置"部分的详细要求和示例
  - 宁可详细也不要简略

### 2. 代码实现

- ✅ 使用类型提示提高代码可读性
- ✅ 将复杂逻辑封装为独立函数
- ✅ 添加适当的注释和文档字符串
- ✅ 实现完善的错误处理和资源清理
- ✅ 使用 UUID 命名输出文件，避免冲突
- ✅ 临时文件及时清理

### 3. 数据处理

- ✅ 支持多种文件格式（如 `auto` 模式自动检测）
- ✅ 验证输入数据的有效性
- ✅ 处理边界情况（如缺失数据、空文件等）
- ✅ 提供有意义的错误消息

### 4. 输出管理

- ✅ **输出文件描述尽可能详细**（⚠️ 最重要）
  - 对于 h5ad 文件：详细描述 AnnData 对象的所有属性（X, obs, var, obsm, uns）及其内容
  - 对于 CSV 文件：列出所有列名，说明每列的含义、数据类型、取值范围
  - 对于图像文件：说明图表类型、DPI、内容、颜色编码等
  - 对于 JSON 文件：说明数据结构、主要键名及其含义
  - 参考其他服务的优秀描述示例（如 `spatial-variation-analysis`、`spatialde`、`gene-enrichment-analysis`）
- ✅ 输出文件命名规范（使用 UUID）
- ✅ 生成统计报告，便于用户了解处理结果
- ✅ 可视化图表清晰、美观（DPI >= 300）
- ✅ 输出文件格式标准化（如 h5ad、PNG）

### 5. 性能优化

- ✅ 使用适当的数据结构（如稀疏矩阵）
- ✅ 避免不必要的数据复制
- ✅ 合理使用缓存（如计算结果）
- ✅ 处理大文件时使用流式处理

### 6. 安全性

- ✅ 验证文件类型和大小
- ✅ 防止路径遍历攻击
- ✅ 限制资源使用（内存、CPU、时间）
- ✅ 不在错误消息中泄露敏感信息

### 7. 可维护性

- ✅ 代码结构清晰，模块化设计
- ✅ 遵循 PEP 8 代码风格
- ✅ 添加单元测试（可选但推荐）
- ✅ 编写 README 文档说明使用方法

---

## 常见问题

### Q1: 如何选择端口号？

A: 查看 `system_server/services/` 目录下其他服务的端口，选择一个未被占用的端口（建议使用 54800-54999 范围）。

### Q2: 如何处理大文件？

A: 使用流式处理，避免一次性加载到内存。对于非常大的文件，考虑分块处理或使用数据库。

### Q3: 如何调试服务？

A: 
- 本地运行：直接运行 `python main.py`，查看控制台输出
- Docker 运行：使用 `docker-compose logs -f` 查看日志
- 添加日志记录：使用 Python `logging` 模块

### Q4: 服务启动失败怎么办？

A: 
1. 检查端口是否被占用
2. 检查依赖是否安装完整
3. 检查配置文件格式是否正确（JSON 语法）
4. 查看错误日志定位问题

### Q5: 如何更新服务？

A: 
1. 修改代码和配置
2. 更新 `version` 字段
3. 重新构建 Docker 镜像（如使用）
4. 重启服务

---

## 参考示例

完整示例请参考：
- `spatial-clustering/` - 空间聚类服务
- `spatialde/` - 空间差异表达分析服务
- `spatial-cell-type-annotation/` - 空间细胞类型注释服务

---

## 总结

构建新服务的标准流程：

1. **创建服务目录**：在 `services/` 下创建新目录
2. **编写配置文件**：创建 `service_config.json`，定义服务元数据和参数
3. **实现服务代码**：编写 `main.py`，实现处理逻辑和 API 接口
4. **配置依赖**：创建 `requirements.txt`，列出所需包
5. **配置 Docker**：创建 `Dockerfile` 和 `docker-compose.yml`（可选）
6. **测试服务**：本地运行测试，确保功能正常
7. **部署服务**：通过系统服务管理器或 Docker 部署

遵循本指南，可以快速构建符合系统规范的服务。

