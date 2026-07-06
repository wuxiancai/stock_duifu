from dataclasses import asdict
from datetime import date
import os
import threading
from typing import Optional

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.engine import Engine

from backend.app.candidate.service import load_latest_candidates
from backend.app.core.config import get_settings
from backend.app.data.providers import (
    AkShareRealtimeQuoteProvider,
    AkShareSinaRealtimeQuoteProvider,
    EastmoneyDirectRealtimeQuoteProvider,
    FallbackRealtimeQuoteProvider,
    SinaDirectRealtimeQuoteProvider,
    TencentDirectRealtimeQuoteProvider,
)
from backend.app.data.realtime_quotes import RealtimeQuoteBackfillResult, backfill_trade_plan_realtime_quotes
from backend.app.db.session import create_database_engine
from backend.app.market.service import load_index_ticker, load_latest_market_environment, load_market_environment_history
from backend.app.sector.service import load_latest_sector_rankings, load_sector_rankings_by_date
from backend.app.simulation.service import load_latest_simulation, run_simulation, run_simulation_workflow
from backend.app.system.monitoring import load_database_health, load_latest_data_job_runs
from backend.app.trade.service import (
    generate_trade_reviews,
    load_trade_plan_detail,
    load_trade_plans_by_target_date,
    load_latest_trade_plans,
    load_latest_trade_reviews,
    load_trade_reviews_by_date,
    track_trade_plans,
    update_trade_review,
    update_trade_plan_status,
)


class TradePlanTrackingRequest(BaseModel):
    target_trade_date: str
    mark_untriggered_at_close: bool = False


class TradePlanRealtimeTrackingRequest(BaseModel):
    target_trade_date: str
    mark_untriggered_at_close: bool = False
    include_existing: bool = True
    allow_date_mismatch: bool = False


class TradeReviewGenerateRequest(BaseModel):
    trade_date: str


class SimulationRunRequest(BaseModel):
    trade_date: str


class SimulationWorkflowRunRequest(BaseModel):
    trade_date: str
    mark_untriggered_at_close: bool = False


class TradePlanStatusUpdate(BaseModel):
    status: str
    trigger_price: Optional[float] = None
    note: str = ""
    is_watched: Optional[bool] = None


class TradeReviewUpdate(BaseModel):
    result: Optional[str] = None
    failure_reason: Optional[str] = None
    discipline_check: Optional[bool] = None
    note: Optional[str] = None


def _review_group_payload(item) -> dict:
    return {
        "name": item.name,
        "total_count": item.total_count,
        "triggered_count": item.triggered_count,
        "win_count": item.win_count,
        "win_rate": item.win_rate,
        "avg_day_return": item.avg_day_return,
        "avg_t5_return": item.avg_t5_return,
    }


def _trade_review_payload(summary) -> dict:
    return {
        "review_date": summary.review_date.isoformat(),
        "total_count": summary.total_count,
        "triggered_count": summary.triggered_count,
        "win_count": summary.win_count,
        "win_rate": summary.win_rate,
        "avg_day_return": summary.avg_day_return,
        "avg_t5_return": summary.avg_t5_return,
        "strategy_stats": [_review_group_payload(item) for item in summary.strategy_stats],
        "sector_stats": [_review_group_payload(item) for item in summary.sector_stats],
        "items": [
            {
                "id": item.id,
                "trade_plan_id": item.trade_plan_id,
                "trade_date": item.trade_date.isoformat(),
                "stock_code": item.stock_code,
                "stock_name": item.stock_name,
                "sector_name": item.sector_name,
                "strategy_type": item.strategy_type,
                "triggered": item.triggered,
                "trigger_price": item.trigger_price,
                "close_price": item.close_price,
                "day_return": item.day_return,
                "t5_return": item.t5_return,
                "max_profit": item.max_profit,
                "max_loss": item.max_loss,
                "result": item.result,
                "failure_reason": item.failure_reason,
                "discipline_check": item.discipline_check,
                "note": item.note,
            }
            for item in summary.items
        ],
    }


def _trade_plan_payload(item) -> dict:
    return {
        "id": item.id,
        "plan_date": item.plan_date.isoformat(),
        "target_trade_date": item.target_trade_date.isoformat(),
        "stock_code": item.stock_code,
        "stock_name": item.stock_name,
        "sector_name": item.sector_name,
        "strategy_type": item.strategy_type,
        "stock_score": item.stock_score,
        "sector_score": item.sector_score,
        "market_status": item.market_status,
        "buy_condition": item.buy_condition,
        "buy_price_low": item.buy_price_low,
        "buy_price_high": item.buy_price_high,
        "stop_loss_price": item.stop_loss_price,
        "take_profit_price": item.take_profit_price,
        "position_ratio": item.position_ratio,
        "status": item.status,
        "trigger_price": item.trigger_price,
        "trigger_time": item.trigger_time.isoformat() if item.trigger_time else None,
        "tracking_note": item.tracking_note,
        "is_watched": item.is_watched,
        "risk_note": item.risk_note,
        "current_price": item.current_price,
        "pct_chg": item.pct_chg,
    }


def _trade_plan_detail_payload(item: dict) -> dict:
    payload = _trade_plan_payload(type("TradePlanLike", (), item)())
    payload["selection_reason"] = item["selection_reason"]
    payload["key_indicators"] = item["key_indicators"]
    return payload


def _tracking_payload(target_trade_date: date, items) -> dict:
    return {
        "target_trade_date": target_trade_date.isoformat(),
        "items": [
            {
                "id": item.id,
                "stock_code": item.stock_code,
                "stock_name": item.stock_name,
                "status": item.status,
                "current_price": item.current_price,
                "pct_chg": item.pct_chg,
                "trigger_price": item.trigger_price,
                "tracking_note": item.tracking_note,
            }
            for item in items
        ],
    }


def _realtime_backfill_payload(backfill) -> dict:
    return {
        "target_trade_date": backfill.target_trade_date.isoformat(),
        "china_today": backfill.china_today.isoformat(),
        "provider": backfill.provider,
        "planned_stock_count": backfill.planned_stock_count,
        "existing_stock_count": backfill.existing_stock_count,
        "requested_stock_count": backfill.requested_stock_count,
        "fetched_stock_daily_rows": backfill.fetched_stock_daily_rows,
        "target_is_open": backfill.target_is_open,
        "missing_stock_codes": backfill.missing_stock_codes,
        "skipped_reason": backfill.skipped_reason,
    }


_realtime_tracking_lock = threading.Lock()


def _realtime_quote_provider():
    provider_name = os.environ.get("STOCK_API_REALTIME_PROVIDER", "auto").strip().lower()
    if provider_name in {"auto", "auto-lite"}:
        return FallbackRealtimeQuoteProvider(
            [SinaDirectRealtimeQuoteProvider(), EastmoneyDirectRealtimeQuoteProvider(), TencentDirectRealtimeQuoteProvider()]
        )
    if provider_name in {"auto-full", "legacy-auto"}:
        return FallbackRealtimeQuoteProvider(
            [
                SinaDirectRealtimeQuoteProvider(),
                EastmoneyDirectRealtimeQuoteProvider(),
                TencentDirectRealtimeQuoteProvider(),
                AkShareRealtimeQuoteProvider(),
                AkShareSinaRealtimeQuoteProvider(),
            ]
        )
    if provider_name in {"eastmoney", "direct-eastmoney"}:
        return EastmoneyDirectRealtimeQuoteProvider()
    if provider_name in {"tencent", "direct-tencent"}:
        return TencentDirectRealtimeQuoteProvider()
    if provider_name == "akshare":
        return AkShareRealtimeQuoteProvider()
    if provider_name == "sina":
        return AkShareSinaRealtimeQuoteProvider()
    return SinaDirectRealtimeQuoteProvider()


def _busy_realtime_backfill(target_trade_date: date) -> RealtimeQuoteBackfillResult:
    return RealtimeQuoteBackfillResult(
        target_trade_date=target_trade_date,
        china_today=target_trade_date,
        provider="skipped_busy_realtime",
        planned_stock_count=0,
        existing_stock_count=0,
        requested_stock_count=0,
        fetched_stock_daily_rows=0,
        target_is_open=None,
        missing_stock_codes=[],
        skipped_reason="已有 /api/trade-plans/track-realtime 请求正在执行，本次跳过实时行情回补，避免并发堆积导致 502",
        ingest_summary=None,
    )


def _sector_payload(item) -> dict:
    return {
        "rank_no": item.rank_no,
        "sector_name": item.sector_name,
        "daily_return": item.daily_return,
        "five_day_return": item.five_day_return,
        "three_day_return": item.three_day_return,
        "amount_change": item.amount_change,
        "limit_up_count": item.limit_up_count,
        "strong_stock_count": item.strong_stock_count,
        "sector_score": item.sector_score,
        "rank_history": [
            {
                "trade_date": history.trade_date.isoformat(),
                "rank_no": history.rank_no,
            }
            for history in item.rank_history
        ],
    }


def _market_payload(result) -> dict:
    return {
        "trade_date": result.trade_date.isoformat(),
        "market_score": result.market_score,
        "market_status": result.market_status,
        "suggested_position": result.suggested_position,
        "up_count": result.up_count,
        "down_count": result.down_count,
        "limit_up_count": result.limit_up_count,
        "limit_down_count": result.limit_down_count,
        "limit_up_height": result.limit_up_height,
        "total_amount": result.total_amount,
        "suggestion": result.suggestion,
    }


def _index_ticker_payload(item) -> dict:
    return {
        "name": item.name,
        "index_code": item.index_code,
        "trade_date": item.trade_date.isoformat() if item.trade_date else "",
        "close": item.close,
        "change": item.change,
        "pct_chg": item.pct_chg,
        "amount": item.amount,
        "available": item.available,
    }


def _data_job_run_payload(run) -> dict:
    return {
        "id": run.id,
        "job_name": run.job_name,
        "trade_date": run.trade_date.isoformat(),
        "status": run.status,
        "command": run.command,
        "message": run.message,
        "started_at": run.started_at.isoformat(),
        "ended_at": run.ended_at.isoformat() if run.ended_at else None,
        "steps": [
            {
                "step_name": step.step_name,
                "status": step.status,
                "started_at": step.started_at.isoformat(),
                "ended_at": step.ended_at.isoformat() if step.ended_at else None,
                "rows_count": step.rows_count,
                "summary": step.summary,
                "error_message": step.error_message,
            }
            for step in run.steps
        ],
    }


def _database_health_payload(summary) -> dict:
    return {
        "trade_date": summary.trade_date.isoformat() if summary.trade_date else "",
        "status": summary.status,
        "generated_at": summary.generated_at.isoformat(),
        "items": [
            {
                "name": item.name,
                "status": item.status,
                "message": item.message,
                "actual": item.actual,
                "expected": item.expected,
                "fix_command": item.fix_command,
            }
            for item in summary.items
        ],
    }


def _parse_iso_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"{field_name} must be YYYY-MM-DD") from exc


def create_app(database_url: Optional[str] = None, engine: Optional[Engine] = None) -> FastAPI:
    settings = get_settings()
    database_engine = engine or create_database_engine(database_url)
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="A股短线量化辅助决策系统 API",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health", tags=["system"])
    def health() -> dict:
        return {
            "status": "ok",
            "service": settings.app_name,
            "environment": settings.app_env,
            "database": {
                "engine": "postgresql",
                "configured": settings.database_configured,
            },
        }

    @app.get("/api/system/data-runs/latest", tags=["system"])
    def latest_data_runs(limit: int = 5) -> dict:
        if limit < 1 or limit > 20:
            raise HTTPException(status_code=400, detail="limit must be between 1 and 20")
        return {
            "items": [
                _data_job_run_payload(run)
                for run in load_latest_data_job_runs(database_engine, limit=limit)
            ]
        }

    @app.get("/api/system/database-health", tags=["system"])
    def database_health(date: Optional[str] = None) -> dict:
        trade_date = _parse_iso_date(date, "date") if date else None
        return _database_health_payload(load_database_health(database_engine, trade_date))

    @app.get("/api/market/latest", tags=["market"])
    def latest_market_environment() -> dict:
        result = load_latest_market_environment(database_engine)
        if result is None:
            return {
                "trade_date": "",
                "market_score": None,
                "market_status": "",
                "suggested_position": "",
                "up_count": None,
                "down_count": None,
                "limit_up_count": None,
                "limit_down_count": None,
                "limit_up_height": None,
                "total_amount": None,
                "suggestion": "暂无市场建议，请先生成市场环境数据。",
            }
        return _market_payload(result)

    @app.get("/api/market/history", tags=["market"])
    def market_environment_history(limit: int = 5) -> dict:
        if limit < 1 or limit > 30:
            raise HTTPException(status_code=400, detail="limit must be between 1 and 30")
        return {
            "items": [
                _market_payload(result)
                for result in load_market_environment_history(database_engine, limit=limit)
            ]
        }

    @app.get("/api/market/today", tags=["market"])
    def today_market_environment() -> dict:
        return latest_market_environment()

    @app.get("/api/market/index-ticker", tags=["market"])
    def market_index_ticker() -> dict:
        return {"items": [_index_ticker_payload(item) for item in load_index_ticker(database_engine)]}

    @app.get("/api/sectors/top", tags=["sector"])
    def top_sectors() -> dict:
        result = load_latest_sector_rankings(database_engine)
        if result is None:
            return {"trade_date": "", "items": []}
        trade_date, items = result
        return {
            "trade_date": trade_date.isoformat(),
            "items": [_sector_payload(item) for item in items],
        }

    @app.get("/api/sectors/strong", tags=["sector"])
    def strong_sectors(date: str) -> dict:
        trade_date = _parse_iso_date(date, "date")
        result = load_sector_rankings_by_date(database_engine, trade_date)
        if result is None:
            raise HTTPException(status_code=404, detail="sector rankings are not generated")
        trade_date, items = result
        return {
            "trade_date": trade_date.isoformat(),
            "items": [_sector_payload(item) for item in items],
        }

    @app.get("/api/candidates/latest", tags=["candidate"])
    def latest_candidates() -> dict:
        result = load_latest_candidates(database_engine)
        if result is None:
            return {"trade_date": "", "items": []}
        trade_date, items = result
        return {
            "trade_date": trade_date.isoformat(),
            "items": [
                {
                    "stock_code": item.stock_code,
                    "stock_name": item.stock_name,
                    "sector_name": item.sector_name,
                    "sector_rank": item.sector_rank,
                    "sector_category": item.sector_category,
                    "stock_pool_rank": item.stock_pool_rank,
                    "strategy_type": item.strategy_type,
                    "stock_score": item.stock_score,
                    "sector_score": item.sector_score,
                    "nine_turn_signal": item.nine_turn_signal,
                    "nine_turn_count": item.nine_turn_count,
                    "nine_turn_score": item.nine_turn_score,
                    "close_price": item.close_price,
                    "amount": item.amount,
                    "reason": item.reason,
                    "risk_note": item.risk_note,
                }
                for item in items
            ],
        }

    @app.get("/api/trade-plans/latest", tags=["trade"])
    def latest_trade_plans() -> dict:
        result = load_latest_trade_plans(database_engine)
        if result is None:
            return {"plan_date": "", "target_trade_date": "", "items": []}
        plan_date, target_trade_date, items = result
        return {
            "plan_date": plan_date.isoformat(),
            "target_trade_date": target_trade_date.isoformat(),
            "items": [_trade_plan_payload(item) for item in items],
        }

    @app.get("/api/trade-plans", tags=["trade"])
    def trade_plans_by_date(date: str) -> dict:
        target_trade_date = _parse_iso_date(date, "date")
        result = load_trade_plans_by_target_date(database_engine, target_trade_date)
        if result is None:
            raise HTTPException(status_code=404, detail="trade plans are not generated")
        plan_date, target_trade_date, items = result
        return {
            "plan_date": plan_date.isoformat(),
            "target_trade_date": target_trade_date.isoformat(),
            "items": [_trade_plan_payload(item) for item in items],
        }

    @app.get("/api/trade-plans/{plan_id}", tags=["trade"])
    def trade_plan_detail(plan_id: int) -> dict:
        result = load_trade_plan_detail(database_engine, plan_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"trade plan not found: {plan_id}")
        return _trade_plan_detail_payload(result)

    @app.post("/api/trade-plans/track", tags=["trade"])
    def track_trade_plans_api(payload: TradePlanTrackingRequest) -> dict:
        try:
            target_trade_date = date.fromisoformat(payload.target_trade_date)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="target_trade_date must be YYYY-MM-DD") from exc
        items = track_trade_plans(
            database_engine,
            target_trade_date,
            mark_untriggered_at_close=payload.mark_untriggered_at_close,
        )
        return _tracking_payload(target_trade_date, items)

    @app.post("/api/trade-plans/track-realtime", tags=["trade"])
    def track_trade_plans_with_realtime_api(payload: TradePlanRealtimeTrackingRequest) -> dict:
        target_trade_date = _parse_iso_date(payload.target_trade_date, "target_trade_date")
        lock_acquired = _realtime_tracking_lock.acquire(blocking=False)
        if not lock_acquired:
            backfill = _busy_realtime_backfill(target_trade_date)
        else:
            try:
                backfill = backfill_trade_plan_realtime_quotes(
                    database_engine,
                    target_trade_date,
                    _realtime_quote_provider(),
                    include_existing=payload.include_existing,
                    allow_date_mismatch=payload.allow_date_mismatch,
                )
            finally:
                _realtime_tracking_lock.release()
        items = track_trade_plans(
            database_engine,
            target_trade_date,
            mark_untriggered_at_close=payload.mark_untriggered_at_close,
        )
        payload_dict = _tracking_payload(target_trade_date, items)
        payload_dict["realtime"] = _realtime_backfill_payload(backfill)
        return payload_dict

    @app.patch("/api/trade-plans/{plan_id}/status", tags=["trade"])
    def update_trade_plan_status_api(plan_id: int, payload: TradePlanStatusUpdate) -> dict:
        try:
            item = update_trade_plan_status(
                database_engine,
                plan_id,
                payload.status,
                trigger_price=payload.trigger_price,
                note=payload.note,
                is_watched=payload.is_watched,
            )
        except ValueError as exc:
            message = str(exc)
            if "not found" in message:
                raise HTTPException(status_code=404, detail=message) from exc
            raise HTTPException(status_code=400, detail=message) from exc
        return _trade_plan_payload(item)

    @app.post("/api/trade-reviews/generate", tags=["trade"])
    def generate_trade_reviews_api(payload: TradeReviewGenerateRequest) -> dict:
        try:
            trade_date = date.fromisoformat(payload.trade_date)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="trade_date must be YYYY-MM-DD") from exc
        return _trade_review_payload(generate_trade_reviews(database_engine, trade_date))

    @app.get("/api/trade-reviews/latest", tags=["trade"])
    def latest_trade_reviews() -> dict:
        result = load_latest_trade_reviews(database_engine)
        if result is None:
            raise HTTPException(status_code=404, detail="trade reviews are not generated")
        return _trade_review_payload(result)

    @app.get("/api/reviews", tags=["trade"])
    def trade_reviews_by_date(date: str) -> dict:
        trade_date = _parse_iso_date(date, "date")
        result = load_trade_reviews_by_date(database_engine, trade_date)
        if result is None:
            raise HTTPException(status_code=404, detail="trade reviews are not generated")
        return _trade_review_payload(result)

    @app.post("/api/reviews", tags=["trade"])
    def create_trade_reviews(payload: TradeReviewGenerateRequest) -> dict:
        trade_date = _parse_iso_date(payload.trade_date, "trade_date")
        return _trade_review_payload(generate_trade_reviews(database_engine, trade_date))

    @app.patch("/api/reviews/{review_id}", tags=["trade"])
    def update_trade_review_api(review_id: int, payload: TradeReviewUpdate) -> dict:
        try:
            item = update_trade_review(
                database_engine,
                review_id,
                result=payload.result,
                failure_reason=payload.failure_reason,
                discipline_check=payload.discipline_check,
                note=payload.note,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            "id": item.id,
            "trade_plan_id": item.trade_plan_id,
            "trade_date": item.trade_date.isoformat(),
            "stock_code": item.stock_code,
            "stock_name": item.stock_name,
            "sector_name": item.sector_name,
            "strategy_type": item.strategy_type,
            "triggered": item.triggered,
            "trigger_price": item.trigger_price,
            "close_price": item.close_price,
            "day_return": item.day_return,
            "t5_return": item.t5_return,
            "max_profit": item.max_profit,
            "max_loss": item.max_loss,
            "result": item.result,
            "failure_reason": item.failure_reason,
            "discipline_check": item.discipline_check,
            "note": item.note,
        }

    @app.post("/api/simulation/run", tags=["simulation"])
    def run_simulation_api(payload: SimulationRunRequest) -> dict:
        try:
            trade_date = date.fromisoformat(payload.trade_date)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="trade_date must be YYYY-MM-DD") from exc
        return asdict(run_simulation(database_engine, trade_date))

    @app.post("/api/simulation/run-workflow", tags=["simulation"])
    def run_simulation_workflow_api(payload: SimulationWorkflowRunRequest) -> dict:
        try:
            trade_date = date.fromisoformat(payload.trade_date)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="trade_date must be YYYY-MM-DD") from exc
        return asdict(
            run_simulation_workflow(
                database_engine,
                trade_date,
                mark_untriggered_at_close=payload.mark_untriggered_at_close,
            )
        )

    @app.get("/api/simulation/latest", tags=["simulation"])
    def latest_simulation() -> dict:
        result = load_latest_simulation(database_engine)
        if result is None:
            raise HTTPException(status_code=404, detail="simulation is not generated")
        return asdict(result)

    return app


app = create_app()
