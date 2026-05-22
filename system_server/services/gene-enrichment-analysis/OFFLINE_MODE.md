# 离线模式使用说明

## 概述

富集分析服务支持两种模式：
1. **在线模式**：使用 Enrichr API（需要网络连接）
2. **离线模式**：使用本地下载的 GMT 文件（无需网络连接）

默认情况下，服务会优先尝试使用本地文件，如果本地文件不可用，则回退到网络 API。

## 下载基因集库文件

### 使用下载脚本

运行下载脚本来下载常用的基因集库：

```bash
# 下载预定义的常用库（推荐）
python download_enrichr_libraries.py

# 下载所有可用的库（需要较长时间）
python download_enrichr_libraries.py --all

# 下载指定的库
python download_enrichr_libraries.py --libraries GO_Biological_Process_2021 KEGG_2021_Human

# 指定输出目录
python download_enrichr_libraries.py --output-dir /path/to/gmt

# 使用 JSON 格式（而不是 GMT 格式）
python download_enrichr_libraries.py --mode json
```

### 下载的文件位置

默认情况下，下载的文件保存在 `./gmt/` 目录下，文件格式为 `{库名}.gmt`。

例如：
- `GO_Biological_Process_2021.gmt`
- `KEGG_2021_Human.gmt`

## 配置离线模式

### 环境变量

通过设置环境变量来控制服务的行为：

```bash
# 优先使用本地文件（默认：true）
export USE_LOCAL_GMT=true

# GMT 文件目录（默认：./gmt）
export GMT_DIR=/path/to/gmt

# 输出目录
export OUTPUT_DIR=/path/to/outputs
```

### Docker 配置

在 `docker-compose.yml` 中添加环境变量：

```yaml
services:
  gene-enrichment-analysis:
    environment:
      - USE_LOCAL_GMT=true
      - GMT_DIR=/app/gmt
    volumes:
      - ./gmt:/app/gmt  # 挂载 GMT 文件目录
```

## 工作原理

1. **优先使用本地文件**：
   - 服务首先检查 `GMT_DIR` 目录下是否存在对应的 `.gmt` 文件
   - 如果存在，使用本地文件进行超几何检验富集分析
   - 结果格式与 Enrichr API 兼容

2. **回退到网络 API**：
   - 如果本地文件不存在或分析失败
   - 服务会自动回退到使用 Enrichr API（需要网络连接）

3. **完全离线模式**：
   - 设置 `USE_LOCAL_GMT=true` 且确保所有需要的库文件都已下载
   - 如果网络请求失败且没有本地文件，会抛出错误

## 支持的基因集库

### 常用库（预定义）

- **GO 数据库**：
  - `GO_Biological_Process_2021`
  - `GO_Cellular_Component_2021`
  - `GO_Molecular_Function_2021`
  - `GO_Biological_Process_2023`
  - `GO_Cellular_Component_2023`
  - `GO_Molecular_Function_2023`

- **KEGG 数据库**：
  - `KEGG_2021_Human`
  - `KEGG_2021_Mouse`
  - `KEGG_2019_Human`
  - `KEGG_2019_Mouse`

- **其他常用库**：
  - `Reactome_2022`
  - `WikiPathways_2021_Human`
  - `WikiPathways_2021_Mouse`
  - `MSigDB_Hallmark_2020`
  - 等等...

### 查看所有可用库

运行以下命令查看 Enrichr 上所有可用的库：

```bash
python download_enrichr_libraries.py --all --libraries ""  # 会列出所有库
```

或者访问：https://maayanlab.cloud/Enrichr/datasetStatistics

## 故障排除

### 问题：网络请求失败

**原因**：网络连接问题或 Enrichr API 不可用

**解决方案**：
1. 下载所需的基因集库到本地
2. 设置 `USE_LOCAL_GMT=true`
3. 确保 GMT 文件在正确的目录下

### 问题：本地文件分析失败

**原因**：GMT 文件格式错误或损坏

**解决方案**：
1. 重新下载 GMT 文件
2. 检查文件格式是否正确
3. 查看日志获取详细错误信息

### 问题：找不到库文件

**原因**：库名称不匹配或文件未下载

**解决方案**：
1. 检查库名称是否正确（区分大小写）
2. 确认文件已下载到 `GMT_DIR` 目录
3. 检查文件名格式：`{库名}.gmt`

## 性能说明

- **本地文件模式**：
  - 优点：无需网络连接，响应速度快
  - 缺点：需要预先下载文件，占用磁盘空间

- **网络 API 模式**：
  - 优点：无需预先下载，总是使用最新数据
  - 缺点：需要网络连接，可能受网络延迟影响

## 注意事项

1. GMT 文件可能较大（几十到几百 MB），确保有足够的磁盘空间
2. 下载所有库可能需要较长时间，建议只下载需要的库
3. 本地文件不会自动更新，如需最新数据，需要重新下载
4. 超几何检验的结果可能与 Enrichr API 的结果略有不同（由于背景基因集大小的估计）

