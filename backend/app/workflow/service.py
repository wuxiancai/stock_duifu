from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.app.candidate.service import CandidateResult, generate_candidate_stocks
from backend.app.data.ingest import ingest_market_snapshot
from backend.app.market.service import generate_market_environment
from backend.app.db.models import CandidateStock
from backend.app.sector.service import SectorRankingResult, generate_sector_rankings, load_sector_rankings_by_date
from backend.app.trade.service import generate_trade_plans, generate_trade_reviews
from backend.app.system.monitoring import (
    audit_step_status,
    create_data_job_run,
    finish_data_job_run,
    record_data_job_step,
    run_coverage_audit_step,
)


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
    review_count: int
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
    record_job = isinstance(engine, Engine)
    run_id = (
        create_data_job_run(
            engine,
            trade_date,
            command=f"bash get_data.sh {trade_date.isoformat()}",
        )
        if record_job
        else None
    )

    try:
        if record_job and run_id is not None:
            snapshot = record_data_job_step(
                engine,
                run_id,
                "拉取行情快照",
                lambda: market_provider.fetch_snapshot(
                    trade_date=trade_date,
                    sample_size=0,
                    stock_codes=None,
                ),
                lambda item: {
                    "provider": item.provider,
                    "trading_calendar_rows": len(item.trading_calendar),
                    "stock_basic_rows": len(item.stock_basic),
                    "index_daily_rows": len(item.index_daily),
                    "stock_daily_rows": len(item.stock_daily),
                    "limit_snapshot_rows": len(item.limit_snapshot),
                },
                lambda item: len(item.stock_daily),
            )
            ingest_summary = record_data_job_step(
                engine,
                run_id,
                "写入行情数据库",
                lambda: ingest_market_snapshot(engine, snapshot),
                lambda item: item.__dict__,
                lambda item: item.stock_daily_rows,
            )
            market = record_data_job_step(
                engine,
                run_id,
                "生成市场环境",
                lambda: generate_market_environment(engine, trade_date),
                lambda item: {"market_score": item.market_score, "market_status": item.market_status},
                lambda item: 1,
            )
            try:
                sectors = record_data_job_step(
                    engine,
                    run_id,
                    "生成强势板块",
                    lambda: generate_sector_rankings(engine, trade_date, sector_provider),
                    lambda items: {"sector_count": len(items), "top_sector": items[0].sector_name if items else ""},
                    lambda items: len(items),
                )
            except Exception as exc:
                sectors = _load_existing_sector_rankings_or_raise(engine, trade_date, exc)
            try:
                candidates = record_data_job_step(
                    engine,
                    run_id,
                    "生成候选股票",
                    lambda: generate_candidate_stocks(engine, trade_date, candidate_provider, limit=candidate_limit),
                    lambda items: {"candidate_count": len(items)},
                    lambda items: len(items),
                )
            except Exception as exc:
                candidates = _load_existing_candidates_or_raise(engine, trade_date, exc)
            reviews = record_data_job_step(
                engine,
                run_id,
                "生成交易复盘",
                lambda: generate_trade_reviews(engine, trade_date),
                lambda item: {
                    "review_date": item.review_date,
                    "review_count": item.total_count,
                    "triggered_count": item.triggered_count,
                    "win_rate": item.win_rate,
                },
                lambda item: item.total_count,
            )
            plans = record_data_job_step(
                engine,
                run_id,
                "生成交易计划",
                lambda: generate_trade_plans(engine, trade_date, limit=trade_plan_limit),
                lambda items: {
                    "trade_plan_count": len(items),
                    "target_trade_date": items[0].target_trade_date if items else None,
                },
                lambda items: len(items),
            )
            audit = run_coverage_audit_step(engine, run_id, trade_date)
            status, message = audit_step_status(engine, audit)
            finish_data_job_run(engine, run_id, status, message)
        else:
            snapshot = market_provider.fetch_snapshot(
                trade_date=trade_date,
                sample_size=0,
                stock_codes=None,
            )
            ingest_summary = ingest_market_snapshot(engine, snapshot)
            market = generate_market_environment(engine, trade_date)
            try:
                sectors = generate_sector_rankings(engine, trade_date, sector_provider)
            except Exception as exc:
                sectors = _load_existing_sector_rankings_or_raise(engine, trade_date, exc)
            try:
                candidates = generate_candidate_stocks(engine, trade_date, candidate_provider, limit=candidate_limit)
            except Exception as exc:
                candidates = _load_existing_candidates_or_raise(engine, trade_date, exc)
            reviews = generate_trade_reviews(engine, trade_date)
            plans = generate_trade_plans(engine, trade_date, limit=trade_plan_limit)
    except Exception as exc:
        if record_job and run_id is not None:
            finish_data_job_run(engine, run_id, "failed", str(exc))
        raise

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
        review_count=reviews.total_count,
        trade_plan_count=len(plans),
        target_trade_date=target_trade_date,
    )


def _load_existing_sector_rankings_or_raise(
    engine: Engine,
    trade_date: date,
    original_exc: Exception,
) -> list[SectorRankingResult]:
    existing = load_sector_rankings_by_date(engine, trade_date)
    if existing is None or not existing[1]:
        raise original_exc
    return existing[1]


def _load_existing_candidates_or_raise(
    engine: Engine,
    trade_date: date,
    original_exc: Exception,
) -> list[CandidateResult]:
    with Session(engine) as session:
        records = session.scalars(
            select(CandidateStock)
            .where(CandidateStock.trade_date == trade_date)
            .order_by(desc(CandidateStock.stock_score), CandidateStock.stock_code)
        ).all()
    if not records:
        raise original_exc
    return [
        CandidateResult(
            trade_date=record.trade_date,
            stock_code=record.stock_code,
            stock_name=record.stock_name,
            sector_name=record.sector_name,
            sector_rank=record.sector_rank,
            sector_category=record.sector_category,
            stock_pool_rank=record.stock_pool_rank,
            strategy_type=record.strategy_type,
            stock_score=record.stock_score,
            sector_score=record.sector_score,
            nine_turn_signal=record.nine_turn_signal,
            nine_turn_count=record.nine_turn_count,
            nine_turn_score=record.nine_turn_score,
            close_price=float(record.close_price or 0),
            amount=float(record.amount or 0),
            reason=record.reason,
            risk_note=record.risk_note,
        )
        for record in records
    ]
