#!/usr/bin/env Rscript
# 网络图绘图脚本（用于SpaOTsc风格）
# 用法: Rscript plot_network.R <centroids_csv> <edges_csv> <output_png> <title> [width] [height]

args <- commandArgs(trailingOnly = TRUE)

if (length(args) < 4) {
    stop("用法: Rscript plot_network.R <centroids_csv> <edges_csv> <output_png> <title> [width] [height]")
}

centroids_csv <- args[1]
edges_csv <- args[2]
output_png <- args[3]
title <- args[4]
width <- if (length(args) >= 5) as.numeric(args[5]) else 6
height <- if (length(args) >= 6) as.numeric(args[6]) else 6

# 加载必要的库
if (!requireNamespace("ggplot2", quietly = TRUE)) {
    install.packages("ggplot2", repos = "https://cran.rstudio.com/")
}
if (!requireNamespace("rlang", quietly = TRUE)) {
    install.packages("rlang", repos = "https://cran.rstudio.com/")
}

library(ggplot2)
library(rlang)

# 读取数据
centroids <- read.csv(centroids_csv, check.names = FALSE)
edges <- read.csv(edges_csv, check.names = FALSE)

# 绘制网络图
p <- ggplot() +
    # 绘制边
    geom_segment(
        data = edges,
        aes(x = x1, y = y1, xend = x2, yend = y2, linewidth = weight),
        color = "orangered",
        alpha = 0.6
    ) +
    # 绘制节点
    geom_point(
        data = centroids,
        aes(x = x, y = y),
        size = 8,
        color = "steelblue",
        fill = "steelblue"
    ) +
    # 添加标签
    geom_text(
        data = centroids,
        aes(x = x, y = y, label = label),
        color = "white",
        size = 3,
        fontface = "bold"
    ) +
    labs(title = title, x = "X", y = "Y") +
    theme_minimal() +
    theme(
        plot.title = element_text(size = 14, face = "bold", hjust = 0.5),
        legend.position = "none"
    )

ggsave(output_png, plot = p, width = width, height = height, dpi = 300, units = "in")

cat(sprintf("网络图已保存到: %s\n", output_png))

