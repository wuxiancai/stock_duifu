#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -x ".venv/bin/alembic" ]; then
  echo "Missing .venv. Run: make install" >&2
  exit 1
fi

exec .venv/bin/alembic upgrade head

