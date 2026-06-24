import os
import re
import socket
import subprocess
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]


def run_script(path: str, env: Optional[dict[str, str]] = None) -> subprocess.CompletedProcess[str]:
    command_env = os.environ.copy()
    command_env.update(env or {})
    return subprocess.run(
        ["bash", path],
        cwd=ROOT,
        env=command_env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_deploy_script_has_dry_run_and_keeps_database_empty() -> None:
    script = ROOT / "deploy_ubuntu.sh"

    result = run_script(
        str(script),
        {
            "STOCK_DEPLOY_DRY_RUN": "1",
            "FORCE_INSTALL": "1",
            "TUSHARE_TOKEN": "token-for-dry-run",
        },
    )

    assert result.returncode == 0, result.stderr
    assert "pip install -e ." in result.stdout
    assert "npm ci" in result.stdout
    assert "docker compose up -d postgres" in result.stdout
    assert "scripts/db-upgrade.sh" in result.stdout
    assert "does not fetch market data" in result.stdout
    assert "checking Docker daemon and permissions" in result.stdout
    assert "systemctl enable --now docker" in result.stdout
    assert "usermod -aG docker" in result.stdout
    assert "installing systemd services: stock-api.service, stock-web.service" in result.stdout
    assert "systemctl enable stock-api.service stock-web.service" in result.stdout
    assert "get_data.sh" in result.stdout
    assert "installing daily 23:00 get_data.sh cron" in result.stdout
    assert "CRON_TZ=Asia/Shanghai" in result.stdout
    assert "0 23 * * 1-5" in result.stdout
    assert "codex-stock-nightly-get-data" in result.stdout
    assert "After deployment, start the system with:" in result.stdout
    assert "bash start.sh" in result.stdout


def test_deploy_script_uses_high_default_postgres_port_instead_of_5432() -> None:
    script = ROOT / "deploy_ubuntu.sh"

    result = run_script(
        str(script),
        {
            "STOCK_DEPLOY_DRY_RUN": "1",
            "FORCE_INSTALL": "1",
            "TUSHARE_TOKEN": "token-for-dry-run",
        },
    )

    assert result.returncode == 0, result.stderr
    selected_port_match = re.search(r"selected PostgreSQL host port: (\d+)", result.stdout)
    assert selected_port_match is not None, result.stdout
    selected_port = int(selected_port_match.group(1))

    assert selected_port >= 15432
    assert f"POSTGRES_HOST_PORT={selected_port} docker compose up -d postgres" in result.stdout
    assert f"127.0.0.1:{selected_port}/stock" in result.stdout


def test_deploy_script_honors_explicit_postgres_host_port() -> None:
    script = ROOT / "deploy_ubuntu.sh"

    result = run_script(
        str(script),
        {
            "STOCK_DEPLOY_DRY_RUN": "1",
            "FORCE_INSTALL": "1",
            "TUSHARE_TOKEN": "token-for-dry-run",
            "POSTGRES_HOST_PORT": "16432",
        },
    )

    assert result.returncode == 0, result.stderr
    assert "selected PostgreSQL host port: 16432" in result.stdout
    assert "POSTGRES_HOST_PORT=16432 docker compose up -d postgres" in result.stdout
    assert "127.0.0.1:16432/stock" in result.stdout


def test_deploy_script_advances_postgres_port_when_base_port_is_busy() -> None:
    busy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        busy_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        for candidate_port in range(56000, 59000, 2):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.settimeout(0.1)
                if probe.connect_ex(("127.0.0.1", candidate_port + 1)) == 0:
                    continue
            try:
                busy_socket.bind(("127.0.0.1", candidate_port))
                break
            except OSError:
                continue
        else:
            raise AssertionError("No suitable adjacent ports found for deployment port test")

        busy_socket.listen(1)
        busy_port = busy_socket.getsockname()[1]
        expected_port = busy_port + 1

        script = ROOT / "deploy_ubuntu.sh"
        result = run_script(
            str(script),
            {
                "STOCK_DEPLOY_DRY_RUN": "1",
                "FORCE_INSTALL": "1",
                "TUSHARE_TOKEN": "token-for-dry-run",
                "POSTGRES_BASE_PORT": str(busy_port),
            },
        )
    finally:
        busy_socket.close()

    assert result.returncode == 0, result.stderr
    assert f"selected PostgreSQL host port: {expected_port}" in result.stdout
    assert f"POSTGRES_HOST_PORT={expected_port} docker compose up -d postgres" in result.stdout
    assert f"127.0.0.1:{expected_port}/stock" in result.stdout


def test_deploy_script_overrides_stale_local_database_url_when_port_advances() -> None:
    busy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        busy_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        for candidate_port in range(59000, 62000, 2):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.settimeout(0.1)
                if probe.connect_ex(("127.0.0.1", candidate_port + 1)) == 0:
                    continue
            try:
                busy_socket.bind(("127.0.0.1", candidate_port))
                break
            except OSError:
                continue
        else:
            raise AssertionError("No suitable adjacent ports found for stale DATABASE_URL test")

        busy_socket.listen(1)
        busy_port = busy_socket.getsockname()[1]
        expected_port = busy_port + 1

        script = ROOT / "deploy_ubuntu.sh"
        result = run_script(
            str(script),
            {
                "STOCK_DEPLOY_DRY_RUN": "1",
                "FORCE_INSTALL": "1",
                "TUSHARE_TOKEN": "token-for-dry-run",
                "POSTGRES_BASE_PORT": str(busy_port),
                "DATABASE_URL": f"postgresql+psycopg://stock:stock@127.0.0.1:{busy_port}/stock",
            },
        )
    finally:
        busy_socket.close()

    assert result.returncode == 0, result.stderr
    assert f"selected PostgreSQL host port: {expected_port}" in result.stdout
    assert (
        f"DATABASE_URL='postgresql+psycopg://stock:stock@127.0.0.1:{expected_port}/stock' "
        "scripts/db-upgrade.sh"
    ) in result.stdout


def test_get_data_script_runs_after_close_workflow_in_dry_run() -> None:
    script = ROOT / "get_data.sh"

    result = run_script(
        str(script),
        {
            "STOCK_GET_DATA_DRY_RUN": "1",
            "TRADE_DATE": "2026-06-18",
            "STOCK_GET_DATA_OPEN_DATES": "2026-06-18",
            "TUSHARE_TOKEN": "token-for-dry-run",
        },
    )

    assert result.returncode == 0, result.stderr
    assert "bash scripts/run-after-close-workflow.sh --trade-date 2026-06-18" in result.stdout
    assert "--provider auto" in result.stdout
    assert "bash scripts/audit-market-data.sh --trade-date 2026-06-18" in result.stdout


def test_get_data_script_defaults_to_latest_completed_open_date_before_close() -> None:
    script = ROOT / "get_data.sh"

    result = run_script(
        str(script),
        {
            "STOCK_GET_DATA_DRY_RUN": "1",
            "TUSHARE_TOKEN": "token-for-dry-run",
            "STOCK_GET_DATA_OPEN_DATES": "2026-06-22 2026-06-23",
            "STOCK_GET_DATA_NOW": "2026-06-23T09:30:00+08:00",
        },
    )

    assert result.returncode == 0, result.stderr
    assert "using latest completed open trading date 2026-06-22" in result.stdout
    assert "bash scripts/run-after-close-workflow.sh --trade-date 2026-06-22" in result.stdout
    assert "--trade-date 2026-06-23" not in result.stdout


def test_get_data_script_bootstraps_recent_open_dates_when_history_is_missing() -> None:
    script = ROOT / "get_data.sh"

    result = run_script(
        str(script),
        {
            "STOCK_GET_DATA_DRY_RUN": "1",
            "TUSHARE_TOKEN": "token-for-dry-run",
            "STOCK_GET_DATA_OPEN_DATES": "2026-06-18 2026-06-22 2026-06-23",
            "STOCK_GET_DATA_NOW": "2026-06-23T09:30:00+08:00",
            "STOCK_GET_DATA_STOCK_DAILY_DAYS": "0",
            "STOCK_GET_DATA_BOOTSTRAP_OPEN_DAYS": "25",
        },
    )

    assert result.returncode == 0, result.stderr
    assert "stock_daily history has 0 trading dates; bootstrapping latest 25 open trading dates through 2026-06-22" in result.stdout
    assert "bash scripts/run-after-close-workflow.sh --trade-date 2026-06-18" in result.stdout
    assert "bash scripts/run-after-close-workflow.sh --trade-date 2026-06-22" in result.stdout
    assert "--trade-date 2026-06-23" not in result.stdout


def test_get_data_script_defaults_to_today_after_close() -> None:
    script = ROOT / "get_data.sh"

    result = run_script(
        str(script),
        {
            "STOCK_GET_DATA_DRY_RUN": "1",
            "TUSHARE_TOKEN": "token-for-dry-run",
            "STOCK_GET_DATA_OPEN_DATES": "2026-06-22 2026-06-23",
            "STOCK_GET_DATA_NOW": "2026-06-23T20:00:00+08:00",
        },
    )

    assert result.returncode == 0, result.stderr
    assert "using latest completed open trading date 2026-06-23" in result.stdout
    assert "bash scripts/run-after-close-workflow.sh --trade-date 2026-06-23" in result.stdout


def test_get_data_script_skips_closed_dates_in_batch_dry_run() -> None:
    script = ROOT / "get_data.sh"

    result = run_script(
        str(script),
        {
            "STOCK_GET_DATA_DRY_RUN": "1",
            "TUSHARE_TOKEN": "token-for-dry-run",
            "STOCK_GET_DATA_OPEN_DATES": "2026-06-18 2026-06-22",
            "START_DATE": "20260618",
            "END_DATE": "20260622",
        },
    )

    assert result.returncode == 0, result.stderr
    assert "bash scripts/run-after-close-workflow.sh --trade-date 2026-06-18" in result.stdout
    assert "bash scripts/run-after-close-workflow.sh --trade-date 2026-06-22" in result.stdout
    assert "--trade-date 2026-06-19" not in result.stdout
    assert "--trade-date 2026-06-20" not in result.stdout
    assert "--trade-date 2026-06-21" not in result.stdout


def test_get_data_script_skips_closed_single_date_in_dry_run() -> None:
    script = ROOT / "get_data.sh"

    result = run_script(
        str(script),
        {
            "STOCK_GET_DATA_DRY_RUN": "1",
            "TRADE_DATE": "2026-06-21",
            "TUSHARE_TOKEN": "token-for-dry-run",
            "STOCK_GET_DATA_OPEN_DATES": "2026-06-18 2026-06-22",
        },
    )

    assert result.returncode == 0, result.stderr
    assert "2026-06-21 is not an open trading date; skipping workflow" in result.stdout
    assert "bash scripts/run-after-close-workflow.sh --trade-date 2026-06-21" not in result.stdout
    assert "bash scripts/audit-market-data.sh --trade-date 2026-06-21" not in result.stdout


def test_start_script_defaults_to_lan_listen_host() -> None:
    script = (ROOT / "start.sh").read_text()

    assert "CONFIGURED_POSTGRES_HOST_PORT=\"${POSTGRES_HOST_PORT:-}\"" in script
    assert 'POSTGRES_BASE_PORT="${POSTGRES_BASE_PORT:-${POSTGRES_HOST_PORT:-15432}}"' in script
    assert 'API_BASE_PORT="${API_BASE_PORT:-${API_PORT:-8000}}"' in script
    assert 'WEB_BASE_PORT="${WEB_BASE_PORT:-${WEB_PORT:-5173}}"' in script
    assert 'API_LISTEN_HOST="${API_LISTEN_HOST:-${API_HOST:-0.0.0.0}}"' in script
    assert 'WEB_LISTEN_HOST="${WEB_LISTEN_HOST:-${WEB_HOST:-0.0.0.0}}"' in script
    assert 'HEALTHCHECK_HOST="${HEALTHCHECK_HOST:-127.0.0.1}"' in script
    assert 'VITE_DEV_API_PROXY_TARGET="http://$HEALTHCHECK_HOST:$API_PORT"' in script
    assert 'VITE_API_BASE_URL="" VITE_DEV_API_PROXY_TARGET="$VITE_DEV_API_PROXY_TARGET" nohup npm run dev' in script
    assert 'sync_runtime_env' in script
    assert 'upsert_env_key "POSTGRES_HOST_PORT" "$POSTGRES_HOST_PORT"' in script
    assert 'upsert_env_key "DATABASE_URL" "$DATABASE_URL"' in script
    assert 'upsert_env_key "API_PORT" "$API_PORT"' in script
    assert 'upsert_env_key "WEB_PORT" "$WEB_PORT"' in script
    assert 'upsert_env_key "VITE_DEV_API_PROXY_TARGET" "$VITE_DEV_API_PROXY_TARGET"' in script
    assert 'remove_env_key "VITE_API_BASE_URL"' in script
    assert 'synced selected ports to .env' in script
    assert script.index("sync_runtime_env") < script.index("start_postgres")
    assert script.index("check_and_fill_decision_data") < script.index("start_systemd_or_fallback")
    assert "API proxy:      /api -> $VITE_DEV_API_PROXY_TARGET" in script
    assert "sudo ufw allow $WEB_PORT/tcp" in script
    assert "API_RELOAD=0" in script
    assert "sock.bind((host, port))" in script
    assert 'API_PORT="$(next_available_port "$API_LISTEN_HOST" "$API_BASE_PORT")"' in script
    assert 'WEB_PORT="$(next_available_port "$WEB_LISTEN_HOST" "$WEB_BASE_PORT")"' in script
    assert 'POSTGRES_HOST_PORT="$(next_available_port "$DB_HOST" "${CONFIGURED_POSTGRES_HOST_PORT:-$POSTGRES_BASE_PORT}")' in script
    assert "systemd units not installed; falling back to nohup background processes" in script
    assert 'systemctl restart "${SERVICE_PREFIX}-api.service"' in script
    assert 'systemctl restart "${SERVICE_PREFIX}-web.service"' in script
    assert "database decision data check" in script
    assert "bash get_data.sh" in script


def test_start_script_stops_existing_project_before_restart_and_stop_script_exists() -> None:
    script = (ROOT / "start.sh").read_text()

    assert (ROOT / "stop.sh").exists()
    assert "stop_existing_project" in script
    assert script.index("\n  stop_existing_project") > 0
    assert "stop_systemd_services" in script
    assert "project_process_pids" in script
    assert "port_listener_pids" in script
    assert "docker_compose down" in script
    assert "stopping existing project before restart" in script


def test_stop_script_stops_services_processes_and_preserves_database_volume() -> None:
    script = (ROOT / "stop.sh").read_text()

    assert '${SERVICE_PREFIX}-web.service' in script
    assert '${SERVICE_PREFIX}-api.service' in script
    assert "project_process_pids" in script
    assert "pid_file_pids" in script
    assert "port_listener_pids" in script
    assert "docker_compose down --remove-orphans" in script
    assert "PostgreSQL data volume is preserved" in script
    assert "down -v" not in script


def test_vite_dev_server_proxies_same_origin_api_requests() -> None:
    vite_config = (ROOT / "frontend" / "vite.config.ts").read_text()
    dashboard_api = (ROOT / "frontend" / "src" / "api" / "dashboard.ts").read_text()
    health_api = (ROOT / "frontend" / "src" / "api" / "health.ts").read_text()
    env_example = (ROOT / ".env.example").read_text()

    assert "process.env.VITE_DEV_API_PROXY_TARGET" in vite_config
    assert "target: apiProxyTarget" in vite_config
    assert "process.env.VITE_API_BASE_URL" not in vite_config
    assert "VITE_API_BASE_URL" not in env_example
    assert "const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''" in dashboard_api
    assert "const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''" in health_api
