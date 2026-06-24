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

SERVICE_PREFIX="${STOCK_SERVICE_PREFIX:-stock}"
CONFIGURED_POSTGRES_HOST_PORT="${POSTGRES_HOST_PORT:-}"
POSTGRES_BASE_PORT="${POSTGRES_BASE_PORT:-${POSTGRES_HOST_PORT:-15432}}"
API_BASE_PORT="${API_BASE_PORT:-${API_PORT:-8000}}"
WEB_BASE_PORT="${WEB_BASE_PORT:-${WEB_PORT:-5173}}"
API_LISTEN_HOST="${API_LISTEN_HOST:-${API_HOST:-0.0.0.0}}"
WEB_LISTEN_HOST="${WEB_LISTEN_HOST:-${WEB_HOST:-0.0.0.0}}"
HEALTHCHECK_HOST="${HEALTHCHECK_HOST:-127.0.0.1}"
DB_HOST="${DB_HOST:-127.0.0.1}"
LOG_DIR="$ROOT_DIR/.logs"
RUN_DIR="$ROOT_DIR/.run"

info() {
  printf '[stock-start] %s\n' "$*"
}

warn() {
  printf '[stock-start] %s\n' "$*" >&2
}

unique_lines() {
  awk 'NF && !seen[$0]++'
}

sudo_cmd() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  else
    sudo "$@"
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

upsert_env_key() {
  local key="$1"
  local value="$2"
  local file=".env"
  local tmp_file

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

  [ -f "$file" ] || return 0
  tmp_file="$(mktemp)"
  awk -v key="$key" '$0 !~ "^" key "=" { print }' "$file" >"$tmp_file"
  mv "$tmp_file" "$file"
}

sync_runtime_env() {
  upsert_env_key "POSTGRES_HOST_PORT" "$POSTGRES_HOST_PORT"
  upsert_env_key "DATABASE_URL" "$DATABASE_URL"
  upsert_env_key "API_HOST" "$API_LISTEN_HOST"
  upsert_env_key "API_PORT" "$API_PORT"
  upsert_env_key "WEB_HOST" "$WEB_LISTEN_HOST"
  upsert_env_key "WEB_PORT" "$WEB_PORT"
  upsert_env_key "VITE_DEV_API_PROXY_TARGET" "$VITE_DEV_API_PROXY_TARGET"
  remove_env_key "VITE_API_BASE_URL"
  info "synced selected ports to .env: api=$API_PORT, web=$WEB_PORT, postgres=$POSTGRES_HOST_PORT"
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

wait_for_url() {
  local url="$1"
  local name="$2"
  local i
  for i in $(seq 1 60); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      info "$name is ready: $url"
      return 0
    fi
    sleep 1
  done
  echo "$name did not become ready in time. Check logs in $LOG_DIR" >&2
  return 1
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
  return 1
}

detect_public_host() {
  if [ -n "${PUBLIC_HOST:-}" ]; then
    printf '%s' "$PUBLIC_HOST"
    return
  fi
  if command -v hostname >/dev/null 2>&1; then
    local detected
    detected="$(hostname -I 2>/dev/null | awk '{print $1}')"
    if [ -n "$detected" ]; then
      printf '%s' "$detected"
      return
    fi
  fi
  if command -v ipconfig >/dev/null 2>&1; then
    local detected
    detected="$(ipconfig getifaddr en0 2>/dev/null || true)"
    if [ -n "$detected" ]; then
      printf '%s' "$detected"
      return
    fi
  fi
  printf '%s' "$HEALTHCHECK_HOST"
}

systemd_unit_exists() {
  local unit="$1"
  command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files "$unit" --no-legend 2>/dev/null | grep -q "$unit"
}

stop_systemd_services() {
  if systemd_unit_exists "${SERVICE_PREFIX}-web.service"; then
    info "stopping existing systemd web service"
    sudo_cmd systemctl stop "${SERVICE_PREFIX}-web.service" || true
  fi
  if systemd_unit_exists "${SERVICE_PREFIX}-api.service"; then
    info "stopping existing systemd API service"
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
    info "no existing $label processes found"
    return 0
  fi

  info "stopping existing $label processes: ${pids[*]}"
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
    warn "force stopping existing $label processes: ${still_running[*]}"
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

stop_existing_app_processes() {
  local pids
  pids="$({ project_process_pids; port_listener_pids "$API_BASE_PORT"; port_listener_pids "$WEB_BASE_PORT"; } | unique_lines)"
  if [ -z "$pids" ]; then
    kill_pids "API/frontend" || true
    return 0
  fi
  # shellcheck disable=SC2206
  local pid_array=($pids)
  kill_pids "API/frontend" "${pid_array[@]}"
}

stop_existing_docker_services() {
  if ! command -v docker >/dev/null 2>&1; then
    info "docker command not found; skipping existing Docker services stop"
    return 0
  fi
  if ! docker compose version >/dev/null 2>&1 && ! sudo docker compose version >/dev/null 2>&1; then
    info "Docker Compose v2 not found; skipping existing Docker services stop"
    return 0
  fi

  info "stopping existing Docker Compose services"
  docker_compose down
}

stop_existing_project() {
  info "stopping existing project before restart"
  stop_systemd_services
  stop_existing_app_processes
  stop_existing_docker_services
}

select_runtime_ports() {
  POSTGRES_HOST_PORT="$(next_available_port "$DB_HOST" "${CONFIGURED_POSTGRES_HOST_PORT:-$POSTGRES_BASE_PORT}")"
  API_PORT="$(next_available_port "$API_LISTEN_HOST" "$API_BASE_PORT")"
  WEB_PORT="$(next_available_port "$WEB_LISTEN_HOST" "$WEB_BASE_PORT")"
  DATABASE_URL="postgresql+psycopg://stock:stock@$DB_HOST:$POSTGRES_HOST_PORT/stock"
  VITE_DEV_API_PROXY_TARGET="http://$HEALTHCHECK_HOST:$API_PORT"
  export POSTGRES_HOST_PORT API_PORT WEB_PORT DATABASE_URL VITE_DEV_API_PROXY_TARGET
}

ensure_dependencies() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "Missing docker command. Please run bash deploy_ubuntu.sh first." >&2
    exit 1
  fi

  if ! docker compose version >/dev/null 2>&1 && ! sudo docker compose version >/dev/null 2>&1; then
    echo "Missing Docker Compose v2 or Docker permission. Please run bash deploy_ubuntu.sh first." >&2
    exit 1
  fi

  if [ ! -x ".venv/bin/uvicorn" ] || [ ! -d "frontend/node_modules" ]; then
    info "dependencies are missing; installing local Python/frontend dependencies"
    make install
  fi
}

run_migrations() {
  info "running database migrations"
  DATABASE_URL="$DATABASE_URL" scripts/db-upgrade.sh
}

start_postgres() {
  info "starting PostgreSQL container: host $DB_HOST:$POSTGRES_HOST_PORT -> container postgres:5432"
  POSTGRES_HOST_PORT="$POSTGRES_HOST_PORT" docker_compose up -d postgres
  wait_for_postgres
}

database_decision_counts() {
  docker_compose exec -T postgres psql -U stock -d stock -At -F '|' -c "
select
  (select count(*) from trading_calendar where is_open = true) as open_trading_days,
  (select count(*) from stock_basic) as stock_basic_rows,
  (select count(distinct trade_date) from stock_daily) as stock_daily_trade_dates,
  (select count(*) from market_daily) as market_daily_rows,
  (select count(*) from sector_daily) as sector_daily_rows,
  (select count(*) from candidate_stock) as candidate_rows,
  (select count(*) from trade_plan) as trade_plan_rows,
  (select count(*) from data_job_run where status in ('success','warning')) as successful_data_jobs;
" 2>/dev/null || true
}

check_and_fill_decision_data() {
  if [ "${STOCK_START_SKIP_DATA_CHECK:-0}" = "1" ]; then
    info "skipping data health check because STOCK_START_SKIP_DATA_CHECK=1"
    return 0
  fi

  local counts
  counts="$(database_decision_counts)"
  if [ -z "$counts" ]; then
    warn "could not read database decision data counts; running get_data.sh to initialize data"
    bash get_data.sh
    return 0
  fi

  IFS='|' read -r open_days stock_basic_rows stock_daily_dates market_rows sector_rows candidate_rows plan_rows data_jobs <<<"$counts"
  cat <<EOF
[stock-start] database decision data check:
  open_trading_days=$open_days
  stock_basic_rows=$stock_basic_rows
  stock_daily_trade_dates=$stock_daily_dates
  market_daily_rows=$market_rows
  sector_daily_rows=$sector_rows
  candidate_rows=$candidate_rows
  trade_plan_rows=$plan_rows
  successful_data_jobs=$data_jobs
EOF

  if [ "$open_days" -lt 20 ] || [ "$stock_daily_dates" -lt 20 ] || [ "$market_rows" -lt 1 ] || [ "$sector_rows" -lt 1 ] || [ "$candidate_rows" -lt 1 ] || [ "$plan_rows" -lt 1 ] || [ "$data_jobs" -lt 1 ]; then
    warn "database does not yet satisfy A-share decision requirements; running bash get_data.sh"
    if ! bash get_data.sh; then
      warn "get_data.sh failed. Check TUSHARE_TOKEN, network access, and $LOG_DIR/get_data_cron.log if cron is involved."
      return 1
    fi
    info "data initialization completed; rechecking counts"
    counts="$(database_decision_counts)"
    IFS='|' read -r open_days stock_basic_rows stock_daily_dates market_rows sector_rows candidate_rows plan_rows data_jobs <<<"$counts"
    cat <<EOF
[stock-start] database decision data check after fill:
  open_trading_days=$open_days
  stock_basic_rows=$stock_basic_rows
  stock_daily_trade_dates=$stock_daily_dates
  market_daily_rows=$market_rows
  sector_daily_rows=$sector_rows
  candidate_rows=$candidate_rows
  trade_plan_rows=$plan_rows
  successful_data_jobs=$data_jobs
EOF
  else
    info "database already has enough data for the decision dashboard"
  fi
}

start_systemd_or_fallback() {
  mkdir -p "$LOG_DIR" "$RUN_DIR"

  if systemd_unit_exists "${SERVICE_PREFIX}-api.service" && systemd_unit_exists "${SERVICE_PREFIX}-web.service"; then
    info "starting API/Web through systemd"
    sudo_cmd systemctl restart "${SERVICE_PREFIX}-api.service"
    sudo_cmd systemctl restart "${SERVICE_PREFIX}-web.service"
  else
    warn "systemd units not installed; falling back to nohup background processes"
    : >"$LOG_DIR/api.log"
    : >"$LOG_DIR/web.log"
    API_HOST="$API_LISTEN_HOST" API_PORT="$API_PORT" API_RELOAD=0 DATABASE_URL="$DATABASE_URL" nohup scripts/dev-api.sh >"$LOG_DIR/api.log" 2>&1 &
    printf '%s\n' "$!" >"$RUN_DIR/api.pid"
    (cd frontend && VITE_API_BASE_URL="" VITE_DEV_API_PROXY_TARGET="$VITE_DEV_API_PROXY_TARGET" nohup npm run dev -- --host "$WEB_LISTEN_HOST" --port "$WEB_PORT" >"$LOG_DIR/web.log" 2>&1 & printf '%s\n' "$!" >"$RUN_DIR/web.pid")
  fi

  wait_for_url "http://$HEALTHCHECK_HOST:$API_PORT/api/health" "API"
  wait_for_url "http://$HEALTHCHECK_HOST:$WEB_PORT" "Frontend"
}

main() {
  stop_existing_project
  ensure_dependencies
  select_runtime_ports
  sync_runtime_env
  start_postgres
  run_migrations
  check_and_fill_decision_data
  start_systemd_or_fallback

  local public_host
  public_host="$(detect_public_host)"

  cat <<EOF

Project is running.

Frontend local: http://$HEALTHCHECK_HOST:$WEB_PORT
Frontend LAN:   http://$public_host:$WEB_PORT
API local:      http://$HEALTHCHECK_HOST:$API_PORT/api/health
API proxy:      /api -> $VITE_DEV_API_PROXY_TARGET
Database:       $DB_HOST:$POSTGRES_HOST_PORT -> postgres:5432
Logs:           $LOG_DIR

Selected ports:
  Web:        $WEB_PORT
  API:        $API_PORT
  PostgreSQL: $POSTGRES_HOST_PORT

If another LAN computer cannot open Frontend LAN, allow the web port on Ubuntu:
  sudo ufw allow $WEB_PORT/tcp

Run bash start.sh again to stop existing services and restart cleanly.
Stop everything with:
  bash stop.sh

EOF
}

main "$@"
