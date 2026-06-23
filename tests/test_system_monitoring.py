from datetime import date
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.data.types import (
    IndexDailyRecord,
    LimitSnapshotRecord,
    MarketDataSnapshot,
    StockBasicRecord,
    StockDailyRecord,
    TradingCalendarRecord,
)
from backend.app.db.models import MarketDaily, SectorDaily, metadata
from backend.app.main import create_app
from backend.app.workflow.service import run_after_close_workflow


def _engine():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    return engine


class FakeMarketProvider:
    source = "unit-test"

    def fetch_snapshot(self, trade_date, sample_size, stock_codes=None):
        return MarketDataSnapshot(
            provider="unit-test",
            trade_date=trade_date,
            trading_calendar=[TradingCalendarRecord(trade_date, True, "unit-test")],
            stock_basic=[
                StockBasicRecord("000001", "平安银行", "SZ", None, False, "active", "unit-test"),
                StockBasicRecord("600519", "贵州茅台", "SH", None, False, "active", "unit-test"),
            ],
            index_daily=[
                IndexDailyRecord("000001.SH", trade_date, 1, 2, 1, 2, 100, 1000, "unit-test"),
                IndexDailyRecord("399001.SZ", trade_date, 1, 2, 1, 2, 100, 1000, "unit-test"),
                IndexDailyRecord("399006.SZ", trade_date, 1, 2, 1, 2, 100, 1000, "unit-test"),
            ],
            stock_daily=[
                StockDailyRecord("000001", trade_date, 10, 11, 9, 10.5, 10, 0.5, 5, 100, 1000, 1.0, "unit-test"),
                StockDailyRecord("600519", trade_date, 20, 21, 19, 20.5, 20, 0.5, 2.5, 100, 2000, 1.0, "unit-test"),
            ],
            limit_snapshot=[
                LimitSnapshotRecord(trade_date, "000001", "平安银行", 10.5, 10, "limit_up", 1000, "unit-test")
            ],
        )


class FakeSectorProvider:
    source = "sector-test"


class FakeCandidateProvider:
    source = "candidate-test"


def test_after_close_workflow_records_step_logs_and_api_returns_them(monkeypatch) -> None:
    engine = _engine()
    trade_date = date(2026, 6, 18)

    def fake_market(engine, trade_date):
        with Session(engine) as session:
            session.add(
                MarketDaily(
                    trade_date=trade_date,
                    market_score=65,
                    market_status="中性",
                    up_count=1,
                    down_count=1,
                    limit_up_count=1,
                    limit_down_count=0,
                    limit_up_height=1,
                    total_amount=1000,
                    suggestion="单元测试",
                )
            )
            session.commit()
        return SimpleNamespace(trade_date=trade_date, market_score=65, market_status="中性")

    def fake_sectors(engine, trade_date, provider):
        with Session(engine) as session:
            for rank in range(1, 512):
                session.add(
                    SectorDaily(
                        trade_date=trade_date,
                        sector_name=f"板块{rank}",
                        rank_no=rank,
                        daily_return=1,
                        five_day_return=5,
                        amount_change=1,
                        limit_up_count=0,
                        strong_stock_count=1,
                        sector_score=80,
                    )
                )
            session.commit()
        return [SimpleNamespace(sector_name="板块1")]

    monkeypatch.setattr("backend.app.workflow.service.generate_market_environment", fake_market)
    monkeypatch.setattr("backend.app.workflow.service.generate_sector_rankings", fake_sectors)
    monkeypatch.setattr(
        "backend.app.workflow.service.generate_candidate_stocks",
        lambda engine, trade_date, provider, limit: [SimpleNamespace(stock_code="000001")],
    )
    monkeypatch.setattr(
        "backend.app.workflow.service.generate_trade_plans",
        lambda engine, plan_date, limit=None: [SimpleNamespace(stock_code="000001", target_trade_date=date(2026, 6, 19))],
    )

    run_after_close_workflow(
        engine,
        trade_date,
        FakeMarketProvider(),
        FakeSectorProvider(),
        FakeCandidateProvider(),
    )

    client = TestClient(create_app(database_url="sqlite+pysqlite://", engine=engine))
    runs = client.get("/api/system/data-runs/latest")

    assert runs.status_code == 200
    payload = runs.json()
    assert payload["items"][0]["trade_date"] == "2026-06-18"
    assert payload["items"][0]["status"] == "warning"
    assert [step["step_name"] for step in payload["items"][0]["steps"]] == [
        "拉取行情快照",
        "写入行情数据库",
        "生成市场环境",
        "生成强势板块",
        "生成候选股票",
        "生成交易计划",
        "覆盖审计",
    ]
    assert payload["items"][0]["steps"][1]["summary"]["stock_daily_rows"] == 2


def test_database_health_api_reports_missing_data_with_fix_command() -> None:
    engine = _engine()
    trade_date = date(2026, 6, 18)
    FakeMarketProvider().fetch_snapshot(trade_date, 0)
    client = TestClient(create_app(database_url="sqlite+pysqlite://", engine=engine))

    response = client.get("/api/system/database-health?date=2026-06-18")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trade_date"] == "2026-06-18"
    assert payload["status"] == "error"
    stock_daily = next(item for item in payload["items"] if item["name"] == "个股日线")
    assert stock_daily["status"] == "error"
    assert stock_daily["fix_command"] == "TRADE_DATE=2026-06-18 bash get_data.sh"
