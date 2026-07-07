from datetime import date

import pytest

from backend.app.data.cli import RouterMarketDataProvider, RouterRealtimeQuoteProvider
from backend.app.data.types import StockDailyRecord
from backend.app.data_source_router import (
    DataDomain,
    DataRequest,
    DataResponse,
    DataSourceRouter,
    DomainPolicy,
    supported_data_sources,
)


class BrokenAdapter:
    name = "broken_source"
    domains = {DataDomain.REALTIME_QUOTE}

    def fetch(self, request: DataRequest) -> DataResponse:
        raise TimeoutError("source timeout")


class EmptyAdapter:
    name = "empty_source"
    domains = {DataDomain.REALTIME_QUOTE}

    def fetch(self, request: DataRequest) -> DataResponse:
        return DataResponse(domain=request.domain, source=self.name, records=[])


class GoodAdapter:
    name = "good_source"
    domains = {DataDomain.REALTIME_QUOTE}

    def fetch(self, request: DataRequest) -> DataResponse:
        return DataResponse(domain=request.domain, source=self.name, records=["ok"], quality="high")


def test_supported_data_sources_include_at_least_ten_mainstream_sources() -> None:
    names = {source["name"] for source in supported_data_sources()}

    assert len(names) >= 10
    assert {
        "tushare",
        "akshare",
        "eastmoney",
        "tencent",
        "sina",
        "netease",
        "ths",
        "baostock",
        "cninfo",
        "exchange_official",
    }.issubset(names)


def test_router_falls_back_after_timeout_and_empty_result() -> None:
    router = DataSourceRouter(
        [BrokenAdapter(), EmptyAdapter(), GoodAdapter()],
        policies=[
            DomainPolicy(
                domain=DataDomain.REALTIME_QUOTE,
                ordered_sources=["broken_source", "empty_source", "good_source"],
                min_rows=1,
            )
        ],
    )

    response = router.fetch(DataRequest(domain=DataDomain.REALTIME_QUOTE, trade_date=date(2026, 7, 7)))

    assert response.source == "good_source"
    assert response.records == ["ok"]
    assert response.is_fallback is True
    assert [attempt.source for attempt in router.attempts] == ["broken_source", "empty_source", "good_source"]
    assert [attempt.status for attempt in router.attempts] == ["failed", "failed", "warning"]
    assert "source timeout" in router.errors[0]
    assert "返回行数不足" in router.errors[1]


def test_router_raises_clear_error_when_all_sources_fail() -> None:
    router = DataSourceRouter(
        [BrokenAdapter(), EmptyAdapter()],
        policies=[
            DomainPolicy(
                domain=DataDomain.REALTIME_QUOTE,
                ordered_sources=["broken_source", "empty_source"],
                min_rows=1,
            )
        ],
    )

    with pytest.raises(RuntimeError, match="所有数据源均失败"):
        router.fetch(DataRequest(domain=DataDomain.REALTIME_QUOTE, trade_date=date(2026, 7, 7)))


class BrokenSnapshotProvider:
    name = "tushare"

    def fetch_snapshot(self, **kwargs):
        raise ConnectionError("tushare unavailable")


class GoodSnapshotProvider:
    name = "akshare_sina"

    def fetch_snapshot(self, **kwargs):
        class Snapshot:
            provider = "akshare_sina"
            stock_daily = ["row"]

        return Snapshot()


def test_router_market_provider_switches_to_next_source() -> None:
    provider = RouterMarketDataProvider([BrokenSnapshotProvider(), GoodSnapshotProvider()])

    snapshot = provider.fetch_snapshot(trade_date=date(2026, 7, 7), sample_size=1)

    assert snapshot.provider == "akshare_sina"
    assert provider.name == "akshare_sina"
    assert provider.router.attempts[0].source == "tushare"
    assert provider.router.attempts[-1].source == "akshare_sina"


class BrokenRealtimeProvider:
    name = "sina_direct_realtime"

    def fetch_realtime_stock_daily(self, stock_codes, trade_date):
        raise ConnectionError("sina unavailable")


class GoodRealtimeProvider:
    name = "eastmoney_direct_realtime"

    def fetch_realtime_stock_daily(self, stock_codes, trade_date):
        return [
            StockDailyRecord(
                stock_code="000001",
                trade_date=trade_date,
                open=10,
                high=11,
                low=9,
                close=10.5,
                pre_close=10,
                change=0.5,
                pct_chg=5,
                volume=100,
                amount=1000,
                turnover_rate=None,
                source=self.name,
            )
        ]


def test_router_realtime_provider_switches_to_next_source() -> None:
    provider = RouterRealtimeQuoteProvider([BrokenRealtimeProvider(), GoodRealtimeProvider()])

    records = provider.fetch_realtime_stock_daily(["000001"], date(2026, 7, 7))

    assert records[0].stock_code == "000001"
    assert provider.name == "eastmoney_direct_realtime"
    assert provider.last_provider_name == "eastmoney_direct_realtime"
    assert provider.router.attempts[0].status == "failed"
    assert provider.router.attempts[-1].status == "warning"
