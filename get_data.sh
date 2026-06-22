#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

DRY_RUN="${STOCK_GET_DATA_DRY_RUN:-0}"
TRADE_DATE="${TRADE_DATE:-${1:-}}"
PROVIDER="${PROVIDER:-auto}"
MEMBER_FETCH_LIMIT="${MEMBER_FETCH_LIMIT:-80}"
CANDIDATE_LIMIT="${CANDIDATE_LIMIT:-50}"
TRADE_PLAN_LIMIT="${TRADE_PLAN_LIMIT:-}"
POSTGRES_HOST_PORT="${POSTGRES_HOST_PORT:-5432}"

info() {
  printf '[stock-data] %s\n' "$*"
}

run_shell() {
  if [ "$DRY_RUN" = "1" ]; then
    printf '+ %s\n' "$*"
    return 0
  fi
  bash -lc "$*"
}

load_env_file() {
  local explicit_database_url="${DATABASE_URL:-}"
  local explicit_tushare_token="${TUSHARE_TOKEN:-}"
  if [ -f ".env" ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
  fi
  if [ -n "$explicit_database_url" ]; then
    DATABASE_URL="$explicit_database_url"
  else
    DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://stock:stock@127.0.0.1:${POSTGRES_HOST_PORT}/stock}"
  fi
  if [ -n "$explicit_tushare_token" ]; then
    TUSHARE_TOKEN="$explicit_tushare_token"
  fi
  export DATABASE_URL TUSHARE_TOKEN
}

china_today() {
  TZ=Asia/Shanghai date +%F
}

require_runtime() {
  if [ ! -x ".venv/bin/python" ]; then
    echo "Missing .venv. Run: bash deploy_ubuntu.sh" >&2
    exit 1
  fi
  if [ ! -x ".venv/bin/alembic" ]; then
    echo "Missing backend dependencies. Run: bash deploy_ubuntu.sh" >&2
    exit 1
  fi
}

require_market_token() {
  if [ -z "${TUSHARE_TOKEN:-}" ]; then
    cat >&2 <<'EOF'
Missing TUSHARE_TOKEN.

get_data.sh runs the real after-close workflow. Sector ranking and candidate
membership currently require TuShare 东方财富板块接口, so mock or empty tokens
are not accepted as completion evidence.

Set it in .env or run:
  TUSHARE_TOKEN=your_token TRADE_DATE=YYYY-MM-DD bash get_data.sh
EOF
    exit 1
  fi
}

run_after_close_workflow() {
  local command
  command="DATABASE_URL='$DATABASE_URL' TUSHARE_TOKEN='${TUSHARE_TOKEN:-}' bash scripts/run-after-close-workflow.sh --trade-date $TRADE_DATE --provider $PROVIDER --member-fetch-limit $MEMBER_FETCH_LIMIT --candidate-limit $CANDIDATE_LIMIT"
  if [ -n "$TRADE_PLAN_LIMIT" ]; then
    command="$command --trade-plan-limit $TRADE_PLAN_LIMIT"
  fi
  info "running after-close workflow for $TRADE_DATE"
  run_shell "$command"
}

run_coverage_audit() {
  info "auditing stored market data coverage for $TRADE_DATE"
  run_shell "DATABASE_URL='$DATABASE_URL' bash scripts/audit-market-data.sh --trade-date $TRADE_DATE"
}

main() {
  load_env_file
  if [ -z "$TRADE_DATE" ]; then
    TRADE_DATE="$(china_today)"
    info "TRADE_DATE not provided; using China date $TRADE_DATE"
  fi

  require_runtime
  require_market_token
  run_shell "DATABASE_URL='$DATABASE_URL' scripts/db-upgrade.sh"
  run_after_close_workflow
  run_coverage_audit

  if [ "$DRY_RUN" = "1" ]; then
    cat <<EOF

Dry run complete. No database rows were changed and no market data was fetched.

EOF
    return
  fi

  cat <<EOF

Data workflow finished for $TRADE_DATE.

The database now contains the market snapshot, market environment, strong
sectors, candidate stocks, and next-trading-day trade plans generated from
real data available to the workflow.

EOF
}

main "$@"
