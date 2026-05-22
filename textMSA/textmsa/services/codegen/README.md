# 代码生成服务 (Codegen Service)

代码生成服务是textMSA的一个子项目，用于根据用户需求、输入问题和输入文件，自动生成对应的输入输出模板文件，并在用户确认后生成代码并执行。

## 功能特性

1. **智能代码生成**：使用LLM根据用户需求自动生成代码模板
2. **多语言支持**：支持Python、R、Julia、Bash等多种编程语言
3. **环境管理**：支持conda环境管理（如LG环境）
4. **参数管理**：自动生成参数schema和模板，支持参数验证
5. **代码执行**：支持异步执行生成的代码
6. **持久化存储**：保存执行环境、代码和执行记录到MongoDB和文件系统

## 架构设计

### 核心组件

1. **CodegenService** (`codegen_service.py`)
   - 主服务类，管理代码生成、确认、执行的完整流程
   - 与MongoDB交互，存储模板和执行记录
   - 协调Agent和执行器

2. **CodegenAgent** (`codegen_agent.py`)
   - 使用LLM生成代码模板
   - 根据用户需求和文件信息生成参数schema和输出配置

3. **CodegenExecutor** (`codegen_executor.py`)
   - 代码执行器，支持多种语言的代码执行
   - 支持conda环境管理
   - 处理执行结果和输出文件

4. **数据模型** (`textmsa/services/data/mongodb_models.py`)
   - `CodegenRequest`: 代码生成请求
   - `CodegenTemplate`: 代码模板
   - `CodegenExecution`: 代码执行记录
   - `ExecutionEnvironment`: 执行环境配置
   - `SupportedLanguage`: 支持的语言枚举
   - `InputFileInfo`: 输入文件信息

## API接口

### 1. 生成代码模板

```http
POST /api/codegen/generate
Content-Type: application/json

{
  "user_requirement": "对h5ad文件进行PCA分析",
  "input_file": {
    filename:"qc_15197.h5ad",
    description:"质量控制后的空间转录组数据"
  },
}
```

### 2. 获取模板信息

```http
GET /api/codegen/template/{template_id}
```

### 3. 获取模板列表

```http
GET /api/codegen/templates?skip=0&limit=100
```

### 4. 确认模板

```http
POST /api/codegen/templates/{template_id}/confirm
```

### 5. 执行模板

```http
POST /api/codegen/templates/{template_id}/execute
Content-Type: application/json

{
  "parameters": {
    "n_components": 50
  }
}
```


## 使用流程

1. **生成模板**：用户提供需求、问题和输入文件，系统使用LLM生成代码模板
2. **查看模板**：用户可以查看生成的代码、参数schema和输出配置
3. **修改模板**（可选）：用户可以修改生成的代码或参数
4. **确认模板**：用户确认模板后，状态变为`confirmed`
5. **执行代码**：用户执行模板，系统在后台异步执行代码
6. **查看结果**：用户可以查看执行状态、输出文件和执行日志

## 数据模型

### CodegenTemplate

- `template_id`: 模板ID（唯一标识）
- `user_requirement`: 用户需求描述
- `input_file`: 字典类型，存在filename和description属性，用来描述文件
- `service_id`: 附属于哪一个服务
- `parameter_template`: 参数模板（默认值）
- `parameter_schema`: 参数定义schema（类型、约束）
- `output_config`: 输出结果配置
- `generated_code`: 生成的代码
- `code_language`: 代码语言（python/r/julia/bash）
- `metadata`: 执行环境配置（conda环境、依赖等）
- `status`: 状态（generated/confirmed）

### CodegenExecution

- `execution_id`: 执行ID（唯一标识）
- `template_id`: 模板ID
- `code`: 执行的代码
- `environment`: 执行环境
- `parameters`: 执行参数
- `status`: 执行状态
- `output_file_id`: 输出文件ID
- `output_data`: 输出数据
- `error_message`: 错误信息
- `execution_log`: 执行日志

## 配置

代码生成服务使用textMSA的统一配置系统：

- MongoDB配置：从`config.json`读取
- 存储配置：代码保存在`{storage.base_dir}/codegen/`目录
- LLM配置：使用textMSA的LLM配置

## 扩展性

代码生成服务设计为可扩展的：

1. **支持新语言**：在`CodegenExecutor`中添加新的执行方法
2. **自定义Agent**：可以替换或扩展`CodegenAgent`的提示词
3. **环境管理**：可以扩展`ExecutionEnvironment`支持更多环境类型
4. **代码模板**：可以在`templates/`目录下添加预定义模板

## 注意事项

1. 代码执行在后台异步进行，需要轮询执行记录获取结果
2. 生成的代码应该包含错误处理和日志输出
43. 参数验证基于parameter_schema，确保参数类型和范围正确

## 示例

### Python代码生成示例

```python
# 用户需求：对h5ad文件进行PCA分析
# 生成的代码可能如下：

import scanpy as sc
import pandas as pd
import sys

def perform_pca(input_file_path, n_components=50):
    """
    对h5ad文件进行PCA分析
    
    Args:
        input_file_path: 输入文件路径
        n_components: PCA主成分数量（默认50）
    
    Returns:
        处理后的AnnData对象
    """
    # 读取数据
    adata = sc.read_h5ad(input_file_path)
    
    # 预处理
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)
    sc.pp.highly_variable_genes(adata, min_mean=0.0125, max_mean=3, min_disp=0.5)
    adata.raw = adata
    adata = adata[:, adata.var.highly_variable]
    sc.pp.scale(adata, max_value=10)
    
    # PCA分析
    sc.tl.pca(adata, n_comps=n_components, svd_solver='arpack')
    
    # 保存结果
    output_path = input_file_path.replace('.h5ad', '_pca.h5ad')
    adata.write(output_path)
    
    return adata

if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "input.h5ad"
    n_components = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    result = perform_pca(input_file, n_components)
    print(f"PCA分析完成，主成分数量: {n_components}")
```

## 未来计划

1. 支持更多编程语言（如MATLAB、C++等）
2. 支持交互式代码编辑和调试
3. 支持代码版本管理和回滚
4. 支持代码模板库和分享
5. 支持代码执行的可视化监控

