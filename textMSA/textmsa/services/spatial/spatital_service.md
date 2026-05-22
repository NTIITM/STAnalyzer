我需要查看 spatial\_service.py 文件的内容，了解其实现的功能和作用。

toolName: view\_files

status: success

filePath: /home/common/hwluo/project/textMSA/textmsa/services/spatial/spatial\_service.py

# Spatial Service 空间转录组数据服务分析

## 核心功能

`spatial_service.py` 是 textMSA 项目中的**空间转录组数据服务**，主要负责：

1. **读取和处理 h5ad 文件**：加载 AnnData 对象，支持空间转录组数据
2. **提供空间可视化数据**：切片图像、Spot 位置、基因表达等
3. **数据转换和处理**：基因列表获取、表达值计算、QC 数据生成

## 技术架构

### 1. 核心类

**`SpatialService`** **类**：空间转录组数据服务的核心实现，包含以下主要功能：

- **文件管理**：获取文件路径、加载 AnnData 对象
- **数据处理**：规范化 AnnData 名称、处理空间坐标
- **可视化数据**：切片图像、Spot 位置、基因表达
- **数据导出**：生成子集 h5ad 文件

### 2. 关键方法

| 方法                       | 功能             | 核心实现                     |
| :----------------------- | :------------- | :----------------------- |
| `_get_file_path`         | 获取文件路径         | 从用户数据管理器获取文件信息           |
| `_load_adata`            | 加载 AnnData 对象  | 支持 backed 模式和内存模式        |
| `_normalize_adata_names` | 规范化 AnnData 名称 | 处理重复名称和类型问题              |
| `get_slices`             | 获取切片列表         | 从 uns\['spatial'] 提取切片信息 |
| `get_slice_image`        | 获取切片图像         | 转换为 base64 编码的图像         |
| `get_spots`              | 获取 Spot 位置数据   | 从 spatial 或 obs 中提取坐标    |
| `get_spot_details`       | 获取 Spot 详细信息   | 包括坐标、聚类、高表达基因            |
| `get_spot_top_genes`     | 获取 Spot 高表达基因  | 计算并返回 top N 基因           |
| `query_raw_qc`           | 提供原始表达和 QC 预览  | 支持基因筛选和细胞采样              |
| `download_raw_h5ad`      | 生成子集 h5ad 文件   | 支持基因和细胞的子集提取             |
| `get_gene_list`          | 获取基因列表         | 去重并支持查询过滤                |
| `get_gene_expression`    | 获取基因表达值        | 提取所有 Spot 的表达数据          |

### 3. 技术实现细节

#### 数据加载策略

- **双模式加载**：支持 `backed='r'` 模式（节省内存）和内存模式（兼容性更好）
- **缓存机制**：使用 `_adata_cache` 缓存已加载的 AnnData 对象
- **错误处理**：优雅处理文件加载失败的情况

#### 图像处理

- **多分辨率支持**：优先使用 hires、lowres、fullres 图像
- **Base64 编码**：将图像转换为 base64 格式，便于前端使用
- **缩放因子处理**：根据 scalefactors 调整图像尺寸，确保与 Spot 坐标对齐

#### 数据处理

- **名称规范化**：处理重复基因名和数值类型索引
- **类型转换**：确保数据可以正确序列化为 JSON
- **稀疏矩阵处理**：支持处理 scipy 稀疏矩阵格式

## 与其他模块的关系

1. **文件服务**：依赖 `file_service` 获取文件信息
2. **用户数据管理**：依赖 `user_data_manager` 管理用户文件
3. **可视化服务**：为可视化模块提供数据支持
4. **API 路由**：通过 API 路由暴露服务接口

## 功能应用场景

### 1. 空间转录组数据可视化

- **切片浏览**：查看组织切片图像
- **Spot 定位**：显示细胞/Spot 在组织中的位置
- **基因表达映射**：将基因表达值映射到空间位置
- **聚类分析**：基于空间位置的聚类可视化

### 2. 数据质量控制

- **QC 指标**：提供总计数、基因数、线粒体基因比例等 QC 指标
- **细胞过滤**：基于 QC 指标过滤低质量细胞
- **数据预览**：快速预览数据质量和分布

### 3. 基因表达分析

- **基因列表查询**：支持基因名称搜索
- **表达值获取**：获取特定基因在所有 Spot 中的表达值
- **高表达基因**：识别每个 Spot 的高表达基因

## 技术优势

1. **内存优化**：支持 backed 模式，减少内存占用
2. **容错处理**：优雅处理各种异常情况
3. **性能优化**：缓存机制和批量处理
4. **灵活性**：支持多种数据格式和处理方式
5. **可扩展性**：模块化设计，易于添加新功能

## 代码优化建议

1. **缓存管理**：
   - 添加缓存大小限制，避免内存泄漏
   - 实现缓存过期机制，处理文件修改情况
2. **错误处理**：
   - 增加更详细的错误信息
   - 实现更细粒度的异常处理
3. **性能优化**：
   - 对于大型数据集，考虑使用更高效的索引结构
   - 实现并行处理，加速数据密集型操作
4. **代码组织**：
   - 拆分大型方法，提高代码可读性
   - 提取公共功能为辅助函数
5. **文档完善**：
   - 增加详细的方法文档
   - 添加使用示例和最佳实践

## 总结

`SpatialService` 是 textMSA 项目中处理空间转录组数据的核心服务，它提供了从 h5ad 文件加载到数据可视化的完整功能链。通过支持多种数据处理方式和优化策略，它能够高效处理空间转录组数据，为前端可视化和数据分析提供强大支持。

该服务的设计体现了对生物信息学数据的深入理解，通过灵活的架构和健壮的错误处理，确保了在各种情况下都能稳定运行，为用户提供高质量的空间转录组数据分析能力。

<br />

# AnnData 数据结构详解

## 基本概念

**AnnData**（Annotated Data）是一种用于**存储和分析单细胞组学数据**的 Python 数据结构，由 Scanpy 团队开发，广泛应用于单细胞 RNA-seq、空间转录组等领域。

## 核心结构

AnnData 对象包含以下主要组件：

| 组件     | 描述        | 数据类型                       |
| :----- | :-------- | :------------------------- |
| `X`    | 基因表达矩阵    | 二维数组（numpy 数组或 scipy 稀疏矩阵） |
| `obs`  | 细胞级别的元数据  | pandas DataFrame           |
| `var`  | 基因级别的元数据  | pandas DataFrame           |
| `obsm` | 细胞级别的多维注释 | 字典，值为二维数组                  |
| `varm` | 基因级别的多维注释 | 字典，值为二维数组                  |
| `uns`  | 非结构化注释    | 字典，可存储任何类型的数据              |

## 在空间转录组中的应用

在空间转录组数据中，AnnData 通常包含：

1. **空间坐标信息**：
   - 存储在 `obsm['spatial']` 中，包含每个细胞/Spot 的 x、y 坐标
   - 或存储在 `obs['x']` 和 `obs['y']` 列中
2. **图像信息**：
   - 存储在 `uns['spatial']` 中，包含组织切片图像和缩放因子
   - 支持多种分辨率的图像（hires、lowres、fullres）
3. **基因表达数据**：
   - 存储在 `X` 中，行代表细胞/Spot，列代表基因
   - 通常使用稀疏矩阵格式以节省内存
4. **细胞类型和聚类信息**：
   - 存储在 `obs` 中，如 `obs['cluster']`、`obs['leiden']` 等

## 与 textMSA 项目的关系

在 textMSA 项目中，`SpatialService` 类使用 AnnData 来：

1. **加载和处理 h5ad 文件**：
   ```python
   adata = ad.read_h5ad(file_path, backed='r')
   ```
2. **提取空间坐标**：
   ```python
   if 'spatial' in adata.obsm:
       coords = adata.obsm['spatial']
   ```
3. **获取基因表达数据**：
   ```python
   gene_vector = adata.X[:, gene_idx]
   ```
4. **处理图像数据**：
   ```python
   if 'spatial' in adata.uns:
       spatial_info = adata.uns['spatial']
   ```

## 核心功能

1. **数据读写**：
   - 支持 h5ad 格式的读写
   - 支持 backed 模式（内存映射）和内存模式
2. **数据操作**：
   - 切片操作：`adata[cell_indices, gene_indices]`
   - 子设置：`adata_subset = adata[adata.obs['cluster'] == 'A']`
   - 合并：`adata_concat = ad.concat([adata1, adata2])`
3. **与 Scanpy 集成**：
   - 支持 Scanpy 的分析函数
   - 如 `sc.pp.highly_variable_genes()`、`sc.tl.pca()` 等
4. **兼容性**：
   - 与 numpy、pandas、scipy 等库无缝集成
   - 支持多种数据格式的转换

## 技术优势

1. **内存效率**：
   - 支持稀疏矩阵存储
   - 支持 backed 模式，适合处理大型数据集
2. **灵活性**：
   - 灵活的注释系统，可存储各种类型的元数据
   - 支持自定义数据结构和分析结果
3. **可扩展性**：
   - 模块化设计，易于扩展
   - 丰富的生态系统，与多种分析工具集成
4. **标准化**：
   - 成为单细胞和空间转录组数据的标准格式
   - 促进数据共享和重现性研究

## 应用场景

1. **单细胞 RNA-seq 分析**：
   - 基因表达矩阵存储
   - 细胞聚类和分型
   - 差异表达分析
2. **空间转录组分析**：
   - 空间坐标存储
   - 组织切片图像管理
   - 空间表达模式分析
3. **多组学整合**：
   - 整合 scRNA-seq 和空间转录组数据
   - 整合蛋白质组学和转录组学数据

## 总结

AnnData 是处理单细胞和空间转录组数据的**标准数据结构**，它提供了一个统一、灵活的框架来存储和分析复杂的组学数据。在 textMSA 项目中，AnnData 作为空间转录组数据的核心存储格式，为空间可视化和分析提供了强大的基础。

通过 AnnData，研究人员可以更有效地管理和分析空间转录组数据，探索基因表达的空间模式，为生物学研究提供更深入的见解。

<br />

# 空间可视化与分析的实现流程

## 一、核心实现架构

textMSA 项目的空间可视化和分析功能主要通过以下模块实现：

1. **数据服务层**：`SpatialService` 负责数据加载和处理
2. **API 接口层**：提供空间数据的 HTTP 接口
3. **前端可视化层**：使用前端库实现数据展示

## 二、具体实现步骤

### 1. 数据加载与预处理

**核心代码**：`SpatialService._load_adata` 方法

```python
def _load_adata(self, file_id: str, file_path: str) -> Any:
    # 尝试使用 backed='r' 模式（节省内存）
    try:
        adata = ad.read_h5ad(file_path, backed='r')
    except Exception:
        # 失败时尝试内存模式
        adata = ad.read_h5ad(file_path, backed=False)
    # 缓存数据
    self._adata_cache[file_id] = adata
    return adata
```

**处理流程**：

- 支持两种加载模式：`backed='r'`（内存映射，节省内存）和内存模式（兼容性更好）
- 缓存已加载的 AnnData 对象，提高性能
- 处理加载失败的情况，确保系统稳定性

### 2. 空间数据提取

#### 2.1 切片图像获取

**核心代码**：`SpatialService.get_slice_image` 方法

```python
def get_slice_image(self, file_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    # 加载数据
    adata = self._load_adata(file_id, file_path)
    # 从 uns['spatial'] 获取图像
    if 'spatial' in adata.uns:
        # 处理图像数据，转换为 base64
        # 计算缩放后的尺寸
        return {
            "imageUrl": f"data:image/png;base64,{img_base64}",
            "width": display_width,
            "height": display_height
        }
```

**实现要点**：

- 从 `adata.uns['spatial']` 提取图像数据
- 支持多种分辨率图像（hires、lowres、fullres）
- 将图像转换为 base64 编码，便于前端使用
- 根据缩放因子调整图像尺寸，确保与 Spot 坐标对齐

#### 2.2 Spot 位置数据获取

**核心代码**：`SpatialService.get_spots` 方法

```python
def get_spots(self, file_id: str, user_id: str) -> Dict[str, Any]:
    # 加载数据
    adata = self._load_adata(file_id, file_path)
    # 获取空间坐标
    if 'spatial' in adata.obsm:
        coords = adata.obsm['spatial']
        x_coords = coords[:, 0]
        y_coords = coords[:, 1]
    elif 'x' in adata.obs.columns and 'y' in adata.obs.columns:
        x_coords = adata.obs['x'].values
        y_coords = adata.obs['y'].values
    # 构建 spots 数据
    spots = []
    for idx in range(len(x_coords)):
        spot_data = {
            "id": str(adata.obs_names[idx]),
            "x": float(x_coords[idx]),
            "y": float(y_coords[idx]),
            "group": {...}  # 包含所有 obs 属性
        }
        spots.append(spot_data)
    return {"spots": spots, "totalCount": len(spots)}
```

**实现要点**：

- 支持两种坐标存储方式：`obsm['spatial']` 或 `obs` 中的 x、y 列
- 提取每个 Spot 的位置信息和元数据
- 处理数据类型转换，确保可序列化

### 3. 基因表达分析

#### 3.1 基因列表获取

**核心代码**：`SpatialService.get_gene_list` 方法

```python
def get_gene_list(self, file_id: str, user_id: str, query: Optional[str] = None) -> List[str]:
    # 加载数据并规范化基因名称
    adata = self._load_adata(file_id, file_path)
    adata = self._normalize_adata_names(adata)
    # 去重处理
    gene_names = list(adata.var_names)
    unique_genes = []
    # 应用查询过滤
    if query:
        result_genes = [g for g in result_genes if query.lower() in str(g).lower()]
    return sorted([str(g) for g in result_genes])
```

**实现要点**：

- 处理重复基因名称
- 支持基因名称查询过滤
- 确保返回唯一且排序的基因列表

#### 3.2 基因表达值获取

**核心代码**：`SpatialService.get_gene_expression` 方法

```python
def get_gene_expression(self, file_id: str, gene_name: str, user_id: str) -> List[Dict[str, Any]]:
    # 加载数据
    adata = self._load_adata(file_id, file_path)
    # 检查基因是否存在
    if gene_name not in adata.var_names:
        raise HTTPException(status_code=404, detail=f"基因 {gene_name} 不存在")
    # 获取表达值
    gene_idx = adata.var_names.get_loc(gene_name)
    gene_vector = adata.X[:, gene_idx]
    # 转换为密集数组
    if sparse.issparse(gene_vector):
        expr_values = gene_vector.toarray().flatten()
    else:
        expr_values = gene_vector.flatten()
    # 构建结果
    expression_data = [
        {"spotId": str(spot_id), "value": float(value)}
        for spot_id, value in zip(adata.obs_names, expr_values)
    ]
    return expression_data
```

**实现要点**：

- 支持稀疏矩阵和密集矩阵
- 处理基因不存在的情况
- 批量构建结果，提高效率

### 4. 数据质量控制

**核心代码**：`SpatialService.query_raw_qc` 方法

```python
def query_raw_qc(self, file_id: str, user_id: str, genes: List[str], max_cells: int = 2000) -> Dict[str, Any]:
    # 加载数据
    adata = self._load_adata(file_id, file_path)
    # 基因匹配
    genes_found = [g for g in genes if g in adata.var_names]
    # 细胞采样
    cell_indices = list(range(min(max_cells, adata.n_obs)))
    # 计算 QC 指标
    qc = {
        "counts": self._compute_counts(adata, cell_indices),
        "n_genes": self._compute_n_genes(adata, cell_indices),
        "pct_mt": self._compute_pct_mt(adata, cell_indices)
    }
    # 返回结果
    return {
        "meta": {...},
        "qc": qc,
        "cells": [...],
        "genes": genes_found,
        "expression": expr,
        "coords": coords
    }
```

**实现要点**：

- 支持基因筛选和细胞采样
- 计算总计数、基因数、线粒体基因比例等 QC 指标
- 提供降维坐标（UMAP、PCA、t-SNE）

## 三、前端可视化实现

### 1. API 调用流程

前端通过以下 API 接口获取数据：

| API 端点                         | 功能         | 数据返回格式                                                                      |
| :----------------------------- | :--------- | :-------------------------------------------------------------------------- |
| `/api/spatial/slices`          | 获取切片列表     | `[{"id": "slice1", "name": "切片 1", ...}]`                                   |
| `/api/spatial/slice-image`     | 获取切片图像     | `{"imageUrl": "data:image/png;base64,...", "width": 1000, "height": 800}`   |
| `/api/spatial/spots`           | 获取 Spot 位置 | `{"spots": [{"id": "spot1", "x": 100, "y": 200, ...}], "totalCount": 1000}` |
| `/api/spatial/spot-details`    | 获取 Spot 详情 | `{"id": "spot1", "x": 100, "y": 200, "cluster": "A", "topGenes": [...]}`    |
| `/api/spatial/gene-list`       | 获取基因列表     | `["TP53", "EGFR", ...]`                                                     |
| `/api/spatial/gene-expression` | 获取基因表达     | `[{"spotId": "spot1", "value": 10.5}, ...]`                                 |
| `/api/spatial/query-raw-qc`    | 获取 QC 数据   | `{"meta": {...}, "qc": {...}, ...}`                                         |

### 2. 前端渲染技术

前端通常使用以下技术实现空间可视化：

1. **图像渲染**：
   - 使用 `<img>` 标签加载 base64 编码的图像
   - 或使用 Canvas 进行自定义渲染
2. **Spot 绘制**：
   - 使用 SVG 或 Canvas 绘制 Spot
   - 根据基因表达值调整 Spot 颜色和大小
   - 支持交互（悬停显示详情）
3. **数据可视化库**：
   - **Plotly.js**：用于交互式散点图和热图
   - **D3.js**：用于自定义空间布局
   - **React/Vue 组件**：封装可视化逻辑
4. **交互功能**：
   - 缩放和平移
   - 点击 Spot 查看详情
   - 基因选择和表达映射
   - 聚类结果可视化

## 四、分析功能实现

### 1. 空间聚类分析

**实现步骤**：

1. 前端获取 Spot 位置和聚类信息
2. 根据聚类结果为 Spot 着色
3. 提供聚类图例和筛选功能

### 2. 基因表达空间分布

**实现步骤**：

1. 前端选择基因
2. 调用 `/api/spatial/gene-expression` 获取表达值
3. 根据表达值为 Spot 着色（热图）
4. 提供颜色比例尺和阈值调整

### 3. 差异表达分析

**实现步骤**：

1. 前端选择两个区域或聚类
2. 后端计算差异表达基因
3. 前端展示差异基因列表和表达热图

### 4. 通路富集分析

**实现步骤**：

1. 前端选择感兴趣的基因集
2. 后端进行通路富集分析
3. 前端展示富集结果和通路网络图

## 五、技术优势与优化

### 1. 性能优化

- **数据缓存**：缓存已加载的 AnnData 对象
- **数据压缩**：使用 base64 编码和适当的图像分辨率
- **批量处理**：批量构建结果，减少 API 调用
- **数据采样**：对大型数据集进行细胞采样，提高前端渲染速度

### 2. 可靠性

- **错误处理**：优雅处理各种异常情况
- **兼容性**：支持多种数据格式和存储方式
- **容错机制**：当某些数据缺失时提供默认值

### 3. 可扩展性

- **模块化设计**：分离数据处理和可视化逻辑
- **插件架构**：支持添加新的分析方法和可视化组件
- **API 设计**：RESTful API 便于集成和扩展

## 六、示例工作流程

1. **用户上传空间转录组数据**（h5ad 文件）
2. **系统加载数据**：`SpatialService._load_adata`
3. **前端获取切片信息**：调用 `/api/spatial/slices`
4. **前端渲染切片图像**：调用 `/api/spatial/slice-image`
5. **前端获取 Spot 位置**：调用 `/api/spatial/spots`
6. **用户选择基因**：前端展示基因列表（`/api/spatial/gene-list`）
7. **前端渲染基因表达**：调用 `/api/spatial/gene-expression`，根据表达值着色
8. **用户查看 Spot 详情**：点击 Spot，调用 `/api/spatial/spot-details`
9. **系统提供 QC 分析**：调用 `/api/spatial/query-raw-qc`

## 总结

textMSA 项目通过 **分层架构** 实现了空间转录组数据的可视化和分析：

- **数据层**：使用 AnnData 存储和处理数据
- **服务层**：`SpatialService` 提供数据提取和处理功能
- **API 层**：暴露 RESTful 接口供前端调用
- **前端层**：使用现代前端技术实现交互式可视化

这种设计不仅实现了复杂的空间数据可视化，还提供了强大的分析功能，为研究人员探索空间转录组数据提供了直观、高效的工具。

<br />

