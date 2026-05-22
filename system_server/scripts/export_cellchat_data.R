#!/usr/bin/env Rscript
# CellChat 数据导出脚本
# 从 CellChat R 包中导出配体-受体相互作用数据

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

# 安装 CellChat（如果未安装）
if (!requireNamespace("CellChat", quietly = TRUE)) {
    cat("正在安装 CellChat 包...\n")
    library(devtools)
    install_github("sqjin/CellChat", quiet = TRUE)
}

# 加载 CellChat
library(CellChat)

# 设置输出目录
output_dir <- "data/cellchat"
if (!dir.exists(output_dir)) {
    dir.create(output_dir, recursive = TRUE)
}

cat("正在导出 CellChat 数据...\n")

# 导出人类数据
cat("导出人类数据...\n")
CellChatDB.human <- CellChatDB.human
interactions_human <- CellChatDB.human$interaction

# 添加物种信息
if (!"species" %in% colnames(interactions_human)) {
    interactions_human$species <- "human"
}

# 导出为 CSV
output_file_human <- file.path(output_dir, "cellchat_interactions_human.csv")
write.csv(interactions_human, output_file_human, row.names = FALSE)
cat(sprintf("人类数据已导出到: %s (%d 条记录)\n", output_file_human, nrow(interactions_human)))

# 导出小鼠数据（如果可用）
if (exists("CellChatDB.mouse")) {
    cat("导出小鼠数据...\n")
    CellChatDB.mouse <- CellChatDB.mouse
    interactions_mouse <- CellChatDB.mouse$interaction
    
    # 添加物种信息
    if (!"species" %in% colnames(interactions_mouse)) {
        interactions_mouse$species <- "mouse"
    }
    
    # 导出为 CSV
    output_file_mouse <- file.path(output_dir, "cellchat_interactions_mouse.csv")
    write.csv(interactions_mouse, output_file_mouse, row.names = FALSE)
    cat(sprintf("小鼠数据已导出到: %s (%d 条记录)\n", output_file_mouse, nrow(interactions_mouse)))
}

# 合并数据（可选）
cat("合并人类和小鼠数据...\n")
all_interactions <- interactions_human
if (exists("interactions_mouse")) {
    all_interactions <- rbind(interactions_human, interactions_mouse)
}

output_file_all <- file.path(output_dir, "cellchat_interactions_all.csv")
write.csv(all_interactions, output_file_all, row.names = FALSE)
cat(sprintf("合并数据已导出到: %s (%d 条记录)\n", output_file_all, nrow(all_interactions)))

cat("CellChat 数据导出完成！\n")

