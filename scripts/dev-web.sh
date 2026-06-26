#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

load_node_runtime() {
  export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:$PATH"

  if command -v npm >/dev/null 2>&1; then
    return 0
  fi

  export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  if [ -s "$NVM_DIR/nvm.sh" ]; then
    # shellcheck disable=SC1090
    . "$NVM_DIR/nvm.sh"
  fi

  if command -v npm >/dev/null 2>&1; then
    return 0
  fi

  local node_bin
  node_bin="$(find "$HOME/.nvm/versions/node" -maxdepth 3 -type f -name npm 2>/dev/null | sort -V | tail -n 1 || true)"
  if [ -n "$node_bin" ]; then
    export PATH="$(dirname "$node_bin"):$PATH"
  fi
}

load_node_runtime
cd "$ROOT_DIR/frontend"

if ! command -v npm >/dev/null 2>&1; then
  cat >&2 <<EOF
npm not found in PATH for Web service.
PATH=$PATH
HOME=$HOME
NVM_DIR=${NVM_DIR:-}
Please install Node.js 20+ or ensure npm is visible to systemd.
EOF
  exit 127
fi

if [ ! -d "node_modules" ]; then
  echo "Missing frontend/node_modules. Run: make install" >&2
  exit 1
fi

HOST="${WEB_HOST:-0.0.0.0}"
PORT="${WEB_PORT:-5173}"

echo "Starting Vite web service"
echo "node=$(command -v node || true) $(node --version 2>/dev/null || true)"
echo "npm=$(command -v npm || true) $(npm --version 2>/dev/null || true)"
echo "host=$HOST port=$PORT proxy=${VITE_DEV_API_PROXY_TARGET:-}"

exec npm run dev -- --host "$HOST" --port "$PORT"
