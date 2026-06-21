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

CONFIGURED_POSTGRES_HOST_PORT="${POSTGRES_HOST_PORT:-}"
POSTGRES_BASE_PORT="${POSTGRES_BASE_PORT:-${POSTGRES_HOST_PORT:-15432}}"
API_BASE_PORT="${API_BASE_PORT:-8000}"
WEB_BASE_PORT="${WEB_BASE_PORT:-5173}"
API_LISTEN_HOST="${API_LISTEN_HOST:-0.0.0.0}"
WEB_LISTEN_HOST="${WEB_LISTEN_HOST:-0.0.0.0}"
HEALTHCHECK_HOST="${HEALTHCHECK_HOST:-127.0.0.1}"
DB_HOST="${DB_HOST:-127.0.0.1}"
LOG_DIR="$ROOT_DIR/.logs"
API_PID=""
WEB_PID=""

info() {
  printf '[stock-start] %s\n' "$*"
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
  local pid="${3:-}"
  local log_file="${4:-}"
  local i
  for i in $(seq 1 60); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      info "$name is ready: $url"
      return 0
    fi
    if [ -n "$pid" ] && ! kill -0 "$pid" >/dev/null 2>&1; then
      echo "$name process exited before becoming ready. Check log: $log_file" >&2
      if [ -n "$log_file" ] && [ -f "$log_file" ]; then
        tail -n 80 "$log_file" >&2
      fi
      return 1
    fi
    sleep 1
  done
  echo "$name did not become ready in time. Check logs in $LOG_DIR" >&2
  if [ -n "$log_file" ] && [ -f "$log_file" ]; then
    tail -n 80 "$log_file" >&2
  fi
  return 1
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

cleanup() {
  if [ -n "$API_PID" ] && kill -0 "$API_PID" >/dev/null 2>&1; then
    kill "$API_PID" >/dev/null 2>&1 || true
  fi
  if [ -n "$WEB_PID" ] && kill -0 "$WEB_PID" >/dev/null 2>&1; then
    kill "$WEB_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

if ! command -v docker >/dev/null 2>&1; then
  echo "Missing docker command. Please start/install Docker first." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Missing Docker Compose v2. Please update Docker Desktop." >&2
  exit 1
fi

if [ ! -x ".venv/bin/uvicorn" ] || [ ! -d "frontend/node_modules" ]; then
  info "dependencies are missing; running make install"
  make install
fi

if [ -n "$CONFIGURED_POSTGRES_HOST_PORT" ]; then
  POSTGRES_HOST_PORT="$CONFIGURED_POSTGRES_HOST_PORT"
else
  POSTGRES_HOST_PORT="$(next_available_port "$DB_HOST" "$POSTGRES_BASE_PORT")"
fi
API_PORT="$(next_available_port "$API_LISTEN_HOST" "$API_BASE_PORT")"
WEB_PORT="$(next_available_port "$WEB_LISTEN_HOST" "$WEB_BASE_PORT")"
PUBLIC_HOST="$(detect_public_host)"
DATABASE_URL="postgresql+psycopg://stock:stock@$DB_HOST:$POSTGRES_HOST_PORT/stock"
VITE_DEV_API_PROXY_TARGET="http://$HEALTHCHECK_HOST:$API_PORT"

mkdir -p "$LOG_DIR"
: >"$LOG_DIR/api.log"
: >"$LOG_DIR/web.log"

info "starting PostgreSQL container: host $DB_HOST:$POSTGRES_HOST_PORT -> container postgres:5432"
POSTGRES_HOST_PORT="$POSTGRES_HOST_PORT" docker compose up -d postgres
wait_for_postgres

info "running database migrations"
DATABASE_URL="$DATABASE_URL" scripts/db-upgrade.sh

info "starting API on $API_LISTEN_HOST:$API_PORT, log: $LOG_DIR/api.log"
API_HOST="$API_LISTEN_HOST" API_PORT="$API_PORT" API_RELOAD=0 DATABASE_URL="$DATABASE_URL" scripts/dev-api.sh >"$LOG_DIR/api.log" 2>&1 &
API_PID="$!"
wait_for_url "http://$HEALTHCHECK_HOST:$API_PORT/api/health" "API" "$API_PID" "$LOG_DIR/api.log"

info "starting frontend on $WEB_LISTEN_HOST:$WEB_PORT, log: $LOG_DIR/web.log"
(cd frontend && VITE_API_BASE_URL="" VITE_DEV_API_PROXY_TARGET="$VITE_DEV_API_PROXY_TARGET" npm run dev -- --host "$WEB_LISTEN_HOST" --port "$WEB_PORT") >"$LOG_DIR/web.log" 2>&1 &
WEB_PID="$!"
wait_for_url "http://$HEALTHCHECK_HOST:$WEB_PORT" "Frontend" "$WEB_PID" "$LOG_DIR/web.log"

cat <<EOF

Project is running.

Frontend local: http://$HEALTHCHECK_HOST:$WEB_PORT
Frontend LAN:   http://$PUBLIC_HOST:$WEB_PORT
API local:      http://$HEALTHCHECK_HOST:$API_PORT/api/health
API proxy:      /api -> $VITE_DEV_API_PROXY_TARGET
Database:       $DB_HOST:$POSTGRES_HOST_PORT -> postgres:5432
Logs:     $LOG_DIR

If another LAN computer cannot open Frontend LAN, allow the web port on Ubuntu:
  sudo ufw allow $WEB_PORT/tcp

Press Ctrl+C to stop API and frontend.
PostgreSQL keeps running in Docker. Stop it with:
  docker compose down

EOF

wait "$API_PID" "$WEB_PID"
