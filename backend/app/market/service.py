from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import delete, desc, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.app.db.models import IndexDaily, LimitSnapshot, MarketDaily, StockDaily


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
    total_amount: float
    suggestion: str


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

    reasons.append("连板高度暂无结构化数据，未计入评分")
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
        total_amount=total_amount,
        suggestion=suggestion,
    )


def load_latest_market_environment(engine: Engine) -> Optional[MarketEnvironmentResult]:
    with Session(engine) as session:
        record = session.scalar(select(MarketDaily).order_by(desc(MarketDaily.trade_date)).limit(1))
        if record is None:
            return None
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
