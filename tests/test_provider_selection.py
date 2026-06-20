from datetime import date

import pytest

from backend.app.data.cli import load_provider
from backend.app.data.cli import main as cli_main
from backend.app.data.providers import MissingTushareTokenError, TushareMarketDataProvider


def test_load_provider_prefers_tushare_when_requested() -> None:
    provider = load_provider("tushare", tushare_token="token-value")

    assert isinstance(provider, TushareMarketDataProvider)


def test_tushare_provider_requires_token_for_fetch() -> None:
    provider = TushareMarketDataProvider(token="")

    with pytest.raises(MissingTushareTokenError, match="TUSHARE_TOKEN"):
        provider.fetch_snapshot(trade_date=date(2026, 6, 18), sample_size=5)


def test_auto_provider_falls_back_to_akshare_without_token() -> None:
    provider = load_provider("auto", tushare_token="")

    assert provider.name == "akshare_sina"


def test_cli_reports_missing_tushare_token_without_traceback(monkeypatch, capsys) -> None:
    monkeypatch.setenv("TUSHARE_TOKEN", "")
    monkeypatch.setattr(
        "sys.argv",
        ["market-data", "ingest", "--provider", "tushare", "--trade-date", "2026-06-18"],
    )

    with pytest.raises(SystemExit) as exc:
        cli_main()

    assert exc.value.code == 2
    assert "TUSHARE_TOKEN is required" in capsys.readouterr().err
