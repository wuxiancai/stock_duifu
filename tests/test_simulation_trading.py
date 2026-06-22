from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.core.config import get_settings
from backend.app.db.models import (
    MarketDaily,
    SectorDaily,
    SimulationAccount,
    SimulationEquity,
    SimulationPosition,
    SimulationTrade,
    StockDaily,
    TradePlan,
    TradingCalendar,
    metadata,
)
from backend.app.main import create_app
from backend.app.simulation.service import _fees, load_latest_simulation, run_simulation, run_simulation_workflow


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
    target_trade_date: date = date(2026, 6, 19),
) -> TradePlan:
    plan = TradePlan(
        plan_date=date(2026, 6, 18),
        target_trade_date=target_trade_date,
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


def _add_market(session: Session, trade_date: date, market_status: str = "风险") -> None:
    session.add(
        MarketDaily(
            trade_date=trade_date,
            market_score=20,
            market_status=market_status,
            up_count=500,
            down_count=4500,
            limit_up_count=20,
            limit_down_count=40,
            total_amount=800000000000,
            suggestion="市场风险，降低模拟仓位",
        )
    )


def _add_sector(
    session: Session,
    trade_date: date,
    sector_name: str = "科技风格",
    daily_return: float = -3.5,
) -> None:
    session.add(
        SectorDaily(
            trade_date=trade_date,
            sector_name=sector_name,
            rank_no=10,
            daily_return=daily_return,
            five_day_return=-6.0,
            amount_change=-20.0,
            limit_up_count=0,
            strong_stock_count=0,
            sector_score=20,
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


def test_simulation_fee_rates_are_configurable(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("SIMULATION_COMMISSION_RATE", "0.001")
    monkeypatch.setenv("SIMULATION_STAMP_TAX_RATE", "0.002")
    monkeypatch.setenv("SIMULATION_TRANSFER_FEE_RATE", "0.0002")
    monkeypatch.setenv("SIMULATION_MIN_COMMISSION", "1")

    sell_fee = _fees(10000, "卖出")

    assert sell_fee == {
        "commission": 10.0,
        "stamp_tax": 20.0,
        "transfer_fee": 2.0,
        "total_fee": 32.0,
    }
    get_settings.cache_clear()


def test_run_simulation_sells_half_at_first_take_profit_and_marks_partial_position() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_trade_plan(session)
        _add_daily(session, "000001", date(2026, 6, 19), 10.2, 10.8, 10.0, 10.5)
        _add_daily(session, "000001", date(2026, 6, 22), 13.0, 13.5, 12.9, 13.3, pct_chg=6.0)
        session.commit()

    run_simulation(engine, date(2026, 6, 19))
    summary = run_simulation(engine, date(2026, 6, 22))

    assert len(summary.positions) == 1
    position = summary.positions[0]
    assert position.position_status == "部分止盈"
    assert position.quantity > 0
    sell = next(trade for trade in summary.trades if trade.trade_type == "卖出")
    assert sell.reason == "达到第一止盈位，模拟卖出 50%"
    assert sell.quantity % 100 == 0
    assert sell.profit_loss is not None and sell.profit_loss > 0
    assert summary.risk.win_rate == 1.0
    assert summary.risk.profit_loss_ratio is None


def test_run_simulation_sells_thirty_percent_more_at_second_take_profit() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_trade_plan(session)
        _add_daily(session, "000001", date(2026, 6, 19), 10.2, 10.8, 10.0, 10.5)
        _add_daily(session, "000001", date(2026, 6, 22), 13.0, 13.5, 12.9, 13.3, pct_chg=6.0)
        _add_daily(session, "000001", date(2026, 6, 23), 14.6, 15.0, 14.2, 14.8, pct_chg=7.0)
        session.commit()

    run_simulation(engine, date(2026, 6, 19))
    first = run_simulation(engine, date(2026, 6, 22))
    second = run_simulation(engine, date(2026, 6, 23))

    first_sell = next(trade for trade in first.trades if trade.trade_type == "卖出")
    second_sell = next(trade for trade in second.trades if trade.trade_type == "卖出")
    assert first_sell.reason == "达到第一止盈位，模拟卖出 50%"
    assert second_sell.reason == "达到第二止盈位，模拟再卖出 30%"
    assert second.positions[0].position_status == "部分止盈"
    assert second.positions[0].quantity < first.positions[0].quantity


def test_run_simulation_sells_remaining_position_when_close_breaks_ma5() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_trade_plan(session)
        _add_daily(session, "000001", date(2026, 6, 19), 10.2, 10.8, 10.0, 10.5)
        for index, close in enumerate([11.0, 11.2, 11.1, 10.9], start=1):
            day = date(2026, 6, 19) + timedelta(days=index)
            _add_daily(session, "000001", day, close, close + 0.2, close - 0.2, close)
        _add_daily(session, "000001", date(2026, 6, 24), 10.2, 10.3, 10.0, 10.1, pct_chg=-4.0)
        session.commit()

    run_simulation(engine, date(2026, 6, 19))
    summary = run_simulation(engine, date(2026, 6, 24))

    assert summary.positions == []
    sell = next(trade for trade in summary.trades if trade.trade_type == "卖出")
    assert sell.reason == "跌破 MA5，模拟卖出剩余仓位"


def test_run_simulation_sells_position_when_market_turns_risk() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_trade_plan(session)
        _add_daily(session, "000001", date(2026, 6, 19), 10.2, 10.8, 10.0, 10.5)
        _add_daily(session, "000001", date(2026, 6, 22), 10.4, 10.7, 10.2, 10.6)
        _add_market(session, date(2026, 6, 22), market_status="风险")
        session.commit()

    run_simulation(engine, date(2026, 6, 19))
    summary = run_simulation(engine, date(2026, 6, 22))

    assert summary.positions == []
    sell = next(trade for trade in summary.trades if trade.trade_type == "卖出")
    assert sell.reason == "大盘转风险，模拟卖出剩余仓位"


def test_run_simulation_sells_position_when_sector_fades() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_trade_plan(session)
        _add_daily(session, "000001", date(2026, 6, 19), 10.2, 10.8, 10.0, 10.5)
        _add_daily(session, "000001", date(2026, 6, 22), 10.4, 10.7, 10.2, 10.6)
        _add_sector(session, date(2026, 6, 22), daily_return=-3.5)
        session.commit()

    run_simulation(engine, date(2026, 6, 19))
    summary = run_simulation(engine, date(2026, 6, 22))

    assert summary.positions == []
    sell = next(trade for trade in summary.trades if trade.trade_type == "卖出")
    assert sell.reason == "板块退潮，模拟卖出剩余仓位"


def test_run_simulation_sells_position_after_plan_holding_period() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_trade_plan(session)
        _add_daily(session, "000001", date(2026, 6, 19), 10.2, 10.8, 10.0, 10.5)
        _add_daily(session, "000001", date(2026, 6, 25), 10.4, 10.7, 10.2, 10.6)
        session.commit()

    run_simulation(engine, date(2026, 6, 19))
    summary = run_simulation(engine, date(2026, 6, 25))

    assert summary.positions == []
    sell = next(trade for trade in summary.trades if trade.trade_type == "卖出")
    assert sell.reason == "持仓超期，按收盘价模拟卖出剩余仓位"


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
    assert payload["trades"][0]["trade_time"]
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


def test_run_simulation_uses_next_open_trade_date_when_requested_date_is_closed() -> None:
    engine = _engine()
    with Session(engine) as session:
        session.add(TradingCalendar(trade_date=date(2026, 6, 19), is_open=False, source="unit-test"))
        session.add(TradingCalendar(trade_date=date(2026, 6, 22), is_open=True, source="unit-test"))
        _seed_trade_plan(session, target_trade_date=date(2026, 6, 22))
        _add_daily(session, "000001", date(2026, 6, 22), 10.2, 10.8, 10.0, 10.5)
        session.commit()

    summary = run_simulation(engine, date(2026, 6, 19))

    assert summary.as_of_date == date(2026, 6, 22)
    assert summary.trades[0].trade_date == date(2026, 6, 22)
    assert [point.trade_date for point in summary.equity_curve] == [date(2026, 6, 22)]
    with Session(engine) as session:
        assert session.scalar(select(SimulationEquity).where(SimulationEquity.trade_date == date(2026, 6, 19))) is None


def test_run_simulation_workflow_uses_next_open_trade_date_when_requested_date_is_closed() -> None:
    engine = _engine()
    with Session(engine) as session:
        session.add(TradingCalendar(trade_date=date(2026, 6, 19), is_open=False, source="unit-test"))
        session.add(TradingCalendar(trade_date=date(2026, 6, 22), is_open=True, source="unit-test"))
        _seed_trade_plan(
            session,
            status="待触发",
            trigger_price=None,
            tracking_note="",
            target_trade_date=date(2026, 6, 22),
        )
        _add_daily(session, "000001", date(2026, 6, 22), 10.1, 10.8, 10.0, 10.5)
        session.commit()

    workflow = run_simulation_workflow(engine, date(2026, 6, 19))

    assert workflow.target_trade_date == date(2026, 6, 22)
    assert workflow.tracking[0].target_trade_date == date(2026, 6, 22)
    assert workflow.simulation.as_of_date == date(2026, 6, 22)
    assert workflow.simulation.positions[0].stock_code == "000001"


def test_load_latest_simulation_ignores_closed_calendar_equity_dates() -> None:
    engine = _engine()
    with Session(engine) as session:
        session.add(TradingCalendar(trade_date=date(2026, 6, 19), is_open=False, source="unit-test"))
        session.add(TradingCalendar(trade_date=date(2026, 6, 22), is_open=True, source="unit-test"))
        account = SimulationAccount(
            account_name="默认模拟账户",
            initial_cash=1000000,
            available_cash=1000000,
            frozen_cash=0,
            market_value=0,
            total_assets=1000000,
            total_profit=0,
            total_return=0,
            max_drawdown=0,
        )
        session.add(account)
        session.flush()
        session.add(
            SimulationEquity(
                account_id=account.id,
                trade_date=date(2026, 6, 19),
                available_cash=1000000,
                market_value=0,
                total_assets=1000000,
                daily_profit=0,
                daily_return=0,
                max_drawdown=0,
            )
        )
        session.add(
            SimulationEquity(
                account_id=account.id,
                trade_date=date(2026, 6, 22),
                available_cash=990000,
                market_value=20000,
                total_assets=1010000,
                daily_profit=10000,
                daily_return=0.01,
                max_drawdown=0,
            )
        )
        session.commit()

    summary = load_latest_simulation(engine)

    assert summary is not None
    assert summary.as_of_date == date(2026, 6, 22)
    assert [point.trade_date for point in summary.equity_curve] == [date(2026, 6, 22)]


def test_load_latest_simulation_refreshes_position_price_from_latest_daily() -> None:
    engine = _engine()
    trade_date = date(2026, 6, 22)
    with Session(engine) as session:
        plan = _seed_trade_plan(session, stock_code="300308", target_trade_date=trade_date)
        account = SimulationAccount(
            account_name="默认模拟账户",
            initial_cash=1000000,
            available_cash=700000,
            frozen_cash=0,
            market_value=271648,
            total_assets=971648,
            total_profit=-28352,
            total_return=-0.0284,
            max_drawdown=0.0284,
        )
        session.add(account)
        session.flush()
        session.add(
            SimulationPosition(
                account_id=account.id,
                trade_plan_id=plan.id,
                stock_code="300308",
                stock_name="中际旭创",
                sector_name="科技风格",
                strategy_type="趋势强势",
                buy_price=1367.78,
                current_price=1358.24,
                quantity=200,
                market_value=271648,
                cost_amount=273640.0,
                unrealized_profit=-1992.0,
                unrealized_return=-0.0073,
                stop_loss_price=1299.49,
                take_profit_price=1641.46,
                position_status="持仓中",
                buy_reason="目标交易日价格触达计划买入区间",
                sell_reason="",
            )
        )
        session.add(
            SimulationEquity(
                account_id=account.id,
                trade_date=trade_date,
                available_cash=700000,
                market_value=271648,
                total_assets=971648,
                daily_profit=-28352,
                daily_return=-0.0284,
                max_drawdown=0.0284,
            )
        )
        _add_daily(session, "300308", trade_date, 1367.78, 1388, 1358.24, 1382.33)
        session.commit()

    summary = load_latest_simulation(engine)

    assert summary is not None
    assert summary.as_of_date == trade_date
    assert summary.positions[0].current_price == 1382.33
    assert summary.positions[0].market_value == 276466.0
    assert summary.positions[0].unrealized_profit == 2826.0
    assert summary.account.market_value == 276466.0
    assert summary.account.total_assets == 976466.0


def test_load_latest_simulation_keeps_unsold_pending_positions_visible() -> None:
    engine = _engine()
    trade_date = date(2026, 6, 22)
    with Session(engine) as session:
        plan = _seed_trade_plan(session, stock_code="300308", target_trade_date=trade_date)
        account = SimulationAccount(
            account_name="默认模拟账户",
            initial_cash=1000000,
            available_cash=700000,
            frozen_cash=0,
            market_value=271648,
            total_assets=971648,
            total_profit=-28352,
            total_return=-0.0284,
            max_drawdown=0.0284,
        )
        session.add(account)
        session.flush()
        session.add(
            SimulationPosition(
                account_id=account.id,
                trade_plan_id=plan.id,
                stock_code="300308",
                stock_name="中际旭创",
                sector_name="科技风格",
                strategy_type="趋势强势",
                buy_price=1367.78,
                current_price=1358.24,
                quantity=200,
                market_value=271648,
                cost_amount=273640.0,
                unrealized_profit=-1992.0,
                unrealized_return=-0.0073,
                stop_loss_price=1299.49,
                take_profit_price=1641.46,
                position_status="待卖出",
                buy_reason="目标交易日价格触达计划买入区间",
                sell_reason="等待下一次可成交卖出",
            )
        )
        session.add(
            SimulationEquity(
                account_id=account.id,
                trade_date=trade_date,
                available_cash=700000,
                market_value=271648,
                total_assets=971648,
                daily_profit=-28352,
                daily_return=-0.0284,
                max_drawdown=0.0284,
            )
        )
        session.commit()

    summary = load_latest_simulation(engine)

    assert summary is not None
    assert len(summary.positions) == 1
    assert summary.positions[0].position_status == "待卖出"
    assert summary.risk.position_count == 1


def test_load_latest_simulation_returns_trade_history_with_latest_first() -> None:
    engine = _engine()
    with Session(engine) as session:
        plan = _seed_trade_plan(session, stock_code="300308", target_trade_date=date(2026, 6, 22))
        account = SimulationAccount(
            account_name="默认模拟账户",
            initial_cash=1000000,
            available_cash=700000,
            frozen_cash=0,
            market_value=0,
            total_assets=700000,
            total_profit=-300000,
            total_return=-0.3,
            max_drawdown=0.3,
        )
        session.add(account)
        session.flush()
        for equity_date in [date(2026, 6, 19), date(2026, 6, 22)]:
            session.add(
                SimulationEquity(
                    account_id=account.id,
                    trade_date=equity_date,
                    available_cash=700000,
                    market_value=0,
                    total_assets=700000,
                    daily_profit=0,
                    daily_return=0,
                    max_drawdown=0.3,
                )
            )
        session.add(
            SimulationTrade(
                account_id=account.id,
                trade_plan_id=plan.id,
                stock_code="300308",
                stock_name="中际旭创",
                trade_date=date(2026, 6, 19),
                trade_time=datetime(2026, 6, 19, 10, 1, tzinfo=timezone.utc),
                trade_type="买入",
                price=1367.78,
                quantity=200,
                amount=273556,
                commission=82.0668,
                stamp_tax=0,
                transfer_fee=2.7356,
                total_fee=84.8024,
                net_amount=-273640.8024,
                cash_after=726359.1976,
                position_ratio_after=0.27,
                profit_loss=None,
                profit_loss_return=None,
                reason="目标交易日价格触达计划买入区间",
            )
        )
        session.add(
            SimulationTrade(
                account_id=account.id,
                trade_plan_id=plan.id,
                stock_code="300308",
                stock_name="中际旭创",
                trade_date=date(2026, 6, 22),
                trade_time=datetime(2026, 6, 22, 14, 55, tzinfo=timezone.utc),
                trade_type="卖出",
                price=1299.49,
                quantity=200,
                amount=259898,
                commission=77.9694,
                stamp_tax=129.949,
                transfer_fee=2.599,
                total_fee=210.5174,
                net_amount=259687.4826,
                cash_after=986046.6802,
                position_ratio_after=0,
                profit_loss=-13953.3198,
                profit_loss_return=-0.051,
                reason="跌破计划止损价，模拟全仓止损",
            )
        )
        session.commit()

    summary = load_latest_simulation(engine)

    assert summary is not None
    assert [trade.trade_date for trade in summary.trades] == [date(2026, 6, 22), date(2026, 6, 19)]
    assert [trade.trade_type for trade in summary.trades] == ["卖出", "买入"]


def test_load_latest_simulation_returns_none_without_account() -> None:
    engine = _engine()

    assert load_latest_simulation(engine) is None
