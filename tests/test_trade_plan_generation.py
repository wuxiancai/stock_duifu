from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.db.models import CandidateStock, MarketDaily, StockDaily, TradePlan, TradingCalendar, metadata
from backend.app.main import create_app
from backend.app.trade.service import generate_trade_plans


def _engine():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    return engine


def _seed_fixture(engine, market_status: str = "中性") -> date:
    plan_date = date(2026, 6, 18)
    with Session(engine) as session:
        session.add(
            MarketDaily(
                trade_date=plan_date,
                market_score=65,
                market_status=market_status,
                up_count=2600,
                down_count=2300,
                limit_up_count=58,
                limit_down_count=5,
                total_amount=1200000000000,
                suggestion="轻仓参与强势板块",
            )
        )
        session.add(TradingCalendar(trade_date=date(2026, 6, 19), is_open=True, source="unit-test"))
        _seed_candidates(session, plan_date)
        _seed_histories(session, plan_date)
        session.commit()
    return plan_date


def _seed_candidates(session: Session, plan_date: date) -> None:
    rows = [
        ("000001", "趋势强势A", "机器人", "趋势强势", 99, 100, 13.6, "趋势风险"),
        ("000002", "突破B", "半导体", "放量突破", 96, 100, 13.0, "突破风险"),
        ("000003", "回踩C", "CPO概念", "强势回踩", 94, 95, 14.2, "回踩风险"),
        ("000004", "同板块D", "机器人", "趋势强势", 93, 90, 11.0, "同板块风险"),
    ]
    for code, name, sector, strategy, stock_score, sector_score, close, risk in rows:
        session.add(
            CandidateStock(
                trade_date=plan_date,
                stock_code=code,
                stock_name=name,
                sector_name=sector,
                sector_rank=1,
                strategy_type=strategy,
                stock_score=stock_score,
                sector_score=sector_score,
                close_price=close,
                amount=1200000000,
                reason="板块排名 Top 10",
                risk_note=risk,
            )
        )


def _seed_histories(session: Session, plan_date: date) -> None:
    for code, base, step in [
        ("000001", 10.0, 0.15),
        ("000002", 9.0, 0.17),
        ("000003", 12.0, 0.09),
        ("000004", 8.0, 0.12),
    ]:
        start = plan_date - timedelta(days=24)
        for offset in range(25):
            close = base + offset * step
            _add_daily(session, code, start + timedelta(days=offset), close)


def _add_daily(session: Session, stock_code: str, trade_date: date, close: float) -> None:
    session.add(
        StockDaily(
            stock_code=stock_code,
            trade_date=trade_date,
            open=close * 0.99,
            high=close * 1.02,
            low=close * 0.97,
            close=close,
            pre_close=close * 0.99,
            change=close * 0.01,
            pct_chg=1.0,
            volume=1000,
            amount=1000000000,
            turnover_rate=3.0,
            source="unit-test",
        )
    )


def test_generate_trade_plans_persists_complete_risk_controlled_plans() -> None:
    engine = _engine()
    plan_date = _seed_fixture(engine)

    plans = generate_trade_plans(engine, plan_date)

    assert len(plans) == 2
    assert {plan.stock_code for plan in plans} == {"000001", "000002"}
    assert all(plan.target_trade_date == date(2026, 6, 19) for plan in plans)
    assert all(plan.status == "待触发" for plan in plans)
    assert all(plan.buy_condition for plan in plans)
    assert all(plan.stop_loss_price < plan.buy_price_high for plan in plans)
    assert all(plan.take_profit_price > plan.buy_price_high for plan in plans)
    assert all(plan.position_ratio in {0.4, 0.2} for plan in plans)

    with Session(engine) as session:
        saved = session.scalars(select(TradePlan).order_by(TradePlan.stock_code)).all()
        assert len(saved) == 2
        assert saved[0].market_status == "中性"


def test_generate_trade_plans_is_idempotent_for_same_plan_date() -> None:
    engine = _engine()
    plan_date = _seed_fixture(engine)

    first = generate_trade_plans(engine, plan_date)
    generate_trade_plans(engine, plan_date)

    with Session(engine) as session:
        assert session.query(TradePlan).count() == len(first)


def test_generate_trade_plans_skips_risk_market() -> None:
    engine = _engine()
    plan_date = _seed_fixture(engine, market_status="风险")

    assert generate_trade_plans(engine, plan_date) == []

    with Session(engine) as session:
        assert session.query(TradePlan).count() == 0


def test_trade_plans_latest_api_returns_persisted_plans() -> None:
    engine = _engine()
    plan_date = _seed_fixture(engine)
    generate_trade_plans(engine, plan_date)

    client = TestClient(create_app(database_url="sqlite+pysqlite://", engine=engine))
    response = client.get("/api/trade-plans/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["plan_date"] == "2026-06-18"
    assert payload["target_trade_date"] == "2026-06-19"
    assert len(payload["items"]) == 2
    assert all(item["stop_loss_price"] for item in payload["items"])
