#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/frontend"

if [ ! -d "node_modules" ]; then
  echo "Missing frontend/node_modules. Run: make install" >&2
  exit 1
fi

HOST="${WEB_HOST:-0.0.0.0}"
PORT="${WEB_PORT:-5173}"

exec npm run dev -- --host "$HOST" --port "$PORT"
