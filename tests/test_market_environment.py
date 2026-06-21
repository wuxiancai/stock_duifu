from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.db.models import IndexDaily, LimitSnapshot, MarketDaily, StockDaily, metadata
from backend.app.main import create_app
from backend.app.market.service import generate_market_environment


def _engine():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    return engine


def _seed_index_history(session: Session, trade_date: date) -> None:
    start = trade_date - timedelta(days=19)
    for offset in range(20):
        day = start + timedelta(days=offset)
        session.add(
            IndexDaily(
                index_code="000001.SH",
                trade_date=day,
                open=3000 + offset,
                high=3010 + offset,
                low=2990 + offset,
                close=3000 + offset,
                volume=1000,
                amount=100000000,
                source="unit-test",
            )
        )
        session.add(
            IndexDaily(
                index_code="399006.SZ",
                trade_date=day,
                open=2000 + offset,
                high=2010 + offset,
                low=1990 + offset,
                close=2000 + offset,
                volume=1000,
                amount=100000000,
                source="unit-test",
            )
        )


def _seed_market_width(session: Session, trade_date: date) -> None:
    previous_date = trade_date - timedelta(days=1)
    for idx in range(8):
        stock_code = f"0000{idx + 1:02d}"
        session.add(
            StockDaily(
                stock_code=stock_code,
                trade_date=previous_date,
                open=10,
                high=10.2,
                low=9.8,
                close=10,
                pre_close=10,
                change=0,
                pct_chg=0,
                volume=1000,
                amount=100000000,
                source="unit-test",
            )
        )
        pct_chg = 1.5 if idx < 5 else -1.2
        session.add(
            StockDaily(
                stock_code=stock_code,
                trade_date=trade_date,
                open=10,
                high=10.5,
                low=9.8,
                close=10 + pct_chg / 10,
                pre_close=10,
                change=pct_chg / 10,
                pct_chg=pct_chg,
                volume=2000,
                amount=150000000,
                source="unit-test",
            )
        )

    for idx in range(40):
        session.add(
            LimitSnapshot(
                trade_date=trade_date,
                stock_code=f"6{idx:05d}",
                stock_name=f"涨停{idx}",
                close_price=10,
                pct_chg=10,
                limit_status="limit_up",
                amount=10000000,
                source="unit-test",
            )
        )
    for idx in range(10):
        session.add(
            LimitSnapshot(
                trade_date=trade_date,
                stock_code=f"3{idx:05d}",
                stock_name=f"跌停{idx}",
                close_price=10,
                pct_chg=-10,
                limit_status="limit_down",
                amount=10000000,
                source="unit-test",
            )
        )


def _seed_limit_streak(session: Session, trade_date: date, stock_code: str = "688888", days: int = 3) -> None:
    for offset in range(days):
        day = trade_date - timedelta(days=offset)
        session.add(
            LimitSnapshot(
                trade_date=day,
                stock_code=stock_code,
                stock_name="连板股",
                close_price=10 + offset,
                pct_chg=10,
                limit_status="limit_up",
                amount=10000000,
                source="unit-test",
            )
        )


def test_generate_market_environment_scores_and_persists_real_metrics() -> None:
    engine = _engine()
    trade_date = date(2026, 6, 18)
    with Session(engine) as session:
        _seed_index_history(session, trade_date)
        _seed_market_width(session, trade_date)
        session.commit()

    result = generate_market_environment(engine, trade_date)

    assert result.trade_date == trade_date
    assert result.market_score == 85
    assert result.market_status == "强势"
    assert result.suggested_position == "80% - 100%"
    assert result.up_count == 5
    assert result.down_count == 3
    assert result.limit_up_count == 40
    assert result.limit_down_count == 10
    assert result.limit_up_height == 1
    assert result.total_amount == 1200000000
    assert "连板高度 1 板，未达到 3 板，+0" in result.suggestion

    with Session(engine) as session:
        saved = session.scalar(select(MarketDaily).where(MarketDaily.trade_date == trade_date))
        assert saved is not None
    assert saved.market_score == 85
    assert saved.market_status == "强势"


def test_generate_market_environment_counts_limit_up_height_in_score() -> None:
    engine = _engine()
    trade_date = date(2026, 6, 18)
    with Session(engine) as session:
        _seed_index_history(session, trade_date)
        _seed_market_width(session, trade_date)
        _seed_limit_streak(session, trade_date, days=3)
        session.commit()

    result = generate_market_environment(engine, trade_date)

    assert result.limit_up_height == 3
    assert result.market_score == 100
    assert "连板高度达到 3 板，+15" in result.suggestion

    with Session(engine) as session:
        saved = session.scalar(select(MarketDaily).where(MarketDaily.trade_date == trade_date))
        assert saved is not None
        assert saved.limit_up_height == 3


def test_generate_market_environment_is_idempotent_for_same_trade_date() -> None:
    engine = _engine()
    trade_date = date(2026, 6, 18)
    with Session(engine) as session:
        _seed_index_history(session, trade_date)
        _seed_market_width(session, trade_date)
        session.commit()

    generate_market_environment(engine, trade_date)
    generate_market_environment(engine, trade_date)

    with Session(engine) as session:
        assert session.query(MarketDaily).count() == 1


def test_market_latest_api_returns_persisted_environment() -> None:
    engine = _engine()
    trade_date = date(2026, 6, 18)
    with Session(engine) as session:
        _seed_index_history(session, trade_date)
        _seed_market_width(session, trade_date)
        session.commit()
    generate_market_environment(engine, trade_date)

    client = TestClient(create_app(database_url="sqlite+pysqlite://", engine=engine))
    response = client.get("/api/market/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trade_date"] == "2026-06-18"
    assert payload["market_score"] == 85
    assert payload["market_status"] == "强势"
    assert payload["suggested_position"] == "80% - 100%"
    assert payload["limit_up_height"] == 1


def test_prd_market_today_api_returns_latest_environment() -> None:
    engine = _engine()
    trade_date = date(2026, 6, 18)
    with Session(engine) as session:
        _seed_index_history(session, trade_date)
        _seed_market_width(session, trade_date)
        session.commit()
    generate_market_environment(engine, trade_date)

    client = TestClient(create_app(database_url="sqlite+pysqlite://", engine=engine))
    response = client.get("/api/market/today")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trade_date"] == "2026-06-18"
    assert payload["market_status"] == "强势"
    assert payload["suggested_position"] == "80% - 100%"
