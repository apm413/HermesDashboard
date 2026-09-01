#!/usr/bin/env bash
# start.sh — Linux/Mac запуск HermesDashboard backend (dev)
set -e
PORT="${HERMES_PORT:-5557}"
cd "$(dirname "$0")/dashboard"
export HERMES_VIDEO_ROOT="${HERMES_VIDEO_ROOT:-$HOME/HermeSvideo}"
export TIER1_ROOT="${TIER1_ROOT:-$HOME/Desktop/tier1-fresh}"
VENV_PY="$(dirname "$(dirname "$(readlink -f "$0")")")/.venv/bin/python3"
if [ -x "$VENV_PY" ]; then
  exec "$VENV_PY" -m uvicorn plugin_api:router --host 0.0.0.0 --port "$PORT" --log-level info
fi
exec python3 -m uvicorn plugin_api:router --host 0.0.0.0 --port "$PORT" --log-level info