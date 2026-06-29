from datetime import date, datetime, timezone
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
from backend.app.db.models import (
    CandidateStock,
    DataJobRun,
    MarketDaily,
    SectorDaily,
    StockBasic,
    StockDaily,
    TradingCalendar,
    metadata,
)
from backend.app.main import create_app
from backend.app.system.monitoring import _sector_health_item
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
        "生成交易复盘",
        "生成交易计划",
        "覆盖审计",
    ]
    assert payload["items"][0]["steps"][1]["summary"]["stock_daily_rows"] == 2


def test_data_runs_latest_api_ignores_closed_calendar_dates() -> None:
    engine = _engine()
    with Session(engine) as session:
        session.add_all(
            [
                TradingCalendar(trade_date=date(2026, 6, 20), is_open=False, source="unit-test"),
                TradingCalendar(trade_date=date(2026, 6, 22), is_open=True, source="unit-test"),
                DataJobRun(
                    job_name="after_close_data_pull",
                    trade_date=date(2026, 6, 20),
                    status="error",
                    command="bash get_data.sh 2026-06-20",
                    message="闭市日历史误跑任务",
                    started_at=datetime(2026, 6, 23, 8, 57, tzinfo=timezone.utc),
                    ended_at=datetime(2026, 6, 23, 8, 58, tzinfo=timezone.utc),
                ),
                DataJobRun(
                    job_name="after_close_data_pull",
                    trade_date=date(2026, 6, 22),
                    status="success",
                    command="bash get_data.sh 2026-06-22",
                    message="开市日任务",
                    started_at=datetime(2026, 6, 23, 8, 59, tzinfo=timezone.utc),
                    ended_at=datetime(2026, 6, 23, 9, 1, tzinfo=timezone.utc),
                ),
            ]
        )
        session.commit()

    client = TestClient(create_app(database_url="sqlite+pysqlite://", engine=engine))
    response = client.get("/api/system/data-runs/latest")

    assert response.status_code == 200
    payload = response.json()
    assert [item["trade_date"] for item in payload["items"]] == ["2026-06-22"]


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


def test_sector_health_uses_primary_industry_ranking_universe() -> None:
    item = _sector_health_item(date(2026, 6, 25), sector_rows=31, max_rank=31, command="TRADE_DATE=2026-06-25 bash get_data.sh")

    assert item.name == "强势行业排名"
    assert item.status == "ok"
    assert item.fix_command == ""
    assert "东财一级行业" in item.message
    assert "511" not in item.expected


def test_sector_health_rejects_legacy_mixed_sector_universe() -> None:
    item = _sector_health_item(date(2026, 6, 25), sector_rows=511, max_rank=511, command="TRADE_DATE=2026-06-25 bash get_data.sh")

    assert item.status == "error"
    assert item.fix_command == "TRADE_DATE=2026-06-25 bash get_data.sh"
    assert "概念板块" in item.message


def test_database_health_treats_excluded_st_and_inactive_stock_daily_gaps_as_ok() -> None:
    engine = _engine()
    trade_date = date(2026, 6, 18)
    with Session(engine) as session:
        session.add(TradingCalendar(trade_date=trade_date, is_open=True, source="unit-test"))
        session.add_all(
            [
                StockBasic(
                    stock_code="000001",
                    stock_name="平安银行",
                    market="SZ",
                    list_date=date(2020, 1, 1),
                    is_st=False,
                    status="active",
                    source="unit-test",
                ),
                StockBasic(
                    stock_code="000002",
                    stock_name="ST测试",
                    market="SZ",
                    list_date=date(2020, 1, 1),
                    is_st=True,
                    status="active",
                    source="unit-test",
                ),
                StockBasic(
                    stock_code="000003",
                    stock_name="退市测试",
                    market="SZ",
                    list_date=date(2020, 1, 1),
                    is_st=False,
                    status="inactive",
                    source="unit-test",
                ),
            ]
        )
        session.add(
            StockDaily(
                stock_code="000001",
                trade_date=trade_date,
                open=10,
                high=11,
                low=9,
                close=10.5,
                pre_close=10,
                change=0.5,
                pct_chg=5,
                volume=100,
                amount=1000,
                turnover_rate=1,
                source="unit-test",
            )
        )
        session.commit()

    client = TestClient(create_app(database_url="sqlite+pysqlite://", engine=engine))
    response = client.get("/api/system/database-health?date=2026-06-18")

    assert response.status_code == 200
    stock_daily = next(item for item in response.json()["items"] if item["name"] == "个股日线")
    assert stock_daily["status"] == "ok"
    assert stock_daily["actual"] == "1 / 1"
    assert stock_daily["fix_command"] == ""
    assert "已排除" in stock_daily["expected"]


def test_database_health_treats_empty_stock_pool_as_ok_for_trade_plan() -> None:
    engine = _engine()
    trade_date = date(2026, 6, 29)
    with Session(engine) as session:
        session.add(TradingCalendar(trade_date=trade_date, is_open=True, source="unit-test"))
        for index in range(12):
            session.add(
                CandidateStock(
                    trade_date=trade_date,
                    stock_code=f"300{index:03d}",
                    stock_name=f"趋势观察{index}",
                    sector_name="医药生物",
                    sector_rank=2,
                    sector_category="趋势观察",
                    stock_pool_rank=None,
                    strategy_type="趋势强势",
                    stock_score=100 - index,
                    sector_score=80,
                    close_price=20 + index,
                    amount=1_000_000_000,
                    reason="行业持续性：趋势观察，不进入股票池",
                    risk_note="未满足股票池规则",
                )
            )
        session.commit()

    client = TestClient(create_app(database_url="sqlite+pysqlite://", engine=engine))
    response = client.get("/api/system/database-health?date=2026-06-29")

    assert response.status_code == 200
    trade_plan = next(item for item in response.json()["items"] if item["name"] == "交易计划")
    assert trade_plan["status"] == "ok"
    assert trade_plan["actual"] == "0"
    assert trade_plan["fix_command"] == ""
    assert "股票池规则" in trade_plan["message"]
