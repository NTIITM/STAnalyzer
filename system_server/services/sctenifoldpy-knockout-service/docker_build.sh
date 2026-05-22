#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="sctenifoldpy-knockout-service"
docker build -t "${IMAGE_NAME}:latest" .

