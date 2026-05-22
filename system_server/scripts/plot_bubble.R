#!/usr/bin/env Rscript
# 气泡图绘图脚本
# 用法: Rscript plot_bubble.R <input_csv> <output_png> <x_col> <y_col> <size_col> <color_col> <title> [width] [height]

args <- commandArgs(trailingOnly = TRUE)

if (length(args) < 7) {
    stop("用法: Rscript plot_bubble.R <input_csv> <output_png> <x_col> <y_col> <size_col> <color_col> <title> [width] [height]")
}

input_csv <- args[1]
output_png <- args[2]
x_col <- args[3]
y_col <- args[4]
size_col <- args[5]
color_col <- args[6]
title <- args[7]
width <- if (length(args) >= 8) as.numeric(args[8]) else 8
height <- if (length(args) >= 9) as.numeric(args[9]) else 6

# 加载必要的库
if (!requireNamespace("ggplot2", quietly = TRUE)) {
    install.packages("ggplot2", repos = "https://cran.rstudio.com/")
}
if (!requireNamespace("rlang", quietly = TRUE)) {
    install.packages("rlang", repos = "https://cran.rstudio.com/")
}
if (!requireNamespace("viridis", quietly = TRUE)) {
    install.packages("viridis", repos = "https://cran.rstudio.com/")
}

library(ggplot2)
library(rlang)
library(viridis)

# 读取数据
data <- read.csv(input_csv, check.names = FALSE)

# 确保列存在
if (!x_col %in% colnames(data)) stop(sprintf("列 '%s' 不存在", x_col))
if (!y_col %in% colnames(data)) stop(sprintf("列 '%s' 不存在", y_col))
if (!size_col %in% colnames(data)) stop(sprintf("列 '%s' 不存在", size_col))
if (!color_col %in% colnames(data)) stop(sprintf("列 '%s' 不存在", color_col))

# 绘制气泡图
# 使用aes()和sym()替代已弃用的aes_string()
library(rlang)
p <- ggplot(data, aes(x = !!sym(x_col), y = !!sym(y_col), size = !!sym(size_col), color = !!sym(color_col))) +
    geom_point(alpha = 0.7) +
    scale_size_continuous(range = c(2, 15), name = size_col) +
    scale_color_viridis_c(name = color_col) +
    labs(title = title, x = x_col, y = y_col) +
    theme_minimal() +
    theme(
        plot.title = element_text(size = 14, face = "bold", hjust = 0.5),
        axis.text.x = element_text(angle = 45, hjust = 1),
        legend.position = "right"
    )

ggsave(output_png, plot = p, width = width, height = height, dpi = 300, units = "in")

cat(sprintf("气泡图已保存到: %s\n", output_png))

