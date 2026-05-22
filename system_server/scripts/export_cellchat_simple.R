#!/usr/bin/env Rscript
# CellChat 数据导出脚本（简化版 - 使用在线数据源）

# 设置输出目录
output_dir <- "data/cellchat"
if (!dir.exists(output_dir)) {
    dir.create(output_dir, recursive = TRUE)
}

cat("正在尝试导出 CellChat 数据...\n")

# 方法1: 尝试加载已安装的包
if (requireNamespace("CellChat", quietly = TRUE)) {
    cat("使用已安装的 CellChat 包...\n")
    library(CellChat)
    
    CellChatDB.human <- CellChatDB.human
    interactions_human <- CellChatDB.human$interaction
    
    if (!"species" %in% colnames(interactions_human)) {
        interactions_human$species <- "human"
    }
    
    output_file <- file.path(output_dir, "cellchat_interactions_human.csv")
    write.csv(interactions_human, output_file, row.names = FALSE)
    cat(sprintf("数据已导出到: %s (%d 条记录)\n", output_file, nrow(interactions_human)))
    quit(status = 0)
}

# 方法2: 尝试从 GitHub 直接下载数据
cat("尝试从 GitHub 下载 CellChat 数据...\n")
tryCatch({
    if (!requireNamespace("httr", quietly = TRUE)) {
        install.packages("httr", repos = "https://cran.rstudio.com/", lib = "~/R/x86_64-pc-linux-gnu-library/4.1")
    }
    library(httr)
    
    # 尝试从 CellChat GitHub 仓库下载数据
    url <- "https://raw.githubusercontent.com/sqjin/CellChat/master/data/CellChatDB.human.rda"
    temp_file <- tempfile(fileext = ".rda")
    download.file(url, temp_file, quiet = TRUE)
    
    # 加载数据
    load(temp_file)
    if (exists("CellChatDB.human")) {
        interactions_human <- CellChatDB.human$interaction
        if (!"species" %in% colnames(interactions_human)) {
            interactions_human$species <- "human"
        }
        
        output_file <- file.path(output_dir, "cellchat_interactions_human.csv")
        write.csv(interactions_human, output_file, row.names = FALSE)
        cat(sprintf("数据已导出到: %s (%d 条记录)\n", output_file, nrow(interactions_human)))
        quit(status = 0)
    }
}, error = function(e) {
    cat(sprintf("从 GitHub 下载失败: %s\n", e$message))
})

cat("错误: 无法获取 CellChat 数据。请手动安装 CellChat 包或提供数据文件。\n")
cat("安装命令: Rscript -e \"devtools::install_github('sqjin/CellChat')\"\n")
quit(status = 1)

