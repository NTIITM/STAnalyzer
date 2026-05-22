#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required but was not found in PATH" >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose is required but was not found" >&2
  exit 1
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

mkdir -p textMSA/runtime textMSA/logs system_server/logs

docker compose up -d --build

cat <<'MSG'

STAnalyzer deployment started.

Open:
MSG
printf '  Frontend:      http://localhost:%s/STAnalyzer/\n' "${FRONTEND_PORT:-8080}"
printf '  STAnalyzer API: http://localhost:%s/docs\n' "${TEXTMSA_API_PORT:-8000}"
printf '  system_server: http://localhost:%s/docs\n' "${SYSTEM_SERVER_PORT:-9000}"
cat <<'MSG'

Useful commands:
  docker compose ps
  docker compose logs -f textmsa-api
  docker compose down

MSG
