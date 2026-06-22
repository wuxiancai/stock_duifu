from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class TradingCalendarRecord:
    trade_date: date
    is_open: bool
    source: str


@dataclass(frozen=True)
class StockBasicRecord:
    stock_code: str
    stock_name: str
    market: str
    list_date: Optional[date]
    is_st: bool
    status: str
    source: str


@dataclass(frozen=True)
class IndexDailyRecord:
    index_code: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: Optional[float]
    source: str


@dataclass(frozen=True)
class StockDailyRecord:
    stock_code: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    pre_close: float
    change: float
    pct_chg: float
    volume: float
    amount: float
    turnover_rate: Optional[float]
    source: str


@dataclass(frozen=True)
class LimitSnapshotRecord:
    trade_date: date
    stock_code: str
    stock_name: str
    close_price: float
    pct_chg: float
    limit_status: str
    amount: float
    source: str


@dataclass(frozen=True)
class MarketDataSnapshot:
    provider: str
    trade_date: date
    trading_calendar: list[TradingCalendarRecord]
    stock_basic: list[StockBasicRecord]
    index_daily: list[IndexDailyRecord]
    stock_daily: list[StockDailyRecord]
    limit_snapshot: list[LimitSnapshotRecord]


@dataclass(frozen=True)
class IngestSummary:
    provider: str
    trade_date: date
    status: str
    message: str
    ingest_run_id: Optional[int]
    trading_calendar_rows: int
    stock_basic_rows: int
    index_daily_rows: int
    stock_daily_rows: int
    limit_snapshot_rows: int
