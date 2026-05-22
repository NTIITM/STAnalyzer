#!/usr/bin/env bash
set -euo pipefail

# Tangram 官方教程数据下载脚本（MOp snRNAseq + Slide-seq2）
# 数据来源：
# https://storage.googleapis.com/tommaso-brain-data/tangram_demo/mop_sn_tutorial.h5ad.gz
# https://storage.googleapis.com/tommaso-brain-data/tangram_demo/slideseq_MOp_1217.h5ad.gz
# https://storage.googleapis.com/tommaso-brain-data/tangram_demo/MOp_markers.csv

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${ROOT_DIR}/data/without"
mkdir -p "${DATA_DIR}"

download() {
  local url="$1"
  local out="$2"
  if [[ -s "${out}" ]]; then
    echo "Skip existing ${out}"
    return
  fi
  echo "Downloading ${url} -> ${out}"
  curl -L --retry 3 --fail --output "${out}" "${url}"
}

download "https://storage.googleapis.com/tommaso-brain-data/tangram_demo/mop_sn_tutorial.h5ad.gz" "${DATA_DIR}/mop_sn_tutorial.h5ad.gz"
download "https://storage.googleapis.com/tommaso-brain-data/tangram_demo/slideseq_MOp_1217.h5ad.gz" "${DATA_DIR}/slideseq_MOp_1217.h5ad.gz"
download "https://storage.googleapis.com/tommaso-brain-data/tangram_demo/MOp_markers.csv" "${DATA_DIR}/MOp_markers.csv"

echo "Unzipping .gz files..."
gunzip -f "${DATA_DIR}/mop_sn_tutorial.h5ad.gz"
gunzip -f "${DATA_DIR}/slideseq_MOp_1217.h5ad.gz"

echo "Done. Files in ${DATA_DIR}:"
ls -lh "${DATA_DIR}"

