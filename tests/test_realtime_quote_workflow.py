from datetime import date

import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.data.providers import (
    AkShareRealtimeQuoteProvider,
    AkShareSinaRealtimeQuoteProvider,
    FallbackRealtimeQuoteProvider,
)
from backend.app.data.realtime_quotes import run_realtime_quote_workflow
from backend.app.data.types import StockDailyRecord
from backend.app.db.models import SimulationTrade, StockDaily, TradePlan, TradingCalendar, metadata


def _engine():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    return engine


def _seed_plan(session: Session, stock_code: str = "000001") -> None:
    session.add(
        TradingCalendar(trade_date=date(2026, 6, 19), is_open=True, source="unit-test")
    )
    session.add(
        TradePlan(
            plan_date=date(2026, 6, 18),
            target_trade_date=date(2026, 6, 19),
            stock_code=stock_code,
            stock_name="计划内股票",
            sector_name="科技风格",
            strategy_type="趋势强势",
            stock_score=99,
            sector_score=100,
            market_status="中性",
            buy_condition="目标交易日价格触达计划买入区间",
            buy_price_low=10.0,
            buy_price_high=11.0,
            stop_loss_price=9.5,
            take_profit_price=13.2,
            position_ratio=0.4,
            status="待触发",
            risk_note="严格执行止损",
        )
    )


def _daily(stock_code: str = "000001") -> StockDailyRecord:
    return StockDailyRecord(
        stock_code=stock_code,
        trade_date=date(2026, 6, 19),
        open=10.1,
        high=10.8,
        low=10.0,
        close=10.5,
        pre_close=10.0,
        change=0.5,
        pct_chg=5.0,
        volume=100000,
        amount=105000000,
        turnover_rate=3.0,
        source="unit-test-realtime",
    )


class FakeRealtimeProvider:
    name = "unit-test-realtime"

    def __init__(self, rows: list[StockDailyRecord]):
        self.rows = rows
        self.calls = []

    def fetch_realtime_stock_daily(self, stock_codes, trade_date):
        self.calls.append((list(stock_codes), trade_date))
        wanted = set(stock_codes)
        return [row for row in self.rows if row.stock_code in wanted and row.trade_date == trade_date]


class FailingRealtimeProvider:
    name = "failing-realtime"

    def __init__(self):
        self.calls = []

    def fetch_realtime_stock_daily(self, stock_codes, trade_date):
        self.calls.append((list(stock_codes), trade_date))
        raise RuntimeError("primary disconnected")


def test_akshare_realtime_quote_provider_maps_spot_rows_to_stock_daily_records() -> None:
    frame = pd.DataFrame(
        [
            {
                "代码": "000001",
                "名称": "平安银行",
                "最新价": 10.5,
                "今开": 10.1,
                "最高": 10.8,
                "最低": 10.0,
                "昨收": 10.0,
                "涨跌额": 0.5,
                "涨跌幅": 5.0,
                "成交量": 100000,
                "成交额": 105000000,
                "换手率": 3.0,
            },
            {
                "代码": "000002",
                "最新价": 0,
                "今开": 0,
                "最高": 0,
                "最低": 0,
                "昨收": 10.0,
            },
        ]
    )
    provider = AkShareRealtimeQuoteProvider(spot_fetcher=lambda: frame)

    records = provider.fetch_realtime_stock_daily(["000001", "000002"], date(2026, 6, 19))

    assert len(records) == 1
    record = records[0]
    assert record.stock_code == "000001"
    assert record.trade_date == date(2026, 6, 19)
    assert record.open == 10.1
    assert record.high == 10.8
    assert record.low == 10.0
    assert record.close == 10.5
    assert record.pre_close == 10.0
    assert record.pct_chg == 5.0
    assert record.turnover_rate == 3.0
    assert record.source == "akshare_realtime"


def test_akshare_sina_realtime_quote_provider_maps_sina_spot_rows() -> None:
    frame = pd.DataFrame(
        [
            {
                "symbol": "sh600000",
                "code": "600000",
                "name": "浦发银行",
                "trade": 8.88,
                "open": 8.8,
                "high": 9.0,
                "low": 8.7,
                "settlement": 8.6,
                "pricechange": 0.28,
                "changepercent": 3.25,
                "volume": 123456,
                "amount": 12345678,
                "turnoverratio": 1.23,
            }
        ]
    )
    provider = AkShareSinaRealtimeQuoteProvider(spot_fetcher=lambda: frame)

    records = provider.fetch_realtime_stock_daily(["600000"], date(2026, 6, 19))

    assert len(records) == 1
    record = records[0]
    assert record.stock_code == "600000"
    assert record.close == 8.88
    assert record.pre_close == 8.6
    assert record.change == 0.28
    assert record.pct_chg == 3.25
    assert record.turnover_rate == 1.23
    assert record.source == "akshare_sina_realtime"


def test_fallback_realtime_quote_provider_uses_sina_after_primary_error() -> None:
    primary = FailingRealtimeProvider()
    fallback = FakeRealtimeProvider([_daily("600000")])
    provider = FallbackRealtimeQuoteProvider([primary, fallback])

    records = provider.fetch_realtime_stock_daily(["600000"], date(2026, 6, 19))

    assert len(records) == 1
    assert records[0].stock_code == "600000"
    assert primary.calls == [(["600000"], date(2026, 6, 19))]
    assert fallback.calls == [(["600000"], date(2026, 6, 19))]
    assert provider.last_provider_name == "unit-test-realtime"
    assert provider.name == "unit-test-realtime"
    assert provider.errors == ["failing-realtime: RuntimeError: primary disconnected"]


def test_run_realtime_quote_workflow_backfills_quotes_tracks_plan_and_buys() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_plan(session)
        session.commit()

    provider = FakeRealtimeProvider([_daily()])

    result = run_realtime_quote_workflow(
        engine,
        date(2026, 6, 19),
        provider,
        allow_date_mismatch=True,
    )

    assert result.backfill.planned_stock_count == 1
    assert result.backfill.requested_stock_count == 1
    assert result.backfill.fetched_stock_daily_rows == 1
    assert result.backfill.missing_stock_codes == []
    assert result.backfill.skipped_reason == ""
    assert provider.calls == [(["000001"], date(2026, 6, 19))]
    assert result.workflow is not None
    assert result.workflow.tracking[0].status == "已触发"
    assert result.workflow.simulation.trades[0].trade_type == "买入"

    with Session(engine) as session:
        plan = session.scalar(select(TradePlan).where(TradePlan.stock_code == "000001"))
        assert plan.status == "已触发"
        assert plan.trigger_price is not None
        assert session.scalar(select(StockDaily).where(StockDaily.stock_code == "000001"))
        assert session.scalar(select(SimulationTrade).where(SimulationTrade.stock_code == "000001"))


def test_run_realtime_quote_workflow_runs_when_stock_daily_already_exists() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_plan(session)
        session.add(StockDaily(**_daily().__dict__))
        session.commit()

    provider = FakeRealtimeProvider([])

    result = run_realtime_quote_workflow(
        engine,
        date(2026, 6, 19),
        provider,
        allow_date_mismatch=True,
    )

    assert result.backfill.requested_stock_count == 0
    assert result.backfill.skipped_reason == "目标交易日计划股已有 stock_daily，无需拉取实时行情"
    assert provider.calls == []
    assert result.workflow is not None
    assert result.workflow.tracking[0].status == "已触发"
    assert result.workflow.simulation.trades[0].trade_type == "买入"
