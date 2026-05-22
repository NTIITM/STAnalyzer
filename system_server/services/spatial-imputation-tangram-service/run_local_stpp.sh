#!/usr/bin/env bash
set -euo pipefail

# 在本地 conda 环境（默认 stpp）下启动 Tangram 服务
# 使用方法：
#   ENV_NAME=stpp bash run_local_stpp.sh
# 需要已安装 conda，并在 env 中具备 gcc/g++（用于 torch/scanpy 等）。

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_NAME="${ENV_NAME:-stpp}"
PORT="${PORT:-60890}"

if ! command -v conda >/dev/null 2>&1; then
  echo "conda 未安装，退出。" >&2
  exit 1
fi

# shellcheck disable=SC1091
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "${ENV_NAME}"

echo "正在安装 Python 依赖到环境 ${ENV_NAME} ..."
pip install -r "${ROOT_DIR}/requirements.txt"

cd "${ROOT_DIR}"
export OUTPUT_DIR="${ROOT_DIR}/outputs"
mkdir -p "${OUTPUT_DIR}"

echo "启动 uvicorn 于 0.0.0.0:${PORT}（环境：${ENV_NAME}，输出目录：${OUTPUT_DIR}）"
exec uvicorn main:app --host 0.0.0.0 --port "${PORT}"

