from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.data.types import StockDailyRecord
from backend.app.db.models import (
    CandidateStock,
    MarketDaily,
    SimulationAccount,
    SimulationPosition,
    SimulationTrade,
    StockDaily,
    TradePlan,
    TradeReview,
    TradingCalendar,
    metadata,
)
from backend.app.main import create_app
import backend.app.main as app_main
from backend.app.trade.service import (
    generate_trade_plans,
    generate_trade_reviews,
    load_latest_trade_reviews,
    retarget_closed_trade_plans,
    track_trade_plans,
)


def _engine():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    return engine


def _engine_with_foreign_keys():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

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


def test_generate_trade_plans_fallback_target_skips_weekend_when_future_calendar_missing() -> None:
    engine = _engine()
    plan_date = date(2026, 6, 26)
    with Session(engine) as session:
        session.add(
            MarketDaily(
                trade_date=plan_date,
                market_score=45,
                market_status="弱势",
                up_count=1600,
                down_count=3300,
                limit_up_count=28,
                limit_down_count=12,
                total_amount=900000000000,
                suggestion="弱势市场只做低仓位条件计划",
            )
        )
        _seed_candidates(session, plan_date)
        _seed_histories(session, plan_date)
        session.commit()

    plans = generate_trade_plans(engine, plan_date)

    assert plans
    assert all(plan.target_trade_date == date(2026, 6, 29) for plan in plans)


def test_generate_trade_plans_is_idempotent_for_same_plan_date() -> None:
    engine = _engine()
    plan_date = _seed_fixture(engine)

    first = generate_trade_plans(engine, plan_date)
    generate_trade_plans(engine, plan_date)

    with Session(engine) as session:
        assert session.query(TradePlan).count() == len(first)


def test_generate_trade_plans_expires_previous_untriggered_plans_before_creating_next_day_plans() -> None:
    engine = _engine()
    first_plan_date = _seed_fixture(engine)
    generate_trade_plans(engine, first_plan_date)
    next_plan_date = date(2026, 6, 19)
    next_target_date = date(2026, 6, 22)
    with Session(engine) as session:
        triggered_plan = session.scalar(select(TradePlan).where(TradePlan.stock_code == "000001"))
        triggered_plan.status = "已触发"
        triggered_plan.trigger_price = float(triggered_plan.buy_price_low)
        triggered_plan.tracking_note = "目标交易日价格触达计划买入区间"
        session.add(
            MarketDaily(
                trade_date=next_plan_date,
                market_score=80,
                market_status="强势",
                up_count=3200,
                down_count=1600,
                limit_up_count=90,
                limit_down_count=2,
                total_amount=1500000000000,
                suggestion="市场强势，可以正常交易",
            )
        )
        session.add(TradingCalendar(trade_date=next_target_date, is_open=True, source="unit-test"))
        _seed_candidates(session, next_plan_date)
        session.commit()

    generate_trade_plans(engine, next_plan_date)

    with Session(engine) as session:
        expired = session.scalars(
            select(TradePlan).where(
                TradePlan.plan_date == first_plan_date,
                TradePlan.target_trade_date == next_plan_date,
            )
        ).all()
        latest = session.scalars(
            select(TradePlan).where(
                TradePlan.plan_date == next_plan_date,
                TradePlan.target_trade_date == next_target_date,
            )
        ).all()

        assert expired
        expired_by_code = {plan.stock_code: plan for plan in expired}
        assert expired_by_code["000001"].status == "已触发"
        assert expired_by_code["000001"].tracking_note == "目标交易日价格触达计划买入区间"
        assert expired_by_code["000002"].status == "未触发"
        assert "目标交易日结束未触发" in expired_by_code["000002"].tracking_note
        assert latest
        assert all(plan.status == "待触发" for plan in latest)


def test_regenerating_trade_plans_preserves_simulation_history() -> None:
    engine = _engine_with_foreign_keys()
    plan_date = _seed_fixture(engine)
    generate_trade_plans(engine, plan_date)
    with Session(engine) as session:
        plan = session.scalar(select(TradePlan).where(TradePlan.stock_code == "000001"))
        account = SimulationAccount(
            account_name="默认模拟账户",
            initial_cash=1000000,
            available_cash=726359.1976,
            frozen_cash=0,
            market_value=276466,
            total_assets=1002825.1976,
            total_profit=2825.1976,
            total_return=0.0028,
            max_drawdown=0,
        )
        session.add(account)
        session.flush()
        session.add(
            SimulationPosition(
                account_id=account.id,
                trade_plan_id=plan.id,
                stock_code=plan.stock_code,
                stock_name=plan.stock_name,
                sector_name=plan.sector_name,
                strategy_type=plan.strategy_type,
                buy_price=1367.78,
                current_price=1382.33,
                quantity=200,
                market_value=276466,
                cost_amount=273640.8024,
                unrealized_profit=2825.1976,
                unrealized_return=0.0103,
                stop_loss_price=1299.49,
                take_profit_price=1641.46,
                position_status="持仓中",
                buy_reason="目标交易日价格触达计划买入区间",
                sell_reason="",
            )
        )
        session.add(
            SimulationTrade(
                account_id=account.id,
                trade_plan_id=plan.id,
                stock_code=plan.stock_code,
                stock_name=plan.stock_name,
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
        session.commit()

    generate_trade_plans(engine, plan_date)

    with Session(engine) as session:
        assert session.query(SimulationPosition).count() == 1
        assert session.query(SimulationTrade).count() == 1
        position = session.scalar(select(SimulationPosition))
        assert session.get(TradePlan, position.trade_plan_id) is not None


def test_generate_trade_plans_skips_risk_market() -> None:
    engine = _engine()
    plan_date = _seed_fixture(engine, market_status="风险")

    assert generate_trade_plans(engine, plan_date) == []

    with Session(engine) as session:
        assert session.query(TradePlan).count() == 0


def test_generate_trade_plans_does_not_fallback_to_new_trend_watch_candidates_without_stock_pool() -> None:
    engine = _engine()
    plan_date = date(2026, 6, 29)
    with Session(engine) as session:
        session.add(
            MarketDaily(
                trade_date=plan_date,
                market_score=65,
                market_status="中性",
                up_count=2000,
                down_count=1800,
                limit_up_count=45,
                limit_down_count=5,
                total_amount=1_000_000_000_000,
                suggestion="轻仓参与强势板块",
            )
        )
        session.add(TradingCalendar(trade_date=date(2026, 6, 30), is_open=True, source="unit-test"))
        session.add(
            CandidateStock(
                trade_date=plan_date,
                stock_code="603259",
                stock_name="药明康德",
                sector_name="医药生物",
                sector_rank=2,
                sector_category="趋势观察",
                stock_pool_rank=None,
                strategy_type="趋势强势",
                stock_score=104,
                sector_score=80,
                nine_turn_signal="sell",
                nine_turn_count=9,
                nine_turn_score=2,
                close_price=126.17,
                amount=12_743_790_053,
                reason="行业持续性：趋势观察，近5日排名 2/27/6/5/1，均值 8.2，Top10 出现 4 天",
                risk_note="趋势票避免高开追涨",
            )
        )
        for offset in range(25):
            _add_daily(session, "603259", plan_date - timedelta(days=24 - offset), 100 + offset * 1.1)
        session.commit()

    plans = generate_trade_plans(engine, plan_date)

    assert plans == []


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
    assert all("id" in item for item in payload["items"])
    assert all("tracking_note" in item for item in payload["items"])


def test_trade_plans_latest_api_falls_back_to_latest_available_quote_before_target() -> None:
    engine = _engine()
    plan_date = _seed_fixture(engine)
    generate_trade_plans(engine, plan_date)
    with Session(engine) as session:
        for plan in session.scalars(select(TradePlan)).all():
            plan.target_trade_date = date(2026, 6, 23)
        session.add(TradingCalendar(trade_date=date(2026, 6, 23), is_open=True, source="unit-test"))
        session.add(
            StockDaily(
                stock_code="000001",
                trade_date=date(2026, 6, 22),
                open=13.5,
                high=14.0,
                low=13.0,
                close=13.82,
                pre_close=13.6,
                change=0.22,
                pct_chg=1.62,
                volume=1000,
                amount=1000000000,
                turnover_rate=3.0,
                source="unit-test",
            )
        )
        session.commit()

    client = TestClient(create_app(database_url="sqlite+pysqlite://", engine=engine))
    response = client.get("/api/trade-plans/latest")

    assert response.status_code == 200
    row = next(item for item in response.json()["items"] if item["stock_code"] == "000001")
    assert row["target_trade_date"] == "2026-06-23"
    assert row["current_price"] == 13.82
    assert row["pct_chg"] == 1.62


def test_trade_plans_latest_api_returns_empty_state_without_plans() -> None:
    engine = _engine()
    client = TestClient(create_app(database_url="sqlite+pysqlite://", engine=engine))

    response = client.get("/api/trade-plans/latest")

    assert response.status_code == 200
    assert response.json() == {"plan_date": "", "target_trade_date": "", "items": []}


def test_prd_trade_plan_api_returns_plans_by_date_and_detail_reason() -> None:
    engine = _engine()
    plan_date = _seed_fixture(engine)
    generate_trade_plans(engine, plan_date)
    with Session(engine) as session:
        plan_id = session.scalar(select(TradePlan.id).where(TradePlan.stock_code == "000001"))

    client = TestClient(create_app(database_url="sqlite+pysqlite://", engine=engine))

    list_response = client.get("/api/trade-plans?date=2026-06-19")
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["target_trade_date"] == "2026-06-19"
    assert {item["stock_code"] for item in list_payload["items"]} == {"000001", "000002"}

    detail_response = client.get(f"/api/trade-plans/{plan_id}")
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["stock_code"] == "000001"
    assert detail_payload["selection_reason"] == "板块排名 Top 10"
    assert detail_payload["key_indicators"]["ma5"] > detail_payload["key_indicators"]["ma20"]
    assert detail_payload["key_indicators"]["atr14"] > 0


def test_track_trade_plans_marks_triggered_from_target_day_daily_data() -> None:
    engine = _engine()
    plan_date = _seed_fixture(engine)
    generate_trade_plans(engine, plan_date)
    with Session(engine) as session:
        plan = session.scalar(select(TradePlan).where(TradePlan.stock_code == "000001"))
        trigger_price = max(float(plan.buy_price_low), float(plan.stop_loss_price) + 0.01)
        session.add(
            StockDaily(
                stock_code="000001",
                trade_date=date(2026, 6, 19),
                open=trigger_price,
                high=float(plan.buy_price_high),
                low=trigger_price,
                close=float(plan.buy_price_high),
                pre_close=trigger_price,
                change=1.0,
                pct_chg=3.0,
                volume=1000,
                amount=1000000000,
                turnover_rate=3.0,
                source="unit-test",
            )
        )
        session.commit()

    results = track_trade_plans(engine, date(2026, 6, 19))

    assert len(results) == 2
    triggered = next(item for item in results if item.stock_code == "000001")
    assert triggered.status == "已触发"
    assert triggered.trigger_price is not None
    with Session(engine) as session:
        saved = session.scalar(select(TradePlan).where(TradePlan.stock_code == "000001"))
        assert saved.status == "已触发"
        assert saved.tracking_note == "目标交易日价格触达计划买入区间"


def test_track_realtime_trade_plans_api_backfills_quotes_and_returns_current_price(monkeypatch) -> None:
    engine = _engine()
    plan_date = _seed_fixture(engine)
    generate_trade_plans(engine, plan_date)
    with Session(engine) as session:
        plans = session.scalars(select(TradePlan).order_by(TradePlan.stock_code)).all()
        rows = [
            StockDailyRecord(
                stock_code=plan.stock_code,
                trade_date=date(2026, 6, 19),
                open=float(plan.buy_price_low),
                high=float(plan.buy_price_high),
                low=float(plan.buy_price_low),
                close=float(plan.buy_price_high),
                pre_close=float(plan.buy_price_low),
                change=float(plan.buy_price_high) - float(plan.buy_price_low),
                pct_chg=3.0,
                volume=1000,
                amount=1000000000,
                turnover_rate=3.0,
                source="unit-test-realtime",
            )
            for plan in plans
        ]

    class FakeRealtimeProvider:
        name = "unit-test-realtime"

        def fetch_realtime_stock_daily(self, stock_codes, trade_date):
            wanted = set(stock_codes)
            return [row for row in rows if row.stock_code in wanted and row.trade_date == trade_date]

    monkeypatch.setattr(app_main, "_realtime_quote_provider", lambda: FakeRealtimeProvider())
    client = TestClient(create_app(database_url="sqlite+pysqlite://", engine=engine))

    response = client.post(
        "/api/trade-plans/track-realtime",
        json={"target_trade_date": "2026-06-19", "allow_date_mismatch": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["realtime"]["fetched_stock_daily_rows"] == len(plans)
    assert all(item["current_price"] is not None for item in payload["items"])
    assert any(item["status"] == "已触发" for item in payload["items"])

    latest = client.get("/api/trade-plans/latest")

    assert latest.status_code == 200
    assert all(item["current_price"] is not None for item in latest.json()["items"])
    assert all(item["pct_chg"] is not None for item in latest.json()["items"])


def test_track_trade_plans_triggers_when_gap_up_later_pulls_back_into_buy_range() -> None:
    engine = _engine()
    plan_date = _seed_fixture(engine)
    generate_trade_plans(engine, plan_date)
    with Session(engine) as session:
        plan = session.scalar(select(TradePlan).where(TradePlan.stock_code == "000001"))
        session.add(
            StockDaily(
                stock_code="000001",
                trade_date=date(2026, 6, 19),
                open=float(plan.buy_price_high) * 1.05,
                high=float(plan.buy_price_high) * 1.06,
                low=float(plan.buy_price_high),
                close=float(plan.buy_price_high) * 1.04,
                pre_close=float(plan.buy_price_low),
                change=1.0,
                pct_chg=5.0,
                volume=1000,
                amount=1000000000,
                turnover_rate=3.0,
                source="unit-test-realtime",
            )
        )
        session.commit()

    results = track_trade_plans(engine, date(2026, 6, 19))

    item = next(row for row in results if row.stock_code == "000001")
    assert item.status == "已触发"


def test_track_trade_plans_cancels_gap_up_that_never_pulls_back_into_buy_range() -> None:
    engine = _engine()
    plan_date = _seed_fixture(engine)
    generate_trade_plans(engine, plan_date)
    with Session(engine) as session:
        plan = session.scalar(select(TradePlan).where(TradePlan.stock_code == "000001"))
        price = float(plan.buy_price_high) * 1.05
        session.add(
            StockDaily(
                stock_code="000001",
                trade_date=date(2026, 6, 19),
                open=price,
                high=price * 1.01,
                low=price,
                close=price,
                pre_close=float(plan.buy_price_low),
                change=1.0,
                pct_chg=5.0,
                volume=1000,
                amount=1000000000,
                turnover_rate=3.0,
                source="unit-test-realtime",
            )
        )
        session.commit()

    results = track_trade_plans(engine, date(2026, 6, 19))

    item = next(row for row in results if row.stock_code == "000001")
    assert item.status == "取消"
    assert "盘中未回落触达买入区间" in item.tracking_note


def test_track_trade_plans_triggers_when_stop_break_later_recovers_into_buy_range() -> None:
    engine = _engine()
    plan_date = _seed_fixture(engine)
    generate_trade_plans(engine, plan_date)
    with Session(engine) as session:
        plan = session.scalar(select(TradePlan).where(TradePlan.stock_code == "000001"))
        session.add(
            StockDaily(
                stock_code="000001",
                trade_date=date(2026, 6, 19),
                open=float(plan.stop_loss_price) * 0.99,
                high=float(plan.buy_price_low),
                low=float(plan.stop_loss_price) * 0.98,
                close=float(plan.buy_price_low),
                pre_close=float(plan.buy_price_low),
                change=0.0,
                pct_chg=0.0,
                volume=1000,
                amount=1000000000,
                turnover_rate=3.0,
                source="unit-test-realtime",
            )
        )
        session.commit()

    results = track_trade_plans(engine, date(2026, 6, 19))

    item = next(row for row in results if row.stock_code == "000001")
    assert item.status == "已触发"


def test_track_trade_plans_cancels_when_price_remains_below_stop_without_recovery() -> None:
    engine = _engine()
    plan_date = _seed_fixture(engine)
    generate_trade_plans(engine, plan_date)
    with Session(engine) as session:
        plan = session.scalar(select(TradePlan).where(TradePlan.stock_code == "000001"))
        price = float(plan.stop_loss_price) * 0.99
        session.add(
            StockDaily(
                stock_code="000001",
                trade_date=date(2026, 6, 19),
                open=price,
                high=price,
                low=price * 0.99,
                close=price,
                pre_close=float(plan.buy_price_low),
                change=-1.0,
                pct_chg=-5.0,
                volume=1000,
                amount=1000000000,
                turnover_rate=3.0,
                source="unit-test-realtime",
            )
        )
        session.commit()

    results = track_trade_plans(engine, date(2026, 6, 19))

    item = next(row for row in results if row.stock_code == "000001")
    assert item.status == "取消"
    assert "仍低于计划止损价" in item.tracking_note


def test_track_trade_plans_can_mark_untriggered_after_close() -> None:
    engine = _engine()
    plan_date = _seed_fixture(engine)
    generate_trade_plans(engine, plan_date)
    with Session(engine) as session:
        plan = session.scalar(select(TradePlan).where(TradePlan.stock_code == "000001"))
        price = float(plan.buy_price_high) * 1.01
        session.add(
            StockDaily(
                stock_code="000001",
                trade_date=date(2026, 6, 19),
                open=price,
                high=price,
                low=price,
                close=price,
                pre_close=price,
                change=0.0,
                pct_chg=0.0,
                volume=1000,
                amount=1000000000,
                turnover_rate=3.0,
                source="unit-test",
            )
        )
        session.commit()

    results = track_trade_plans(engine, date(2026, 6, 19), mark_untriggered_at_close=True)

    item = next(row for row in results if row.stock_code == "000001")
    assert item.status == "未触发"


def test_track_trade_plans_reports_closed_target_date_without_daily_data() -> None:
    engine = _engine()
    plan_date = _seed_fixture(engine)
    generate_trade_plans(engine, plan_date)
    with Session(engine) as session:
        calendar = session.scalar(select(TradingCalendar).where(TradingCalendar.trade_date == date(2026, 6, 19)))
        calendar.is_open = False
        session.commit()

    results = track_trade_plans(engine, date(2026, 6, 19))

    assert len(results) == 2
    assert all(item.status == "待触发" for item in results)
    assert all("不是开市日" in item.tracking_note for item in results)


def test_retarget_closed_trade_plans_cancels_closed_target_and_generates_next_open_target() -> None:
    engine = _engine()
    plan_date = _seed_fixture(engine)
    generate_trade_plans(engine, plan_date)
    with Session(engine) as session:
        closed = session.scalar(select(TradingCalendar).where(TradingCalendar.trade_date == date(2026, 6, 19)))
        closed.is_open = False
        session.add(TradingCalendar(trade_date=date(2026, 6, 20), is_open=False, source="unit-test"))
        session.add(TradingCalendar(trade_date=date(2026, 6, 22), is_open=True, source="unit-test"))
        session.commit()

    result = retarget_closed_trade_plans(engine, date(2026, 6, 19))

    assert result.target_is_open is False
    assert result.new_target_trade_date == date(2026, 6, 22)
    assert result.plan_dates == [plan_date]
    assert result.closed_plan_count == 2
    assert result.generated_plan_count == 2
    assert {item.stock_code for item in result.items} == {"000001", "000002"}
    assert all(item.target_trade_date == date(2026, 6, 22) for item in result.items)

    with Session(engine) as session:
        old_plans = session.scalars(select(TradePlan).where(TradePlan.target_trade_date == date(2026, 6, 19))).all()
        new_plans = session.scalars(select(TradePlan).where(TradePlan.target_trade_date == date(2026, 6, 22))).all()
        assert len(old_plans) == 2
        assert len(new_plans) == 2
        assert all(plan.status == "取消" for plan in old_plans)
        assert all("2026-06-22" in plan.tracking_note for plan in old_plans)
        assert all(plan.status == "待触发" for plan in new_plans)


def test_retarget_closed_trade_plans_skips_open_target_date() -> None:
    engine = _engine()
    plan_date = _seed_fixture(engine)
    generate_trade_plans(engine, plan_date)

    result = retarget_closed_trade_plans(engine, date(2026, 6, 19))

    assert result.target_is_open is True
    assert result.new_target_trade_date is None
    assert result.generated_plan_count == 0
    assert result.skipped_reason == "目标交易日是开市日，无需顺延"
    with Session(engine) as session:
        assert session.query(TradePlan).count() == 2
        assert all(plan.status == "待触发" for plan in session.scalars(select(TradePlan)).all())


def test_trade_plan_status_api_updates_manual_status_and_note() -> None:
    engine = _engine()
    plan_date = _seed_fixture(engine)
    generate_trade_plans(engine, plan_date)
    with Session(engine) as session:
        plan_id = session.scalar(select(TradePlan.id).where(TradePlan.stock_code == "000001"))

    client = TestClient(create_app(database_url="sqlite+pysqlite://", engine=engine))
    response = client.patch(
        f"/api/trade-plans/{plan_id}/status",
        json={"status": "取消", "note": "板块退潮，手动取消"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "取消"
    assert payload["tracking_note"] == "板块退潮，手动取消"


def test_trade_plan_status_api_updates_attention_flag_without_changing_status() -> None:
    engine = _engine()
    plan_date = _seed_fixture(engine)
    generate_trade_plans(engine, plan_date)
    with Session(engine) as session:
        plan_id = session.scalar(select(TradePlan.id).where(TradePlan.stock_code == "000001"))

    client = TestClient(create_app(database_url="sqlite+pysqlite://", engine=engine))
    response = client.patch(
        f"/api/trade-plans/{plan_id}/status",
        json={"status": "待触发", "note": "重点关注", "is_watched": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "待触发"
    assert payload["is_watched"] is True
    with Session(engine) as session:
        saved = session.get(TradePlan, plan_id)
        assert saved.is_watched is True


def test_trade_plan_tracking_api_returns_updated_items() -> None:
    engine = _engine()
    plan_date = _seed_fixture(engine)
    generate_trade_plans(engine, plan_date)
    with Session(engine) as session:
        plan = session.scalar(select(TradePlan).where(TradePlan.stock_code == "000001"))
        trigger_price = max(float(plan.buy_price_low), float(plan.stop_loss_price) + 0.01)
        session.add(
            StockDaily(
                stock_code="000001",
                trade_date=date(2026, 6, 19),
                open=trigger_price,
                high=float(plan.buy_price_high),
                low=trigger_price,
                close=float(plan.buy_price_high),
                pre_close=trigger_price,
                change=1.0,
                pct_chg=3.0,
                volume=1000,
                amount=1000000000,
                turnover_rate=3.0,
                source="unit-test",
            )
        )
        session.commit()

    client = TestClient(create_app(database_url="sqlite+pysqlite://", engine=engine))
    response = client.post("/api/trade-plans/track", json={"target_trade_date": "2026-06-19"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["target_trade_date"] == "2026-06-19"
    assert any(item["status"] == "已触发" for item in payload["items"])


def _seed_review_target_day(engine) -> None:
    with Session(engine) as session:
        triggered = session.scalar(select(TradePlan).where(TradePlan.stock_code == "000001"))
        untriggered = session.scalar(select(TradePlan).where(TradePlan.stock_code == "000002"))
        trigger_price = max(float(triggered.buy_price_low), float(triggered.stop_loss_price) + 0.01)
        triggered.status = "已触发"
        triggered.trigger_price = trigger_price
        triggered.tracking_note = "目标交易日价格触达计划买入区间"
        untriggered.status = "未触发"
        untriggered.tracking_note = "收盘未触达计划买入区间"

        for offset, multiplier in enumerate([1.10, 1.12, 1.14, 1.16, 1.18]):
            close = trigger_price * multiplier
            session.add(
                StockDaily(
                    stock_code="000001",
                    trade_date=date(2026, 6, 19) + timedelta(days=offset),
                    open=trigger_price,
                    high=close * 1.01,
                    low=max(trigger_price * 0.99, float(triggered.stop_loss_price) + 0.01),
                    close=close,
                    pre_close=trigger_price,
                    change=close - trigger_price,
                    pct_chg=(multiplier - 1) * 100,
                    volume=1000,
                    amount=1000000000,
                    turnover_rate=3.0,
                    source="unit-test",
                )
            )
        session.add(
            StockDaily(
                stock_code="000002",
                trade_date=date(2026, 6, 19),
                open=float(untriggered.buy_price_high) * 1.01,
                high=float(untriggered.buy_price_high) * 1.01,
                low=float(untriggered.buy_price_high) * 1.01,
                close=float(untriggered.buy_price_high) * 1.01,
                pre_close=float(untriggered.buy_price_high),
                change=0.0,
                pct_chg=0.0,
                volume=1000,
                amount=1000000000,
                turnover_rate=3.0,
                source="unit-test",
            )
        )
        session.commit()


def test_generate_trade_reviews_calculates_returns_and_group_stats() -> None:
    engine = _engine()
    plan_date = _seed_fixture(engine)
    generate_trade_plans(engine, plan_date)
    _seed_review_target_day(engine)

    summary = generate_trade_reviews(engine, date(2026, 6, 19))

    assert summary.review_date == date(2026, 6, 19)
    assert summary.total_count == 2
    assert summary.triggered_count == 1
    assert summary.win_count == 1
    assert summary.win_rate == 1.0
    triggered = next(item for item in summary.items if item.stock_code == "000001")
    assert triggered.result == "盈利"
    assert triggered.day_return == 0.1
    assert triggered.t5_return == 0.18
    assert triggered.sector_name == "机器人"
    assert summary.strategy_stats[0].name == "趋势强势"

    generate_trade_reviews(engine, date(2026, 6, 19))
    with Session(engine) as session:
        assert session.query(TradeReview).count() == 2


def test_trade_review_api_generates_and_returns_latest_summary() -> None:
    engine = _engine()
    plan_date = _seed_fixture(engine)
    generate_trade_plans(engine, plan_date)
    _seed_review_target_day(engine)

    client = TestClient(create_app(database_url="sqlite+pysqlite://", engine=engine))
    response = client.post("/api/trade-reviews/generate", json={"trade_date": "2026-06-19"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["review_date"] == "2026-06-19"
    assert payload["triggered_count"] == 1
    assert payload["items"][0]["sector_name"] == "机器人"

    latest = client.get("/api/trade-reviews/latest")
    assert latest.status_code == 200
    assert latest.json()["win_rate"] == 1.0


def test_generate_trade_reviews_uses_next_open_date_when_requested_date_is_closed() -> None:
    engine = _engine()
    plan_date = _seed_fixture(engine)
    generate_trade_plans(engine, plan_date)
    with Session(engine) as session:
        calendar = session.scalar(select(TradingCalendar).where(TradingCalendar.trade_date == date(2026, 6, 19)))
        calendar.is_open = False
        session.add(TradingCalendar(trade_date=date(2026, 6, 22), is_open=True, source="unit-test"))
        triggered = session.scalar(select(TradePlan).where(TradePlan.stock_code == "000001"))
        triggered.target_trade_date = date(2026, 6, 22)
        triggered.status = "已触发"
        triggered.trigger_price = float(triggered.buy_price_low)
        triggered.tracking_note = "目标交易日价格触达计划买入区间"
        untriggered = session.scalar(select(TradePlan).where(TradePlan.stock_code == "000002"))
        untriggered.target_trade_date = date(2026, 6, 22)
        untriggered.status = "未触发"
        untriggered.tracking_note = "收盘未触达计划买入区间"
        _add_daily(session, "000001", date(2026, 6, 22), float(triggered.buy_price_low) * 1.05)
        _add_daily(session, "000002", date(2026, 6, 22), float(untriggered.buy_price_high) * 1.01)
        session.commit()

    summary = generate_trade_reviews(engine, date(2026, 6, 19))

    assert summary.review_date == date(2026, 6, 22)
    assert summary.total_count == 2
    with Session(engine) as session:
        assert session.scalar(select(TradeReview).where(TradeReview.trade_date == date(2026, 6, 19))) is None


def test_load_latest_trade_reviews_ignores_closed_calendar_dates() -> None:
    engine = _engine()
    plan_date = _seed_fixture(engine)
    generate_trade_plans(engine, plan_date)
    _seed_review_target_day(engine)
    generate_trade_reviews(engine, date(2026, 6, 19))
    with Session(engine) as session:
        calendar = session.scalar(select(TradingCalendar).where(TradingCalendar.trade_date == date(2026, 6, 19)))
        calendar.is_open = False
        session.add(TradingCalendar(trade_date=date(2026, 6, 22), is_open=True, source="unit-test"))
        plans = session.scalars(select(TradePlan)).all()
        for plan in plans:
            plan.target_trade_date = date(2026, 6, 22)
        session.commit()

    generate_trade_reviews(engine, date(2026, 6, 22))

    summary = load_latest_trade_reviews(engine)

    assert summary is not None
    assert summary.review_date == date(2026, 6, 22)


def test_prd_review_post_api_generates_review_records() -> None:
    engine = _engine()
    plan_date = _seed_fixture(engine)
    generate_trade_plans(engine, plan_date)
    _seed_review_target_day(engine)

    client = TestClient(create_app(database_url="sqlite+pysqlite://", engine=engine))
    response = client.post("/api/reviews", json={"trade_date": "2026-06-19"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["review_date"] == "2026-06-19"
    assert payload["total_count"] == 2
    with Session(engine) as session:
        assert session.query(TradeReview).count() == 2


def test_prd_review_api_returns_by_date_and_updates_manual_fields() -> None:
    engine = _engine()
    plan_date = _seed_fixture(engine)
    generate_trade_plans(engine, plan_date)
    _seed_review_target_day(engine)
    generate_trade_reviews(engine, date(2026, 6, 19))
    with Session(engine) as session:
        review_id = session.scalar(select(TradeReview.id).where(TradeReview.stock_code == "000001"))

    client = TestClient(create_app(database_url="sqlite+pysqlite://", engine=engine))
    response = client.get("/api/reviews?date=2026-06-19")

    assert response.status_code == 200
    payload = response.json()
    assert payload["review_date"] == "2026-06-19"
    assert payload["total_count"] == 2

    update_response = client.patch(
        f"/api/reviews/{review_id}",
        json={
            "result": "失败",
            "failure_reason": "板块退潮",
            "discipline_check": False,
            "note": "人工复盘：突破失败",
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["result"] == "失败"
    assert updated["failure_reason"] == "板块退潮"
    assert updated["discipline_check"] is False
    assert updated["note"] == "人工复盘：突破失败"
