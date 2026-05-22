#!/usr/bin/env Rscript
# 热图绘图脚本
# 用法: Rscript plot_heatmap.R <input_csv> <output_png> <title> [colormap] [width] [height]

args <- commandArgs(trailingOnly = TRUE)

if (length(args) < 3) {
    stop("用法: Rscript plot_heatmap.R <input_csv> <output_png> <title> [colormap] [width] [height]")
}

input_csv <- args[1]
output_png <- args[2]
title <- args[3]
colormap <- if (length(args) >= 4) args[4] else "YlGnBu"
width <- if (length(args) >= 5) as.numeric(args[5]) else 10
height <- if (length(args) >= 6) as.numeric(args[6]) else 8

# 加载必要的库
if (!requireNamespace("pheatmap", quietly = TRUE)) {
    install.packages("pheatmap", repos = "https://cran.rstudio.com/")
}
if (!requireNamespace("viridis", quietly = TRUE)) {
    install.packages("viridis", repos = "https://cran.rstudio.com/")
}

library(pheatmap)
library(viridis)

# 读取数据
data <- read.csv(input_csv, row.names = 1, check.names = FALSE)

# 转换为数值矩阵
data_matrix <- as.matrix(data)
data_matrix[is.na(data_matrix)] <- 0

# 检查数据有效性
if (nrow(data_matrix) == 0 || ncol(data_matrix) == 0) {
    stop("数据矩阵为空，无法绘制热图")
}

# 检查数据是否全为NaN或无效
valid_data <- data_matrix[!is.na(data_matrix) & is.finite(data_matrix)]
if (length(valid_data) == 0) {
    stop("数据矩阵全为NaN或无效值，无法绘制热图")
}

# 检查数据是否全为0或全相同
data_min <- min(valid_data)
data_max <- max(valid_data)

if (is.infinite(data_min) || is.infinite(data_max) || is.na(data_min) || is.na(data_max)) {
    stop("数据矩阵无效，无法绘制热图")
}

if (data_min == data_max) {
    # 如果所有值都相同
    if (data_min == 0) {
        # 如果全为0，创建一个简单的占位图
        png(output_png, width = width * 100, height = height * 100, res = 300, units = "px")
        par(mar = c(5, 5, 4, 2))
        image(matrix(0, nrow = nrow(data_matrix), ncol = ncol(data_matrix)), 
              col = "gray90", 
              main = paste0(title, "\n(所有值为0)"),
              xaxt = "n", yaxt = "n")
        dev.off()
        cat(sprintf("热图已保存到: %s (所有值为0，已生成占位图)\n", output_png))
        quit(status = 0)
    } else {
        # 如果所有值都相同但不为0，添加小的随机扰动以避免pheatmap错误
        set.seed(123)
        noise <- matrix(rnorm(length(data_matrix), mean = 0, sd = abs(data_min) * 0.001), 
                       nrow = nrow(data_matrix), ncol = ncol(data_matrix))
        data_matrix <- data_matrix + noise
        # 确保扰动后的数据仍然接近原值
        data_matrix[is.na(data_matrix)] <- data_min
    }
}

# 设置颜色映射
colormap_map <- list(
    "YlGnBu" = colorRampPalette(c("#FFFFCC", "#41B6C4", "#225EA8"))(100),
    "RdBu_r" = colorRampPalette(c("#2166AC", "#F7F7F7", "#B2182B"))(100),
    "coolwarm" = colorRampPalette(c("#3B4CC0", "#FFFFFF", "#B40426"))(100),
    "viridis" = viridis::viridis(100)
)

colors <- if (colormap %in% names(colormap_map)) {
    colormap_map[[colormap]]
} else {
    colormap_map[["YlGnBu"]]
}

# 绘制热图
# 使用pheatmap的filename参数直接保存文件，避免在无显示设备环境下png()+dev.off()不工作的问题
pheatmap(
    data_matrix,
    filename = output_png,
    color = colors,
    cluster_rows = FALSE,
    cluster_cols = FALSE,
    main = title,
    fontsize = 8,
    fontsize_row = 7,
    fontsize_col = 7,
    display_numbers = if (nrow(data_matrix) <= 20 && ncol(data_matrix) <= 20) TRUE else FALSE,
    number_format = "%.2f",
    silent = TRUE,
    width = width,
    height = height
)

cat(sprintf("热图已保存到: %s\n", output_png))

