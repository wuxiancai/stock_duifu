from datetime import date

import pandas as pd
import pytest

from backend.app.candidate.providers import EastmoneyIndustrySectorMembershipProvider
from backend.app.data.providers import TushareMarketDataProvider
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
