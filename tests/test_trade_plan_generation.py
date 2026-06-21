from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.db.models import CandidateStock, MarketDaily, StockDaily, TradePlan, TradeReview, TradingCalendar, metadata
from backend.app.main import create_app
from backend.app.trade.service import (
    generate_trade_plans,
    generate_trade_reviews,
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
    assert all("id" in item for item in payload["items"])
    assert all("tracking_note" in item for item in payload["items"])


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
