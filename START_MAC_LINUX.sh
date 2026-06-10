#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

PORT=8520
PY_CMD="python3"
if ! command -v python3 >/dev/null 2>&1; then
  PY_CMD="python"
fi

if ! command -v "$PY_CMD" >/dev/null 2>&1; then
  echo "[ERROR] Python was not found. Install Python 3.10+."
  exit 1
fi

if [ ! -d .venv ]; then
  echo "[v100] Creating local Python environment..."
  "$PY_CMD" -m venv .venv
fi

source .venv/bin/activate

if [ ! -f .venv/v100_ready.txt ]; then
  echo "[v100] Installing required packages..."
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
  echo ready > .venv/v100_ready.txt
fi

python scripts/stop_port.py "$PORT" || true

echo "[v100] Starting app."
echo "[v100] Local URL: http://127.0.0.1:$PORT"
python app.py
