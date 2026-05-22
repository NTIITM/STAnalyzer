#!/bin/bash
# 从 Zenodo 下载 NicheNet 数据

set -e

OUTPUT_DIR="data/nichenet"
mkdir -p "$OUTPUT_DIR"

echo "正在从 Zenodo 下载 NicheNet 数据..."

# 激活 conda 环境
eval "$(conda shell.bash hook)"
conda activate r_env

# 下载配体-受体网络
echo "下载配体-受体网络..."
Rscript -e "
library(httr)
lr_url <- 'https://zenodo.org/record/3260758/files/lr_network.rds'
lr_file <- file.path('$OUTPUT_DIR', 'lr_network.rds')
download.file(lr_url, lr_file, mode = 'wb', quiet = TRUE)
lr_network <- readRDS(lr_file)
if ('from' %in% colnames(lr_network) && 'to' %in% colnames(lr_network)) {
    colnames(lr_network)[colnames(lr_network) == 'from'] <- 'ligand'
    colnames(lr_network)[colnames(lr_network) == 'to'] <- 'receptor'
}
write.csv(lr_network, '$OUTPUT_DIR/nichenet_ligand_receptor.csv', row.names = FALSE)
cat('配体-受体网络已导出: ', nrow(lr_network), ' 条记录\n', sep='')
"

# 下载配体-靶基因矩阵（仅下载，不转换，因为文件可能很大）
echo "下载配体-靶基因矩阵..."
Rscript -e "
library(httr)
lt_url <- 'https://zenodo.org/record/3260758/files/ligand_target_matrix.rds'
lt_file <- file.path('$OUTPUT_DIR', 'ligand_target_matrix.rds')
download.file(lt_url, lt_file, mode = 'wb', quiet = TRUE)
cat('配体-靶基因矩阵已下载到: ', lt_file, '\n', sep='')
"

# 转换配体-靶基因矩阵为文本格式（仅非零值）
echo "转换配体-靶基因矩阵..."
Rscript -e "
ligand_target_matrix <- readRDS('$OUTPUT_DIR/ligand_target_matrix.rds')
cat('矩阵维度: ', nrow(ligand_target_matrix), ' x ', ncol(ligand_target_matrix), '\n', sep='')

# 导出为矩阵格式
write.table(ligand_target_matrix, '$OUTPUT_DIR/nichenet_ligand_target_matrix.txt', 
            sep = '\t', quote = FALSE, row.names = TRUE, col.names = TRUE)
cat('矩阵格式已导出\n')

# 导出为长格式（仅非零值）
ligand_target_long <- as.data.frame(as.table(as.matrix(ligand_target_matrix)))
colnames(ligand_target_long) <- c('ligand', 'target', 'weight')
ligand_target_long <- ligand_target_long[ligand_target_long\$weight > 0, ]
write.table(ligand_target_long, '$OUTPUT_DIR/nichenet_ligand_target_long.txt', 
            sep = '\t', quote = FALSE, row.names = FALSE)
cat('长格式已导出: ', nrow(ligand_target_long), ' 条记录\n', sep='')
"

echo "NicheNet 数据导出完成！"

