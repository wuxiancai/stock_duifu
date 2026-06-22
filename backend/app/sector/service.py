from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from math import ceil
from typing import Iterable, Optional, Protocol

from sqlalchemy import delete, desc, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.app.db.models import LimitSnapshot, SectorDaily, TradingCalendar


@dataclass(frozen=True)
class SectorRawRecord:
    sector_code: str
    sector_name: str
    trade_date: date
    daily_return: float
    amount: float
    up_num: int
    down_num: int
    member_codes: list[str]
    source: str


@dataclass(frozen=True)
class SectorRankingResult:
    trade_date: date
    sector_name: str
    rank_no: int
    daily_return: float
    five_day_return: float
    amount_change: float
    limit_up_count: int
    strong_stock_count: int
    sector_score: int
    rank_history: list["SectorRankHistoryItem"] = field(default_factory=list)

    @property
    def three_day_return(self) -> float:
        return self.five_day_return


@dataclass(frozen=True)
class SectorRankHistoryItem:
    trade_date: date
    rank_no: Optional[int]


class SectorDataProvider(Protocol):
    source: str

    def fetch_sector_window(self, trade_date: date, lookback_days: int = 5) -> list[SectorRawRecord]:
        ...


def generate_sector_rankings(
    engine: Engine,
    trade_date: date,
    provider: SectorDataProvider,
    top_n: int = 10,
) -> list[SectorRankingResult]:
    raw_records = provider.fetch_sector_window(trade_date=trade_date, lookback_days=5)
    with Session(engine) as session:
        rankings = calculate_sector_rankings(session, raw_records, trade_date, top_n=top_n)
        session.execute(delete(SectorDaily).where(SectorDaily.trade_date == trade_date))
        session.flush()
        for ranking in rankings:
            session.add(
                SectorDaily(
                    trade_date=ranking.trade_date,
                    sector_name=ranking.sector_name,
                    rank_no=ranking.rank_no,
                    daily_return=ranking.daily_return,
                    five_day_return=ranking.five_day_return,
                    amount_change=ranking.amount_change,
                    limit_up_count=ranking.limit_up_count,
                    strong_stock_count=ranking.strong_stock_count,
                    sector_score=ranking.sector_score,
                )
            )
        session.commit()
        return rankings[:top_n]


def calculate_sector_rankings(
    session: Session,
    raw_records: Iterable[SectorRawRecord],
    trade_date: date,
    top_n: int = 10,
) -> list[SectorRankingResult]:
    by_sector: dict[str, list[SectorRawRecord]] = {}
    for record in raw_records:
        by_sector.setdefault(record.sector_code, []).append(record)

    candidates = []
    for records in by_sector.values():
        ordered = sorted(records, key=lambda item: item.trade_date)
        today = next((record for record in ordered if record.trade_date == trade_date), None)
        if today is None:
            continue
        recent = [record for record in ordered if record.trade_date <= trade_date][-5:]
        previous = [record for record in ordered if record.trade_date < trade_date][-5:]
        previous_amount_avg = (
            sum(record.amount for record in previous) / len(previous)
            if previous
            else None
        )
        amount_change = (
            (today.amount - previous_amount_avg) / previous_amount_avg * 100
            if previous_amount_avg
            else 0.0
        )
        candidates.append(
            {
                "record": today,
                "five_day_return": sum(record.daily_return for record in recent),
                "amount_change": amount_change,
                "limit_up_count": _limit_up_count(session, trade_date, today.member_codes),
                "strong_stock_count": int(today.up_num),
            }
        )

    if not candidates:
        return []

    daily_winners = _top_codes(
        candidates,
        key=lambda item: item["record"].daily_return,
        size=max(1, ceil(len(candidates) * 0.1)),
    )
    five_day_winners = _top_codes(
        candidates,
        key=lambda item: item["five_day_return"],
        size=max(1, ceil(len(candidates) * 0.2)),
    )

    scored = []
    for item in candidates:
        record = item["record"]
        score = 0
        if record.sector_code in daily_winners:
            score += 20
        if record.sector_code in five_day_winners:
            score += 20
        if item["amount_change"] > 0:
            score += 20
        if item["limit_up_count"] >= 2:
            score += 20
        if item["strong_stock_count"] >= 5:
            score += 20
        scored.append((score, item))

    ranked = sorted(
        scored,
        key=lambda pair: (
            pair[0],
            pair[1]["record"].daily_return,
            pair[1]["five_day_return"],
            pair[1]["amount_change"],
        ),
        reverse=True,
    )

    return [
        SectorRankingResult(
            trade_date=trade_date,
            sector_name=item["record"].sector_name,
            rank_no=index + 1,
            daily_return=item["record"].daily_return,
            five_day_return=item["five_day_return"],
            amount_change=item["amount_change"],
            limit_up_count=item["limit_up_count"],
            strong_stock_count=item["strong_stock_count"],
            sector_score=score,
        )
        for index, (score, item) in enumerate(ranked)
    ]


def load_latest_sector_rankings(engine: Engine) -> Optional[tuple[date, list[SectorRankingResult]]]:
    with Session(engine) as session:
        latest_date = session.scalar(select(func.max(SectorDaily.trade_date)))
        if latest_date is None:
            return None
        return _load_sector_rankings_for_date(session, latest_date)


def load_sector_rankings_by_date(engine: Engine, trade_date: date) -> Optional[tuple[date, list[SectorRankingResult]]]:
    with Session(engine) as session:
        return _load_sector_rankings_for_date(session, trade_date)


def _load_sector_rankings_for_date(
    session: Session,
    trade_date: date,
    limit: int = 10,
) -> Optional[tuple[date, list[SectorRankingResult]]]:
    records = session.scalars(
        select(SectorDaily)
        .where(SectorDaily.trade_date == trade_date)
        .order_by(SectorDaily.rank_no)
        .limit(limit)
    ).all()
    if not records:
        return None
    rank_history = _rank_history_by_sector(session, trade_date, [record.sector_name for record in records])
    return (
        trade_date,
        [
            SectorRankingResult(
                trade_date=record.trade_date,
                sector_name=record.sector_name,
                rank_no=record.rank_no,
                daily_return=_number(record.daily_return),
                five_day_return=_number(record.five_day_return),
                amount_change=_number(record.amount_change),
                limit_up_count=record.limit_up_count,
                strong_stock_count=record.strong_stock_count,
                sector_score=record.sector_score,
                rank_history=rank_history.get(record.sector_name, []),
            )
            for record in records
        ],
    )


def _rank_history_by_sector(
    session: Session,
    trade_date: date,
    sector_names: list[str],
    days: int = 5,
) -> dict[str, list[SectorRankHistoryItem]]:
    if not sector_names:
        return {}

    has_calendar = bool(session.scalar(select(func.count()).select_from(TradingCalendar)))
    history_dates_query = (
        select(SectorDaily.trade_date)
        .where(SectorDaily.trade_date <= trade_date)
        .distinct()
        .order_by(desc(SectorDaily.trade_date))
        .limit(days)
    )
    if has_calendar:
        history_dates_query = (
            history_dates_query
            .join(TradingCalendar, TradingCalendar.trade_date == SectorDaily.trade_date)
            .where(TradingCalendar.is_open.is_(True))
        )
    history_dates = session.scalars(history_dates_query).all()
    if not history_dates:
        return {sector_name: [] for sector_name in sector_names}

    history_records = session.scalars(
        select(SectorDaily).where(
            SectorDaily.trade_date.in_(history_dates),
            SectorDaily.sector_name.in_(sector_names),
        )
    ).all()
    rank_by_key = {
        (record.sector_name, record.trade_date): record.rank_no
        for record in history_records
    }

    return {
        sector_name: [
            SectorRankHistoryItem(
                trade_date=history_date,
                rank_no=rank_by_key.get((sector_name, history_date)),
            )
            for history_date in history_dates
        ]
        for sector_name in sector_names
    }


def _top_codes(candidates: list[dict], key, size: int) -> set[str]:
    return {
        item["record"].sector_code
        for item in sorted(candidates, key=key, reverse=True)[:size]
    }


def _limit_up_count(session: Session, trade_date: date, member_codes: list[str]) -> int:
    if not member_codes:
        return 0
    normalized = [code.split(".")[0].zfill(6) for code in member_codes]
    return int(
        session.scalar(
            select(func.count())
            .select_from(LimitSnapshot)
            .where(
                LimitSnapshot.trade_date == trade_date,
                LimitSnapshot.limit_status == "limit_up",
                LimitSnapshot.stock_code.in_(normalized),
            )
        )
        or 0
    )


def _number(value) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return float(value or 0)
