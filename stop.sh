#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"
LOG_DIR="$ROOT_DIR/.logs"
STOP_DOCKER="${STOP_DOCKER:-1}"

info() {
  printf '[stock-stop] %s\n' "$*"
}

warn() {
  printf '[stock-stop] %s\n' "$*" >&2
}

unique_lines() {
  awk 'NF && !seen[$0]++'
}

kill_pid_tree() {
  local pid="$1"
  local child

  if ! kill -0 "$pid" >/dev/null 2>&1; then
    return 0
  fi

  if command -v pgrep >/dev/null 2>&1; then
    for child in $(pgrep -P "$pid" 2>/dev/null || true); do
      kill_pid_tree "$child"
    done
  fi

  kill "$pid" >/dev/null 2>&1 || true
}

kill_pids() {
  local label="$1"
  shift
  local pids=("$@")
  local pid
  local still_running=()

  if [ "${#pids[@]}" -eq 0 ]; then
    info "no $label processes found"
    return 0
  fi

  info "stopping $label processes: ${pids[*]}"
  for pid in "${pids[@]}"; do
    if [ "$pid" != "$$" ]; then
      kill_pid_tree "$pid"
    fi
  done

  sleep 2
  for pid in "${pids[@]}"; do
    if [ "$pid" != "$$" ] && kill -0 "$pid" >/dev/null 2>&1; then
      still_running+=("$pid")
    fi
  done

  if [ "${#still_running[@]}" -gt 0 ]; then
    warn "force stopping $label processes: ${still_running[*]}"
    for pid in "${still_running[@]}"; do
      kill -KILL "$pid" >/dev/null 2>&1 || true
    done
  fi
}

project_process_pids() {
  python3 - "$ROOT_DIR" <<'PY'
import os
import sys

root = os.path.realpath(sys.argv[1])
frontend = os.path.join(root, "frontend")
keywords = (
    "scripts/dev-api.sh",
    "backend.app.main",
    "uvicorn",
    "vite",
    "npm run dev",
)

if not os.path.isdir("/proc"):
    raise SystemExit(0)

for name in os.listdir("/proc"):
    if not name.isdigit():
        continue
    pid = int(name)
    if pid == os.getpid() or pid == os.getppid():
        continue
    proc_dir = os.path.join("/proc", name)
    try:
        cwd = os.path.realpath(os.readlink(os.path.join(proc_dir, "cwd")))
        with open(os.path.join(proc_dir, "cmdline"), "rb") as fh:
            cmdline = fh.read().replace(b"\0", b" ").decode("utf-8", "ignore")
    except OSError:
        continue
    in_project = cwd == root or cwd == frontend or cwd.startswith(root + os.sep)
    if in_project and any(keyword in cmdline for keyword in keywords):
        print(pid)
PY
}

port_listener_pids() {
  local port="$1"
  if [ -z "$port" ]; then
    return 0
  fi
  if command -v lsof >/dev/null 2>&1; then
    lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true
    return 0
  fi
  if command -v fuser >/dev/null 2>&1; then
    fuser "${port}/tcp" 2>/dev/null | tr ' ' '\n' || true
    return 0
  fi
}

stop_app_processes() {
  local pids
  pids="$({ project_process_pids; port_listener_pids "$API_PORT"; port_listener_pids "$WEB_PORT"; } | unique_lines)"
  if [ -z "$pids" ]; then
    kill_pids "API/frontend" || true
    return 0
  fi
  # shellcheck disable=SC2206
  local pid_array=($pids)
  kill_pids "API/frontend" "${pid_array[@]}"
}

stop_docker() {
  if [ "$STOP_DOCKER" != "1" ]; then
    info "skipping Docker stop because STOP_DOCKER=$STOP_DOCKER"
    return 0
  fi
  if ! command -v docker >/dev/null 2>&1; then
    info "docker command not found; skipping PostgreSQL container stop"
    return 0
  fi
  if ! docker compose version >/dev/null 2>&1; then
    info "Docker Compose v2 not found; skipping PostgreSQL container stop"
    return 0
  fi

  info "stopping Docker Compose services"
  docker compose down
}

main() {
  info "stopping project processes under $ROOT_DIR"
  stop_app_processes
  stop_docker
  info "stopped project processes"
  if [ -d "$LOG_DIR" ]; then
    info "logs remain in $LOG_DIR"
  fi
}

main "$@"
