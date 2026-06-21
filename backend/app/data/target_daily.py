from dataclasses import dataclass
from datetime import date
from typing import Optional, Protocol

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.app.data.ingest import ingest_market_snapshot
from backend.app.data.types import IngestSummary, MarketDataSnapshot
from backend.app.db.models import StockDaily, TradePlan, TradingCalendar


class MarketDataProvider(Protocol):
    name: str

    def fetch_snapshot(
        self,
        trade_date: Optional[date] = None,
        sample_size: int = 30,
        stock_codes: Optional[list[str]] = None,
    ) -> MarketDataSnapshot:
        ...


@dataclass(frozen=True)
class TargetDailyBackfillResult:
    target_trade_date: date
    provider: str
    planned_stock_count: int
    existing_stock_count: int
    requested_stock_count: int
    fetched_stock_daily_rows: int
    target_is_open: Optional[bool]
    missing_stock_codes: list[str]
    ingest_summary: Optional[IngestSummary]


def backfill_trade_plan_target_daily(
    engine: Engine,
    target_trade_date: date,
    provider: MarketDataProvider,
    include_existing: bool = False,
) -> TargetDailyBackfillResult:
    planned_codes = _planned_stock_codes(engine, target_trade_date)
    existing_codes = _existing_daily_codes(engine, target_trade_date, planned_codes)
    requested_codes = planned_codes if include_existing else [code for code in planned_codes if code not in existing_codes]

    if not requested_codes:
        return TargetDailyBackfillResult(
            target_trade_date=target_trade_date,
            provider=provider.name,
            planned_stock_count=len(planned_codes),
            existing_stock_count=len(existing_codes),
            requested_stock_count=0,
            fetched_stock_daily_rows=0,
            target_is_open=_calendar_open_status(engine, target_trade_date),
            missing_stock_codes=[],
            ingest_summary=None,
        )

    snapshot = provider.fetch_snapshot(
        trade_date=target_trade_date,
        sample_size=len(requested_codes),
        stock_codes=requested_codes,
    )
    summary = ingest_market_snapshot(engine, snapshot)
    fetched_codes = {record.stock_code for record in snapshot.stock_daily if record.trade_date == target_trade_date}
    missing_codes = [code for code in requested_codes if code not in fetched_codes]
    target_is_open = _snapshot_open_status(snapshot)

    return TargetDailyBackfillResult(
        target_trade_date=target_trade_date,
        provider=snapshot.provider,
        planned_stock_count=len(planned_codes),
        existing_stock_count=len(existing_codes),
        requested_stock_count=len(requested_codes),
        fetched_stock_daily_rows=len(fetched_codes),
        target_is_open=target_is_open,
        missing_stock_codes=missing_codes,
        ingest_summary=summary,
    )


def _planned_stock_codes(engine: Engine, target_trade_date: date) -> list[str]:
    with Session(engine) as session:
        rows = session.scalars(
            select(TradePlan.stock_code)
            .where(TradePlan.target_trade_date == target_trade_date)
            .distinct()
            .order_by(TradePlan.stock_code)
        ).all()
        return list(rows)


def _snapshot_open_status(snapshot: MarketDataSnapshot) -> Optional[bool]:
    for record in snapshot.trading_calendar:
        if record.trade_date == snapshot.trade_date:
            return record.is_open
    return None


def _calendar_open_status(engine: Engine, target_trade_date: date) -> Optional[bool]:
    with Session(engine) as session:
        row = session.scalar(select(TradingCalendar).where(TradingCalendar.trade_date == target_trade_date))
        return row.is_open if row is not None else None


def _existing_daily_codes(engine: Engine, target_trade_date: date, stock_codes: list[str]) -> set[str]:
    if not stock_codes:
        return set()
    with Session(engine) as session:
        rows = session.scalars(
            select(StockDaily.stock_code).where(
                StockDaily.trade_date == target_trade_date,
                StockDaily.stock_code.in_(stock_codes),
            )
        ).all()
        return set(rows)
