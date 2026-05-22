#!/usr/bin/env Rscript
# NicheNet 数据导出脚本
# 从 NicheNet R 包中导出配体-受体和配体-靶基因数据

# 设置用户库路径
user_lib <- Sys.getenv("R_LIBS_USER")
if (user_lib == "") {
    user_lib <- file.path(Sys.getenv("HOME"), "R", paste0("R-", R.version$major, ".", R.version$minor))
    dir.create(user_lib, recursive = TRUE, showWarnings = FALSE)
    .libPaths(c(user_lib, .libPaths()))
}

# 检查并安装必要的包
if (!requireNamespace("devtools", quietly = TRUE)) {
    cat("正在安装 devtools 包...\n")
    install.packages("devtools", repos = "https://cran.rstudio.com/", lib = user_lib)
}

# 安装 NicheNet（如果未安装）
if (!requireNamespace("nichenetr", quietly = TRUE)) {
    cat("正在安装 NicheNet 包...\n")
    library(devtools)
    install_github("saeyslab/nichenetr", quiet = TRUE)
}

# 加载 NicheNet
library(nichenetr)

# 设置输出目录
output_dir <- "data/nichenet"
if (!dir.exists(output_dir)) {
    dir.create(output_dir, recursive = TRUE)
}

cat("正在导出 NicheNet 数据...\n")

# 1. 导出配体-受体网络
cat("导出配体-受体网络...\n")
tryCatch({
    # 尝试从在线资源加载
    lr_network_url <- "https://zenodo.org/record/3260758/files/lr_network.rds"
    lr_network <- readRDS(url(lr_network_url))
    cat("从在线资源加载配体-受体网络成功\n")
}, error = function(e) {
    # 如果在线加载失败，尝试从包中加载
    cat("在线加载失败，尝试从包中加载...\n")
    tryCatch({
        data("lr_network", package = "nichenetr")
        cat("从包中加载配体-受体网络成功\n")
    }, error = function(e2) {
        cat("警告: 无法加载配体-受体网络\n")
        lr_network <- NULL
    })
})

if (!is.null(lr_network)) {
    # 确保列名正确
    if ("from" %in% colnames(lr_network) && "to" %in% colnames(lr_network)) {
        # 重命名列以匹配导入脚本的期望
        colnames(lr_network)[colnames(lr_network) == "from"] <- "ligand"
        colnames(lr_network)[colnames(lr_network) == "to"] <- "receptor"
    }
    
    output_file_lr <- file.path(output_dir, "nichenet_ligand_receptor.csv")
    write.csv(lr_network, output_file_lr, row.names = FALSE)
    cat(sprintf("配体-受体网络已导出到: %s (%d 条记录)\n", output_file_lr, nrow(lr_network)))
} else {
    cat("警告: 配体-受体网络为空，跳过导出\n")
}

# 2. 导出配体-靶基因矩阵
cat("导出配体-靶基因矩阵...\n")
tryCatch({
    # 尝试从在线资源加载
    ligand_target_url <- "https://zenodo.org/record/3260758/files/ligand_target_matrix.rds"
    ligand_target_matrix <- readRDS(url(ligand_target_url))
    cat("从在线资源加载配体-靶基因矩阵成功\n")
}, error = function(e) {
    # 如果在线加载失败，尝试从包中加载
    cat("在线加载失败，尝试从包中加载...\n")
    tryCatch({
        data("ligand_target_matrix", package = "nichenetr")
        cat("从包中加载配体-靶基因矩阵成功\n")
    }, error = function(e2) {
        cat("警告: 无法加载配体-靶基因矩阵\n")
        ligand_target_matrix <- NULL
    })
})

if (!is.null(ligand_target_matrix)) {
    # 转换为数据框格式（第一列为配体，后续列为靶基因）
    # 将矩阵转换为长格式
    cat("转换配体-靶基因矩阵格式...\n")
    
    # 方法1: 导出为矩阵格式（制表符分隔）
    output_file_lt_matrix <- file.path(output_dir, "nichenet_ligand_target_matrix.txt")
    write.table(ligand_target_matrix, output_file_lt_matrix, sep = "\t", quote = FALSE, row.names = TRUE, col.names = TRUE)
    cat(sprintf("配体-靶基因矩阵已导出到: %s (维度: %d x %d)\n", 
                output_file_lt_matrix, nrow(ligand_target_matrix), ncol(ligand_target_matrix)))
    
    # 方法2: 导出为长格式（仅非零值，节省空间）
    cat("导出配体-靶基因长格式数据...\n")
    ligand_target_long <- as.data.frame(as.table(as.matrix(ligand_target_matrix)))
    colnames(ligand_target_long) <- c("ligand", "target", "weight")
    # 只保留非零值
    ligand_target_long <- ligand_target_long[ligand_target_long$weight > 0, ]
    
    output_file_lt_long <- file.path(output_dir, "nichenet_ligand_target_long.txt")
    write.table(ligand_target_long, output_file_lt_long, sep = "\t", quote = FALSE, row.names = FALSE)
    cat(sprintf("配体-靶基因长格式数据已导出到: %s (%d 条记录)\n", 
                output_file_lt_long, nrow(ligand_target_long)))
} else {
    cat("警告: 配体-靶基因矩阵为空，跳过导出\n")
}

cat("NicheNet 数据导出完成！\n")

