from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.data.ingest import ingest_market_snapshot
from backend.app.data.types import (
    IndexDailyRecord,
    LimitSnapshotRecord,
    MarketDataSnapshot,
    StockBasicRecord,
    StockDailyRecord,
    TradingCalendarRecord,
)
from backend.app.db.models import (
    DataIngestRun,
    IndexDaily,
    LimitSnapshot,
    StockBasic,
    StockDaily,
    TradingCalendar,
    metadata,
)


def _engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata.create_all(engine)
    return engine


def _snapshot(stock_name: str = "平安银行") -> MarketDataSnapshot:
    trade_date = date(2026, 6, 19)
    return MarketDataSnapshot(
        provider="unit-test",
        trade_date=trade_date,
        trading_calendar=[
            TradingCalendarRecord(trade_date=trade_date, is_open=True, source="unit-test")
        ],
        stock_basic=[
            StockBasicRecord(
                stock_code="000001",
                stock_name=stock_name,
                market="SZ",
                list_date=date(1991, 4, 3),
                is_st=False,
                status="active",
                source="unit-test",
            )
        ],
        index_daily=[
            IndexDailyRecord(
                index_code="000001.SH",
                trade_date=trade_date,
                open=3000,
                high=3030,
                low=2990,
                close=3020,
                volume=1000000,
                amount=2500000000,
                source="unit-test",
            )
        ],
        stock_daily=[
            StockDailyRecord(
                stock_code="000001",
                trade_date=trade_date,
                open=10,
                high=10.5,
                low=9.8,
                close=10.3,
                pre_close=10,
                change=0.3,
                pct_chg=3,
                volume=120000,
                amount=123600000,
                turnover_rate=1.2,
                source="unit-test",
            )
        ],
        limit_snapshot=[
            LimitSnapshotRecord(
                trade_date=trade_date,
                stock_code="000001",
                stock_name=stock_name,
                close_price=10.3,
                pct_chg=10.0,
                limit_status="limit_up",
                amount=123600000,
                source="unit-test",
            )
        ],
    )


def _multi_day_calendar_snapshot() -> MarketDataSnapshot:
    snapshot = _snapshot()
    previous_date = date(2026, 6, 18)
    snapshot.trading_calendar.append(
        TradingCalendarRecord(trade_date=previous_date, is_open=True, source="unit-test")
    )
    return snapshot


def test_ingest_market_snapshot_writes_all_market_data_tables() -> None:
    engine = _engine()

    summary = ingest_market_snapshot(engine, _snapshot())

    assert summary.status == "success"
    assert summary.stock_daily_rows == 1
    with Session(engine) as session:
        assert session.scalar(select(TradingCalendar).where(TradingCalendar.trade_date == date(2026, 6, 19)))
        assert session.scalar(select(StockBasic).where(StockBasic.stock_code == "000001")).stock_name == "平安银行"
        assert session.scalar(select(IndexDaily).where(IndexDaily.index_code == "000001.SH")).close == 3020
        assert session.scalar(select(StockDaily).where(StockDaily.stock_code == "000001")).amount == 123600000
        assert session.scalar(select(LimitSnapshot).where(LimitSnapshot.limit_status == "limit_up"))
        assert session.scalar(select(DataIngestRun).where(DataIngestRun.provider == "unit-test"))


def test_ingest_market_snapshot_is_idempotent_for_same_trade_date() -> None:
    engine = _engine()

    ingest_market_snapshot(engine, _snapshot())
    ingest_market_snapshot(engine, _snapshot(stock_name="平安银行A"))

    with Session(engine) as session:
        assert session.query(TradingCalendar).count() == 1
        assert session.query(StockBasic).count() == 1
        assert session.query(IndexDaily).count() == 1
        assert session.query(StockDaily).count() == 1
        assert session.query(LimitSnapshot).count() == 1
        assert session.query(DataIngestRun).count() == 2
        assert session.scalar(select(StockBasic).where(StockBasic.stock_code == "000001")).stock_name == "平安银行A"


def test_ingest_market_snapshot_replaces_existing_multi_day_calendar_rows() -> None:
    engine = _engine()

    ingest_market_snapshot(engine, _multi_day_calendar_snapshot())
    ingest_market_snapshot(engine, _multi_day_calendar_snapshot())

    with Session(engine) as session:
        assert session.query(TradingCalendar).count() == 2
