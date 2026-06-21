#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

missing=0

check_command() {
  local name="$1"
  local hint="$2"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "Missing command: $name. $hint" >&2
    missing=1
  fi
}

check_command docker "Install Docker Desktop or another Docker-compatible runtime."
check_command python3 "Install Python 3.11+ and rerun make install."
check_command npm "Install Node.js/npm and rerun make install."

if ! docker compose version >/dev/null 2>&1; then
  echo "Missing Docker Compose v2. Install/update Docker Desktop." >&2
  missing=1
fi

if [ ! -x ".venv/bin/uvicorn" ]; then
  echo "Missing backend virtualenv dependencies. Run: make install" >&2
  missing=1
fi

if [ ! -d "frontend/node_modules" ]; then
  echo "Missing frontend dependencies. Run: make install" >&2
  missing=1
fi

if [ "$missing" -ne 0 ]; then
  exit 1
fi

echo "Development environment looks ready."
