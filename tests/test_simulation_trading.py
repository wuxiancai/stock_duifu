from datetime import date, timedelta
from typing import Optional

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.db.models import SimulationAccount, SimulationEquity, SimulationPosition, SimulationTrade, StockDaily, TradePlan, metadata
from backend.app.main import create_app
from backend.app.simulation.service import load_latest_simulation, run_simulation, run_simulation_workflow


def _engine():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    return engine


def _seed_trade_plan(
    session: Session,
    stock_code: str = "000001",
    status: str = "已触发",
    trigger_price: Optional[float] = 10.2,
    tracking_note: str = "目标交易日价格触达计划买入区间",
) -> TradePlan:
    plan = TradePlan(
        plan_date=date(2026, 6, 18),
        target_trade_date=date(2026, 6, 19),
        stock_code=stock_code,
        stock_name="计划内股票",
        sector_name="科技风格",
        strategy_type="趋势强势",
        stock_score=99,
        sector_score=100,
        market_status="中性",
        buy_condition="目标交易日价格触达计划买入区间",
        buy_price_low=10.0,
        buy_price_high=11.0,
        stop_loss_price=9.5,
        take_profit_price=13.2,
        position_ratio=0.4,
        status=status,
        trigger_price=trigger_price,
        tracking_note=tracking_note,
        risk_note="严格执行止损",
    )
    session.add(plan)
    session.flush()
    return plan


def _add_daily(
    session: Session,
    stock_code: str,
    trade_date: date,
    open_price: float,
    high: float,
    low: float,
    close: float,
    pct_chg: float = 2.0,
) -> None:
    session.add(
        StockDaily(
            stock_code=stock_code,
            trade_date=trade_date,
            open=open_price,
            high=high,
            low=low,
            close=close,
            pre_close=10.0,
            change=close - 10.0,
            pct_chg=pct_chg,
            volume=1000,
            amount=1000000000,
            turnover_rate=3.0,
            source="unit-test",
        )
    )


def test_run_simulation_creates_default_account_and_buys_plan_stock_with_fees() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_trade_plan(session)
        _add_daily(session, "000001", date(2026, 6, 19), 10.2, 10.8, 10.0, 10.5)
        session.commit()

    summary = run_simulation(engine, date(2026, 6, 19))

    assert summary.account.initial_cash == 1000000.0
    assert summary.account.available_cash < 1000000.0
    assert summary.account.market_value > 0
    assert summary.account.total_assets > 0
    assert summary.risk.max_drawdown == 0.0
    assert len(summary.positions) == 1
    assert summary.positions[0].stock_code == "000001"
    assert summary.positions[0].quantity % 100 == 0
    assert summary.positions[0].buy_reason == "目标交易日价格触达计划买入区间"
    assert len(summary.trades) == 1
    assert summary.trades[0].trade_type == "买入"
    assert summary.trades[0].total_fee > 0
    assert summary.trades[0].reason == "目标交易日价格触达计划买入区间"
    assert len(summary.equity_curve) == 1

    with Session(engine) as session:
        assert session.query(SimulationAccount).count() == 1
        assert session.query(SimulationPosition).count() == 1
        assert session.query(SimulationTrade).count() == 1
        assert session.query(SimulationEquity).count() == 1


def test_run_simulation_only_executes_planned_stocks_and_blocks_limit_up_buy() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_trade_plan(session, "000001")
        _add_daily(session, "000001", date(2026, 6, 19), 11.0, 11.0, 11.0, 11.0, pct_chg=10.0)
        _add_daily(session, "000002", date(2026, 6, 19), 10.0, 10.5, 9.9, 10.4)
        session.commit()

    summary = run_simulation(engine, date(2026, 6, 19))

    assert summary.positions == []
    assert summary.trades == []
    assert summary.risk.position_count == 0
    assert summary.messages == ["000001 计划触发但目标交易日涨停，按保守成交规则不买入"]


def test_run_simulation_sells_position_when_stop_loss_is_hit() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_trade_plan(session)
        _add_daily(session, "000001", date(2026, 6, 19), 10.2, 10.8, 10.0, 10.5)
        _add_daily(session, "000001", date(2026, 6, 22), 9.4, 9.5, 9.2, 9.3, pct_chg=-8.0)
        session.commit()

    run_simulation(engine, date(2026, 6, 19))
    summary = run_simulation(engine, date(2026, 6, 22))

    assert summary.positions == []
    assert any(trade.trade_type == "卖出" for trade in summary.trades)
    sell = next(trade for trade in summary.trades if trade.trade_type == "卖出")
    assert sell.reason == "跌破计划止损价，模拟全仓止损"
    assert sell.profit_loss is not None
    assert summary.risk.max_drawdown > 0


def test_run_simulation_workflow_tracks_pending_plan_then_buys() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_trade_plan(session, status="待触发", trigger_price=None, tracking_note="")
        _add_daily(session, "000001", date(2026, 6, 19), 10.1, 10.8, 10.0, 10.5)
        session.commit()

    workflow = run_simulation_workflow(engine, date(2026, 6, 19))

    assert workflow.target_trade_date == date(2026, 6, 19)
    assert workflow.tracking[0].status == "已触发"
    assert workflow.tracking[0].trigger_price is not None
    assert workflow.simulation.positions[0].stock_code == "000001"
    assert workflow.simulation.trades[0].trade_type == "买入"
    assert workflow.simulation.trades[0].reason == "目标交易日价格触达计划买入区间"

    with Session(engine) as session:
        plan = session.scalar(select(TradePlan).where(TradePlan.stock_code == "000001"))
        assert plan.status == "已触发"
        assert plan.trigger_price is not None
        assert session.query(SimulationTrade).count() == 1


def test_simulation_api_runs_and_returns_latest_summary() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_trade_plan(session)
        _add_daily(session, "000001", date(2026, 6, 19), 10.2, 10.8, 10.0, 10.5)
        session.commit()

    client = TestClient(create_app(database_url="sqlite+pysqlite://", engine=engine))
    response = client.post("/api/simulation/run", json={"trade_date": "2026-06-19"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["account"]["initial_cash"] == 1000000.0
    assert payload["positions"][0]["stock_code"] == "000001"
    assert payload["trades"][0]["reason"]
    assert payload["risk"]["max_drawdown"] == 0.0

    latest = client.get("/api/simulation/latest")
    assert latest.status_code == 200
    assert latest.json()["as_of_date"] == "2026-06-19"


def test_simulation_workflow_api_tracks_and_runs_simulation() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_trade_plan(session, status="待触发", trigger_price=None, tracking_note="")
        _add_daily(session, "000001", date(2026, 6, 19), 10.1, 10.8, 10.0, 10.5)
        session.commit()

    client = TestClient(create_app(database_url="sqlite+pysqlite://", engine=engine))
    response = client.post("/api/simulation/run-workflow", json={"trade_date": "2026-06-19"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["target_trade_date"] == "2026-06-19"
    assert payload["tracking"][0]["status"] == "已触发"
    assert payload["simulation"]["positions"][0]["stock_code"] == "000001"
    assert payload["simulation"]["trades"][0]["trade_type"] == "买入"


def test_load_latest_simulation_returns_none_without_account() -> None:
    engine = _engine()

    assert load_latest_simulation(engine) is None
