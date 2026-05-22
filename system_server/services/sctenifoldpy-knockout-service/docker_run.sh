#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="sctenifoldpy-knockout-service"
docker run --rm -it \
  -p 44030:44030 \
  -e OUTPUT_DIR=/app/outputs \
  -e LOG_LEVEL=INFO \
  -v "$(pwd)/outputs:/app/outputs" \
  "${IMAGE_NAME}:latest"

