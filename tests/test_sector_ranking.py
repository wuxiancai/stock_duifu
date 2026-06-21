from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.db.models import LimitSnapshot, SectorDaily, metadata
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
        assert len(saved) == 10
        assert saved[0].sector_name == "机器人"
        assert saved[0].sector_score == 100
        assert float(saved[0].five_day_return) == 12.0


def test_generate_sector_rankings_is_idempotent_for_same_trade_date() -> None:
    engine = _engine()
    trade_date = date(2026, 6, 18)
    with Session(engine) as session:
        _seed_limit_up(session, trade_date)
        session.commit()

    generate_sector_rankings(engine, trade_date, FakeSectorProvider())
    generate_sector_rankings(engine, trade_date, FakeSectorProvider())

    with Session(engine) as session:
        assert session.query(SectorDaily).count() == 10


def test_sector_top_api_returns_latest_rankings() -> None:
    engine = _engine()
    trade_date = date(2026, 6, 18)
    with Session(engine) as session:
        _seed_limit_up(session, trade_date)
        session.commit()
    generate_sector_rankings(engine, trade_date, FakeSectorProvider())

    client = TestClient(create_app(database_url="sqlite+pysqlite://", engine=engine))
    response = client.get("/api/sectors/top")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trade_date"] == "2026-06-18"
    assert payload["items"][0]["sector_name"] == "机器人"
    assert payload["items"][0]["sector_score"] == 100
    assert payload["items"][0]["five_day_return"] == 12.0


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
