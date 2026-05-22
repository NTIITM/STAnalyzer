# R 数据导出脚本使用说明

本目录包含用于从 R 包中导出 CellChat 和 NicheNet 数据的脚本。

## 快速开始

### 方法 1: 使用下载脚本（推荐）

这些脚本直接从 GitHub/Zenodo 下载数据，无需安装 R 包：

```bash
# 导出 CellChat 数据
bash scripts/download_cellchat_data.sh

# 导出 NicheNet 数据
bash scripts/download_nichenet_data.sh
```

### 方法 2: 使用 R 脚本（需要安装 R 包）

如果已安装 CellChat 和 NicheNet R 包，可以使用 R 脚本：

```bash
# 激活 conda 环境（如果使用）
eval "$(conda shell.bash hook)"
conda activate r_env

# 导出 CellChat 数据
Rscript scripts/export_cellchat_data.R

# 导出 NicheNet 数据
Rscript scripts/export_nichenet_data.R
```

## 环境设置

### 使用 Conda 环境（推荐）

```bash
# 创建 R 环境
bash scripts/setup_r_env.sh

# 或手动创建
conda create -n r_data_export -y -c conda-forge r-base r-essentials
conda activate r_data_export
Rscript -e "install.packages(c('devtools', 'httr'), repos='https://cran.rstudio.com/')"
```

### 使用系统 R

如果系统已安装 R 和必要的系统依赖，可以直接使用：

```bash
Rscript scripts/export_cellchat_data.R
Rscript scripts/export_nichenet_data.R
```

## 脚本说明

### download_cellchat_data.sh
- **功能**: 直接从 GitHub 下载 CellChat 数据并转换为 CSV
- **输出**: `data/cellchat/cellchat_interactions_human.csv`
- **优点**: 无需安装 R 包，速度快

### download_nichenet_data.sh
- **功能**: 从 Zenodo 下载 NicheNet 数据
- **输出**: 
  - `data/nichenet/nichenet_ligand_receptor.csv` (配体-受体网络)
  - `data/nichenet/nichenet_ligand_target_matrix.txt` (配体-靶基因矩阵)
  - `data/nichenet/nichenet_ligand_target_long.txt` (配体-靶基因长格式)
- **优点**: 无需安装 R 包，包含完整数据

### export_cellchat_data.R
- **功能**: 从已安装的 CellChat R 包中导出数据
- **要求**: 需要安装 CellChat 包
- **安装**: `Rscript -e "devtools::install_github('sqjin/CellChat')"`

### export_nichenet_data.R
- **功能**: 从已安装的 NicheNet R 包中导出数据
- **要求**: 需要安装 nichenetr 包
- **安装**: `Rscript -e "devtools::install_github('saeyslab/nichenetr')"`

## 数据导入

导出数据后，使用 Python 脚本导入到 MongoDB：

```bash
# 导入 CellChat 数据
python -m database.import_cellchat --import \
    --csv-file data/cellchat/cellchat_interactions_human.csv \
    --validate

# 导入 NicheNet 配体-受体数据
python -m database.import_nichenet --import \
    --ligand-receptor-file data/nichenet/nichenet_ligand_receptor.csv \
    --data-type ligand_receptor \
    --validate

# 导入 NicheNet 配体-靶基因数据（可选，文件较大）
python -m database.import_nichenet --import \
    --ligand-target-file data/nichenet/nichenet_ligand_target_long.txt \
    --data-type ligand_target \
    --validate
```

## 当前数据统计

- **总记录数**: 15,425 条配体-受体对
- **CellChat**: 1,985 条
- **NicheNet**: 12,044 条
- **CellPhoneDB**: 1,396 条
- **唯一配体**: 1,413 个
- **唯一受体**: 1,514 个

## 故障排除

### GitHub API 速率限制

如果遇到 GitHub API 速率限制错误，使用下载脚本而不是 R 脚本：

```bash
bash scripts/download_cellchat_data.sh
```

### 系统依赖缺失

如果 R 包安装失败（如缺少 libcurl），使用 conda 环境：

```bash
conda create -n r_env -y -c conda-forge r-base r-essentials
conda activate r_env
```

### 数据文件过大

NicheNet 的配体-靶基因矩阵文件很大（约 1600 万条记录）。如果导入时间过长，可以：

1. 仅导入配体-受体网络（推荐）
2. 使用批量导入和进度条
3. 考虑使用内存缓存（如果数据量 < 5GB）

## 注意事项

1. **数据更新**: 数据源可能会更新，建议定期重新导出和导入
2. **存储空间**: NicheNet 数据文件较大，确保有足够的磁盘空间
3. **网络连接**: 下载脚本需要网络连接访问 GitHub 和 Zenodo
4. **权限**: 确保对输出目录有写权限

