from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.app.data.ingest import ingest_market_snapshot
from backend.app.data.types import IngestSummary, MarketDataSnapshot, StockDailyRecord
from backend.app.db.models import SimulationPosition, StockDaily, TradePlan, TradingCalendar, VirtualPosition
from backend.app.simulation.service import ACTIVE_POSITION_STATUSES, SimulationWorkflowSummary, run_simulation_workflow


class RealtimeQuoteProvider(Protocol):
    name: str

    def fetch_realtime_stock_daily(
        self,
        stock_codes: list[str],
        trade_date: date,
    ) -> list[StockDailyRecord]:
        ...


@dataclass(frozen=True)
class RealtimeQuoteBackfillResult:
    target_trade_date: date
    china_today: date
    provider: str
    planned_stock_count: int
    existing_stock_count: int
    requested_stock_count: int
    fetched_stock_daily_rows: int
    target_is_open: Optional[bool]
    missing_stock_codes: list[str]
    skipped_reason: str
    ingest_summary: Optional[IngestSummary]


@dataclass(frozen=True)
class RealtimeQuoteWorkflowResult:
    backfill: RealtimeQuoteBackfillResult
    workflow: Optional[SimulationWorkflowSummary]


def backfill_trade_plan_realtime_quotes(
    engine: Engine,
    target_trade_date: date,
    provider: RealtimeQuoteProvider,
    include_existing: bool = True,
    allow_date_mismatch: bool = False,
) -> RealtimeQuoteBackfillResult:
    china_today = _china_today()
    planned_codes = _planned_stock_codes(engine, target_trade_date)
    quote_codes = _quote_stock_codes(engine, target_trade_date)
    existing_codes = _existing_daily_codes(engine, target_trade_date, quote_codes)
    requested_codes = quote_codes if include_existing else [code for code in quote_codes if code not in existing_codes]
    target_is_open = _calendar_open_status(engine, target_trade_date)

    skipped_reason = _skip_reason(
        target_trade_date=target_trade_date,
        china_today=china_today,
        target_is_open=target_is_open,
        quote_codes=quote_codes,
        requested_codes=requested_codes,
        allow_date_mismatch=allow_date_mismatch,
    )
    if skipped_reason:
        return RealtimeQuoteBackfillResult(
            target_trade_date=target_trade_date,
            china_today=china_today,
            provider=provider.name,
            planned_stock_count=len(planned_codes),
            existing_stock_count=len(existing_codes),
            requested_stock_count=len(requested_codes),
            fetched_stock_daily_rows=0,
            target_is_open=target_is_open,
            missing_stock_codes=requested_codes,
            skipped_reason=skipped_reason,
            ingest_summary=None,
        )

    try:
        stock_daily = provider.fetch_realtime_stock_daily(requested_codes, target_trade_date)
    except Exception as exc:
        return RealtimeQuoteBackfillResult(
            target_trade_date=target_trade_date,
            china_today=china_today,
            provider=provider.name,
            planned_stock_count=len(planned_codes),
            existing_stock_count=len(existing_codes),
            requested_stock_count=len(requested_codes),
            fetched_stock_daily_rows=0,
            target_is_open=target_is_open,
            missing_stock_codes=requested_codes,
            skipped_reason=f"实时行情数据源拉取失败: {exc.__class__.__name__}: {exc}",
            ingest_summary=None,
        )

    snapshot = MarketDataSnapshot(
        provider=provider.name,
        trade_date=target_trade_date,
        trading_calendar=[],
        stock_basic=[],
        index_daily=[],
        stock_daily=stock_daily,
        limit_snapshot=[],
    )
    summary = ingest_market_snapshot(engine, snapshot)
    fetched_codes = {record.stock_code for record in stock_daily if record.trade_date == target_trade_date}
    missing_codes = [code for code in requested_codes if code not in fetched_codes]

    return RealtimeQuoteBackfillResult(
        target_trade_date=target_trade_date,
        china_today=china_today,
        provider=provider.name,
        planned_stock_count=len(planned_codes),
        existing_stock_count=len(existing_codes),
        requested_stock_count=len(requested_codes),
        fetched_stock_daily_rows=len(fetched_codes),
        target_is_open=target_is_open,
        missing_stock_codes=missing_codes,
        skipped_reason="",
        ingest_summary=summary,
    )


def run_realtime_quote_workflow(
    engine: Engine,
    target_trade_date: date,
    provider: RealtimeQuoteProvider,
    include_existing: bool = True,
    mark_untriggered_at_close: bool = False,
    allow_date_mismatch: bool = False,
) -> RealtimeQuoteWorkflowResult:
    backfill = backfill_trade_plan_realtime_quotes(
        engine,
        target_trade_date,
        provider,
        include_existing=include_existing,
        allow_date_mismatch=allow_date_mismatch,
    )
    if backfill.skipped_reason and backfill.skipped_reason not in {
        "目标交易日计划股已有 stock_daily，无需拉取实时行情",
        "目标交易日计划股和模拟持仓已有 stock_daily，无需拉取实时行情",
    }:
        return RealtimeQuoteWorkflowResult(backfill=backfill, workflow=None)
    workflow = run_simulation_workflow(
        engine,
        target_trade_date,
        mark_untriggered_at_close=mark_untriggered_at_close,
    )
    return RealtimeQuoteWorkflowResult(backfill=backfill, workflow=workflow)


def _skip_reason(
    target_trade_date: date,
    china_today: date,
    target_is_open: Optional[bool],
    quote_codes: list[str],
    requested_codes: list[str],
    allow_date_mismatch: bool,
) -> str:
    if not quote_codes:
        return "目标交易日没有交易计划或模拟持仓，无需拉取实时行情"
    if target_is_open is False:
        return "目标交易日不是开市日，不写入实时行情"
    if target_is_open is None and not _can_fetch_live_without_calendar(target_trade_date, china_today):
        return "目标交易日缺少交易日历，需先采集或回补交易日历"
    if not requested_codes:
        return "目标交易日计划股和模拟持仓已有 stock_daily，无需拉取实时行情"
    if target_trade_date != china_today and not allow_date_mismatch:
        return "实时行情只能默认写入中国当前自然日；如确认数据日期匹配，请显式使用 allow_date_mismatch"
    return ""


def _can_fetch_live_without_calendar(target_trade_date: date, china_today: date) -> bool:
    return target_trade_date == china_today and target_trade_date.weekday() < 5


def _china_today() -> date:
    return datetime.now(ZoneInfo("Asia/Shanghai")).date()


def _planned_stock_codes(engine: Engine, target_trade_date: date) -> list[str]:
    with Session(engine) as session:
        rows = session.scalars(
            select(TradePlan.stock_code)
            .where(TradePlan.target_trade_date == target_trade_date)
            .distinct()
            .order_by(TradePlan.stock_code)
        ).all()
        return list(rows)


def _quote_stock_codes(engine: Engine, target_trade_date: date) -> list[str]:
    codes = set(_planned_stock_codes(engine, target_trade_date))
    with Session(engine) as session:
        active_simulation_codes = session.scalars(
            select(SimulationPosition.stock_code)
            .where(SimulationPosition.position_status.in_(ACTIVE_POSITION_STATUSES))
            .distinct()
        ).all()
        active_virtual_codes = session.scalars(
            select(VirtualPosition.stock_code)
            .where(VirtualPosition.position_status.in_(ACTIVE_POSITION_STATUSES))
            .distinct()
        ).all()
    codes.update(active_simulation_codes)
    codes.update(active_virtual_codes)
    return sorted(codes)


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


def _calendar_open_status(engine: Engine, target_trade_date: date) -> Optional[bool]:
    with Session(engine) as session:
        row = session.scalar(select(TradingCalendar).where(TradingCalendar.trade_date == target_trade_date))
        return row.is_open if row is not None else None
