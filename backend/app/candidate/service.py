from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional, Protocol

from sqlalchemy import delete, desc, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.app.db.models import CandidateStock, LimitSnapshot, SectorDaily, StockBasic, StockDaily


@dataclass(frozen=True)
class CandidateResult:
    trade_date: date
    stock_code: str
    stock_name: str
    sector_name: str
    sector_rank: int
    strategy_type: str
    stock_score: int
    sector_score: int
    close_price: float
    amount: float
    reason: str
    risk_note: str


class CandidateSectorMembershipProvider(Protocol):
    def sector_members(self, sector_names: list[str]) -> dict[str, list[str]]:
        ...


def generate_candidate_stocks(
    engine: Engine,
    trade_date: date,
    membership_provider: CandidateSectorMembershipProvider,
    limit: int = 50,
) -> list[CandidateResult]:
    with Session(engine) as session:
        candidates = calculate_candidate_stocks(session, trade_date, membership_provider, limit=limit)
        session.execute(delete(CandidateStock).where(CandidateStock.trade_date == trade_date))
        session.flush()
        for candidate in candidates:
            session.add(CandidateStock(**candidate.__dict__))
        session.commit()
        return candidates


def calculate_candidate_stocks(
    session: Session,
    trade_date: date,
    membership_provider: CandidateSectorMembershipProvider,
    limit: int = 50,
) -> list[CandidateResult]:
    sectors = session.scalars(
        select(SectorDaily)
        .where(SectorDaily.trade_date == trade_date)
        .order_by(SectorDaily.rank_no)
        .limit(10)
    ).all()
    if not sectors:
        return []
    sector_by_name = {sector.sector_name: sector for sector in sectors}
    membership = membership_provider.sector_members(list(sector_by_name.keys()))
    sector_by_stock: dict[str, SectorDaily] = {}
    for sector_name, codes in membership.items():
        sector = sector_by_name.get(sector_name)
        if sector is None:
            continue
        for code in codes:
            normalized = _normalize_code(code)
            current = sector_by_stock.get(normalized)
            if current is None or sector.rank_no < current.rank_no:
                sector_by_stock[normalized] = sector

    results: list[CandidateResult] = []
    for stock_code, sector in sector_by_stock.items():
        basic = session.scalar(select(StockBasic).where(StockBasic.stock_code == stock_code))
        if basic is None or not _passes_basic_filter(session, basic, trade_date):
            continue
        history = session.scalars(
            select(StockDaily)
            .where(StockDaily.stock_code == stock_code, StockDaily.trade_date <= trade_date)
            .order_by(StockDaily.trade_date)
        ).all()
        if len(history) < 20:
            continue
        if _is_one_word_limit_up(session, stock_code, trade_date, history[-1]):
            continue
        results.extend(_strategy_candidates(basic, sector, history, trade_date))

    return sorted(
        results,
        key=lambda item: (item.stock_score, item.sector_score, item.amount),
        reverse=True,
    )[:limit]


def load_latest_candidates(engine: Engine) -> Optional[tuple[date, list[CandidateResult]]]:
    with Session(engine) as session:
        latest_date = session.scalar(select(func.max(CandidateStock.trade_date)))
        if latest_date is None:
            return None
        records = session.scalars(
            select(CandidateStock)
            .where(CandidateStock.trade_date == latest_date)
            .order_by(desc(CandidateStock.stock_score), CandidateStock.stock_code)
        ).all()
        return (
            latest_date,
            [
                CandidateResult(
                    trade_date=record.trade_date,
                    stock_code=record.stock_code,
                    stock_name=record.stock_name,
                    sector_name=record.sector_name,
                    sector_rank=record.sector_rank,
                    strategy_type=record.strategy_type,
                    stock_score=record.stock_score,
                    sector_score=record.sector_score,
                    close_price=_number(record.close_price),
                    amount=_number(record.amount),
                    reason=record.reason,
                    risk_note=record.risk_note,
                )
                for record in records
            ],
        )


def _strategy_candidates(
    basic: StockBasic,
    sector: SectorDaily,
    history: list[StockDaily],
    trade_date: date,
) -> list[CandidateResult]:
    latest = history[-1]
    closes = [_number(row.close) for row in history]
    volumes = [_number(row.volume) for row in history]
    ma5 = _ma(closes, 5)
    ma10 = _ma(closes, 10)
    ma20 = _ma(closes, 20)
    last_close = closes[-1]
    amount = _number(latest.amount)
    twenty_day_return = (last_close / closes[-20] - 1) * 100 if closes[-20] else 0.0
    five_day_return = (last_close / closes[-5] - 1) * 100 if closes[-5] else 0.0
    previous_20_high = max(closes[-20:-1])
    avg_volume5 = sum(volumes[-6:-1]) / 5 if len(volumes) >= 6 else 0.0
    volume_ratio = volumes[-1] / avg_volume5 if avg_volume5 else 0.0

    common = {
        "trade_date": trade_date,
        "stock_code": basic.stock_code,
        "stock_name": basic.stock_name,
        "sector_name": sector.sector_name,
        "sector_rank": sector.rank_no,
        "sector_score": sector.sector_score,
        "close_price": last_close,
        "amount": amount,
    }
    candidates: list[CandidateResult] = []
    sector_note = f"板块排名 Top 10：{sector.sector_name} 第 {sector.rank_no} 名，板块评分 {sector.sector_score}"

    if (
        last_close > ma5 > ma10 > ma20
        and last_close / ma20 <= 1.25
        and twenty_day_return > 15
        and five_day_return > 3
        and amount >= 1_000_000_000
    ):
        candidates.append(
            CandidateResult(
                **common,
                strategy_type="趋势强势",
                stock_score=_score(70 + min(twenty_day_return, 30) + min(five_day_return, 10)),
                reason=(
                    f"{sector_note}；收盘价站上 MA5/MA10/MA20 且均线多头；"
                    f"20 日涨幅 {twenty_day_return:.2f}%、5 日涨幅 {five_day_return:.2f}%；"
                    f"成交额 {amount / 100000000:.2f} 亿"
                ),
                risk_note="趋势票避免高开追涨，后续交易计划必须设置 MA10/MA20 或固定比例止损",
            )
        )

    if (
        last_close > previous_20_high
        and volume_ratio > 1.5
        and 3 <= _number(latest.pct_chg) <= 8
        and last_close > ma5 > ma10
    ):
        candidates.append(
            CandidateResult(
                **common,
                strategy_type="放量突破",
                stock_score=_score(72 + min(volume_ratio * 8, 20) + min(_number(latest.pct_chg), 8)),
                reason=(
                    f"{sector_note}；收盘价突破近 20 日高点 {previous_20_high:.2f}；"
                    f"量能为 5 日均量 {volume_ratio:.2f} 倍；当日涨幅 {_number(latest.pct_chg):.2f}%"
                ),
                risk_note="突破票次日必须确认不低开过多且放量延续，假突破需快速取消",
            )
        )

    pullback_near_ma = min(abs(last_close - ma10) / ma10, abs(last_close - ma20) / ma20)
    recent_volume_avg = sum(volumes[-5:]) / 5
    previous_volume_avg = sum(volumes[-10:-5]) / 5
    if (
        twenty_day_return > 20
        and last_close > ma20
        and pullback_near_ma <= 0.05
        and recent_volume_avg < previous_volume_avg
        and _number(latest.pct_chg) > -5
    ):
        candidates.append(
            CandidateResult(
                **common,
                strategy_type="强势回踩",
                stock_score=_score(68 + min(twenty_day_return, 30) + max(0, 10 - pullback_near_ma * 100)),
                reason=(
                    f"{sector_note}；20 日涨幅 {twenty_day_return:.2f}% 后回踩 MA10/MA20 附近；"
                    f"当前仍在 MA20 上方；近 5 日成交量较前 5 日缩小"
                ),
                risk_note="回踩票只适合低吸确认，跌破 MA20 或板块退潮应取消",
            )
        )

    return candidates


def _passes_basic_filter(session: Session, basic: StockBasic, trade_date: date) -> bool:
    if basic.is_st or "ST" in basic.stock_name.upper() or "退" in basic.stock_name:
        return False
    if basic.status != "active":
        return False
    if basic.list_date is not None and (trade_date - basic.list_date).days < 60:
        return False
    daily = session.scalar(
        select(StockDaily).where(
            StockDaily.stock_code == basic.stock_code,
            StockDaily.trade_date == trade_date,
        )
    )
    if daily is None:
        return False
    if _number(daily.amount) < 500_000_000:
        return False
    if _number(daily.close) < 2:
        return False
    return True


def _is_one_word_limit_up(session: Session, stock_code: str, trade_date: date, latest: StockDaily) -> bool:
    limit_up = session.scalar(
        select(LimitSnapshot).where(
            LimitSnapshot.trade_date == trade_date,
            LimitSnapshot.stock_code == stock_code,
            LimitSnapshot.limit_status == "limit_up",
        )
    )
    if limit_up is None:
        return False
    return (
        _number(latest.open) == _number(latest.high)
        == _number(latest.low)
        == _number(latest.close)
    )


def _normalize_code(code: str) -> str:
    return code.split(".")[0].zfill(6)


def _ma(values: list[float], window: int) -> float:
    return sum(values[-window:]) / window


def _score(value: float) -> int:
    return max(0, min(100, int(round(value))))


def _number(value) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return float(value or 0)
