from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import delete, desc, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.app.data.global_index_quotes import GlobalIndexQuote, load_global_index_quotes
from backend.app.db.models import IndexDaily, LimitSnapshot, MarketDaily, StockDaily, TradingCalendar


SHANGHAI_INDEX = "000001.SH"
CHINEXT_INDEX = "399006.SZ"


@dataclass(frozen=True)
class MarketEnvironmentResult:
    trade_date: date
    market_score: int
    market_status: str
    suggested_position: str
    up_count: int
    down_count: int
    limit_up_count: int
    limit_down_count: int
    limit_up_height: int
    total_amount: float
    suggestion: str


@dataclass(frozen=True)
class IndexTickerItem:
    name: str
    index_code: str
    trade_date: Optional[date]
    close: Optional[float]
    change: Optional[float]
    pct_chg: Optional[float]
    amount: Optional[float]
    available: bool


INDEX_TICKER_ITEMS: tuple[tuple[str, str], ...] = (
    ("沪指", "000001.SH"),
    ("深指", "399001.SZ"),
    ("创指", "399006.SZ"),
    ("科创", "000688.SH"),
    ("沪深300", "000300.SH"),
    ("深证100", "399330.SZ"),
    ("恒生", "HSI"),
    ("纳斯达克", "IXIC"),
    ("标普", "SPX"),
    ("道琼斯", "DJI"),
)
CHINA_INDEX_CODES = {index_code for _, index_code in INDEX_TICKER_ITEMS[:6]}
TUSHARE_INDEX_AMOUNT_YUAN_FLOOR = 100_000_000_000


def generate_market_environment(engine: Engine, trade_date: date) -> MarketEnvironmentResult:
    with Session(engine) as session:
        result = calculate_market_environment(session, trade_date)
        session.execute(delete(MarketDaily).where(MarketDaily.trade_date == trade_date))
        session.add(
            MarketDaily(
                trade_date=result.trade_date,
                market_score=result.market_score,
                market_status=result.market_status,
                up_count=result.up_count,
                down_count=result.down_count,
                limit_up_count=result.limit_up_count,
                limit_down_count=result.limit_down_count,
                limit_up_height=result.limit_up_height,
                total_amount=result.total_amount,
                suggestion=result.suggestion,
            )
        )
        session.commit()
        return result


def calculate_market_environment(session: Session, trade_date: date) -> MarketEnvironmentResult:
    sh_close = _index_close(session, SHANGHAI_INDEX, trade_date)
    sh_ma20 = _index_ma20(session, SHANGHAI_INDEX, trade_date)
    chinext_close = _index_close(session, CHINEXT_INDEX, trade_date)
    chinext_ma20 = _index_ma20(session, CHINEXT_INDEX, trade_date)
    up_count = _stock_count(session, trade_date, StockDaily.pct_chg > 0)
    down_count = _stock_count(session, trade_date, StockDaily.pct_chg < 0)
    limit_up_count = _limit_count(session, trade_date, "limit_up")
    limit_down_count = _limit_count(session, trade_date, "limit_down")
    limit_up_height = _limit_up_height(session, trade_date)
    total_amount = _total_amount(session, trade_date)
    previous_amount = _previous_total_amount(session, trade_date)

    score = 0
    reasons: list[str] = []
    if sh_close is not None and sh_ma20 is not None and sh_close > sh_ma20:
        score += 15
        reasons.append("上证指数收盘价站上 MA20，+15")
    else:
        reasons.append("上证指数未站上 MA20 或数据不足，+0")

    if chinext_close is not None and chinext_ma20 is not None and chinext_close > chinext_ma20:
        score += 15
        reasons.append("创业板指收盘价站上 MA20，+15")
    else:
        reasons.append("创业板指未站上 MA20 或数据不足，+0")

    if up_count > down_count:
        score += 15
        reasons.append("上涨家数多于下跌家数，+15")
    else:
        reasons.append("上涨家数未超过下跌家数，+0")

    if limit_up_count >= 40:
        score += 15
        reasons.append("涨停家数不少于 40，+15")
    else:
        reasons.append("涨停家数少于 40，+0")

    if limit_down_count <= 10:
        score += 15
        reasons.append("跌停家数不超过 10，+15")
    else:
        reasons.append("跌停家数超过 10，+0")

    if previous_amount is not None and total_amount > previous_amount:
        score += 10
        reasons.append("全市场成交额较上一交易日放大，+10")
    else:
        reasons.append("全市场成交额未放大或缺少上一交易日数据，+0")

    if limit_up_height >= 3:
        score += 15
        reasons.append(f"连板高度达到 {limit_up_height} 板，+15")
    else:
        reasons.append(f"连板高度 {limit_up_height} 板，未达到 3 板，+0")
    status, position, action = _status_for_score(score)
    suggestion = f"{action}；" + "；".join(reasons)

    return MarketEnvironmentResult(
        trade_date=trade_date,
        market_score=score,
        market_status=status,
        suggested_position=position,
        up_count=up_count,
        down_count=down_count,
        limit_up_count=limit_up_count,
        limit_down_count=limit_down_count,
        limit_up_height=limit_up_height,
        total_amount=total_amount,
        suggestion=suggestion,
    )


def load_latest_market_environment(engine: Engine) -> Optional[MarketEnvironmentResult]:
    with Session(engine) as session:
        record = session.scalar(select(MarketDaily).order_by(desc(MarketDaily.trade_date)).limit(1))
        if record is None:
            return None
        return _result_from_record(record)


def load_market_environment_history(engine: Engine, limit: int = 5) -> list[MarketEnvironmentResult]:
    with Session(engine) as session:
        query = select(MarketDaily).order_by(desc(MarketDaily.trade_date)).limit(limit)
        if _calendar_has_rows(session):
            query = (
                query.join(TradingCalendar, TradingCalendar.trade_date == MarketDaily.trade_date)
                .where(TradingCalendar.is_open.is_(True))
            )
        records = session.scalars(query).all()
        return [_result_from_record(record) for record in records]


def load_index_ticker(engine: Engine) -> list[IndexTickerItem]:
    global_quotes = _load_global_index_quotes()
    with Session(engine) as session:
        return [
            _index_ticker_item(session, name, index_code, global_quotes.get(index_code))
            for name, index_code in INDEX_TICKER_ITEMS
        ]


def _index_ticker_item(
    session: Session,
    name: str,
    index_code: str,
    global_quote: Optional[GlobalIndexQuote] = None,
) -> IndexTickerItem:
    record = session.scalar(
        select(IndexDaily)
        .where(IndexDaily.index_code == index_code)
        .order_by(desc(IndexDaily.trade_date))
        .limit(1)
    )
    if record is None:
        if global_quote is not None:
            return IndexTickerItem(
                name=name,
                index_code=index_code,
                trade_date=global_quote.trade_date,
                close=global_quote.close,
                change=global_quote.change,
                pct_chg=global_quote.pct_chg,
                amount=global_quote.amount,
                available=True,
            )
        return IndexTickerItem(
            name=name,
            index_code=index_code,
            trade_date=None,
            close=None,
            change=None,
            pct_chg=None,
            amount=None,
            available=False,
        )

    previous_close = _previous_index_close(session, index_code, record.trade_date)
    close = _number(record.close)
    change = round(close - previous_close, 4) if close is not None and previous_close else None
    pct_chg = round((change / previous_close) * 100, 4) if change is not None and previous_close else None

    return IndexTickerItem(
        name=name,
        index_code=index_code,
        trade_date=record.trade_date,
        close=close,
        change=change,
        pct_chg=pct_chg,
        amount=_index_amount_yuan(index_code, record.amount),
        available=True,
    )


def _load_global_index_quotes() -> dict[str, GlobalIndexQuote]:
    try:
        return load_global_index_quotes(timeout=3.0)
    except Exception:
        return {}


def _previous_index_close(session: Session, index_code: str, trade_date: date) -> Optional[float]:
    value = session.scalar(
        select(IndexDaily.close)
        .where(IndexDaily.index_code == index_code, IndexDaily.trade_date < trade_date)
        .order_by(desc(IndexDaily.trade_date))
        .limit(1)
    )
    return _number(value)


def _result_from_record(record: MarketDaily) -> MarketEnvironmentResult:
    status, position, _ = _status_for_score(record.market_score)
    return MarketEnvironmentResult(
        trade_date=record.trade_date,
        market_score=record.market_score,
        market_status=status,
        suggested_position=position,
        up_count=record.up_count,
        down_count=record.down_count,
        limit_up_count=record.limit_up_count,
        limit_down_count=record.limit_down_count,
        limit_up_height=record.limit_up_height,
        total_amount=float(record.total_amount),
        suggestion=record.suggestion,
    )


def _index_close(session: Session, index_code: str, trade_date: date) -> Optional[float]:
    value = session.scalar(
        select(IndexDaily.close).where(
            IndexDaily.index_code == index_code,
            IndexDaily.trade_date == trade_date,
        )
    )
    return _number(value)


def _index_ma20(session: Session, index_code: str, trade_date: date) -> Optional[float]:
    rows = session.scalars(
        select(IndexDaily.close)
        .where(IndexDaily.index_code == index_code, IndexDaily.trade_date <= trade_date)
        .order_by(desc(IndexDaily.trade_date))
        .limit(20)
    ).all()
    if len(rows) < 20:
        return None
    return sum(_number(row) or 0.0 for row in rows) / 20


def _stock_count(session: Session, trade_date: date, condition) -> int:
    return int(
        session.scalar(
            select(func.count()).select_from(StockDaily).where(StockDaily.trade_date == trade_date, condition)
        )
        or 0
    )


def _limit_count(session: Session, trade_date: date, status: str) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(LimitSnapshot)
            .where(LimitSnapshot.trade_date == trade_date, LimitSnapshot.limit_status == status)
        )
        or 0
    )


def _limit_up_height(session: Session, trade_date: date) -> int:
    current_codes = set(
        session.scalars(
            select(LimitSnapshot.stock_code).where(
                LimitSnapshot.trade_date == trade_date,
                LimitSnapshot.limit_status == "limit_up",
            )
        ).all()
    )
    if not current_codes:
        return 0

    limit_dates = session.scalars(
        select(LimitSnapshot.trade_date)
        .where(LimitSnapshot.trade_date <= trade_date, LimitSnapshot.limit_status == "limit_up")
        .group_by(LimitSnapshot.trade_date)
        .order_by(desc(LimitSnapshot.trade_date))
        .limit(10)
    ).all()
    if not limit_dates:
        return 0

    max_height = 0
    for code in current_codes:
        height = 0
        for limit_date in limit_dates:
            hit = session.scalar(
                select(LimitSnapshot.id)
                .where(
                    LimitSnapshot.trade_date == limit_date,
                    LimitSnapshot.stock_code == code,
                    LimitSnapshot.limit_status == "limit_up",
                )
                .limit(1)
            )
            if hit is None:
                break
            height += 1
        max_height = max(max_height, height)
    return max_height


def _total_amount(session: Session, trade_date: date) -> float:
    return _number(
        session.scalar(select(func.sum(StockDaily.amount)).where(StockDaily.trade_date == trade_date))
    ) or 0.0


def _previous_total_amount(session: Session, trade_date: date) -> Optional[float]:
    previous_date = session.scalar(
        select(StockDaily.trade_date)
        .where(StockDaily.trade_date < trade_date)
        .group_by(StockDaily.trade_date)
        .order_by(desc(StockDaily.trade_date))
        .limit(1)
    )
    if previous_date is None:
        return None
    return _total_amount(session, previous_date)


def _calendar_has_rows(session: Session) -> bool:
    return bool(session.scalar(select(func.count()).select_from(TradingCalendar)))


def _status_for_score(score: int) -> tuple[str, str, str]:
    if score >= 75:
        return "强势", "80% - 100%", "市场赚钱效应较好，可以正常交易但仍需执行止损"
    if score >= 55:
        return "中性", "50% - 80%", "市场处于震荡区间，适合轻仓参与高确定性机会"
    if score >= 35:
        return "弱势", "10% - 30%", "市场亏钱效应明显，应降低仓位并提高买入条件"
    return "风险", "0% - 10%", "市场风险较高，建议空仓或只观察"


def _number(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _index_amount_yuan(index_code: str, amount) -> Optional[float]:
    value = _number(amount)
    if value is None:
        return None
    if index_code in CHINA_INDEX_CODES and 0 < value < TUSHARE_INDEX_AMOUNT_YUAN_FLOOR:
        return value * 1000
    return value
