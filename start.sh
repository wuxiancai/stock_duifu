#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

POSTGRES_BASE_PORT="${POSTGRES_BASE_PORT:-5432}"
API_BASE_PORT="${API_BASE_PORT:-8000}"
WEB_BASE_PORT="${WEB_BASE_PORT:-5173}"
HOST="127.0.0.1"
LOG_DIR="$ROOT_DIR/.logs"
API_PID=""
WEB_PID=""

info() {
  printf '[stock-start] %s\n' "$*"
}

is_port_available() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    ! lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
  else
    ! nc -z "$HOST" "$port" >/dev/null 2>&1
  fi
}

next_available_port() {
  local port="$1"
  while ! is_port_available "$port"; do
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
    if docker compose exec -T postgres pg_isready -U stock -d stock >/dev/null 2>&1; then
      info "PostgreSQL is ready in Docker: postgres:5432"
      return 0
    fi
    sleep 1
  done
  echo "PostgreSQL did not become ready in time." >&2
  return 1
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

POSTGRES_HOST_PORT="$(next_available_port "$POSTGRES_BASE_PORT")"
API_PORT="$(next_available_port "$API_BASE_PORT")"
WEB_PORT="$(next_available_port "$WEB_BASE_PORT")"
API_HOST="$HOST"
WEB_HOST="$HOST"
DATABASE_URL="postgresql+psycopg://stock:stock@$HOST:$POSTGRES_HOST_PORT/stock"
VITE_API_BASE_URL="http://$API_HOST:$API_PORT"

mkdir -p "$LOG_DIR"

info "starting PostgreSQL container: host $HOST:$POSTGRES_HOST_PORT -> container postgres:5432"
POSTGRES_HOST_PORT="$POSTGRES_HOST_PORT" docker compose up -d postgres
wait_for_postgres

info "running database migrations"
DATABASE_URL="$DATABASE_URL" scripts/db-upgrade.sh

info "starting API on $API_HOST:$API_PORT, log: $LOG_DIR/api.log"
API_HOST="$API_HOST" API_PORT="$API_PORT" DATABASE_URL="$DATABASE_URL" scripts/dev-api.sh >"$LOG_DIR/api.log" 2>&1 &
API_PID="$!"
wait_for_url "http://$API_HOST:$API_PORT/api/health" "API"

info "starting frontend on $WEB_HOST:$WEB_PORT, log: $LOG_DIR/web.log"
(cd frontend && VITE_API_BASE_URL="$VITE_API_BASE_URL" npm run dev -- --host "$WEB_HOST" --port "$WEB_PORT") >"$LOG_DIR/web.log" 2>&1 &
WEB_PID="$!"
wait_for_url "http://$WEB_HOST:$WEB_PORT" "Frontend"

cat <<EOF

Project is running.

Frontend: http://$WEB_HOST:$WEB_PORT
API:      http://$API_HOST:$API_PORT/api/health
Database: $HOST:$POSTGRES_HOST_PORT -> postgres:5432
Logs:     $LOG_DIR

Press Ctrl+C to stop API and frontend.
PostgreSQL keeps running in Docker. Stop it with:
  docker compose down

EOF

wait "$API_PID" "$WEB_PID"
