from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.data.target_daily import backfill_trade_plan_target_daily
from backend.app.data.types import (
    IndexDailyRecord,
    LimitSnapshotRecord,
    MarketDataSnapshot,
    StockBasicRecord,
    StockDailyRecord,
    TradingCalendarRecord,
)
from backend.app.db.models import DataIngestRun, StockDaily, TradePlan, metadata


def _engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata.create_all(engine)
    return engine


def _add_plan(session: Session, stock_code: str, stock_name: str = "测试股票") -> None:
    session.add(
        TradePlan(
            plan_date=date(2026, 6, 18),
            target_trade_date=date(2026, 6, 19),
            stock_code=stock_code,
            stock_name=stock_name,
            sector_name="科技风格",
            strategy_type="趋势强势",
            stock_score=95,
            sector_score=100,
            market_status="中性",
            buy_condition="回踩 MA5/MA10 不破",
            buy_price_low=10,
            buy_price_high=11,
            stop_loss_price=9.5,
            take_profit_price=13,
            position_ratio=0.4,
            status="待触发",
            risk_note="测试风险",
        )
    )


def _daily(stock_code: str, trade_date: date = date(2026, 6, 19)) -> StockDailyRecord:
    return StockDailyRecord(
        stock_code=stock_code,
        trade_date=trade_date,
        open=10,
        high=10.8,
        low=9.9,
        close=10.5,
        pre_close=10,
        change=0.5,
        pct_chg=5,
        volume=100000,
        amount=105000000,
        turnover_rate=None,
        source="unit-test",
    )


class FakeProvider:
    name = "unit-test"

    def __init__(self, daily_rows: list[StockDailyRecord], is_open: bool = True):
        self.daily_rows = daily_rows
        self.is_open = is_open
        self.calls = []

    def fetch_snapshot(self, trade_date=None, sample_size=30, stock_codes=None):
        self.calls.append((trade_date, sample_size, list(stock_codes or [])))
        codes = set(stock_codes or [])
        return MarketDataSnapshot(
            provider=self.name,
            trade_date=trade_date,
            trading_calendar=[TradingCalendarRecord(trade_date=trade_date, is_open=self.is_open, source=self.name)],
            stock_basic=[
                StockBasicRecord(
                    stock_code=code,
                    stock_name=f"股票{code}",
                    market="SZ",
                    list_date=date(2020, 1, 1),
                    is_st=False,
                    status="active",
                    source=self.name,
                )
                for code in sorted(codes)
            ],
            index_daily=[
                IndexDailyRecord(
                    index_code="000001.SH",
                    trade_date=trade_date,
                    open=3000,
                    high=3010,
                    low=2990,
                    close=3005,
                    volume=1000000,
                    amount=2000000000,
                    source=self.name,
                )
            ],
            stock_daily=[row for row in self.daily_rows if row.stock_code in codes],
            limit_snapshot=[],
        )


def test_backfill_trade_plan_target_daily_fetches_only_missing_plan_stocks() -> None:
    engine = _engine()
    with Session(engine) as session:
        _add_plan(session, "000001", "平安银行")
        _add_plan(session, "000002", "万科A")
        session.add(StockDaily(**_daily("000001").__dict__))
        session.commit()

    provider = FakeProvider([_daily("000002")])

    result = backfill_trade_plan_target_daily(engine, date(2026, 6, 19), provider)

    assert result.planned_stock_count == 2
    assert result.existing_stock_count == 1
    assert result.requested_stock_count == 1
    assert result.fetched_stock_daily_rows == 1
    assert result.target_is_open is True
    assert result.missing_stock_codes == []
    assert provider.calls == [(date(2026, 6, 19), 1, ["000002"])]
    with Session(engine) as session:
        assert session.scalar(select(StockDaily).where(StockDaily.stock_code == "000002"))
        assert session.scalar(select(DataIngestRun).where(DataIngestRun.provider == "unit-test"))


def test_backfill_trade_plan_target_daily_reports_provider_missing_rows() -> None:
    engine = _engine()
    with Session(engine) as session:
        _add_plan(session, "000001", "平安银行")
        _add_plan(session, "000002", "万科A")
        session.commit()

    provider = FakeProvider([_daily("000001")])

    result = backfill_trade_plan_target_daily(engine, date(2026, 6, 19), provider)

    assert result.requested_stock_count == 2
    assert result.fetched_stock_daily_rows == 1
    assert result.target_is_open is True
    assert result.missing_stock_codes == ["000002"]


def test_backfill_trade_plan_target_daily_reports_closed_target_date() -> None:
    engine = _engine()
    with Session(engine) as session:
        _add_plan(session, "000001", "平安银行")
        session.commit()

    provider = FakeProvider([], is_open=False)

    result = backfill_trade_plan_target_daily(engine, date(2026, 6, 19), provider)

    assert result.target_is_open is False
    assert result.fetched_stock_daily_rows == 0
    assert result.missing_stock_codes == ["000001"]


def test_backfill_trade_plan_target_daily_skips_fetch_when_all_plan_daily_exists() -> None:
    engine = _engine()
    with Session(engine) as session:
        _add_plan(session, "000001", "平安银行")
        session.add(StockDaily(**_daily("000001").__dict__))
        session.commit()

    provider = FakeProvider([_daily("000001")])

    result = backfill_trade_plan_target_daily(engine, date(2026, 6, 19), provider)

    assert result.requested_stock_count == 0
    assert result.ingest_summary is None
    assert provider.calls == []
