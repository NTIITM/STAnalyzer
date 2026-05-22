#!/usr/bin/env bash
set -euo pipefail

# 使用官方教程数据对本地服务进行一次调用，并保存响应
# 依赖：curl、已启动的服务（run_local_stpp.sh）

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST="${HOST:-http://localhost:60890}"
DATA_DIR="${ROOT_DIR}/data/without"
OUT_DIR="${ROOT_DIR}/outputs"

mkdir -p "${OUT_DIR}"

if [[ ! -f "${DATA_DIR}/slideseq_MOp_1217.h5ad" || ! -f "${DATA_DIR}/mop_sn_tutorial.h5ad" ]]; then
  echo "未找到示例数据，请先运行 download_mop_slideseq_data.sh" >&2
  exit 1
fi

echo "调用 ${HOST}/api/impute ..."
curl -X POST "${HOST}/api/impute" \
  -F "spatial_file=@${DATA_DIR}/slideseq_MOp_1217.h5ad" \
  -F "single_cell_file=@${DATA_DIR}/mop_sn_tutorial.h5ad" \
  -F "mode=cells" \
  -F "n_epochs=1000" \
  -F "learning_rate=0.005" \
  -F "lambda_dreg=5" \
  -F "top_genes=0" \
  -F "seed=1234" \
  --output "${OUT_DIR}/last_response.json" \
  --silent --show-error --fail

echo "响应已保存到 ${OUT_DIR}/last_response.json"
echo "可通过 data 字段的文件 id，调用 ${HOST}/api/download/{file_id} 获取图片与 h5ad"

