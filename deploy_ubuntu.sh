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
  printf '[股票部署] %s\n' "$*"
}

warn() {
  printf '[股票部署] %s\n' "$*" >&2
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

configure_tushare_token() {
  local input_token=""

  if [ -n "${TUSHARE_TOKEN:-}" ]; then
    info "已检测到 TuShare Token，将写入 .env 供后续自动拉数使用。"
    upsert_env_key "TUSHARE_TOKEN" "$TUSHARE_TOKEN"
    return 0
  fi

  if [ "$DRY_RUN" = "1" ]; then
    info "演练模式：真实部署时会询问 TuShare Token；直接回车可跳过。"
    return 0
  fi

  if [ -t 0 ]; then
    printf '\n请输入 TuShare Token；没有则直接回车跳过： '
    read -r input_token
    if [ -n "$input_token" ]; then
      TUSHARE_TOKEN="$input_token"
      export TUSHARE_TOKEN
      upsert_env_key "TUSHARE_TOKEN" "$TUSHARE_TOKEN"
      info "TuShare Token 已写入 .env。"
    else
      warn "未填写 TuShare Token：系统仍会启动，但不会自动拉取真实行情数据。"
    fi
  else
    warn "当前不是交互终端，无法询问 TuShare Token；如需自动拉数，请手动在 .env 中配置 TUSHARE_TOKEN。"
  fi
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

  info "安装工作日 23:00 自动拉数任务：bash get_data.sh"
  run mkdir -p "$ROOT_DIR/.logs"
  run_shell "(crontab -l 2>/dev/null | grep -v '$marker'; printf '%s\n' '$timezone_line'; printf '%s\n' '$cron_line') | crontab -"
}

auto_start_app() {
  if [ "${STOCK_DEPLOY_SKIP_START:-0}" = "1" ]; then
    warn "已设置 STOCK_DEPLOY_SKIP_START=1，跳过部署后的自动启动。"
    return 0
  fi

  info "部署步骤完成，开始自动执行 bash start.sh 启动系统。"
  if [ "$DRY_RUN" = "1" ]; then
    printf '+ bash start.sh\n'
    return 0
  fi
  bash start.sh
}

main() {
  info "deploying from $ROOT_DIR"
  ensure_system_packages
  ensure_node_runtime
  ensure_docker_permission
  ensure_env_file
  load_env_file
  configure_tushare_token
  select_runtime_ports
  configure_database_url
  sync_runtime_env
  ensure_python_dependencies
  ensure_frontend_dependencies
  start_database
  run_migrations
  write_systemd_units
  install_nightly_cron
  auto_start_app

  if [ "$DRY_RUN" = "1" ]; then
    cat <<EOF

部署演练完成：没有真正修改文件、安装软件、启动容器、写入服务或拉取行情数据。

真实部署会执行以下动作：
  1. 检查并安装 Ubuntu 依赖、Docker、Node.js 和 Python 环境。
  2. 创建或复用 .env，并在需要时询问 TuShare Token；回车可跳过。
  3. 启动 PostgreSQL 容器并执行数据库迁移。
  4. 安装 systemd 服务：${SERVICE_PREFIX}-api.service、${SERVICE_PREFIX}-web.service。
  5. 安装工作日 23:00 自动拉数任务：bash get_data.sh。
  6. 自动执行 bash start.sh 启动系统。

常用命令：
  查看服务状态：systemctl status ${SERVICE_PREFIX}-api.service ${SERVICE_PREFIX}-web.service --no-pager
  查看夜间拉数日志：tail -n 100 $ROOT_DIR/.logs/get_data_cron.log
  手动拉取数据：TRADE_DATE=YYYY-MM-DD bash get_data.sh
  重启系统：bash start.sh
  停止系统：bash stop.sh

EOF
    return
  fi

  cat <<EOF

部署完成，系统已尝试自动启动。

端口信息：
  Web 页面端口：      $WEB_PORT
  API 服务端口：      $API_PORT
  PostgreSQL 宿主端口：$POSTGRES_HOST_PORT

访问地址：
  本机 Web： http://$HEALTHCHECK_HOST:$WEB_PORT
  API 健康： http://$HEALTHCHECK_HOST:$API_PORT/api/health

数据说明：
  - deploy_ubuntu.sh 只负责部署、迁移和启动。
  - start.sh 会检查数据库是否已有 A 股决策数据。
  - 如果 .env 中有 TUSHARE_TOKEN，首次启动会自动执行 get_data.sh 拉取真实行情并生成强势行业、候选股和交易计划。
  - 如果没有 TUSHARE_TOKEN，系统会启动为空页面；后续补 token 后执行 bash start.sh 或 TRADE_DATE=YYYY-MM-DD bash get_data.sh 即可补数据。

已安装自动任务：
  工作日 23:00 中国时区自动执行：bash get_data.sh
  日志文件：$ROOT_DIR/.logs/get_data_cron.log

已安装 systemd 服务：
  ${SERVICE_PREFIX}-api.service
  ${SERVICE_PREFIX}-web.service

常用命令：
  查看 API 服务：systemctl status ${SERVICE_PREFIX}-api.service --no-pager
  查看 Web 服务：systemctl status ${SERVICE_PREFIX}-web.service --no-pager
  查看部署/启动日志：tail -n 100 $ROOT_DIR/.logs/api.log && tail -n 100 $ROOT_DIR/.logs/web.log
  查看夜间拉数日志：tail -n 100 $ROOT_DIR/.logs/get_data_cron.log
  手动补数据：TRADE_DATE=YYYY-MM-DD bash get_data.sh
  重新启动：bash start.sh
  停止全部：bash stop.sh

如果刚才把用户加入了 docker 组，请重新登录服务器，让 Docker 权限在交互终端中生效。

EOF
}

main "$@"
