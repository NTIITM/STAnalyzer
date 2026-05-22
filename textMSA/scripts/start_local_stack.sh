#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
#  start_local_stack.sh
#  启动所有系统服务和 API Server（非 Docker 版本）
# -----------------------------------------------------------------------------

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEXTMSA_ROOT="$PROJECT_ROOT"
LOG_DIR="$PROJECT_ROOT/logs/local"
PID_DIR="$PROJECT_ROOT/logs/pids"
PYTHON_BIN="${PYTHON_BIN:-python3}"
API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8000}"
API_PID=""

export PYTHONPATH="${TEXTMSA_ROOT}${PYTHONPATH:+:$PYTHONPATH}"

mkdir -p "$LOG_DIR" "$PID_DIR"

info() {
  printf '[INFO] %s\n' "$*"
}

warn() {
  printf '[WARN] %s\n' "$*" >&2
}

error() {
  printf '[ERROR] %s\n' "$*" >&2
}

run_cli() {
  "$PYTHON_BIN" -m textmsa.system_services.cli "$@"
}

get_listen_pids() {
  local port="$1"
  local pids=""

  if command -v lsof >/dev/null 2>&1; then
    pids="$(lsof -ti TCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  elif command -v fuser >/dev/null 2>&1; then
    pids="$(fuser "${port}"/tcp 2>/dev/null | tr -s ' ' '\n' || true)"
  else
    error "缺少 lsof 或 fuser，无法检测端口占用情况。"
    exit 1
  fi

  printf '%s' "$pids"
}

ensure_port_free() {
  local port="$1"
  local pids

  pids="$(get_listen_pids "$port")"
  if [[ -z "$pids" ]]; then
    return
  fi

  warn "端口 $port 已被占用，尝试终止相关进程: $pids"
  for pid in $pids; do
    if [[ "$pid" =~ ^[0-9]+$ ]]; then
      warn "  发送 SIGTERM 到进程 $pid"
      kill "$pid" >/dev/null 2>&1 || true
    fi
  done

  local retries=5
  while (( retries > 0 )); do
    sleep 1
    pids="$(get_listen_pids "$port")"
    if [[ -z "$pids" ]]; then
      info "端口 $port 已成功释放。"
      return
    fi
    ((retries--))
  done

  pids="$(get_listen_pids "$port")"
  if [[ -n "$pids" ]]; then
    warn "端口 $port 仍被占用，发送 SIGKILL: $pids"
    for pid in $pids; do
      if [[ "$pid" =~ ^[0-9]+$ ]]; then
        kill -9 "$pid" >/dev/null 2>&1 || true
      fi
    done
    sleep 1
  fi

  pids="$(get_listen_pids "$port")"
  if [[ -n "$pids" ]]; then
    error "无法释放端口 $port，请手动处理后重试。仍占用的进程: $pids"
    exit 1
  fi

  info "端口 $port 已成功释放。"
}

# 清理函数：脚本退出时停止所有后台进程
cleanup() {
  if [[ -n "${TEXTMSA_SKIP_AUTO_STOP:-}" ]]; then
    warn "跳过自动停止（TEXTMSA_SKIP_AUTO_STOP 已设置）。"
    return
  fi

  info "正在停止所有系统服务和 API Server..."
  if ! run_cli --stop all >/dev/null 2>&1; then
    warn "停止系统服务时遇到问题，请手动检查。"
  fi

  if [[ -n "$API_PID" && "$API_PID" =~ ^[0-9]+$ ]]; then
    if kill -0 "$API_PID" >/dev/null 2>&1; then
      kill "$API_PID" >/dev/null 2>&1 || true
    fi
  elif [[ -f "$PID_DIR/api-server.pid" ]]; then
    local stored_pid
    stored_pid="$(cat "$PID_DIR/api-server.pid")"
    if [[ "$stored_pid" =~ ^[0-9]+$ ]] && kill -0 "$stored_pid" >/dev/null 2>&1; then
      kill "$stored_pid" >/dev/null 2>&1 || true
    fi
    rm -f "$PID_DIR/api-server.pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT

info "项目根目录: $PROJECT_ROOT"
info "日志目录:   $LOG_DIR"

# 使用 Python 输出服务列表（名称|路径）
SERVICE_LINES="$("$PYTHON_BIN" - <<'PYTHON'
from textmsa.system_services.service_manager import ServiceManager

manager = ServiceManager()
manager.process_all_services(generate_docker=False)

for svc in manager.services:
    name = svc.get("service_dir") or svc.get("name")
    path = svc.get("service_path")
    if not name or not path:
        continue
    print(f"{name}|{path}")
PYTHON
)"

if [[ -z "$SERVICE_LINES" ]]; then
  error "未找到任何系统服务，无法启动。"
  exit 1
fi

IFS=$'\n'
for line in $SERVICE_LINES; do
  name="${line%%|*}"
  path="${line#*|}"

  if [[ ! -d "$path" ]]; then
    warn "服务目录不存在: $path，跳过 ${name}。"
    continue
  fi

  LOG_FILE="$LOG_DIR/${name}.log"
  PID_FILE="$PID_DIR/${name}.pid"

  info "启动服务 ${name} ..."
  (
    cd "$path"
    nohup "$PYTHON_BIN" main.py >"$LOG_FILE" 2>&1 &
    echo $! >"$PID_FILE"
  )
  info "  日志: $LOG_FILE"
done
unset IFS

# 启动 API Server
API_LOG="$LOG_DIR/api-server.log"
API_PID_FILE="$PID_DIR/api-server.pid"

info "启动 API Server ..."
ensure_port_free "$API_PORT"
cd "$PROJECT_ROOT/server"
"$PYTHON_BIN" app.py >>"$API_LOG" 2>&1 &
API_PID=$!
echo "$API_PID" >"$API_PID_FILE"
info "  日志: $API_LOG"
info "  PID : $API_PID"

info "所有服务已启动。按 Ctrl+C 停止（或执行 scripts/stop_local_stack.sh）。"
wait "$API_PID"

