#!/usr/bin/env Rscript
# 堆叠柱状图绘图脚本
# 用法: Rscript plot_stacked_bar.R <input_csv> <output_png> <title> <x_col> <value_cols> [width] [height]
# value_cols: 逗号分隔的列名，如 "intrinsic,juxtacrine,paracrine"

args <- commandArgs(trailingOnly = TRUE)

if (length(args) < 5) {
    stop("用法: Rscript plot_stacked_bar.R <input_csv> <output_png> <title> <x_col> <value_cols> [width] [height]")
}

input_csv <- args[1]
output_png <- args[2]
title <- args[3]
x_col <- args[4]
value_cols_str <- args[5]
width <- if (length(args) >= 6) as.numeric(args[6]) else 8
height <- if (length(args) >= 7) as.numeric(args[7]) else 6

# 加载必要的库
if (!requireNamespace("ggplot2", quietly = TRUE)) {
    install.packages("ggplot2", repos = "https://cran.rstudio.com/")
}
if (!requireNamespace("tidyr", quietly = TRUE)) {
    install.packages("tidyr", repos = "https://cran.rstudio.com/")
}
if (!requireNamespace("dplyr", quietly = TRUE)) {
    install.packages("dplyr", repos = "https://cran.rstudio.com/")
}
if (!requireNamespace("rlang", quietly = TRUE)) {
    install.packages("rlang", repos = "https://cran.rstudio.com/")
}
if (!requireNamespace("viridis", quietly = TRUE)) {
    install.packages("viridis", repos = "https://cran.rstudio.com/")
}

library(ggplot2)
library(tidyr)
library(dplyr)
library(rlang)
library(viridis)

# 读取数据
data <- read.csv(input_csv, check.names = FALSE)

# 解析value_cols
value_cols <- strsplit(value_cols_str, ",")[[1]]
value_cols <- trimws(value_cols)

# 确保列存在
if (!x_col %in% colnames(data)) stop(sprintf("列 '%s' 不存在", x_col))
for (col in value_cols) {
    if (!col %in% colnames(data)) stop(sprintf("列 '%s' 不存在", col))
}

# 转换为长格式
data_long <- data %>%
    select(all_of(c(x_col, value_cols))) %>%
    pivot_longer(cols = all_of(value_cols), names_to = "category", values_to = "value")

# 绘制堆叠柱状图
p <- ggplot(data_long, aes(x = !!sym(x_col), y = value, fill = category)) +
    geom_bar(stat = "identity", position = "stack") +
    scale_fill_viridis_d(name = "Category") +
    labs(title = title, x = x_col, y = "Contribution weight") +
    theme_minimal() +
    theme(
        plot.title = element_text(size = 14, face = "bold", hjust = 0.5),
        axis.text.x = element_text(angle = 45, hjust = 1),
        legend.position = "right"
    ) +
    coord_flip()

ggsave(output_png, plot = p, width = width, height = height, dpi = 300, units = "in")

cat(sprintf("堆叠柱状图已保存到: %s\n", output_png))

