from datetime import date

from sqlalchemy import create_engine

from backend.app.data.audit import audit_market_data_coverage
from backend.app.data.ingest import ingest_market_snapshot
from backend.app.data.types import (
    IndexDailyRecord,
    LimitSnapshotRecord,
    MarketDataSnapshot,
    StockBasicRecord,
    StockDailyRecord,
    TradingCalendarRecord,
)
from backend.app.db.models import metadata


def _engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata.create_all(engine)
    return engine


def test_audit_market_data_coverage_reports_expected_counts() -> None:
    engine = _engine()
    trade_date = date(2026, 6, 18)
    snapshot = MarketDataSnapshot(
        provider="unit-test",
        trade_date=trade_date,
        trading_calendar=[
            TradingCalendarRecord(trade_date=trade_date, is_open=True, source="unit-test")
        ],
        stock_basic=[
            StockBasicRecord("000001", "平安银行", "SZ", None, False, "active", "unit-test"),
            StockBasicRecord("600519", "贵州茅台", "SH", None, False, "active", "unit-test"),
        ],
        index_daily=[
            IndexDailyRecord("000001.SH", trade_date, 1, 2, 1, 2, 100, None, "unit-test")
        ],
        stock_daily=[
            StockDailyRecord("000001", trade_date, 10, 11, 9, 10.5, 10, 0.5, 5, 100, 1000, 1.0, "unit-test")
        ],
        limit_snapshot=[
            LimitSnapshotRecord(trade_date, "000001", "平安银行", 10.5, 10, "limit_up", 1000, "unit-test")
        ],
    )
    ingest_market_snapshot(engine, snapshot)

    audit = audit_market_data_coverage(engine, trade_date)

    assert audit.trade_date == trade_date
    assert audit.open_trading_days == 1
    assert audit.stock_basic_rows == 2
    assert audit.stock_daily_rows == 1
    assert audit.missing_stock_daily_rows == 1
    assert audit.index_daily_rows == 1
    assert audit.limit_up_rows == 1
    assert audit.limit_down_rows == 0
    assert audit.latest_stock_daily_date == trade_date

