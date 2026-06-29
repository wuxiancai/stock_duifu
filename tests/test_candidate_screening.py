from datetime import date, timedelta
from typing import Optional

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.candidate.service import CandidateSectorMembershipProvider, _classify_sector_selection, _nine_turn_sequence, generate_candidate_stocks
from backend.app.db.models import CandidateStock, SectorDaily, StockBasic, StockDaily, metadata
from backend.app.main import create_app


class FakeMembershipProvider(CandidateSectorMembershipProvider):
    def sector_members(self, sector_names: list[str]) -> dict[str, list[str]]:
        return {"机器人": ["000001", "000002", "000003", "000004", "000005"]}


def _engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    return engine


def _seed_sector(session: Session, trade_date: date) -> None:
    ranks = [5, 4, 3, 2, 1]
    for index, rank in enumerate(ranks):
        session.add(
            SectorDaily(
                trade_date=trade_date - timedelta(days=4 - index),
                sector_name="机器人",
                rank_no=rank,
                daily_return=5.5,
                five_day_return=8.0,
                amount_change=30.0,
                limit_up_count=3,
                strong_stock_count=10,
                sector_score=100,
            )
        )


def _sector_daily(name: str = "电子", rank: int = 1) -> SectorDaily:
    return SectorDaily(
        trade_date=date(2026, 6, 25),
        sector_name=name,
        rank_no=rank,
        daily_return=1.0,
        five_day_return=5.0,
        amount_change=1.0,
        limit_up_count=1,
        strong_stock_count=10,
        sector_score=90,
    )


def test_nine_turn_sequence_returns_current_day_signal_only() -> None:
    sell7_closes = [10, 10, 10, 10, 11, 12, 13, 14, 15, 16, 17]
    no_signal_closes = [10, 10, 10, 10, 11, 12, 13, 14, 13, 12, 13]

    assert _nine_turn_sequence(sell7_closes) == ("sell", 7)
    assert _nine_turn_sequence(no_signal_closes) == ("", 0)


def test_sector_selection_excludes_single_day_spike() -> None:
    assert _classify_sector_selection(_sector_daily(rank=1), (1, 20, 30, 35, 40)) is None


def test_sector_selection_keeps_stable_second_rank_industry() -> None:
    selection = _classify_sector_selection(_sector_daily(rank=2), (2, 2, 2, 2, 2))

    assert selection is not None
    assert selection.category == "稳定强势"
    assert selection.quota == 3
    assert selection.persistence_bonus == 8


def test_sector_selection_allows_core_trend_more_quota() -> None:
    selection = _classify_sector_selection(_sector_daily(rank=1), (1, 1, 3, 2, 4))

    assert selection is not None
    assert selection.category == "核心主升"
    assert selection.quota == 5


def _seed_stock_basic(session: Session) -> None:
    stocks = [
        StockBasic(stock_code="000001", stock_name="趋势股份", market="主板", list_date=date(2020, 1, 1), source="unit-test"),
        StockBasic(stock_code="000002", stock_name="突破股份", market="主板", list_date=date(2020, 1, 1), source="unit-test"),
        StockBasic(stock_code="000003", stock_name="回踩股份", market="主板", list_date=date(2020, 1, 1), source="unit-test"),
        StockBasic(stock_code="000004", stock_name="ST风险", market="主板", list_date=date(2020, 1, 1), is_st=True, source="unit-test"),
        StockBasic(stock_code="000005", stock_name="一字板", market="主板", list_date=date(2020, 1, 1), source="unit-test"),
    ]
    session.add_all(stocks)


def _add_history(session: Session, stock_code: str, trade_date: date, closes: list[float], volumes: Optional[list[float]] = None) -> None:
    if volumes is None:
        volumes = [1000.0] * len(closes)
    start = trade_date - timedelta(days=len(closes) - 1)
    for index, close in enumerate(closes):
        day = start + timedelta(days=index)
        previous = closes[index - 1] if index else close
        high = max(close, previous) * 1.01
        low = min(close, previous) * 0.99
        open_price = previous
        session.add(
            StockDaily(
                stock_code=stock_code,
                trade_date=day,
                open=open_price,
                high=high,
                low=low,
                close=close,
                pre_close=previous,
                change=close - previous,
                pct_chg=(close / previous - 1) * 100 if previous else 0,
                volume=volumes[index],
                amount=800_000_000 + close * 10_000_000,
                turnover_rate=3.0,
                source="unit-test",
            )
        )


def _seed_stock_history(session: Session, trade_date: date) -> None:
    trend = [10 + i * 0.3 for i in range(20)]
    breakout = [10 + i * 0.1 for i in range(19)] + [12.5]
    pullback = [10, 11, 12, 13, 14, 15, 16, 18, 20, 22, 24, 26, 28, 30, 32, 31, 30, 29, 28.5, 28]
    weak = [10] * 20
    one_word = [10 + i * 0.5 for i in range(20)]

    _add_history(session, "000001", trade_date, trend)
    _add_history(session, "000002", trade_date, breakout, [1000.0] * 19 + [3000.0])
    _add_history(session, "000003", trade_date, pullback, [2000.0] * 10 + [1000.0] * 10)
    _add_history(session, "000004", trade_date, trend)
    _add_history(session, "000005", trade_date, one_word)

    latest = session.scalar(select(StockDaily).where(StockDaily.stock_code == "000005", StockDaily.trade_date == trade_date))
    assert latest is not None
    latest.open = latest.high = latest.low = latest.close


def _seed_candidate_fixture(engine) -> date:
    trade_date = date(2026, 6, 25)
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
    assert ("000002", "放量突破") in pairs
    assert all(candidate.stock_code not in {"000004", "000005"} for candidate in candidates)
    assert all("行业持续性" in candidate.reason for candidate in candidates)
    assert all("近5日排名" in candidate.reason for candidate in candidates)
    assert all("当前 机器人 第 1 名" in candidate.reason for candidate in candidates)
    assert all(candidate.nine_turn_signal in {"", "buy", "sell"} for candidate in candidates)

    with Session(engine) as session:
        saved = session.scalars(select(CandidateStock).order_by(CandidateStock.stock_code)).all()
        assert len(saved) == len(candidates)
        assert saved[0].sector_name == "机器人"
        assert saved[0].sector_rank == 1


def test_generate_candidate_stocks_is_idempotent_for_same_trade_date() -> None:
    engine = _engine()
    trade_date = _seed_candidate_fixture(engine)

    first = generate_candidate_stocks(engine, trade_date, FakeMembershipProvider())
    second = generate_candidate_stocks(engine, trade_date, FakeMembershipProvider())

    with Session(engine) as session:
        saved = session.scalars(select(CandidateStock)).all()
        assert len(saved) == len(second)
    assert [item.stock_code for item in first] == [item.stock_code for item in second]


def test_candidates_latest_api_returns_saved_candidates() -> None:
    engine = _engine()
    trade_date = _seed_candidate_fixture(engine)
    generate_candidate_stocks(engine, trade_date, FakeMembershipProvider())
    app = create_app(engine=engine)

    response = TestClient(app).get("/api/candidates/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trade_date"] == "2026-06-25"
    assert {item["strategy_type"] for item in payload["items"]} == {"放量突破"}
    assert "nine_turn_signal" in payload["items"][0]
    assert "nine_turn_count" in payload["items"][0]
    assert "nine_turn_score" in payload["items"][0]


def test_candidates_latest_api_does_not_turn_new_trend_watch_candidates_into_stock_pool() -> None:
    engine = _engine()
    trade_date = date(2026, 6, 29)
    with Session(engine) as session:
        session.add(
            CandidateStock(
                trade_date=trade_date,
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
        session.commit()
    app = create_app(engine=engine)

    response = TestClient(app).get("/api/candidates/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["stock_pool_rank"] is None


def test_candidates_latest_api_returns_empty_state_without_candidates() -> None:
    app = create_app(engine=_engine())

    response = TestClient(app).get("/api/candidates/latest")

    assert response.status_code == 200
    assert response.json() == {"trade_date": "", "items": []}
