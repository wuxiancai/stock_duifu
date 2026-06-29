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

print_port_selection() {
  local name="$1"
  local base_port="$2"
  local selected_port="$3"
  local listen_host="$4"

  if [ "$selected_port" != "$base_port" ]; then
    info "$name base port $base_port is busy on $listen_host; selected available port: $selected_port"
  else
    info "selected $name port: $selected_port"
  fi
}

wait_for_url() {
  local url="$1"
  local name="$2"
  local timeout_seconds="${3:-60}"
  local i
  for i in $(seq 1 "$timeout_seconds"); do
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

print_service_diagnostics() {
  local unit="$1"
  local log_file="$2"
  warn "诊断 systemd 服务：$unit"
  if command -v systemctl >/dev/null 2>&1; then
    sudo_cmd systemctl status "$unit" --no-pager || true
  fi
  if [ -f "$log_file" ]; then
    warn "日志尾部：$log_file"
    tail -n 80 "$log_file" || true
  fi
}

start_fallback_processes() {
  local start_api="${1:-1}"
  local start_web="${2:-1}"
  mkdir -p "$LOG_DIR" "$RUN_DIR"
  if [ "$start_api" = "1" ]; then
    : >"$LOG_DIR/api.log"
    API_HOST="$API_LISTEN_HOST" API_PORT="$API_PORT" API_RELOAD=0 DATABASE_URL="$DATABASE_URL" nohup scripts/dev-api.sh >"$LOG_DIR/api.log" 2>&1 &
    printf '%s\n' "$!" >"$RUN_DIR/api.pid"
  fi
  if [ "$start_web" = "1" ]; then
    : >"$LOG_DIR/web.log"
    VITE_API_BASE_URL="" VITE_DEV_API_PROXY_TARGET="$VITE_DEV_API_PROXY_TARGET" WEB_HOST="$WEB_LISTEN_HOST" WEB_PORT="$WEB_PORT" nohup scripts/dev-web.sh >"$LOG_DIR/web.log" 2>&1 &
    printf '%s\n' "$!" >"$RUN_DIR/web.pid"
  fi
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
  if ! docker_compose_available; then
    info "Docker Compose v2 or Docker daemon permission not available; skipping existing Docker services stop"
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
  print_port_selection "PostgreSQL host" "${CONFIGURED_POSTGRES_HOST_PORT:-$POSTGRES_BASE_PORT}" "$POSTGRES_HOST_PORT" "$DB_HOST"
  print_port_selection "API" "$API_BASE_PORT" "$API_PORT" "$API_LISTEN_HOST"
  print_port_selection "Web" "$WEB_BASE_PORT" "$WEB_PORT" "$WEB_LISTEN_HOST"
  info "browser API requests use same-origin /api -> $VITE_DEV_API_PROXY_TARGET"
}

ensure_dependencies() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "Missing docker command. Please run bash deploy.sh first." >&2
    exit 1
  fi

  if ! docker_compose_available; then
    echo "Missing Docker Compose v2 or Docker daemon permission. Please run bash deploy.sh first." >&2
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

database_date_summary() {
  docker_compose exec -T postgres psql -U stock -d stock -At -F '|' -c "
select
  coalesce((select min(trade_date)::text from stock_daily), '') as stock_daily_start,
  coalesce((select max(trade_date)::text from stock_daily), '') as stock_daily_end,
  coalesce((select max(trade_date)::text from market_daily), '') as market_latest,
  coalesce((select max(trade_date)::text from sector_daily), '') as sector_latest,
  coalesce((select max(trade_date)::text from candidate_stock), '') as candidate_latest,
  coalesce((select max(plan_date)::text from trade_plan), '') as plan_latest;
" 2>/dev/null || true
}

latest_open_data_status() {
  docker_compose exec -T postgres psql -U stock -d stock -At -F '|' -c "
with latest_open as (
  select max(trade_date) as trade_date
  from trading_calendar
  where is_open = true and trade_date <= current_date
)
select
  coalesce((select trade_date::text from latest_open), '') as latest_open_date,
  (select count(*) from stock_daily where trade_date = (select trade_date from latest_open)) as stock_daily_rows,
  (select count(*) from market_daily where trade_date = (select trade_date from latest_open)) as market_rows,
  (select count(*) from sector_daily where trade_date = (select trade_date from latest_open)) as sector_rows,
  (select count(*) from candidate_stock where trade_date = (select trade_date from latest_open)) as candidate_rows,
  (select count(*) from candidate_stock where trade_date = (select trade_date from latest_open) and reason like '%行业持续性%') as current_candidate_rows,
  (select count(*) from candidate_stock where trade_date = (select trade_date from latest_open) and stock_pool_rank is not null) as stock_pool_rows,
  (select count(*) from trade_plan where plan_date = (select trade_date from latest_open)) as plan_rows,
  (
    select count(*)
    from trade_plan tp
    left join trading_calendar tc on tc.trade_date = tp.target_trade_date
    where tp.plan_date = (select trade_date from latest_open)
      and (extract(isodow from tp.target_trade_date) in (6, 7) or tc.is_open = false)
  ) as invalid_target_rows,
  (select count(*) from data_job_run where trade_date = (select trade_date from latest_open) and status in ('success','warning')) as data_jobs;
" 2>/dev/null || true
}

latest_open_data_is_complete() {
  local status_line="$1"
  local latest_open stock_daily_rows market_rows sector_rows candidate_rows current_candidate_rows stock_pool_rows plan_rows invalid_target_rows data_jobs
  if [ -z "$status_line" ]; then
    return 1
  fi
  IFS='|' read -r latest_open stock_daily_rows market_rows sector_rows candidate_rows current_candidate_rows stock_pool_rows plan_rows invalid_target_rows data_jobs <<<"$status_line"
  if [ -z "$latest_open" ]; then
    return 1
  fi
  [ "$stock_daily_rows" -gt 0 ] && [ "$market_rows" -gt 0 ] && [ "$sector_rows" -gt 0 ] && [ "$candidate_rows" -gt 0 ] && [ "$current_candidate_rows" -gt 0 ] && [ "$stock_pool_rows" -gt 0 ] && [ "$plan_rows" -gt 0 ] && [ "$invalid_target_rows" -eq 0 ] && [ "$data_jobs" -gt 0 ]
}

print_latest_open_data_status() {
  local status_line="$1"
  local latest_open stock_daily_rows market_rows sector_rows candidate_rows current_candidate_rows stock_pool_rows plan_rows invalid_target_rows data_jobs
  if [ -z "$status_line" ]; then
    warn "暂时无法读取最新开市日数据状态。"
    return 0
  fi
  IFS='|' read -r latest_open stock_daily_rows market_rows sector_rows candidate_rows current_candidate_rows stock_pool_rows plan_rows invalid_target_rows data_jobs <<<"$status_line"
  cat <<EOF
[stock-start] 最新开市日数据状态：
  最新开市日=${latest_open:-无}
  个股日线行数=$stock_daily_rows
  市场环境行数=$market_rows
  强势行业行数=$sector_rows
  候选股票行数=$candidate_rows
  新口径候选行数=$current_candidate_rows
  股票池排名行数=$stock_pool_rows
  交易计划行数=$plan_rows
  非交易日目标计划行数=$invalid_target_rows
  成功/警告拉数任务数=$data_jobs
EOF
}

print_database_date_summary() {
  local summary
  local stock_start stock_end market_latest sector_latest candidate_latest plan_latest
  summary="$(database_date_summary)"
  if [ -z "$summary" ]; then
    warn "暂时无法读取数据库日期覆盖范围。"
    return 0
  fi
  IFS='|' read -r stock_start stock_end market_latest sector_latest candidate_latest plan_latest <<<"$summary"
  cat <<EOF
[stock-start] 数据日期覆盖范围：
  个股日线：${stock_start:-无} 至 ${stock_end:-无}
  市场环境最新日期：${market_latest:-无}
  强势行业最新日期：${sector_latest:-无}
  候选股票最新日期：${candidate_latest:-无}
  交易计划最新计划日：${plan_latest:-无}
EOF
}

print_manual_data_commands() {
  cat <<EOF
[stock-start] 如需手动补数据，可使用：
  拉取指定交易日：TRADE_DATE=YYYY-MM-DD bash get_data.sh
  拉取指定区间：bash get_data.sh --start YYYYMMDD --end YYYYMMDD
  跳过启动自检：STOCK_START_SKIP_DATA_CHECK=1 bash start.sh
EOF
}

check_and_fill_decision_data() {
  if [ "${STOCK_START_SKIP_DATA_CHECK:-0}" = "1" ]; then
    info "跳过数据健康检查，因为 STOCK_START_SKIP_DATA_CHECK=1。"
    print_database_date_summary
    print_manual_data_commands
    return 0
  fi

  local counts
  local ran_get_data="0"
  counts="$(database_decision_counts)"
  if [ -z "$counts" ]; then
    if [ -z "${TUSHARE_TOKEN:-}" ]; then
      warn "无法读取数据库自检计数，且 TUSHARE_TOKEN 为空；跳过 get_data.sh，先启动空页面。"
      warn "请在 .env 设置 TUSHARE_TOKEN 后执行：bash start.sh 或 TRADE_DATE=YYYY-MM-DD bash get_data.sh"
      print_database_date_summary
      print_manual_data_commands
      return 0
    fi
    warn "无法读取数据库自检计数；将执行 bash get_data.sh 初始化/补齐数据。"
    bash get_data.sh
    ran_get_data="1"
    counts="$(database_decision_counts)"
  fi

  IFS='|' read -r open_days stock_basic_rows stock_daily_dates market_rows sector_rows candidate_rows plan_rows data_jobs <<<"$counts"
  cat <<EOF
[stock-start] 数据库运行数据自检：
  开市交易日数量=$open_days
  股票基础信息行数=$stock_basic_rows
  个股日线交易日数量=$stock_daily_dates
  市场环境行数=$market_rows
  强势行业行数=$sector_rows
  候选股票行数=$candidate_rows
  交易计划行数=$plan_rows
  成功/警告拉数任务数=$data_jobs
EOF

  if [ "$open_days" -lt 20 ] || [ "$stock_daily_dates" -lt 20 ] || [ "$market_rows" -lt 1 ] || [ "$sector_rows" -lt 1 ] || [ "$candidate_rows" -lt 1 ] || [ "$plan_rows" -lt 1 ] || [ "$data_jobs" -lt 1 ]; then
    if [ -z "${TUSHARE_TOKEN:-}" ]; then
      warn "数据库数据不足以完整运行 A 股决策系统，但 TUSHARE_TOKEN 为空；跳过自动拉数，先启动空页面。"
      warn "请在 .env 设置 TUSHARE_TOKEN 后执行：bash start.sh 或 TRADE_DATE=YYYY-MM-DD bash get_data.sh"
      print_database_date_summary
      print_manual_data_commands
      return 0
    fi
    warn "数据库数据不足以完整运行 A 股决策系统；将自动执行 bash get_data.sh 补齐所需数据。"
    warn "get_data.sh 会选择最近已完成开市日；若历史不足 20 个交易日，会自动补最近 25 个开市日。具体日期会在 get_data.sh 日志中逐日打印。"
    if ! bash get_data.sh; then
      warn "get_data.sh 执行失败。请检查 TUSHARE_TOKEN、网络和日志：$LOG_DIR/get_data_cron.log"
      return 1
    fi
    ran_get_data="1"
    info "数据补齐完成；重新检查数据库计数。"
    counts="$(database_decision_counts)"
    IFS='|' read -r open_days stock_basic_rows stock_daily_dates market_rows sector_rows candidate_rows plan_rows data_jobs <<<"$counts"
    cat <<EOF
[stock-start] 数据补齐后的数据库自检：
  开市交易日数量=$open_days
  股票基础信息行数=$stock_basic_rows
  个股日线交易日数量=$stock_daily_dates
  市场环境行数=$market_rows
  强势行业行数=$sector_rows
  候选股票行数=$candidate_rows
  交易计划行数=$plan_rows
  成功/警告拉数任务数=$data_jobs
EOF
  else
    info "数据库已有完整运行基础数据；检查最新开市日是否需要增量补齐。"
    if [ -n "${TUSHARE_TOKEN:-}" ] && [ "${STOCK_START_SKIP_INCREMENTAL_DATA_CHECK:-0}" != "1" ]; then
      local latest_status
      latest_status="$(latest_open_data_status)"
      print_latest_open_data_status "$latest_status"
      if latest_open_data_is_complete "$latest_status"; then
        info "最新开市日数据已完整，本次启动跳过 get_data.sh。"
      else
        info "最新开市日数据不完整，开始执行 bash get_data.sh 增量补齐。"
        if ! bash get_data.sh; then
          warn "增量数据检查失败。系统会继续启动，但建议查看日志并手动补数据。"
          print_manual_data_commands
        else
          ran_get_data="1"
        fi
      fi
    else
      warn "未配置 TUSHARE_TOKEN 或设置了 STOCK_START_SKIP_INCREMENTAL_DATA_CHECK=1，本次不执行最新交易日增量补齐。"
    fi
  fi

  if [ "$ran_get_data" = "1" ]; then
    info "本次启动已执行过 get_data.sh；下方是补齐后的数据库日期范围。"
  else
    info "本次启动未执行 get_data.sh；下方是当前数据库日期范围。"
  fi
  print_database_date_summary
  print_manual_data_commands
}

start_systemd_or_fallback() {
  mkdir -p "$LOG_DIR" "$RUN_DIR"

  if systemd_unit_exists "${SERVICE_PREFIX}-api.service" && systemd_unit_exists "${SERVICE_PREFIX}-web.service"; then
    info "starting API/Web through systemd"
    : >"$LOG_DIR/api.log"
    : >"$LOG_DIR/web.log"
    sudo_cmd systemctl restart "${SERVICE_PREFIX}-api.service"
    sudo_cmd systemctl restart "${SERVICE_PREFIX}-web.service"
  else
    warn "systemd units not installed; falling back to nohup background processes"
    start_fallback_processes 1 1
  fi

  if ! wait_for_url "http://$HEALTHCHECK_HOST:$API_PORT/api/health" "API" 60; then
    print_service_diagnostics "${SERVICE_PREFIX}-api.service" "$LOG_DIR/api.log"
    return 1
  fi
  if ! wait_for_url "http://$HEALTHCHECK_HOST:$WEB_PORT" "Frontend" 60; then
    print_service_diagnostics "${SERVICE_PREFIX}-web.service" "$LOG_DIR/web.log"
    warn "Web systemd service did not become ready; starting Web with nohup fallback."
    if systemd_unit_exists "${SERVICE_PREFIX}-web.service"; then
      sudo_cmd systemctl stop "${SERVICE_PREFIX}-web.service" || true
    fi
    start_fallback_processes 0 1
    wait_for_url "http://$HEALTHCHECK_HOST:$WEB_PORT" "Frontend fallback" 60
  fi
}

check_web_page_access() {
  local web_url="http://$HEALTHCHECK_HOST:$WEB_PORT"
  local lan_host
  lan_host="$(detect_public_host)"
  local lan_url="http://$lan_host:$WEB_PORT"

  info "启动后页面访问检测：$web_url"
  if curl -fsS "$web_url" >/dev/null 2>&1; then
    info "Web 页面本机访问正常：$web_url"
  else
    warn "Web 页面本机访问失败：$web_url。请查看 $LOG_DIR/web.log 或 systemctl status ${SERVICE_PREFIX}-web.service --no-pager"
  fi

  info "局域网访问地址：$lan_url"
  info "如果局域网无法访问，请执行：sudo ufw allow $WEB_PORT/tcp"
  info "API 默认只给前端本机代理使用，通常无需对外放通；如需直接调试 API，可临时放通 $API_PORT/tcp。"
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
  check_web_page_access

  local public_host
  public_host="$(detect_public_host)"

  cat <<EOF

系统已启动。

访问地址：
  本机 Web： http://$HEALTHCHECK_HOST:$WEB_PORT
  局域网 Web：http://$public_host:$WEB_PORT
  API 健康： http://$HEALTHCHECK_HOST:$API_PORT/api/health
  API 代理： /api -> $VITE_DEV_API_PROXY_TARGET
  数据库：   $DB_HOST:$POSTGRES_HOST_PORT -> postgres:5432
  日志目录： $LOG_DIR

端口信息：
  Web：        $WEB_PORT
  API：        $API_PORT
  PostgreSQL： $POSTGRES_HOST_PORT

如果局域网其他电脑打不开页面，请在 Ubuntu 放通 Web 端口：
  sudo ufw allow $WEB_PORT/tcp
API 默认只给 Web 服务在服务器本机代理使用，通常不需要对外放通。
如需直接从外部调试 API，再临时执行：
  sudo ufw allow $API_PORT/tcp

常用命令：
  重新启动系统：bash start.sh
  停止全部服务：bash stop.sh
  查看 API 服务：systemctl status ${SERVICE_PREFIX}-api.service --no-pager
  查看 Web 服务：systemctl status ${SERVICE_PREFIX}-web.service --no-pager
  手动补数据：TRADE_DATE=YYYY-MM-DD bash get_data.sh
  查看夜间拉数日志：tail -n 100 $LOG_DIR/get_data_cron.log

EOF
}

main "$@"
