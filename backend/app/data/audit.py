from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.app.db.models import (
    IndexDaily,
    LimitSnapshot,
    StockBasic,
    StockDaily,
    TradingCalendar,
)


@dataclass(frozen=True)
class MarketDataCoverageAudit:
    trade_date: date
    open_trading_days: int
    stock_basic_rows: int
    stock_daily_rows: int
    missing_stock_daily_rows: int
    index_daily_rows: int
    limit_up_rows: int
    limit_down_rows: int
    latest_stock_daily_date: Optional[date]


def audit_market_data_coverage(engine: Engine, trade_date: date) -> MarketDataCoverageAudit:
    with Session(engine) as session:
        open_trading_days = session.scalar(
            select(func.count()).select_from(TradingCalendar).where(
                TradingCalendar.trade_date <= trade_date,
                TradingCalendar.is_open.is_(True),
            )
        )
        stock_basic_rows = session.scalar(select(func.count()).select_from(StockBasic))
        stock_daily_rows = session.scalar(
            select(func.count()).select_from(StockDaily).where(StockDaily.trade_date == trade_date)
        )
        index_daily_rows = session.scalar(
            select(func.count()).select_from(IndexDaily).where(IndexDaily.trade_date == trade_date)
        )
        limit_up_rows = session.scalar(
            select(func.count()).select_from(LimitSnapshot).where(
                LimitSnapshot.trade_date == trade_date,
                LimitSnapshot.limit_status == "limit_up",
            )
        )
        limit_down_rows = session.scalar(
            select(func.count()).select_from(LimitSnapshot).where(
                LimitSnapshot.trade_date == trade_date,
                LimitSnapshot.limit_status == "limit_down",
            )
        )
        latest_stock_daily_date = session.scalar(select(func.max(StockDaily.trade_date)))

    return MarketDataCoverageAudit(
        trade_date=trade_date,
        open_trading_days=open_trading_days or 0,
        stock_basic_rows=stock_basic_rows or 0,
        stock_daily_rows=stock_daily_rows or 0,
        missing_stock_daily_rows=max((stock_basic_rows or 0) - (stock_daily_rows or 0), 0),
        index_daily_rows=index_daily_rows or 0,
        limit_up_rows=limit_up_rows or 0,
        limit_down_rows=limit_down_rows or 0,
        latest_stock_daily_date=latest_stock_daily_date,
    )
