from typing import Optional

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.engine import Engine

from backend.app.core.config import get_settings
from backend.app.db.session import create_database_engine
from backend.app.market.service import load_latest_market_environment
from backend.app.sector.service import load_latest_sector_rankings


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

    @app.get("/api/market/latest", tags=["market"])
    def latest_market_environment() -> dict:
        result = load_latest_market_environment(database_engine)
        if result is None:
            raise HTTPException(status_code=404, detail="market environment is not generated")
        return {
            "trade_date": result.trade_date.isoformat(),
            "market_score": result.market_score,
            "market_status": result.market_status,
            "suggested_position": result.suggested_position,
            "up_count": result.up_count,
            "down_count": result.down_count,
            "limit_up_count": result.limit_up_count,
            "limit_down_count": result.limit_down_count,
            "total_amount": result.total_amount,
            "suggestion": result.suggestion,
        }

    @app.get("/api/sectors/top", tags=["sector"])
    def top_sectors() -> dict:
        result = load_latest_sector_rankings(database_engine)
        if result is None:
            raise HTTPException(status_code=404, detail="sector rankings are not generated")
        trade_date, items = result
        return {
            "trade_date": trade_date.isoformat(),
            "items": [
                {
                    "rank_no": item.rank_no,
                    "sector_name": item.sector_name,
                    "daily_return": item.daily_return,
                    "three_day_return": item.three_day_return,
                    "amount_change": item.amount_change,
                    "limit_up_count": item.limit_up_count,
                    "strong_stock_count": item.strong_stock_count,
                    "sector_score": item.sector_score,
                }
                for item in items
            ],
        }

    return app


app = create_app()
