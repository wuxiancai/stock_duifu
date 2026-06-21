#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -x ".venv/bin/python" ]; then
  echo "Missing .venv. Run: make install" >&2
  exit 1
fi

case "${1:-}" in
  run|run-workflow|loop|latest)
    exec .venv/bin/python -m backend.app.simulation.cli "$@"
    ;;
  *)
    exec .venv/bin/python -m backend.app.simulation.cli run "$@"
    ;;
esac
