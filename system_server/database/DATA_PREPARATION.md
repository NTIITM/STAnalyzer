# 数据准备指南

本指南说明如何准备 CellChat 和 NicheNet 的数据文件，以便导入到 MongoDB 数据库中。

## CellChat 数据准备

### 方法 1：从 R 包中导出（推荐）

1. **安装 CellChat R 包**（如果尚未安装）：
```r
if (!requireNamespace("CellChat", quietly = TRUE)) {
    install.packages("devtools")
    devtools::install_github("sqjin/CellChat")
}
```

2. **加载 CellChat 并导出数据**：
```r
library(CellChat)

# 加载人类数据库（或使用 CellChatDB.mouse 获取小鼠数据）
CellChatDB <- CellChatDB.human

# 提取配体-受体相互作用数据
interactions <- CellChatDB$interaction

# 导出为 CSV 文件
write.csv(interactions, "cellchat_interactions.csv", row.names = FALSE)
```

3. **导入到数据库**：
```bash
python -m database.import_cellchat --import --csv-file cellchat_interactions.csv
```

### 数据格式要求

CSV 文件应包含以下列（至少需要 `ligand` 和 `receptor`）：

- `ligand`: 配体基因名（必需）
- `receptor`: 受体基因名（必需，可以是复合物，用 `_` 或 `+` 分隔）
- `pathway_name`: 信号通路名称（可选）
- `annotation`: 功能注释（可选）
- `species`: 物种信息（可选，'human' 或 'mouse'）

### 示例数据格式

```csv
ligand,receptor,pathway_name,annotation,species
CXCL12,CXCR4,Chemokine,Chemotaxis / Migration,human
EGF,EGFR,Growth,Proliferation,human
VEGFA,KDR,Angiogenesis,Endothelial activation,human
```

---

## NicheNet 数据准备

### 方法 1：从 R 包中导出（推荐）

1. **安装 NicheNet R 包**（如果尚未安装）：
```r
if (!requireNamespace("nichenetr", quietly = TRUE)) {
    install.packages("devtools")
    devtools::install_github("saeyslab/nichenetr")
}
```

2. **加载 NicheNet 数据并导出**：

#### 导出配体-靶基因矩阵

```r
library(nichenetr)

# 从在线资源加载（推荐）
ligand_target_matrix <- readRDS(url("https://zenodo.org/record/3260758/files/ligand_target_matrix.rds"))

# 或者从已安装的包中加载
# data("ligand_target_matrix")

# 导出为制表符分隔的文本文件
write.table(ligand_target_matrix, "nichenet_ligand_target.txt", sep="\t", quote=FALSE)
```

#### 导出配体-受体网络

```r
# 从在线资源加载
lr_network <- readRDS(url("https://zenodo.org/record/3260758/files/lr_network.rds"))

# 或者从已安装的包中加载
# data("lr_network")

# 导出为 CSV 文件
write.csv(lr_network, "nichenet_ligand_receptor.csv", row.names = FALSE)
```

3. **导入到数据库**：

```bash
# 导入配体-靶基因数据
python -m database.import_nichenet --import \
    --ligand-target-file nichenet_ligand_target.txt \
    --data-type ligand_target

# 导入配体-受体数据
python -m database.import_nichenet --import \
    --ligand-receptor-file nichenet_ligand_receptor.csv \
    --data-type ligand_receptor

# 或者同时导入两种数据
python -m database.import_nichenet --import \
    --ligand-target-file nichenet_ligand_target.txt \
    --ligand-receptor-file nichenet_ligand_receptor.csv \
    --data-type both
```

### 数据格式要求

#### 配体-靶基因矩阵格式

- **文件格式**: 制表符分隔的文本文件（.txt）
- **结构**: 矩阵格式
  - 第一列：配体基因名（作为行名）
  - 后续列：靶基因名（作为列名）
  - 值：权重/置信度分数（数值）

示例：
```
ligand    GENE1    GENE2    GENE3
CXCL12    0.85     0.72     0.91
VEGFA     0.78     0.65     0.88
```

#### 配体-受体网络格式

- **文件格式**: CSV 文件
- **必需列**:
  - `from` 或 `ligand`: 配体基因名
  - `to` 或 `receptor`: 受体基因名
- **可选列**: 权重、置信度等

示例：
```csv
from,to,weight
CXCL12,CXCR4,0.95
VEGFA,KDR,0.92
```

---

## 验证导入的数据

导入完成后，验证数据：

```bash
# 验证 CellChat 数据
python -m database.import_cellchat --validate

# 验证 NicheNet 数据
python -m database.import_nichenet --validate
```

## 加载到内存缓存

如果数据量较小（< 5GB），可以加载到内存缓存以提高查询性能：

```bash
# CellChat
python -m database.import_cellchat --cache-memory

# NicheNet
python -m database.import_nichenet --cache-memory
```

---

## 注意事项

1. **数据来源**: CellChat 和 NicheNet 的数据主要通过 R 包提供，建议从 R 环境中导出数据文件。

2. **数据格式**: 确保导出的文件格式正确，字段名称与脚本期望的一致。

3. **数据量**: NicheNet 的配体-靶基因矩阵可能非常大，导入过程可能需要较长时间。

4. **重复数据**: 脚本会自动处理重复的配体-受体对（基于唯一索引）。

5. **物种信息**: 如果数据中没有明确的物种信息，默认会标记为 `both`（人类和小鼠通用）。

---

## 故障排除

### CellChat 数据导入失败

- 检查 CSV 文件是否包含 `ligand` 和 `receptor` 列
- 确保文件编码为 UTF-8 或 Latin-1
- 检查受体复合物是否正确分隔（使用 `_` 或 `+`）

### NicheNet 数据导入失败

- 配体-靶基因矩阵：确保是制表符分隔，第一列为配体
- 配体-受体网络：确保包含 `from` 和 `to` 列（或 `ligand` 和 `receptor`）
- 检查文件大小，大文件可能需要更多内存

### 数据库连接问题

- 确保 MongoDB 服务正在运行
- 检查配置文件中的连接字符串
- 确保有足够的磁盘空间存储数据

