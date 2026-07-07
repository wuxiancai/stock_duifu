from datetime import date

import pandas as pd
import pytest

from backend.app.candidate.providers import EastmoneyIndustrySectorMembershipProvider
from backend.app.data.providers import TushareMarketDataProvider, infer_limit_snapshot_from_daily
from backend.app.sector.providers import EastmoneyIndustrySectorDataProvider


def test_tushare_market_provider_uses_injected_free_limit_pool_fetcher() -> None:
    called_dates = []

    class FakeTushareClient:
        def trade_cal(self, **kwargs):
            return pd.DataFrame([{"cal_date": "20260618", "is_open": 1}])

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
                        "open": 1,
                        "high": 2,
                        "low": 1,
                        "close": 2,
                        "vol": 100,
                        "amount": 200,
                    }
                ]
            )

        def daily(self, **kwargs):
            return pd.DataFrame(
                [
                    {
                        "ts_code": "000001.SZ",
                        "trade_date": "20260618",
                        "open": 10,
                        "high": 11,
                        "low": 9,
                        "close": 10.5,
                        "pre_close": 10,
                        "change": 0.5,
                        "pct_chg": 5,
                        "vol": 100,
                        "amount": 1000,
                    }
                ]
            )

    def fake_limit_pool(trade_date):
        called_dates.append(trade_date)
        return []

    provider = TushareMarketDataProvider(
        token="token-value",
        pro_client=FakeTushareClient(),
        limit_snapshot_fetcher=fake_limit_pool,
    )

    snapshot = provider.fetch_snapshot(trade_date=date(2026, 6, 18), sample_size=1)

    assert called_dates == [date(2026, 6, 18)]
    assert snapshot.limit_snapshot == []


def test_infers_limit_snapshot_from_full_market_daily_when_limit_pool_fails() -> None:
    from backend.app.data.types import StockBasicRecord, StockDailyRecord

    stock_basic = [
        StockBasicRecord("000001", "平安银行", "主板", None, False, "active", "tushare"),
        StockBasicRecord("300001", "特锐德", "创业板", None, False, "active", "tushare"),
        StockBasicRecord("600001", "邯郸钢铁", "主板", None, False, "active", "tushare"),
    ]
    stock_daily = [
        StockDailyRecord("000001", date(2026, 7, 6), 10, 11, 10, 11, 10, 1, 10.0, 100, 1000, None, "tushare"),
        StockDailyRecord("300001", date(2026, 7, 6), 10, 12, 10, 12, 10, 2, 20.0, 100, 1000, None, "tushare"),
        StockDailyRecord("600001", date(2026, 7, 6), 10, 10, 9, 9, 10, -1, -10.0, 100, 1000, None, "tushare"),
    ]

    records = infer_limit_snapshot_from_daily(stock_daily, stock_basic)

    assert [(record.stock_code, record.stock_name, record.limit_status) for record in records] == [
        ("000001", "平安银行", "limit_up"),
        ("300001", "特锐德", "limit_up"),
        ("600001", "邯郸钢铁", "limit_down"),
    ]


def test_tushare_market_provider_infers_limits_when_free_limit_pool_fails() -> None:
    class FakeTushareClient:
        def trade_cal(self, **kwargs):
            return pd.DataFrame([{"cal_date": "20260706", "is_open": 1}])

        def stock_basic(self, **kwargs):
            return pd.DataFrame(
                [
                    {"ts_code": "000001.SZ", "symbol": "000001", "name": "平安银行", "market": "主板", "list_date": "19910403"},
                    {"ts_code": "600001.SH", "symbol": "600001", "name": "邯郸钢铁", "market": "主板", "list_date": "19910403"},
                ]
            )

        def index_daily(self, **kwargs):
            return pd.DataFrame(
                [{"ts_code": kwargs["ts_code"], "trade_date": "20260706", "open": 1, "high": 2, "low": 1, "close": 2, "vol": 100, "amount": 200}]
            )

        def daily(self, **kwargs):
            return pd.DataFrame(
                [
                    {"ts_code": "000001.SZ", "trade_date": "20260706", "open": 10, "high": 11, "low": 10, "close": 11, "pre_close": 10, "change": 1, "pct_chg": 10, "vol": 100, "amount": 1000},
                    {"ts_code": "600001.SH", "trade_date": "20260706", "open": 10, "high": 10, "low": 9, "close": 9, "pre_close": 10, "change": -1, "pct_chg": -10, "vol": 100, "amount": 1000},
                ]
            )

    provider = TushareMarketDataProvider(
        token="token-value",
        pro_client=FakeTushareClient(),
        limit_snapshot_fetcher=lambda trade_date: (_ for _ in ()).throw(ConnectionError("push2ex timeout")),
    )

    snapshot = provider.fetch_snapshot(trade_date=date(2026, 7, 6), sample_size=0)

    assert {record.limit_status for record in snapshot.limit_snapshot} == {"limit_up", "limit_down"}
    assert {record.source for record in snapshot.limit_snapshot} == {"inferred_from_stock_daily"}


def test_eastmoney_industry_provider_maps_free_industry_rows() -> None:
    def industry_fetcher():
        return pd.DataFrame(
            [
                {"板块名称": "半导体", "板块代码": "BK001", "涨跌幅": 3.2, "成交额": 1000000000, "上涨家数": 20, "下跌家数": 5},
            ]
        )

    def history_fetcher(**kwargs):
        return pd.DataFrame(
            [
                {"日期": "2026-06-17", "涨跌幅": 1.0, "成交额": 800000000},
                {"日期": "2026-06-18", "涨跌幅": 3.2, "成交额": 1000000000},
            ]
        )

    def member_fetcher(**kwargs):
        return pd.DataFrame([{"代码": "000001"}, {"代码": "600519"}])

    provider = EastmoneyIndustrySectorDataProvider(
        industry_fetcher=industry_fetcher,
        history_fetcher=history_fetcher,
        member_fetcher=member_fetcher,
        member_fetch_limit=1,
    )

    records = provider.fetch_sector_window(date(2026, 6, 18))

    assert [record.trade_date for record in records] == [date(2026, 6, 17), date(2026, 6, 18)]
    assert records[-1].sector_name == "半导体"
    assert records[-1].member_codes == ["000001", "600519"]
    assert records[-1].source == "akshare_eastmoney_industry"


def test_eastmoney_industry_membership_provider_maps_free_members() -> None:
    def member_fetcher(**kwargs):
        return pd.DataFrame([{"代码": "000001"}, {"代码": "600519"}])

    provider = EastmoneyIndustrySectorMembershipProvider(
        trade_date=date(2026, 6, 18),
        member_fetcher=member_fetcher,
    )

    assert provider.sector_members(["半导体"]) == {"半导体": ["000001", "600519"]}


def test_eastmoney_industry_membership_provider_raises_when_all_members_fail() -> None:
    def member_fetcher(**kwargs):
        raise ConnectionError("remote closed")

    provider = EastmoneyIndustrySectorMembershipProvider(
        trade_date=date(2026, 6, 18),
        member_fetcher=member_fetcher,
    )

    with pytest.raises(RuntimeError, match="东方财富行业成分股接口全部失败"):
        provider.sector_members(["半导体", "机器人"])
