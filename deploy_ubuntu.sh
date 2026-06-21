#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

DRY_RUN="${STOCK_DEPLOY_DRY_RUN:-0}"
POSTGRES_BASE_PORT="${POSTGRES_BASE_PORT:-15432}"
POSTGRES_HOST_PORT="${POSTGRES_HOST_PORT:-}"
EXPLICIT_DATABASE_URL=""
EXPLICIT_POSTGRES_HOST_PORT=""
EXPLICIT_TUSHARE_TOKEN=""

info() {
  printf '[stock-deploy] %s\n' "$*"
}

run() {
  if [ "$DRY_RUN" = "1" ]; then
    printf '+'
    printf ' %s' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

run_shell() {
  if [ "$DRY_RUN" = "1" ]; then
    printf '+ %s\n' "$*"
    return 0
  fi
  bash -lc "$*"
}

run_root_shell() {
  if [ "$DRY_RUN" = "1" ]; then
    printf '+ sudo bash -lc %q\n' "$*"
    return 0
  fi
  if [ "$(id -u)" -eq 0 ]; then
    bash -lc "$*"
  else
    sudo bash -lc "$*"
  fi
}

sudo_cmd() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
    return
  fi
  sudo "$@"
}

is_port_available() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    ! lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
  elif command -v python3 >/dev/null 2>&1; then
    python3 - "$port" <<'PY'
import socket
import sys

port = int(sys.argv[1])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.settimeout(0.2)
    sys.exit(1 if sock.connect_ex(("127.0.0.1", port)) == 0 else 0)
PY
  else
    ! nc -z 127.0.0.1 "$port" >/dev/null 2>&1
  fi
}

next_available_port() {
  local port="$1"
  while ! is_port_available "$port"; do
    port=$((port + 1))
  done
  printf '%s' "$port"
}

is_local_stock_database_url() {
  local value="$1"
  [[ "$value" =~ ^postgresql\+psycopg://stock:stock@127\.0\.0\.1:[0-9]+/stock$ ]]
}

upsert_env_key() {
  local key="$1"
  local value="$2"
  local file=".env"
  local tmp_file

  if [ "$DRY_RUN" = "1" ]; then
    printf '+ set %s=%s in %s\n' "$key" "$value" "$file"
    return 0
  fi

  tmp_file="$(mktemp)"
  if [ -f "$file" ]; then
    awk -v key="$key" -v replacement="$key=$value" '
      BEGIN { done = 0 }
      $0 ~ "^" key "=" {
        print replacement
        done = 1
        next
      }
      { print }
      END {
        if (!done) {
          print replacement
        }
      }
    ' "$file" >"$tmp_file"
  else
    printf '%s=%s\n' "$key" "$value" >"$tmp_file"
  fi
  mv "$tmp_file" "$file"
}

run_sudo() {
  if [ "$DRY_RUN" = "1" ]; then
    printf '+ sudo'
    printf ' %s' "$@"
    printf '\n'
    return 0
  fi
  sudo_cmd "$@"
}

ensure_system_packages() {
  local missing=0
  local command_name

  for command_name in python3 curl docker; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
      missing=1
    fi
  done

  if ! docker compose version >/dev/null 2>&1; then
    missing=1
  fi

  if [ "$missing" -eq 0 ]; then
    info "system packages already available; skipping apt install"
    return
  fi

  if ! command -v apt-get >/dev/null 2>&1; then
    echo "Missing required system packages and apt-get is unavailable." >&2
    exit 1
  fi

  info "installing missing Ubuntu system packages"
  run_sudo apt-get update
  run_sudo apt-get install -y \
    ca-certificates \
    curl \
    docker.io \
    docker-compose-plugin \
    python3 \
    python3-pip \
    python3-venv
}

node_major_version() {
  if ! command -v node >/dev/null 2>&1; then
    printf '0'
    return
  fi
  node -v | sed -E 's/^v([0-9]+).*/\1/'
}

ensure_node_runtime() {
  local major
  major="$(node_major_version)"
  if [ "$major" -ge 20 ] && command -v npm >/dev/null 2>&1; then
    info "Node.js $(node -v) already satisfies frontend build requirements"
    return
  fi

  if ! command -v apt-get >/dev/null 2>&1; then
    echo "Node.js 20+ is required, and apt-get is unavailable for installation." >&2
    exit 1
  fi

  info "installing Node.js 22.x from NodeSource for Vite frontend build"
  run_root_shell "curl -fsSL https://deb.nodesource.com/setup_22.x | bash -"
  run_sudo apt-get install -y nodejs
}

ensure_env_file() {
  if [ -f ".env" ]; then
    info ".env already exists; keeping current deployment config"
    return
  fi
  if [ ! -f ".env.example" ]; then
    echo "Missing .env.example; cannot create .env" >&2
    exit 1
  fi
  info "creating .env from .env.example"
  run cp .env.example .env
}

load_env_file() {
  EXPLICIT_DATABASE_URL="${DATABASE_URL:-}"
  EXPLICIT_POSTGRES_HOST_PORT="${POSTGRES_HOST_PORT:-}"
  EXPLICIT_TUSHARE_TOKEN="${TUSHARE_TOKEN:-}"
  if [ -f ".env" ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
  fi
  if [ -n "$EXPLICIT_TUSHARE_TOKEN" ]; then
    TUSHARE_TOKEN="$EXPLICIT_TUSHARE_TOKEN"
  fi
  export TUSHARE_TOKEN
}

select_postgres_port() {
  local base_port="${EXPLICIT_POSTGRES_HOST_PORT:-$POSTGRES_BASE_PORT}"
  POSTGRES_HOST_PORT="$(next_available_port "$base_port")"
  info "selected PostgreSQL host port: $POSTGRES_HOST_PORT"
  export POSTGRES_HOST_PORT
}

configure_database_url() {
  local selected_database_url="postgresql+psycopg://stock:stock@127.0.0.1:${POSTGRES_HOST_PORT}/stock"

  if [ -n "$EXPLICIT_DATABASE_URL" ] && ! is_local_stock_database_url "$EXPLICIT_DATABASE_URL"; then
    DATABASE_URL="$EXPLICIT_DATABASE_URL"
  elif [ -z "${DATABASE_URL:-}" ] || is_local_stock_database_url "$DATABASE_URL"; then
    DATABASE_URL="$selected_database_url"
    upsert_env_key "POSTGRES_HOST_PORT" "$POSTGRES_HOST_PORT"
    upsert_env_key "DATABASE_URL" "$DATABASE_URL"
  fi
  export DATABASE_URL
}

ensure_python_dependencies() {
  if [ ! -x ".venv/bin/python" ]; then
    info "creating Python virtualenv"
    run python3 -m venv .venv
  else
    info "Python virtualenv already exists; reusing .venv"
  fi

  if [ ! -x ".venv/bin/uvicorn" ] || [ "${FORCE_INSTALL:-0}" = "1" ]; then
    info "installing backend dependencies in virtualenv"
    run .venv/bin/python -m pip install -U pip
    run .venv/bin/pip install -e .
  else
    info "backend dependencies already available; skipping pip install"
  fi
}

ensure_frontend_dependencies() {
  if [ ! -d "frontend/node_modules" ] || [ "${FORCE_INSTALL:-0}" = "1" ]; then
    info "installing frontend dependencies"
    if [ -f "frontend/package-lock.json" ]; then
      run_shell "cd frontend && npm ci"
    else
      run_shell "cd frontend && npm install"
    fi
  else
    info "frontend dependencies already available; skipping npm install"
  fi

  info "building frontend assets"
  run_shell "cd frontend && npm run build"
}

wait_for_postgres() {
  local i
  for i in $(seq 1 60); do
    if docker compose exec -T postgres pg_isready -U stock -d stock >/dev/null 2>&1; then
      info "PostgreSQL is ready in Docker: postgres:5432"
      return 0
    fi
    sleep 1
  done
  echo "PostgreSQL did not become ready in time." >&2
  exit 1
}

detect_postgres_published_port() {
  docker compose port postgres 5432 2>/dev/null | sed -E 's/.*:([0-9]+)$/\1/' | tail -n 1
}

sync_database_url_from_running_container() {
  local published_port
  published_port="$(detect_postgres_published_port)"
  if [ -z "$published_port" ]; then
    echo "Could not detect PostgreSQL published host port from Docker Compose." >&2
    exit 1
  fi
  if [ "$published_port" != "$POSTGRES_HOST_PORT" ]; then
    info "Docker published PostgreSQL host port is $published_port; updating deployment config"
    POSTGRES_HOST_PORT="$published_port"
    export POSTGRES_HOST_PORT
  fi
  configure_database_url
}

start_database() {
  if [ "${RESET_DB:-0}" = "1" ]; then
    info "RESET_DB=1; removing existing PostgreSQL volume before deployment"
    run docker compose down -v
  fi

  info "starting PostgreSQL; new deployments start with an empty data volume"
  run_shell "POSTGRES_HOST_PORT=$POSTGRES_HOST_PORT docker compose up -d postgres"
  if [ "$DRY_RUN" != "1" ]; then
    wait_for_postgres
    sync_database_url_from_running_container
  fi
}

run_migrations() {
  info "running database migrations only; deploy_ubuntu.sh does not fetch market data"
  run_shell "DATABASE_URL='$DATABASE_URL' scripts/db-upgrade.sh"
}

main() {
  info "deploying from $ROOT_DIR"
  ensure_system_packages
  ensure_node_runtime
  ensure_env_file
  load_env_file
  select_postgres_port
  configure_database_url
  ensure_python_dependencies
  ensure_frontend_dependencies
  start_database
  run_migrations

  if [ "$DRY_RUN" = "1" ]; then
    cat <<EOF

Dry run complete. No files, packages, containers, or database rows were changed.

Real deployment would leave the database schema-only. Fetch data later with:
  TRADE_DATE=YYYY-MM-DD bash get_data.sh

EOF
    return
  fi

  cat <<EOF

Deployment is ready.

Database has schema only. It intentionally does not contain market data yet.
Fetch real market data with:
  TRADE_DATE=YYYY-MM-DD bash get_data.sh

Start the app with LAN access:
  bash start.sh

EOF
}

main "$@"
