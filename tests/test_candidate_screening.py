from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.candidate.service import CandidateSectorMembershipProvider, generate_candidate_stocks
from backend.app.db.models import CandidateStock, SectorDaily, StockBasic, StockDaily, metadata
from backend.app.main import create_app


def _engine():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    return engine


class FakeMembershipProvider(CandidateSectorMembershipProvider):
    def sector_members(self, sector_names: list[str]) -> dict[str, list[str]]:
        return {
            "机器人": ["000001", "000002", "000003", "000004", "000005"],
        }


def _seed_sector(session: Session, trade_date: date) -> None:
    session.add(
        SectorDaily(
            trade_date=trade_date,
            sector_name="机器人",
            rank_no=1,
            daily_return=5.5,
            five_day_return=8.0,
            amount_change=30.0,
            limit_up_count=3,
            strong_stock_count=10,
            sector_score=100,
        )
    )


def _seed_stock_basic(session: Session) -> None:
    basics = [
        ("000001", "趋势强势", date(2020, 1, 1), False),
        ("000002", "放量突破", date(2020, 1, 1), False),
        ("000003", "强势回踩", date(2020, 1, 1), False),
        ("000004", "ST过滤", date(2020, 1, 1), True),
        ("000005", "新股过滤", date(2026, 6, 1), False),
    ]
    for stock_code, name, list_date, is_st in basics:
        session.add(
            StockBasic(
                stock_code=stock_code,
                stock_name=name,
                market="SZ",
                list_date=list_date,
                is_st=is_st,
                status="active",
                source="unit-test",
            )
        )


def _seed_stock_history(session: Session, trade_date: date) -> None:
    start = trade_date - timedelta(days=24)
    for offset in range(25):
        day = start + timedelta(days=offset)
        _add_daily(session, "000001", day, 10 + offset * 0.15, 1200000000, pct_chg=3 if offset == 24 else 1)
        breakout_close = 10 + offset * 0.05
        if offset == 24:
            breakout_close = 13
        _add_daily(
            session,
            "000002",
            day,
            breakout_close,
            1800000000 if offset == 24 else 500000000,
            pct_chg=5 if offset == 24 else 0.5,
            volume=3000 if offset == 24 else 1000,
        )
        pullback_close = 10 + min(offset, 15) * 0.35
        if offset >= 20:
            pullback_close = 14.5
        if offset == 24:
            pullback_close = 14.2
        _add_daily(
            session,
            "000003",
            day,
            pullback_close,
            900000000,
            pct_chg=-1 if offset == 24 else 1,
            volume=700 if offset >= 20 else 1500,
        )
        _add_daily(session, "000004", day, 20 + offset * 0.2, 2000000000, pct_chg=3)
        _add_daily(session, "000005", day, 30 + offset * 0.2, 2000000000, pct_chg=3)


def _add_daily(
    session: Session,
    stock_code: str,
    trade_date: date,
    close: float,
    amount: float,
    pct_chg: float,
    volume: float = 1000,
) -> None:
    session.add(
        StockDaily(
            stock_code=stock_code,
            trade_date=trade_date,
            open=close * 0.98,
            high=close * 1.01,
            low=close * 0.97,
            close=close,
            pre_close=close / (1 + pct_chg / 100),
            change=close - close / (1 + pct_chg / 100),
            pct_chg=pct_chg,
            volume=volume,
            amount=amount,
            turnover_rate=3.0,
            source="unit-test",
        )
    )


def _seed_candidate_fixture(engine) -> date:
    trade_date = date(2026, 6, 18)
    with Session(engine) as session:
        _seed_sector(session, trade_date)
        _seed_stock_basic(session)
        _seed_stock_history(session, trade_date)
        session.commit()
    return trade_date


def test_generate_candidate_stocks_filters_and_persists_explainable_strategies() -> None:
    engine = _engine()
    trade_date = _seed_candidate_fixture(engine)

    candidates = generate_candidate_stocks(engine, trade_date, FakeMembershipProvider())

    pairs = {(candidate.stock_code, candidate.strategy_type) for candidate in candidates}
    assert ("000001", "趋势强势") in pairs
    assert ("000002", "放量突破") in pairs
    assert ("000003", "强势回踩") in pairs
    assert all(candidate.stock_code not in {"000004", "000005"} for candidate in candidates)
    assert all("板块排名 Top 10" in candidate.reason for candidate in candidates)

    with Session(engine) as session:
        saved = session.scalars(select(CandidateStock).order_by(CandidateStock.stock_code)).all()
        assert len(saved) == len(candidates)
        assert saved[0].sector_name == "机器人"
        assert saved[0].sector_rank == 1


def test_generate_candidate_stocks_is_idempotent_for_same_trade_date() -> None:
    engine = _engine()
    trade_date = _seed_candidate_fixture(engine)

    first = generate_candidate_stocks(engine, trade_date, FakeMembershipProvider())
    generate_candidate_stocks(engine, trade_date, FakeMembershipProvider())

    with Session(engine) as session:
        assert session.query(CandidateStock).count() == len(first)


def test_candidates_latest_api_returns_persisted_candidates() -> None:
    engine = _engine()
    trade_date = _seed_candidate_fixture(engine)
    generate_candidate_stocks(engine, trade_date, FakeMembershipProvider())

    client = TestClient(create_app(database_url="sqlite+pysqlite://", engine=engine))
    response = client.get("/api/candidates/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trade_date"] == "2026-06-18"
    assert {item["strategy_type"] for item in payload["items"]} == {
        "趋势强势",
        "放量突破",
        "强势回踩",
    }


def test_candidates_latest_api_returns_empty_state_without_candidates() -> None:
    engine = _engine()
    client = TestClient(create_app(database_url="sqlite+pysqlite://", engine=engine))

    response = client.get("/api/candidates/latest")

    assert response.status_code == 200
    assert response.json() == {"trade_date": "", "items": []}
