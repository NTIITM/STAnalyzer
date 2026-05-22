#!/bin/bash
# Startup script for system_server
# Add to crontab via: crontab -e -> @reboot /path/to/system_server/startup_system_server.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${LOG_DIR:-$SCRIPT_DIR/logs}"
LOG_FILE="$LOG_DIR/system_server.log"
PID_FILE="$LOG_DIR/system_server.pid"
CONDA_ACTIVATE="${CONDA_ACTIVATE:-$HOME/anaconda3/etc/profile.d/conda.sh}"
ENV_NAME="${ENV_NAME:-stpp}"
SERVER_DIR="${SERVER_DIR:-$SCRIPT_DIR}"

mkdir -p "$LOG_DIR"

# Check if already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "$(date): system_server already running (PID $OLD_PID), skipping." >> "$LOG_FILE"
        exit 0
    fi
fi

echo "$(date): Starting system_server..." >> "$LOG_FILE"

# Source conda and launch uvicorn in background
source "$CONDA_ACTIVATE"
conda activate "$ENV_NAME"
cd "$SERVER_DIR"

nohup uvicorn system_server.main:app \
    --host 0.0.0.0 \
    --port 9000 \
    >> "$LOG_FILE" 2>&1 &

NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"
echo "$(date): system_server started with PID $NEW_PID" >> "$LOG_FILE"
