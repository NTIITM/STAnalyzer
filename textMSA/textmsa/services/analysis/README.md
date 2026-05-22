# 文件智能分析服务

## 概述

文件智能分析服务（FileAnalysisService）提供统一的文件分析接口，根据文件类型自动路由到相应的分析工具。

## 功能特性

- **自动文件类型识别**：根据文件扩展名自动识别文件类型
- **智能路由**：根据文件类型调用相应的分析工具
- **统一接口**：提供统一的分析接口，简化调用
- **异常处理**：服务层和工具层不捕获异常，由 API 层统一处理

## 支持的文件类型

### 文本文件
- `.txt`, `.log`, `.md`, `.json`
- 使用 `TextAnalysisTool`，通过 LLM 解读文本内容

### 数据文件
- `.csv`, `.excel`, `.xlsx`, `.h5ad`
- 使用 `DataAnalysisTool`，通过 PythonREPL 生成并执行代码分析数据

### 图片文件
- `.png`, `.jpg`, `.jpeg`, `.bmp`, `.gif`, `.tiff`, `.webp`
- 使用 `ImageAnalysisTool`，通过多模态 LLM 解读图片

### 其他文件
- 使用 `FileReaderTool` 默认预览

## 使用方法

### 服务层调用

```python
from textmsa.services.analysis.file_analysis_service import get_file_analysis_service

service = get_file_analysis_service()
result = service.analyze_file(
    file_id="file_id_here",
    user_id="user_id_here",
    query="请分析这个文件的内容"  # 可选
)
```

### API 调用

```
POST /api/analysis/analyze?file_id=<file_id>&query=<query>
Authorization: Bearer <token>
```

响应格式：
```json
{
  "code": 200,
  "message": "分析成功",
  "data": {
    "file_id": "...",
    "query": "...",
    "result": "分析结果内容",
    "success": true,
    "error_message": null
  }
}
```

## 架构设计

### 服务层

- `FileAnalysisService`：核心服务类，负责文件类型检测和路由

### 工具层

- `FileReaderTool`：文件读取工具
- `TextAnalysisTool`：文本分析工具
- `DataAnalysisTool`：数据分析工具
- `ImageAnalysisTool`：图片分析工具

### API 层

- `/api/analysis/analyze`：文件分析端点

## 异常处理

- **服务层和工具层**：不捕获异常，直接向上抛出
- **API 层**：捕获所有异常，转换为统一的响应格式

## 实现细节

所有工具类都是基于 langgraph 框架的新实现，独立于旧工具（`textmsa/services/agent/langgraph/tools/`）。

## 相关文件

- 服务实现：`file_analysis_service.py`
- 工具实现：`tools/` 目录
- API 路由：`textmsa/services/api/routers/analysis.py`
- 数据模型：`textmsa/services/api/schemas.py`

