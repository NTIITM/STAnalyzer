#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
#  stop_local_stack.sh
#  停止所有通过 start_local_stack.sh 启动的系统服务和 API Server
# -----------------------------------------------------------------------------

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEXTMSA_ROOT="$PROJECT_ROOT"
PID_DIR="$PROJECT_ROOT/logs/pids"
PYTHON_BIN="${PYTHON_BIN:-python3}"

export PYTHONPATH="${TEXTMSA_ROOT}${PYTHONPATH:+:$PYTHONPATH}"

info() {
  printf '[INFO] %s\n' "$*"
}

warn() {
  printf '[WARN] %s\n' "$*" >&2
}

run_cli() {
  "$PYTHON_BIN" -m textmsa.system_services.cli "$@"
}

if [[ ! -d "$PID_DIR" ]]; then
  warn "未找到 PID 目录 ($PID_DIR)，可能尚未启动或已被清理。"
fi

info "尝试通过管理脚本停止系统服务..."
if ! run_cli --stop all >/dev/null 2>&1; then
  warn "管理脚本停止失败或部分失败，请检查各服务状态。"
fi

if [[ -d "$PID_DIR" ]]; then
  shopt -s nullglob
  for pid_file in "$PID_DIR"/*.pid; do
    name="$(basename "$pid_file" .pid)"
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -z "$pid" || ! "$pid" =~ ^[0-9]+$ ]]; then
      warn "PID 文件格式无效: $pid_file"
      continue
    fi
    if kill -0 "$pid" >/dev/null 2>&1; then
      info "终止进程 ${name} (PID $pid)..."
      kill "$pid" >/dev/null 2>&1 || warn "终止 ${name} 失败，请手动检查。"
    fi
    rm -f "$pid_file" 2>/dev/null || true
  done
  shopt -u nullglob
fi

info "完成。"

