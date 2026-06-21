#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -x ".venv/bin/uvicorn" ]; then
  echo "Missing .venv. Run: make install" >&2
  exit 1
fi

HOST="${API_HOST:-127.0.0.1}"
PORT="${API_PORT:-8000}"
RELOAD="${API_RELOAD:-1}"

if [ "$RELOAD" = "1" ]; then
  exec .venv/bin/uvicorn backend.app.main:app --host "$HOST" --port "$PORT" --reload
fi

exec .venv/bin/uvicorn backend.app.main:app --host "$HOST" --port "$PORT"
