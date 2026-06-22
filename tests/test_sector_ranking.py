from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.db.models import LimitSnapshot, SectorDaily, TradingCalendar, metadata
from backend.app.main import create_app
from backend.app.sector.service import SectorRawRecord, generate_sector_rankings


def _engine():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    return engine


class FakeSectorProvider:
    source = "unit-test"

    def fetch_sector_window(self, trade_date: date, lookback_days: int = 5) -> list[SectorRawRecord]:
        records: list[SectorRawRecord] = []
        names = ["机器人", "半导体"] + [f"板块{i}" for i in range(3, 13)]
        base_day = trade_date - timedelta(days=4)
        for idx, name in enumerate(names):
            for offset in range(5):
                day = base_day + timedelta(days=offset)
                daily_return = 8 - idx if offset == 4 else 1 + idx / 10
                amount = 1000 + idx * 10 + offset * (300 if idx == 0 else 20)
                up_num = 8 if idx == 0 else max(0, 6 - idx)
                records.append(
                    SectorRawRecord(
                        sector_code=f"BK{idx:04d}.DC",
                        sector_name=name,
                        trade_date=day,
                        daily_return=daily_return,
                        amount=amount,
                        up_num=up_num,
                        down_num=2,
                        member_codes=["000001", "000002", "000003"] if idx == 0 else [],
                        source=self.source,
                    )
                )
        return records


class DuplicateNameSectorProvider(FakeSectorProvider):
    def fetch_sector_window(self, trade_date: date, lookback_days: int = 5) -> list[SectorRawRecord]:
        records = super().fetch_sector_window(trade_date, lookback_days)
        base_day = trade_date - timedelta(days=4)
        for offset in range(5):
            day = base_day + timedelta(days=offset)
            records.append(
                SectorRawRecord(
                    sector_code="BK9999.DC",
                    sector_name="机器人",
                    trade_date=day,
                    daily_return=0.5,
                    amount=500,
                    up_num=1,
                    down_num=2,
                    member_codes=[],
                    source=self.source,
                )
            )
        return records


def _seed_limit_up(session: Session, trade_date: date) -> None:
    for stock_code in ["000001", "000002"]:
        session.add(
            LimitSnapshot(
                trade_date=trade_date,
                stock_code=stock_code,
                stock_name=stock_code,
                close_price=10,
                pct_chg=10,
                limit_status="limit_up",
                amount=10000000,
                source="unit-test",
            )
        )


def test_generate_sector_rankings_scores_top10_and_persists() -> None:
    engine = _engine()
    trade_date = date(2026, 6, 18)
    with Session(engine) as session:
        _seed_limit_up(session, trade_date)
        session.commit()

    rankings = generate_sector_rankings(engine, trade_date, FakeSectorProvider())

    assert len(rankings) == 10
    assert rankings[0].sector_name == "机器人"
    assert rankings[0].rank_no == 1
    assert rankings[0].sector_score == 100
    assert rankings[0].limit_up_count == 2
    assert rankings[0].strong_stock_count == 8
    assert rankings[0].amount_change > 0
    assert rankings[0].five_day_return == 12.0

    with Session(engine) as session:
        saved = session.scalars(select(SectorDaily).order_by(SectorDaily.rank_no)).all()
        assert len(saved) == 12
        assert saved[0].sector_name == "机器人"
        assert saved[0].sector_score == 100
        assert float(saved[0].five_day_return) == 12.0
        assert saved[-1].rank_no == 12


def test_generate_sector_rankings_is_idempotent_for_same_trade_date() -> None:
    engine = _engine()
    trade_date = date(2026, 6, 18)
    with Session(engine) as session:
        _seed_limit_up(session, trade_date)
        session.commit()

    generate_sector_rankings(engine, trade_date, FakeSectorProvider())
    generate_sector_rankings(engine, trade_date, FakeSectorProvider())

    with Session(engine) as session:
        assert session.query(SectorDaily).count() == 12


def test_generate_sector_rankings_deduplicates_sector_names_before_persisting() -> None:
    engine = _engine()
    trade_date = date(2026, 6, 18)
    with Session(engine) as session:
        _seed_limit_up(session, trade_date)
        session.commit()

    rankings = generate_sector_rankings(engine, trade_date, DuplicateNameSectorProvider())

    assert len(rankings) == 10
    with Session(engine) as session:
        saved = session.scalars(select(SectorDaily).order_by(SectorDaily.rank_no)).all()
        names = [item.sector_name for item in saved]
        assert len(names) == len(set(names))
        assert names.count("机器人") == 1
        assert [item.rank_no for item in saved] == list(range(1, len(saved) + 1))


def test_sector_top_api_returns_latest_rankings() -> None:
    engine = _engine()
    trade_date = date(2026, 6, 18)
    with Session(engine) as session:
        previous_date = trade_date - timedelta(days=1)
        _seed_limit_up(session, previous_date)
        _seed_limit_up(session, trade_date)
        session.commit()
    generate_sector_rankings(engine, previous_date, FakeSectorProvider())
    generate_sector_rankings(engine, trade_date, FakeSectorProvider())

    client = TestClient(create_app(database_url="sqlite+pysqlite://", engine=engine))
    response = client.get("/api/sectors/top")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trade_date"] == "2026-06-18"
    assert payload["items"][0]["sector_name"] == "机器人"
    assert payload["items"][0]["sector_score"] == 100
    assert payload["items"][0]["five_day_return"] == 12.0
    assert payload["items"][0]["rank_history"] == [
        {"trade_date": "2026-06-18", "rank_no": 1},
        {"trade_date": "2026-06-17", "rank_no": 1},
    ]
    assert len(payload["items"]) == 10


def test_sector_rank_history_keeps_ranks_outside_top10() -> None:
    engine = _engine()
    with Session(engine) as session:
        for day in [date(2026, 6, 22), date(2026, 6, 18)]:
            session.add(TradingCalendar(trade_date=day, is_open=True, source="unit-test"))
        for rank_no, sector_name in enumerate(
            ["钛白粉", "培育钻石", "铅锌", "小金属", "非金属材料III", "非金属材料II"] + [f"板块{idx}" for idx in range(7, 12)],
            start=1,
        ):
            session.add(
                SectorDaily(
                    trade_date=date(2026, 6, 22),
                    sector_name=sector_name,
                    rank_no=rank_no,
                    daily_return=1,
                    five_day_return=5,
                    amount_change=1000,
                    limit_up_count=0,
                    strong_stock_count=0,
                    sector_score=80,
                )
            )
        session.add(
            SectorDaily(
                trade_date=date(2026, 6, 18),
                sector_name="小金属",
                rank_no=11,
                daily_return=1,
                five_day_return=5,
                amount_change=1000,
                limit_up_count=0,
                strong_stock_count=0,
                sector_score=60,
            )
        )
        session.commit()

    client = TestClient(create_app(database_url="sqlite+pysqlite://", engine=engine))
    response = client.get("/api/sectors/top")

    assert response.status_code == 200
    row = next(item for item in response.json()["items"] if item["sector_name"] == "小金属")
    assert row["rank_history"] == [
        {"trade_date": "2026-06-22", "rank_no": 4},
        {"trade_date": "2026-06-18", "rank_no": 11},
    ]


def test_sector_rank_history_ignores_closed_calendar_dates() -> None:
    engine = _engine()
    with Session(engine) as session:
        for day, is_open in [
            (date(2026, 6, 22), True),
            (date(2026, 6, 21), False),
            (date(2026, 6, 20), False),
            (date(2026, 6, 19), False),
            (date(2026, 6, 18), True),
            (date(2026, 6, 17), True),
        ]:
            session.add(TradingCalendar(trade_date=day, is_open=is_open, source="unit-test"))
            session.add(
                SectorDaily(
                    trade_date=day,
                    sector_name="机器人",
                    rank_no=1,
                    daily_return=1,
                    five_day_return=5,
                    amount_change=1000,
                    limit_up_count=0,
                    strong_stock_count=0,
                    sector_score=80,
                )
            )
        session.add(
            SectorDaily(
                trade_date=date(2026, 6, 22),
                sector_name="半导体",
                rank_no=2,
                daily_return=1,
                five_day_return=5,
                amount_change=1000,
                limit_up_count=0,
                strong_stock_count=0,
                sector_score=79,
            )
        )
        session.commit()

    client = TestClient(create_app(database_url="sqlite+pysqlite://", engine=engine))
    response = client.get("/api/sectors/top")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trade_date"] == "2026-06-22"
    assert payload["items"][0]["rank_history"] == [
        {"trade_date": "2026-06-22", "rank_no": 1},
        {"trade_date": "2026-06-18", "rank_no": 1},
        {"trade_date": "2026-06-17", "rank_no": 1},
    ]


def test_sector_top_api_returns_empty_state_without_rankings() -> None:
    engine = _engine()
    client = TestClient(create_app(database_url="sqlite+pysqlite://", engine=engine))

    response = client.get("/api/sectors/top")

    assert response.status_code == 200
    assert response.json() == {"trade_date": "", "items": []}


def test_prd_sector_strong_api_returns_rankings_by_date() -> None:
    engine = _engine()
    trade_date = date(2026, 6, 18)
    with Session(engine) as session:
        _seed_limit_up(session, trade_date)
        session.commit()
    generate_sector_rankings(engine, trade_date, FakeSectorProvider())

    client = TestClient(create_app(database_url="sqlite+pysqlite://", engine=engine))
    response = client.get("/api/sectors/strong?date=2026-06-18")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trade_date"] == "2026-06-18"
    assert len(payload["items"]) == 10
    assert payload["items"][0]["sector_name"] == "机器人"
