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
    sector_category: str
    stock_pool_rank: Optional[int]
    strategy_type: str
    stock_score: int
    sector_score: int
    nine_turn_signal: str
    nine_turn_count: int
    nine_turn_score: int
    close_price: float
    amount: float
    reason: str
    risk_note: str


@dataclass(frozen=True)
class SectorSelection:
    sector: SectorDaily
    category: str
    quota: int
    persistence_bonus: int
    recent_ranks: tuple[int, ...]
    average_rank: float
    top3_count: int
    top10_count: int
    rank_std: float


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
    sector_selections = _build_sector_selections(session, trade_date)
    if not sector_selections:
        return []

    sector_by_name = {selection.sector.sector_name: selection for selection in sector_selections}
    membership = membership_provider.sector_members(list(sector_by_name.keys()))
    sector_by_stock: dict[str, SectorSelection] = {}
    for sector_name, codes in membership.items():
        selection = sector_by_name.get(sector_name)
        if selection is None:
            continue
        for code in codes:
            normalized = _normalize_code(code)
            current = sector_by_stock.get(normalized)
            if current is None or selection.sector.rank_no < current.sector.rank_no:
                sector_by_stock[normalized] = selection

    results: list[CandidateResult] = []
    for stock_code, selection in sector_by_stock.items():
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
        results.extend(_strategy_candidates(basic, selection, history, trade_date))

    ordered = sorted(
        results,
        key=lambda item: (item.stock_score, item.sector_score, item.amount),
        reverse=True,
    )[:limit]
    return _rank_stock_pool(ordered, sector_by_name)


def _build_sector_selections(session: Session, trade_date: date) -> list[SectorSelection]:
    current_sectors = session.scalars(
        select(SectorDaily)
        .where(SectorDaily.trade_date == trade_date)
        .order_by(SectorDaily.rank_no)
        .limit(10)
    ).all()

    selections: list[SectorSelection] = []
    for sector in current_sectors:
        history = session.scalars(
            select(SectorDaily)
            .where(SectorDaily.sector_name == sector.sector_name, SectorDaily.trade_date <= trade_date)
            .order_by(desc(SectorDaily.trade_date))
            .limit(5)
        ).all()
        ranks = tuple(int(row.rank_no) for row in history)
        selection = _classify_sector_selection(sector, ranks)
        if selection is not None:
            selections.append(selection)

    return sorted(
        selections,
        key=lambda item: (
            item.persistence_bonus,
            item.top3_count,
            item.top10_count,
            -item.average_rank,
            item.sector.sector_score,
        ),
        reverse=True,
    )


def _classify_sector_selection(sector: SectorDaily, ranks: tuple[int, ...]) -> Optional[SectorSelection]:
    if not ranks:
        return None
    current_rank = ranks[0]
    previous_rank = ranks[1] if len(ranks) > 1 else None
    average_rank = sum(ranks) / len(ranks)
    rank_std = _rank_std(ranks, average_rank)
    top3_count = sum(1 for rank in ranks if rank <= 3)
    top10_count = sum(1 for rank in ranks if rank <= 10)

    if current_rank <= 3 and previous_rank is not None and previous_rank > 10 and top10_count <= 2:
        return None

    if top3_count >= 3 and average_rank <= 5 and min(ranks) == 1:
        category = "核心主升"
        quota = 5
        bonus = 10
    elif top10_count >= 5 and average_rank <= 6 and rank_std <= 4:
        category = "稳定强势"
        quota = 3
        bonus = 8
    elif current_rank <= 5 and top10_count >= 3 and average_rank <= 8:
        category = "强势延续"
        quota = 2
        bonus = 5
    elif top10_count >= 3 and average_rank <= 10:
        category = "趋势观察"
        quota = 0
        bonus = 2
    else:
        return None

    return SectorSelection(
        sector=sector,
        category=category,
        quota=quota,
        persistence_bonus=bonus,
        recent_ranks=ranks,
        average_rank=average_rank,
        top3_count=top3_count,
        top10_count=top10_count,
        rank_std=rank_std,
    )


def _rank_stock_pool(
    ordered: list[CandidateResult],
    selection_by_sector: dict[str, SectorSelection],
    pool_limit: int = 10,
) -> list[CandidateResult]:
    selected_keys: set[tuple[str, str]] = set()
    sector_counts: dict[str, int] = {}
    pool: list[CandidateResult] = []

    for item in ordered:
        selection = selection_by_sector.get(item.sector_name)
        if selection is None or selection.quota <= 0:
            continue
        key = (item.stock_code, item.strategy_type)
        if key in selected_keys:
            continue
        if sector_counts.get(item.sector_name, 0) >= selection.quota:
            continue
        pool.append(_with_stock_pool_rank(item, len(pool) + 1))
        selected_keys.add(key)
        sector_counts[item.sector_name] = sector_counts.get(item.sector_name, 0) + 1
        if len(pool) >= pool_limit:
            break

    pool_by_key = {(item.stock_code, item.strategy_type): item for item in pool}
    ranked: list[CandidateResult] = []
    for item in ordered:
        key = (item.stock_code, item.strategy_type)
        ranked.append(pool_by_key.get(key) or item)
    return ranked


def _with_stock_pool_rank(item: CandidateResult, rank: int) -> CandidateResult:
    return CandidateResult(
        trade_date=item.trade_date,
        stock_code=item.stock_code,
        stock_name=item.stock_name,
        sector_name=item.sector_name,
        sector_rank=item.sector_rank,
        sector_category=item.sector_category,
        stock_pool_rank=rank,
        strategy_type=item.strategy_type,
        stock_score=item.stock_score,
        sector_score=item.sector_score,
        nine_turn_signal=item.nine_turn_signal,
        nine_turn_count=item.nine_turn_count,
        nine_turn_score=item.nine_turn_score,
        close_price=item.close_price,
        amount=item.amount,
        reason=item.reason,
        risk_note=item.risk_note,
    )


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
        records = _ensure_displayable_stock_pool(records)
        return (
            latest_date,
            [
                CandidateResult(
                    trade_date=record.trade_date,
                    stock_code=record.stock_code,
                    stock_name=record.stock_name,
                    sector_name=record.sector_name,
                    sector_rank=record.sector_rank,
                    sector_category=record.sector_category,
                    stock_pool_rank=record.stock_pool_rank,
                    strategy_type=record.strategy_type,
                    stock_score=record.stock_score,
                    sector_score=record.sector_score,
                    nine_turn_signal=record.nine_turn_signal,
                    nine_turn_count=record.nine_turn_count,
                    nine_turn_score=record.nine_turn_score,
                    close_price=_number(record.close_price),
                    amount=_number(record.amount),
                    reason=record.reason,
                    risk_note=record.risk_note,
                )
                for record in records
            ],
        )


def _ensure_displayable_stock_pool(records: list[CandidateStock]) -> list[CandidateStock]:
    if any(record.stock_pool_rank is not None for record in records):
        return sorted(
            records,
            key=lambda item: (
                item.stock_pool_rank is None,
                item.stock_pool_rank or 9999,
                -item.stock_score,
                item.stock_code,
            ),
        )

    ordered = sorted(
        records,
        key=lambda item: (item.stock_score, item.sector_score, item.amount),
        reverse=True,
    )
    for rank, record in enumerate(ordered[:10], start=1):
        record.stock_pool_rank = rank
    return ordered


def _strategy_candidates(
    basic: StockBasic,
    selection: SectorSelection,
    history: list[StockDaily],
    trade_date: date,
) -> list[CandidateResult]:
    sector = selection.sector
    latest = history[-1]
    closes = [_number(row.close) for row in history]
    volumes = [_number(row.volume) for row in history]
    ma5 = _ma(closes, 5)
    ma10 = _ma(closes, 10)
    ma20 = _ma(closes, 20)
    last_close = closes[-1]
    amount = _number(latest.amount)
    nine_turn_signal, nine_turn_count = _nine_turn_sequence(closes)
    nine_turn_score = _nine_turn_score(nine_turn_signal, nine_turn_count)
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
        "sector_category": selection.category,
        "stock_pool_rank": None,
        "sector_score": sector.sector_score,
        "nine_turn_signal": nine_turn_signal,
        "nine_turn_count": nine_turn_count,
        "nine_turn_score": nine_turn_score,
        "close_price": last_close,
        "amount": amount,
    }
    candidates: list[CandidateResult] = []
    rank_text = "/".join(str(rank) for rank in selection.recent_ranks)
    sector_note = (
        f"行业持续性：{selection.category}，近5日排名 {rank_text}，"
        f"均值 {selection.average_rank:.1f}，Top10 出现 {selection.top10_count} 天；"
        f"当前 {sector.sector_name} 第 {sector.rank_no} 名，行业评分 {sector.sector_score}"
    )

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
                stock_score=_score_with_modifiers(
                    70 + min(twenty_day_return, 30) + min(five_day_return, 10),
                    selection.persistence_bonus,
                    nine_turn_score,
                ),
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
                stock_score=_score_with_modifiers(
                    72 + min(volume_ratio * 8, 20) + min(_number(latest.pct_chg), 8),
                    selection.persistence_bonus,
                    nine_turn_score,
                ),
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
                stock_score=_score_with_modifiers(
                    68 + min(twenty_day_return, 30) + max(0, 10 - pullback_near_ma * 100),
                    selection.persistence_bonus,
                    nine_turn_score,
                ),
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


def _rank_std(ranks: tuple[int, ...], average_rank: float) -> float:
    if len(ranks) <= 1:
        return 0.0
    return (sum((rank - average_rank) ** 2 for rank in ranks) / len(ranks)) ** 0.5


def _score(value: float) -> int:
    return max(0, min(100, int(round(value))))


def _score_with_modifiers(value: float, persistence_bonus: int, nine_turn_score: int) -> int:
    return max(0, min(120, _score(value) + persistence_bonus + nine_turn_score))


def _nine_turn_sequence(closes: list[float]) -> tuple[str, int]:
    if len(closes) < 5:
        return "", 0
    sell_count = 0
    buy_count = 0
    for index in range(4, len(closes)):
        if closes[index] > closes[index - 4]:
            sell_count = min(sell_count + 1, 9)
            buy_count = 0
        elif closes[index] < closes[index - 4]:
            buy_count = min(buy_count + 1, 9)
            sell_count = 0
        else:
            sell_count = 0
            buy_count = 0
    if sell_count:
        return "sell", sell_count
    if buy_count:
        return "buy", buy_count
    return "", 0


def _nine_turn_score(signal: str, count: int) -> int:
    if signal == "sell" and 1 <= count <= 3:
        return 2
    if signal == "sell" and 4 <= count <= 6:
        return 4
    if signal == "sell" and 7 <= count <= 9:
        return 2
    if signal == "buy" and 1 <= count <= 8:
        return -4
    if signal == "buy" and count == 9:
        return 1
    return 0


def _number(value) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return float(value or 0)
