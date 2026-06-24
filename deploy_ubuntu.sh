#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

DRY_RUN="${STOCK_DEPLOY_DRY_RUN:-0}"
POSTGRES_BASE_PORT="${POSTGRES_BASE_PORT:-15432}"
API_BASE_PORT="${API_BASE_PORT:-${API_PORT:-8000}}"
WEB_BASE_PORT="${WEB_BASE_PORT:-${WEB_PORT:-5173}}"
API_LISTEN_HOST="${API_LISTEN_HOST:-${API_HOST:-0.0.0.0}}"
WEB_LISTEN_HOST="${WEB_LISTEN_HOST:-${WEB_HOST:-0.0.0.0}}"
HEALTHCHECK_HOST="${HEALTHCHECK_HOST:-127.0.0.1}"
DB_HOST="${DB_HOST:-127.0.0.1}"
POSTGRES_HOST_PORT="${POSTGRES_HOST_PORT:-}"
API_PORT="${API_PORT:-}"
WEB_PORT="${WEB_PORT:-}"
EXPLICIT_DATABASE_URL="${DATABASE_URL:-}"
EXPLICIT_POSTGRES_HOST_PORT="${POSTGRES_HOST_PORT:-}"
EXPLICIT_TUSHARE_TOKEN="${TUSHARE_TOKEN:-}"
DEPLOY_USER="${SUDO_USER:-${USER:-$(id -un)}}"
SERVICE_PREFIX="${STOCK_SERVICE_PREFIX:-stock}"
LOG_DIR="$ROOT_DIR/.logs"

info() {
  printf '[stock-deploy] %s\n' "$*"
}

warn() {
  printf '[stock-deploy] %s\n' "$*" >&2
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

run_sudo() {
  if [ "$DRY_RUN" = "1" ]; then
    printf '+ sudo'
    printf ' %s' "$@"
    printf '\n'
    return 0
  fi
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  else
    sudo "$@"
  fi
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

docker_compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
    return
  fi
  if command -v sudo >/dev/null 2>&1 && sudo docker compose version >/dev/null 2>&1; then
    sudo docker compose "$@"
    return
  fi
  docker compose "$@"
}

is_port_available() {
  local host="$1"
  local port="$2"
  python3 - "$host" "$port" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((host, port))
    except OSError:
        sys.exit(1)
PY
}

next_available_port() {
  local host="$1"
  local port="$2"
  while ! is_port_available "$host" "$port"; do
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

remove_env_key() {
  local key="$1"
  local file=".env"
  local tmp_file

  if [ "$DRY_RUN" = "1" ]; then
    printf '+ remove %s from %s if present\n' "$key" "$file"
    return 0
  fi

  [ -f "$file" ] || return 0
  tmp_file="$(mktemp)"
  awk -v key="$key" '$0 !~ "^" key "=" { print }' "$file" >"$tmp_file"
  mv "$tmp_file" "$file"
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

  if ! command -v systemctl >/dev/null 2>&1; then
    missing=1
  fi

  if [ "$missing" -eq 0 ]; then
    info "system packages already available; skipping apt install"
    return
  fi

  if [ "$DRY_RUN" = "1" ]; then
    info "installing missing Ubuntu system packages"
    run_sudo apt-get update
    run_sudo apt-get install -y \
      ca-certificates \
      curl \
      docker.io \
      docker-compose-plugin \
      python3 \
      python3-pip \
      python3-venv \
      systemd
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
    python3-venv \
    systemd
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

ensure_docker_permission() {
  info "checking Docker daemon and permissions"
  run_sudo systemctl enable --now docker

  if [ "$DRY_RUN" = "1" ]; then
    printf '+ docker compose version || sudo docker compose version\n'
    printf '+ sudo usermod -aG docker %s\n' "$DEPLOY_USER"
    return 0
  fi

  if docker compose version >/dev/null 2>&1; then
    info "current user can run Docker Compose"
    return
  fi

  if sudo docker compose version >/dev/null 2>&1; then
    warn "current session cannot access Docker directly; adding $DEPLOY_USER to docker group"
    sudo usermod -aG docker "$DEPLOY_USER"
    warn "docker group membership takes effect after re-login; this deployment will use sudo for Docker where needed"
    return
  fi

  echo "Docker Compose is installed but not usable by current user or sudo." >&2
  exit 1
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
  if [ -f ".env" ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
  fi
  if [ -n "$EXPLICIT_TUSHARE_TOKEN" ]; then
    TUSHARE_TOKEN="$EXPLICIT_TUSHARE_TOKEN"
  fi
  export TUSHARE_TOKEN="${TUSHARE_TOKEN:-}"
}

select_runtime_ports() {
  local pg_base="${EXPLICIT_POSTGRES_HOST_PORT:-$POSTGRES_BASE_PORT}"
  POSTGRES_HOST_PORT="$(next_available_port "$DB_HOST" "$pg_base")"
  API_PORT="$(next_available_port "$API_LISTEN_HOST" "$API_BASE_PORT")"
  WEB_PORT="$(next_available_port "$WEB_LISTEN_HOST" "$WEB_BASE_PORT")"
  info "selected PostgreSQL host port: $POSTGRES_HOST_PORT"
  info "selected API port: $API_PORT"
  info "selected Web port: $WEB_PORT"
  export POSTGRES_HOST_PORT API_PORT WEB_PORT
}

configure_database_url() {
  local selected_database_url="postgresql+psycopg://stock:stock@127.0.0.1:${POSTGRES_HOST_PORT}/stock"

  if [ -n "$EXPLICIT_DATABASE_URL" ] && ! is_local_stock_database_url "$EXPLICIT_DATABASE_URL"; then
    DATABASE_URL="$EXPLICIT_DATABASE_URL"
  else
    DATABASE_URL="$selected_database_url"
  fi
  export DATABASE_URL
}

sync_runtime_env() {
  upsert_env_key "POSTGRES_HOST_PORT" "$POSTGRES_HOST_PORT"
  upsert_env_key "DATABASE_URL" "$DATABASE_URL"
  upsert_env_key "API_HOST" "$API_LISTEN_HOST"
  upsert_env_key "API_PORT" "$API_PORT"
  upsert_env_key "WEB_HOST" "$WEB_LISTEN_HOST"
  upsert_env_key "WEB_PORT" "$WEB_PORT"
  upsert_env_key "VITE_DEV_API_PROXY_TARGET" "http://$HEALTHCHECK_HOST:$API_PORT"
  remove_env_key "VITE_API_BASE_URL"
  info "synced selected ports to .env: api=$API_PORT, web=$WEB_PORT, postgres=$POSTGRES_HOST_PORT"
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
    if docker_compose exec -T postgres pg_isready -U stock -d stock >/dev/null 2>&1; then
      info "PostgreSQL is ready in Docker: postgres:5432"
      return 0
    fi
    sleep 1
  done
  echo "PostgreSQL did not become ready in time." >&2
  exit 1
}

detect_postgres_published_port() {
  docker_compose port postgres 5432 2>/dev/null | sed -E 's/.*:([0-9]+)$/\1/' | tail -n 1
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
  sync_runtime_env
}

start_database() {
  if [ "${RESET_DB:-0}" = "1" ]; then
    info "RESET_DB=1; removing existing PostgreSQL volume before deployment"
    run_shell "POSTGRES_HOST_PORT=$POSTGRES_HOST_PORT docker compose down -v"
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

write_systemd_units() {
  local api_unit="/etc/systemd/system/${SERVICE_PREFIX}-api.service"
  local web_unit="/etc/systemd/system/${SERVICE_PREFIX}-web.service"

  info "installing systemd services: ${SERVICE_PREFIX}-api.service, ${SERVICE_PREFIX}-web.service"
  run mkdir -p "$LOG_DIR"

  if [ "$DRY_RUN" = "1" ]; then
    printf '+ sudo tee %s >/dev/null <<UNIT\n' "$api_unit"
    printf '+ sudo tee %s >/dev/null <<UNIT\n' "$web_unit"
  else
    run_root_shell "cat > '$api_unit' <<'UNIT'
[Unit]
Description=Stock decision FastAPI service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$DEPLOY_USER
WorkingDirectory=$ROOT_DIR
EnvironmentFile=$ROOT_DIR/.env
Environment=API_RELOAD=0
ExecStart=$ROOT_DIR/scripts/dev-api.sh
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT"
    run_root_shell "cat > '$web_unit' <<'UNIT'
[Unit]
Description=Stock decision Vite web service
After=${SERVICE_PREFIX}-api.service network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$DEPLOY_USER
WorkingDirectory=$ROOT_DIR
EnvironmentFile=$ROOT_DIR/.env
Environment=VITE_API_BASE_URL=
ExecStart=$ROOT_DIR/scripts/dev-web.sh
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT"
  fi

  run_sudo systemctl daemon-reload
  run_sudo systemctl enable "${SERVICE_PREFIX}-api.service" "${SERVICE_PREFIX}-web.service"
}

install_nightly_cron() {
  local marker="codex-stock-nightly-get-data"
  local log_path="$ROOT_DIR/.logs/get_data_cron.log"
  local timezone_line="CRON_TZ=Asia/Shanghai # $marker"
  local cron_line="0 23 * * 1-5 cd $ROOT_DIR && bash get_data.sh >> $log_path 2>&1 # $marker"

  info "installing daily 23:00 get_data.sh cron"
  run mkdir -p "$ROOT_DIR/.logs"
  run_shell "(crontab -l 2>/dev/null | grep -v '$marker'; printf '%s\n' '$timezone_line'; printf '%s\n' '$cron_line') | crontab -"
}

main() {
  info "deploying from $ROOT_DIR"
  ensure_system_packages
  ensure_node_runtime
  ensure_docker_permission
  ensure_env_file
  load_env_file
  select_runtime_ports
  configure_database_url
  sync_runtime_env
  ensure_python_dependencies
  ensure_frontend_dependencies
  start_database
  run_migrations
  write_systemd_units
  install_nightly_cron

  if [ "$DRY_RUN" = "1" ]; then
    cat <<EOF

Dry run complete. No files, packages, containers, services, or database rows were changed.

Real deployment leaves the database schema-only. The first start will check data health
and run get_data.sh if A-share decision data is missing.

Real deployment would install:
  systemd: ${SERVICE_PREFIX}-api.service, ${SERVICE_PREFIX}-web.service
  cron:    0 23 * * 1-5 cd $ROOT_DIR && bash get_data.sh

After deployment, start the system with:
  bash start.sh

EOF
    return
  fi

  cat <<EOF

Deployment is ready.

Selected ports:
  Web:        $WEB_PORT
  API:        $API_PORT
  PostgreSQL: $POSTGRES_HOST_PORT

Database has schema only. It intentionally does not contain market data yet.
On first startup, start.sh checks whether A-share decision data is sufficient and
runs get_data.sh when required.

Nightly data pull is installed in crontab at 23:00 on weekdays.
Logs are written to:
  $ROOT_DIR/.logs/get_data_cron.log

Systemd services are installed and enabled:
  ${SERVICE_PREFIX}-api.service
  ${SERVICE_PREFIX}-web.service

Start the app now with:
  bash start.sh

Stop everything with:
  bash stop.sh

If Docker group membership was just changed, re-login later so Docker works
without sudo in interactive shells.

EOF
}

main "$@"
