#!/bin/bash
# R 环境设置脚本

set -e

echo "正在设置 R 环境..."

# 检查 conda 是否可用
if ! command -v conda &> /dev/null; then
    echo "错误: conda 未找到。请先安装 conda 或使用系统 R。"
    exit 1
fi

# 创建或激活 conda 环境
ENV_NAME="r_data_export"

if conda env list | grep -q "^${ENV_NAME} "; then
    echo "环境 ${ENV_NAME} 已存在，正在激活..."
    eval "$(conda shell.bash hook)"
    conda activate ${ENV_NAME}
else
    echo "创建新的 conda 环境: ${ENV_NAME}"
    conda create -n ${ENV_NAME} -y -c conda-forge r-base r-essentials
    eval "$(conda shell.bash hook)"
    conda activate ${ENV_NAME}
    
    echo "安装 R 包..."
    Rscript -e "install.packages(c('devtools', 'httr'), repos='https://cran.rstudio.com/')"
fi

echo "R 环境设置完成！"
echo "使用方法: conda activate ${ENV_NAME}"

