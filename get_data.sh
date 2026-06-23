#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

DRY_RUN="${STOCK_GET_DATA_DRY_RUN:-0}"
TRADE_DATE="${TRADE_DATE:-}"
START_DATE="${START_DATE:-}"
END_DATE="${END_DATE:-}"
PROVIDER="${PROVIDER:-}"
MEMBER_FETCH_LIMIT="${MEMBER_FETCH_LIMIT:-}"
CANDIDATE_LIMIT="${CANDIDATE_LIMIT:-}"
TRADE_PLAN_LIMIT="${TRADE_PLAN_LIMIT:-}"
POSTGRES_HOST_PORT="${POSTGRES_HOST_PORT:-5432}"
OPEN_DATES_OVERRIDE="${STOCK_GET_DATA_OPEN_DATES:-}"
NOW_OVERRIDE="${STOCK_GET_DATA_NOW:-}"
AFTER_CLOSE_HOUR="${STOCK_GET_DATA_AFTER_CLOSE_HOUR:-18}"
BOOTSTRAP_OPEN_DAYS="${STOCK_GET_DATA_BOOTSTRAP_OPEN_DAYS:-25}"
MIN_HISTORY_OPEN_DAYS="${STOCK_GET_DATA_MIN_HISTORY_OPEN_DAYS:-20}"
STOCK_DAILY_DAYS_OVERRIDE="${STOCK_GET_DATA_STOCK_DAILY_DAYS:-}"

info() {
  printf '[stock-data] %s\n' "$*"
}

usage() {
  cat <<'EOF'
Usage:
  bash get_data.sh [YYYY-MM-DD|YYYYMMDD]
  bash get_data.sh --start YYYYMMDD --end YYYYMMDD

Environment overrides remain supported:
  TRADE_DATE=YYYY-MM-DD bash get_data.sh
  START_DATE=YYYYMMDD END_DATE=YYYYMMDD bash get_data.sh
  PROVIDER=auto|tushare|akshare bash get_data.sh --start YYYYMMDD --end YYYYMMDD

Options:
  --start DATE              Start date for batch mode, accepts YYYYMMDD or YYYY-MM-DD.
  --end DATE                End date for batch mode, accepts YYYYMMDD or YYYY-MM-DD.
  --provider PROVIDER       Data provider: auto, tushare, or akshare.
  --member-fetch-limit N    Sector member fetch limit, default 80.
  --candidate-limit N       Candidate stock limit, default 50.
  --trade-plan-limit N      Trade plan limit.
  -h, --help                Show this help.
EOF
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --start)
        if [ "$#" -lt 2 ]; then
          echo "Missing value for --start" >&2
          exit 2
        fi
        START_DATE="$2"
        shift 2
        ;;
      --end)
        if [ "$#" -lt 2 ]; then
          echo "Missing value for --end" >&2
          exit 2
        fi
        END_DATE="$2"
        shift 2
        ;;
      --provider)
        if [ "$#" -lt 2 ]; then
          echo "Missing value for --provider" >&2
          exit 2
        fi
        PROVIDER="$2"
        shift 2
        ;;
      --member-fetch-limit)
        if [ "$#" -lt 2 ]; then
          echo "Missing value for --member-fetch-limit" >&2
          exit 2
        fi
        MEMBER_FETCH_LIMIT="$2"
        shift 2
        ;;
      --candidate-limit)
        if [ "$#" -lt 2 ]; then
          echo "Missing value for --candidate-limit" >&2
          exit 2
        fi
        CANDIDATE_LIMIT="$2"
        shift 2
        ;;
      --trade-plan-limit)
        if [ "$#" -lt 2 ]; then
          echo "Missing value for --trade-plan-limit" >&2
          exit 2
        fi
        TRADE_PLAN_LIMIT="$2"
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      --*)
        echo "Unknown option: $1" >&2
        usage >&2
        exit 2
        ;;
      *)
        if [ -n "$TRADE_DATE" ]; then
          echo "Only one positional trade date is allowed" >&2
          exit 2
        fi
        TRADE_DATE="$1"
        shift
        ;;
    esac
  done
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
  local explicit_trade_date="${TRADE_DATE:-}"
  local explicit_start_date="${START_DATE:-}"
  local explicit_end_date="${END_DATE:-}"
  local explicit_provider="${PROVIDER:-}"
  local explicit_member_fetch_limit="${MEMBER_FETCH_LIMIT:-}"
  local explicit_candidate_limit="${CANDIDATE_LIMIT:-}"
  local explicit_trade_plan_limit="${TRADE_PLAN_LIMIT:-}"
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
  if [ -n "$explicit_trade_date" ]; then
    TRADE_DATE="$explicit_trade_date"
  fi
  if [ -n "$explicit_start_date" ]; then
    START_DATE="$explicit_start_date"
  fi
  if [ -n "$explicit_end_date" ]; then
    END_DATE="$explicit_end_date"
  fi
  if [ -n "$explicit_provider" ]; then
    PROVIDER="$explicit_provider"
  fi
  if [ -n "$explicit_member_fetch_limit" ]; then
    MEMBER_FETCH_LIMIT="$explicit_member_fetch_limit"
  fi
  if [ -n "$explicit_candidate_limit" ]; then
    CANDIDATE_LIMIT="$explicit_candidate_limit"
  fi
  if [ -n "$explicit_trade_plan_limit" ]; then
    TRADE_PLAN_LIMIT="$explicit_trade_plan_limit"
  fi
  PROVIDER="${PROVIDER:-auto}"
  MEMBER_FETCH_LIMIT="${MEMBER_FETCH_LIMIT:-80}"
  CANDIDATE_LIMIT="${CANDIDATE_LIMIT:-50}"
  export DATABASE_URL TUSHARE_TOKEN
}

default_trade_date() {
  .venv/bin/python - "$OPEN_DATES_OVERRIDE" "$NOW_OVERRIDE" "$AFTER_CLOSE_HOUR" <<'PY'
from datetime import date, datetime, timedelta
import os
import sys

override = sys.argv[1].strip()
now_override = sys.argv[2].strip()
after_close_hour = int(sys.argv[3])

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

def parse_date(raw: str) -> date:
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            pass
    print(f"Invalid open date override: {raw}", file=sys.stderr)
    raise SystemExit(2)

if now_override:
    now = datetime.fromisoformat(now_override)
    if now.tzinfo is not None:
        now = now.astimezone(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None) if ZoneInfo else now.replace(tzinfo=None)
else:
    now = datetime.now(ZoneInfo("Asia/Shanghai")) if ZoneInfo else datetime.now()

today = now.date()
include_today = now.hour >= after_close_hour

if override:
    open_days = sorted(parse_date(item) for item in override.replace(",", " ").split())
else:
    token = os.environ.get("TUSHARE_TOKEN", "")
    if not token:
        print("TUSHARE_TOKEN is required to resolve the default trade date", file=sys.stderr)
        raise SystemExit(1)
    try:
        import tushare as ts
    except ImportError:
        print("tushare is required to resolve the default trade date. Run: bash deploy_ubuntu.sh", file=sys.stderr)
        raise SystemExit(1)
    start = today - timedelta(days=90)
    frame = ts.pro_api(token).trade_cal(
        exchange="",
        start_date=start.strftime("%Y%m%d"),
        end_date=today.strftime("%Y%m%d"),
    )
    open_days = [
        datetime.strptime(str(raw), "%Y%m%d").date()
        for raw in frame[frame["is_open"] == 1]["cal_date"].tolist()
    ]

eligible = [
    item for item in open_days
    if item < today or (include_today and item == today)
]
if not eligible:
    print("No completed open trading date found", file=sys.stderr)
    raise SystemExit(1)
print(max(eligible).isoformat())
PY
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

normalize_date() {
  .venv/bin/python - "$1" <<'PY'
from datetime import datetime
import sys

raw = sys.argv[1].strip()
for fmt in ("%Y-%m-%d", "%Y%m%d"):
    try:
        print(datetime.strptime(raw, fmt).date().isoformat())
        raise SystemExit(0)
    except ValueError:
        pass
print(f"Invalid date: {raw}. Expected YYYYMMDD or YYYY-MM-DD.", file=sys.stderr)
raise SystemExit(2)
PY
}

print_open_date_range() {
  .venv/bin/python - "$1" "$2" "$OPEN_DATES_OVERRIDE" <<'PY'
from datetime import date, datetime
import os
import sys

start = date.fromisoformat(sys.argv[1])
end = date.fromisoformat(sys.argv[2])
override = sys.argv[3].strip()
if start > end:
    print(f"--start must be earlier than or equal to --end: {start} > {end}", file=sys.stderr)
    raise SystemExit(2)

def parse_date(raw: str) -> date:
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            pass
    print(f"Invalid open date override: {raw}", file=sys.stderr)
    raise SystemExit(2)

if override:
    for item in override.replace(",", " ").split():
        current = parse_date(item)
        if start <= current <= end:
            print(current.isoformat())
    raise SystemExit(0)

token = os.environ.get("TUSHARE_TOKEN", "")
if not token:
    print("TUSHARE_TOKEN is required to resolve trading dates", file=sys.stderr)
    raise SystemExit(1)

try:
    import tushare as ts
except ImportError:
    print("tushare is required to resolve trading dates. Run: bash deploy_ubuntu.sh", file=sys.stderr)
    raise SystemExit(1)

pro = ts.pro_api(token)
frame = pro.trade_cal(
    exchange="",
    start_date=start.strftime("%Y%m%d"),
    end_date=end.strftime("%Y%m%d"),
)
if frame.empty:
    raise SystemExit(0)
open_days = frame[frame["is_open"] == 1].sort_values("cal_date")
for raw in open_days["cal_date"].tolist():
    print(datetime.strptime(str(raw), "%Y%m%d").date().isoformat())
PY
}

print_recent_open_dates() {
  .venv/bin/python - "$1" "$2" "$OPEN_DATES_OVERRIDE" <<'PY'
from datetime import date, datetime, timedelta
import os
import sys

end = date.fromisoformat(sys.argv[1])
limit = int(sys.argv[2])
override = sys.argv[3].strip()

def parse_date(raw: str) -> date:
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            pass
    print(f"Invalid open date override: {raw}", file=sys.stderr)
    raise SystemExit(2)

if override:
    open_days = sorted(parse_date(item) for item in override.replace(",", " ").split())
else:
    token = os.environ.get("TUSHARE_TOKEN", "")
    if not token:
        print("TUSHARE_TOKEN is required to resolve trading dates", file=sys.stderr)
        raise SystemExit(1)
    try:
        import tushare as ts
    except ImportError:
        print("tushare is required to resolve trading dates. Run: bash deploy_ubuntu.sh", file=sys.stderr)
        raise SystemExit(1)
    start = end - timedelta(days=max(120, limit * 3))
    frame = ts.pro_api(token).trade_cal(
        exchange="",
        start_date=start.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
    )
    open_days = [
        datetime.strptime(str(raw), "%Y%m%d").date()
        for raw in frame[frame["is_open"] == 1]["cal_date"].tolist()
    ]

selected = [item for item in open_days if item <= end][-limit:]
for item in selected:
    print(item.isoformat())
PY
}

stock_daily_history_days() {
  if [ -n "$STOCK_DAILY_DAYS_OVERRIDE" ]; then
    printf '%s\n' "$STOCK_DAILY_DAYS_OVERRIDE"
    return 0
  fi
  .venv/bin/python - "$DATABASE_URL" "$1" <<'PY'
import sys
from sqlalchemy import create_engine, text

database_url = sys.argv[1]
trade_date = sys.argv[2]
try:
    engine = create_engine(database_url)
    with engine.connect() as connection:
        value = connection.execute(
            text("select count(distinct trade_date) from stock_daily where trade_date <= :trade_date"),
            {"trade_date": trade_date},
        ).scalar()
    print(int(value or 0))
except Exception:
    print(0)
PY
}

run_after_close_workflow() {
  local trade_date="$1"
  local command
  command="DATABASE_URL='$DATABASE_URL' TUSHARE_TOKEN='${TUSHARE_TOKEN:-}' bash scripts/run-after-close-workflow.sh --trade-date $trade_date --provider $PROVIDER --member-fetch-limit $MEMBER_FETCH_LIMIT --candidate-limit $CANDIDATE_LIMIT"
  if [ -n "$TRADE_PLAN_LIMIT" ]; then
    command="$command --trade-plan-limit $TRADE_PLAN_LIMIT"
  fi
  info "running after-close workflow for $trade_date"
  run_shell "$command"
}

run_coverage_audit() {
  local trade_date="$1"
  info "auditing stored market data coverage for $trade_date"
  run_shell "DATABASE_URL='$DATABASE_URL' bash scripts/audit-market-data.sh --trade-date $trade_date"
}

run_one_date() {
  local trade_date="$1"
  run_after_close_workflow "$trade_date"
  run_coverage_audit "$trade_date"
}

validate_mode() {
  if { [ -n "$START_DATE" ] && [ -z "$END_DATE" ]; } || { [ -z "$START_DATE" ] && [ -n "$END_DATE" ]; }; then
    echo "--start and --end must be provided together" >&2
    exit 2
  fi
  if [ -n "$TRADE_DATE" ] && [ -n "$START_DATE" ]; then
    echo "Use either a single trade date or --start/--end, not both" >&2
    exit 2
  fi
}

main() {
  parse_args "$@"
  load_env_file
  validate_mode
  local default_mode="0"

  require_runtime
  require_market_token

  if [ -z "$TRADE_DATE" ] && [ -z "$START_DATE" ]; then
    default_mode="1"
    TRADE_DATE="$(default_trade_date)"
    info "TRADE_DATE not provided; using latest completed open trading date $TRADE_DATE"
  fi

  if [ -n "$TRADE_DATE" ]; then
    TRADE_DATE="$(normalize_date "$TRADE_DATE")"
  fi
  local date_range=""
  if [ -n "$START_DATE" ]; then
    START_DATE="$(normalize_date "$START_DATE")"
    END_DATE="$(normalize_date "$END_DATE")"
    date_range="$(print_open_date_range "$START_DATE" "$END_DATE")"
  fi

  run_shell "DATABASE_URL='$DATABASE_URL' scripts/db-upgrade.sh"

  if [ "$default_mode" = "1" ]; then
    local history_days
    history_days="$(stock_daily_history_days "$TRADE_DATE")"
    if [ "$history_days" -lt "$MIN_HISTORY_OPEN_DAYS" ]; then
      info "stock_daily history has $history_days trading dates; bootstrapping latest $BOOTSTRAP_OPEN_DAYS open trading dates through $TRADE_DATE"
      date_range="$(print_recent_open_dates "$TRADE_DATE" "$BOOTSTRAP_OPEN_DAYS")"
    fi
  fi

  if [ -n "$START_DATE" ]; then
    info "running data workflow from $START_DATE to $END_DATE"
    if [ -z "$date_range" ]; then
      info "no open trading dates found from $START_DATE to $END_DATE; skipping workflow"
    else
      while IFS= read -r trade_date; do
        if [ -z "$trade_date" ]; then
          continue
        fi
        run_one_date "$trade_date"
      done <<< "$date_range"
    fi
  elif [ "$default_mode" = "1" ] && [ -n "$date_range" ]; then
    info "running data workflow for default date set through $TRADE_DATE"
    while IFS= read -r trade_date; do
      if [ -z "$trade_date" ]; then
        continue
      fi
      run_one_date "$trade_date"
    done <<< "$date_range"
  else
    date_range="$(print_open_date_range "$TRADE_DATE" "$TRADE_DATE")"
    if [ -z "$date_range" ]; then
      info "$TRADE_DATE is not an open trading date; skipping workflow"
    else
      run_one_date "$TRADE_DATE"
    fi
  fi

  if [ "$DRY_RUN" = "1" ]; then
    cat <<EOF

Dry run complete. No database rows were changed and no market data was fetched.

EOF
    return
  fi

  if [ -n "$START_DATE" ]; then
    cat <<EOF

Data workflow finished from $START_DATE to $END_DATE.

The database now contains the market snapshots, market environments, strong
sectors, candidate stocks, and next-trading-day trade plans generated from
real data available to the workflow.

EOF
  else
    cat <<EOF

Data workflow finished for $TRADE_DATE.

The database now contains the market snapshot, market environment, strong
sectors, candidate stocks, and next-trading-day trade plans generated from
real data available to the workflow.

EOF
  fi
}

main "$@"
