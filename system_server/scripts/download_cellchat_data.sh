#!/bin/bash
# 直接从 GitHub 下载 CellChat 数据

set -e

OUTPUT_DIR="data/cellchat"
mkdir -p "$OUTPUT_DIR"

echo "正在从 GitHub 下载 CellChat 数据..."

# 下载 CellChatDB.human.rda 文件
URL="https://github.com/sqjin/CellChat/raw/master/data/CellChatDB.human.rda"
TEMP_FILE=$(mktemp)
OUTPUT_FILE="$OUTPUT_DIR/CellChatDB.human.rda"

if command -v wget &> /dev/null; then
    wget -q "$URL" -O "$TEMP_FILE"
elif command -v curl &> /dev/null; then
    curl -sL "$URL" -o "$TEMP_FILE"
else
    echo "错误: 需要 wget 或 curl"
    exit 1
fi

if [ -f "$TEMP_FILE" ] && [ -s "$TEMP_FILE" ]; then
    mv "$TEMP_FILE" "$OUTPUT_FILE"
    echo "数据已下载到: $OUTPUT_FILE"
    
    # 使用 R 转换数据
    echo "正在转换数据格式..."
    eval "$(conda shell.bash hook)"
    conda activate r_env
    
    Rscript -e "
    load('$OUTPUT_FILE')
    if (exists('CellChatDB.human')) {
        interactions <- CellChatDB.human\$interaction
        if (!'species' %in% colnames(interactions)) {
            interactions\$species <- 'human'
        }
        write.csv(interactions, '$OUTPUT_DIR/cellchat_interactions_human.csv', row.names = FALSE)
        cat('数据已导出到: $OUTPUT_DIR/cellchat_interactions_human.csv (', nrow(interactions), ' 条记录)\n', sep='')
    } else {
        cat('错误: 无法从 RDA 文件中提取数据\n')
        quit(status=1)
    }
    "
    
    echo "CellChat 数据导出完成！"
else
    echo "错误: 下载失败"
    exit 1
fi

