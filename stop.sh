#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

SERVICE_PREFIX="${STOCK_SERVICE_PREFIX:-stock}"
RUN_DIR="$ROOT_DIR/.run"

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

API_BASE_PORT="${API_BASE_PORT:-${API_PORT:-8000}}"
WEB_BASE_PORT="${WEB_BASE_PORT:-${WEB_PORT:-5173}}"

info() {
  printf '[stock-stop] %s\n' "$*"
}

warn() {
  printf '[stock-stop] %s\n' "$*" >&2
}

sudo_cmd() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  else
    sudo "$@"
  fi
}

docker_compose_prefix() {
  if docker ps >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    printf 'docker compose'
    return 0
  fi
  if command -v sudo >/dev/null 2>&1 && sudo docker ps >/dev/null 2>&1 && sudo docker compose version >/dev/null 2>&1; then
    printf 'sudo docker compose'
    return 0
  fi
  printf 'docker compose'
}

docker_compose() {
  local prefix
  prefix="$(docker_compose_prefix)"
  if [ "$prefix" = "sudo docker compose" ]; then
    sudo docker compose "$@"
    return
  fi
  docker compose "$@"
}

docker_compose_available() {
  docker ps >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 && return 0
  command -v sudo >/dev/null 2>&1 && sudo docker ps >/dev/null 2>&1 && sudo docker compose version >/dev/null 2>&1
}

unique_lines() {
  awk 'NF && !seen[$0]++'
}

systemd_unit_exists() {
  local unit="$1"
  command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files "$unit" --no-legend 2>/dev/null | grep -q "$unit"
}

stop_systemd_services() {
  if systemd_unit_exists "${SERVICE_PREFIX}-web.service"; then
    info "stopping systemd service ${SERVICE_PREFIX}-web.service"
    sudo_cmd systemctl stop "${SERVICE_PREFIX}-web.service" || true
  fi
  if systemd_unit_exists "${SERVICE_PREFIX}-api.service"; then
    info "stopping systemd service ${SERVICE_PREFIX}-api.service"
    sudo_cmd systemctl stop "${SERVICE_PREFIX}-api.service" || true
  fi
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

pid_file_pids() {
  local file
  for file in "$RUN_DIR"/*.pid; do
    [ -f "$file" ] || continue
    cat "$file"
  done
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

stop_processes() {
  local pids
  pids="$({ pid_file_pids; project_process_pids; port_listener_pids "$API_BASE_PORT"; port_listener_pids "$WEB_BASE_PORT"; } | unique_lines)"
  if [ -z "$pids" ]; then
    kill_pids "API/frontend" || true
    return 0
  fi
  # shellcheck disable=SC2206
  local pid_array=($pids)
  kill_pids "API/frontend" "${pid_array[@]}"
  rm -f "$RUN_DIR"/*.pid 2>/dev/null || true
}

stop_docker_services() {
  if ! command -v docker >/dev/null 2>&1; then
    info "docker command not found; skipping Docker Compose stop"
    return 0
  fi
  if ! docker_compose_available; then
    info "Docker Compose v2 or Docker daemon permission not available; skipping Docker Compose stop"
    return 0
  fi

  info "stopping Docker Compose services; PostgreSQL data volume is preserved"
  docker_compose down --remove-orphans
}

main() {
  stop_systemd_services
  stop_processes
  stop_docker_services
  info "all stock services and project processes have been stopped"
}

main "$@"
