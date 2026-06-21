from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy.engine import Engine

from backend.app.candidate.service import generate_candidate_stocks
from backend.app.data.ingest import ingest_market_snapshot
from backend.app.market.service import generate_market_environment
from backend.app.sector.service import generate_sector_rankings
from backend.app.trade.service import generate_trade_plans


@dataclass(frozen=True)
class AfterCloseWorkflowResult:
    trade_date: date
    trading_calendar_rows: int
    stock_basic_rows: int
    index_daily_rows: int
    stock_daily_rows: int
    limit_snapshot_rows: int
    ingest_run_id: Optional[int]
    market_score: int
    market_status: str
    sector_count: int
    candidate_count: int
    trade_plan_count: int
    target_trade_date: Optional[date]


def run_after_close_workflow(
    engine: Engine,
    trade_date: date,
    market_provider,
    sector_provider,
    candidate_provider,
    candidate_limit: int = 50,
    trade_plan_limit: Optional[int] = None,
) -> AfterCloseWorkflowResult:
    snapshot = market_provider.fetch_snapshot(
        trade_date=trade_date,
        sample_size=0,
        stock_codes=None,
    )
    ingest_summary = ingest_market_snapshot(engine, snapshot)
    market = generate_market_environment(engine, trade_date)
    sectors = generate_sector_rankings(engine, trade_date, sector_provider)
    candidates = generate_candidate_stocks(engine, trade_date, candidate_provider, limit=candidate_limit)
    plans = generate_trade_plans(engine, trade_date, limit=trade_plan_limit)
    target_trade_date = plans[0].target_trade_date if plans else None

    return AfterCloseWorkflowResult(
        trade_date=trade_date,
        trading_calendar_rows=ingest_summary.trading_calendar_rows,
        stock_basic_rows=ingest_summary.stock_basic_rows,
        index_daily_rows=ingest_summary.index_daily_rows,
        stock_daily_rows=ingest_summary.stock_daily_rows,
        limit_snapshot_rows=ingest_summary.limit_snapshot_rows,
        ingest_run_id=ingest_summary.ingest_run_id,
        market_score=market.market_score,
        market_status=market.market_status,
        sector_count=len(sectors),
        candidate_count=len(candidates),
        trade_plan_count=len(plans),
        target_trade_date=target_trade_date,
    )
