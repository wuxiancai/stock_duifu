import os
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
    assert "get_data.sh" in result.stdout


def test_get_data_script_runs_after_close_workflow_in_dry_run() -> None:
    script = ROOT / "get_data.sh"

    result = run_script(
        str(script),
        {
            "STOCK_GET_DATA_DRY_RUN": "1",
            "TRADE_DATE": "2026-06-18",
            "TUSHARE_TOKEN": "token-for-dry-run",
        },
    )

    assert result.returncode == 0, result.stderr
    assert "scripts/run-after-close-workflow.sh --trade-date 2026-06-18" in result.stdout
    assert "--provider auto" in result.stdout
    assert "scripts/audit-market-data.sh --trade-date 2026-06-18" in result.stdout


def test_start_script_defaults_to_lan_listen_host() -> None:
    script = (ROOT / "start.sh").read_text()

    assert 'API_LISTEN_HOST="${API_LISTEN_HOST:-0.0.0.0}"' in script
    assert 'WEB_LISTEN_HOST="${WEB_LISTEN_HOST:-0.0.0.0}"' in script
    assert 'HEALTHCHECK_HOST="${HEALTHCHECK_HOST:-127.0.0.1}"' in script
    assert "VITE_API_BASE_URL=\"http://$PUBLIC_HOST:$API_PORT\"" in script
