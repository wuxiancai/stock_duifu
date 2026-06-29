from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy.engine import Engine

from backend.app.candidate.service import generate_candidate_stocks
from backend.app.data.ingest import ingest_market_snapshot
from backend.app.market.service import generate_market_environment
from backend.app.sector.service import generate_sector_rankings
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
            sectors = record_data_job_step(
                engine,
                run_id,
                "生成强势板块",
                lambda: generate_sector_rankings(engine, trade_date, sector_provider),
                lambda items: {"sector_count": len(items), "top_sector": items[0].sector_name if items else ""},
                lambda items: len(items),
            )
            candidates = record_data_job_step(
                engine,
                run_id,
                "生成候选股票",
                lambda: generate_candidate_stocks(engine, trade_date, candidate_provider, limit=candidate_limit),
                lambda items: {"candidate_count": len(items)},
                lambda items: len(items),
            )
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
            sectors = generate_sector_rankings(engine, trade_date, sector_provider)
            candidates = generate_candidate_stocks(engine, trade_date, candidate_provider, limit=candidate_limit)
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
