from sqlalchemy import delete
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.app.data.types import IngestSummary, MarketDataSnapshot
from backend.app.db.models import (
    DataIngestRun,
    IndexDaily,
    LimitSnapshot,
    StockBasic,
    StockDaily,
    TradingCalendar,
)


def ingest_market_snapshot(engine: Engine, snapshot: MarketDataSnapshot) -> IngestSummary:
    with Session(engine) as session:
        for record in snapshot.trading_calendar:
            session.execute(
                delete(TradingCalendar).where(TradingCalendar.trade_date == record.trade_date)
            )
            session.flush()
            session.add(TradingCalendar(**record.__dict__))

        for record in snapshot.stock_basic:
            session.execute(delete(StockBasic).where(StockBasic.stock_code == record.stock_code))
            session.flush()
            session.add(StockBasic(**record.__dict__))

        for record in snapshot.index_daily:
            session.execute(
                delete(IndexDaily).where(
                    IndexDaily.index_code == record.index_code,
                    IndexDaily.trade_date == record.trade_date,
                )
            )
            session.flush()
            session.add(IndexDaily(**record.__dict__))

        for record in snapshot.stock_daily:
            session.execute(
                delete(StockDaily).where(
                    StockDaily.stock_code == record.stock_code,
                    StockDaily.trade_date == record.trade_date,
                )
            )
            session.flush()
            session.add(StockDaily(**record.__dict__))

        for record in snapshot.limit_snapshot:
            session.execute(
                delete(LimitSnapshot).where(
                    LimitSnapshot.trade_date == record.trade_date,
                    LimitSnapshot.stock_code == record.stock_code,
                    LimitSnapshot.limit_status == record.limit_status,
                )
            )
            session.flush()
            session.add(LimitSnapshot(**record.__dict__))

        ingest_run = DataIngestRun(
            provider=snapshot.provider,
            trade_date=snapshot.trade_date,
            status="success",
            message="market data snapshot ingested",
            trading_calendar_rows=len(snapshot.trading_calendar),
            stock_basic_rows=len(snapshot.stock_basic),
            index_daily_rows=len(snapshot.index_daily),
            stock_daily_rows=len(snapshot.stock_daily),
            limit_snapshot_rows=len(snapshot.limit_snapshot),
        )
        session.add(ingest_run)
        session.flush()

        summary = IngestSummary(
            provider=snapshot.provider,
            trade_date=snapshot.trade_date,
            status="success",
            message="market data snapshot ingested",
            ingest_run_id=ingest_run.id,
            trading_calendar_rows=len(snapshot.trading_calendar),
            stock_basic_rows=len(snapshot.stock_basic),
            index_daily_rows=len(snapshot.index_daily),
            stock_daily_rows=len(snapshot.stock_daily),
            limit_snapshot_rows=len(snapshot.limit_snapshot),
        )
        session.commit()
        return summary
