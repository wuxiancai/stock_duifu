from datetime import date
from types import SimpleNamespace

import pandas as pd
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
        "backend.app.data.cli.get_settings",
        lambda: SimpleNamespace(tushare_token=""),
    )
    monkeypatch.setattr(
        "sys.argv",
        ["market-data", "ingest", "--provider", "tushare", "--trade-date", "2026-06-18"],
    )

    with pytest.raises(SystemExit) as exc:
        cli_main()

    assert exc.value.code == 2
    assert "TUSHARE_TOKEN is required" in capsys.readouterr().err


def test_tushare_provider_maps_real_api_frames_to_snapshot_records() -> None:
    class FakeTushareClient:
        def trade_cal(self, **kwargs):
            return pd.DataFrame(
                [
                    {"cal_date": "20260618", "is_open": 1},
                    {"cal_date": "20260619", "is_open": 0},
                ]
            )

        def stock_basic(self, **kwargs):
            return pd.DataFrame(
                [
                    {
                        "ts_code": "000001.SZ",
                        "symbol": "000001",
                        "name": "平安银行",
                        "market": "主板",
                        "list_date": "19910403",
                    }
                ]
            )

        def index_daily(self, **kwargs):
            return pd.DataFrame(
                [
                    {
                        "ts_code": kwargs["ts_code"],
                        "trade_date": "20260618",
                        "open": 4094.23,
                        "high": 4117.45,
                        "low": 4080.29,
                        "close": 4090.48,
                        "vol": 658116068.0,
                        "amount": 1560473972.7,
                    }
                ]
            )

        def daily(self, **kwargs):
            return pd.DataFrame(
                [
                    {
                        "ts_code": kwargs["ts_code"],
                        "trade_date": "20260618",
                        "open": 10.74,
                        "high": 10.77,
                        "low": 10.52,
                        "close": 10.52,
                        "pre_close": 10.78,
                        "change": -0.26,
                        "pct_chg": -2.4119,
                        "vol": 1426893.16,
                        "amount": 1511009.56495,
                    }
                ]
            )

        def limit_list_d(self, **kwargs):
            return pd.DataFrame(
                [
                    {
                        "trade_date": "20260618",
                        "ts_code": "000001.SZ",
                        "name": "平安银行",
                        "close": 10.52,
                        "pct_chg": 9.99,
                        "amount": 1000,
                        "limit": "U",
                    },
                    {
                        "trade_date": "20260618",
                        "ts_code": "600519.SH",
                        "name": "贵州茅台",
                        "close": 1215,
                        "pct_chg": -9.99,
                        "amount": 2000,
                        "limit": "D",
                    },
                ]
            )

    provider = TushareMarketDataProvider(token="token-value", pro_client=FakeTushareClient())

    snapshot = provider.fetch_snapshot(
        trade_date=date(2026, 6, 18),
        stock_codes=["000001"],
        sample_size=1,
    )

    assert snapshot.provider == "tushare"
    assert snapshot.trade_date == date(2026, 6, 18)
    assert snapshot.trading_calendar[0].is_open is True
    assert snapshot.stock_basic[0].stock_code == "000001"
    assert snapshot.index_daily[0].index_code == "000001.SH"
    assert snapshot.index_daily[0].amount == 1560473972700.0
    assert snapshot.stock_daily[0].amount == 1511009564.95
    assert {record.limit_status for record in snapshot.limit_snapshot} == {
        "limit_up",
        "limit_down",
    }


def test_tushare_provider_uses_trade_date_daily_for_all_stocks() -> None:
    class FakeTushareClient:
        def __init__(self):
            self.daily_kwargs = []

        def trade_cal(self, **kwargs):
            return pd.DataFrame([{"cal_date": "20260618", "is_open": 1}])

        def stock_basic(self, **kwargs):
            return pd.DataFrame(
                [
                    {"ts_code": "000001.SZ", "symbol": "000001", "name": "平安银行", "market": "主板", "list_date": "19910403"},
                    {"ts_code": "600519.SH", "symbol": "600519", "name": "贵州茅台", "market": "主板", "list_date": "20010827"},
                ]
            )

        def index_daily(self, **kwargs):
            return pd.DataFrame(
                [{"ts_code": kwargs["ts_code"], "trade_date": "20260618", "open": 1, "high": 2, "low": 1, "close": 2, "vol": 100, "amount": 200}]
            )

        def daily(self, **kwargs):
            self.daily_kwargs.append(kwargs)
            return pd.DataFrame(
                [
                    {"ts_code": "000001.SZ", "trade_date": "20260618", "open": 10, "high": 11, "low": 9, "close": 10.5, "pre_close": 10, "change": 0.5, "pct_chg": 5, "vol": 100, "amount": 1000},
                    {"ts_code": "600519.SH", "trade_date": "20260618", "open": 1200, "high": 1220, "low": 1190, "close": 1215, "pre_close": 1200, "change": 15, "pct_chg": 1.25, "vol": 200, "amount": 2000},
                ]
            )

        def limit_list_d(self, **kwargs):
            return pd.DataFrame([])

    client = FakeTushareClient()
    provider = TushareMarketDataProvider(token="token-value", pro_client=client)

    snapshot = provider.fetch_snapshot(trade_date=date(2026, 6, 18), sample_size=0)

    assert client.daily_kwargs == [{"trade_date": "20260618"}]
    assert len(snapshot.stock_basic) == 2
    assert len(snapshot.stock_daily) == 2


def test_tushare_provider_fetches_index_history_for_ma20() -> None:
    class FakeTushareClient:
        def __init__(self):
            self.index_daily_kwargs = []

        def trade_cal(self, **kwargs):
            return pd.DataFrame([{"cal_date": "20260618", "is_open": 1}])

        def stock_basic(self, **kwargs):
            return pd.DataFrame(
                [{"ts_code": "000001.SZ", "symbol": "000001", "name": "平安银行", "market": "主板", "list_date": "19910403"}]
            )

        def index_daily(self, **kwargs):
            self.index_daily_kwargs.append(kwargs)
            return pd.DataFrame(
                [
                    {"ts_code": kwargs["ts_code"], "trade_date": "20260520", "open": 1, "high": 2, "low": 1, "close": 1, "vol": 100, "amount": 200},
                    {"ts_code": kwargs["ts_code"], "trade_date": "20260618", "open": 2, "high": 3, "low": 1, "close": 2, "vol": 100, "amount": 200},
                ]
            )

        def daily(self, **kwargs):
            return pd.DataFrame(
                [{"ts_code": "000001.SZ", "trade_date": "20260618", "open": 10, "high": 11, "low": 9, "close": 10.5, "pre_close": 10, "change": 0.5, "pct_chg": 5, "vol": 100, "amount": 1000}]
            )

        def limit_list_d(self, **kwargs):
            return pd.DataFrame([])

    client = FakeTushareClient()
    provider = TushareMarketDataProvider(token="token-value", pro_client=client)

    snapshot = provider.fetch_snapshot(trade_date=date(2026, 6, 18), sample_size=0)

    assert len(snapshot.index_daily) == 12
    assert {record.index_code for record in snapshot.index_daily} == {
        "000001.SH",
        "399001.SZ",
        "399006.SZ",
        "000688.SH",
        "000300.SH",
        "399330.SZ",
    }
    assert client.index_daily_kwargs[0]["start_date"] < "20260618"
