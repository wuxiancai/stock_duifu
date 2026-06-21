from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import delete, desc, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.app.db.models import CandidateStock, MarketDaily, StockDaily, TradePlan, TradingCalendar


@dataclass(frozen=True)
class TradePlanResult:
    plan_date: date
    target_trade_date: date
    stock_code: str
    stock_name: str
    sector_name: str
    strategy_type: str
    stock_score: int
    sector_score: int
    market_status: str
    buy_condition: str
    buy_price_low: float
    buy_price_high: float
    stop_loss_price: float
    take_profit_price: float
    position_ratio: float
    status: str
    risk_note: str
    id: Optional[int] = None
    trigger_price: Optional[float] = None
    trigger_time: Optional[datetime] = None
    tracking_note: str = ""


@dataclass(frozen=True)
class TradePlanTrackingResult:
    id: int
    stock_code: str
    stock_name: str
    target_trade_date: date
    status: str
    current_price: Optional[float]
    pct_chg: Optional[float]
    trigger_price: Optional[float]
    tracking_note: str


def generate_trade_plans(
    engine: Engine,
    plan_date: date,
    target_trade_date: Optional[date] = None,
    limit: Optional[int] = None,
) -> list[TradePlanResult]:
    with Session(engine) as session:
        target = target_trade_date or _next_open_trade_date(session, plan_date)
        plans = calculate_trade_plans(session, plan_date, target, limit=limit)
        session.execute(
            delete(TradePlan).where(
                TradePlan.plan_date == plan_date,
                TradePlan.target_trade_date == target,
            )
        )
        session.flush()
        for plan in plans:
            payload = {key: value for key, value in plan.__dict__.items() if key != "id"}
            session.add(TradePlan(**payload))
        session.commit()
        return plans


def calculate_trade_plans(
    session: Session,
    plan_date: date,
    target_trade_date: date,
    limit: Optional[int] = None,
) -> list[TradePlanResult]:
    market = session.scalar(select(MarketDaily).where(MarketDaily.trade_date == plan_date))
    if market is None or market.market_status == "风险":
        return []

    candidates = session.scalars(
        select(CandidateStock)
        .where(CandidateStock.trade_date == plan_date)
        .order_by(desc(CandidateStock.stock_score), desc(CandidateStock.sector_score), desc(CandidateStock.amount))
    ).all()
    selected = _select_candidates(candidates, market.market_status, limit=limit)

    plans: list[TradePlanResult] = []
    for candidate in selected:
        history = session.scalars(
            select(StockDaily)
            .where(StockDaily.stock_code == candidate.stock_code, StockDaily.trade_date <= plan_date)
            .order_by(StockDaily.trade_date)
        ).all()
        if len(history) < 20:
            continue
        plan = _build_plan(candidate, history, market.market_status, plan_date, target_trade_date)
        if plan is not None:
            plans.append(plan)
    return plans


def load_latest_trade_plans(engine: Engine) -> Optional[tuple[date, date, list[TradePlanResult]]]:
    with Session(engine) as session:
        latest_plan_date = session.scalar(select(func.max(TradePlan.plan_date)))
        if latest_plan_date is None:
            return None
        latest_target_date = session.scalar(
            select(func.max(TradePlan.target_trade_date)).where(TradePlan.plan_date == latest_plan_date)
        )
        records = session.scalars(
            select(TradePlan)
            .where(
                TradePlan.plan_date == latest_plan_date,
                TradePlan.target_trade_date == latest_target_date,
            )
            .order_by(desc(TradePlan.stock_score), TradePlan.stock_code)
        ).all()
        return (latest_plan_date, latest_target_date, [_plan_result(record) for record in records])


def track_trade_plans(
    engine: Engine,
    target_trade_date: date,
    mark_untriggered_at_close: bool = False,
) -> list[TradePlanTrackingResult]:
    with Session(engine) as session:
        plans = session.scalars(
            select(TradePlan)
            .where(TradePlan.target_trade_date == target_trade_date)
            .order_by(desc(TradePlan.stock_score), TradePlan.stock_code)
        ).all()
        results: list[TradePlanTrackingResult] = []
        now = datetime.now(timezone.utc)

        for plan in plans:
            daily = session.scalar(
                select(StockDaily).where(
                    StockDaily.stock_code == plan.stock_code,
                    StockDaily.trade_date == target_trade_date,
                )
            )
            current_price = _number(daily.close) if daily else None
            pct_chg = _number(daily.pct_chg) if daily else None

            if daily and plan.status in {"待触发", "未触发"}:
                status, trigger_price, note = _evaluate_plan_tracking(plan, daily, mark_untriggered_at_close)
                plan.status = status
                plan.tracking_note = note
                if trigger_price is not None:
                    plan.trigger_price = trigger_price
                    plan.trigger_time = now
            elif daily is None and not plan.tracking_note:
                plan.tracking_note = "目标交易日暂无日线数据，保持待触发状态"

            results.append(
                TradePlanTrackingResult(
                    id=plan.id,
                    stock_code=plan.stock_code,
                    stock_name=plan.stock_name,
                    target_trade_date=plan.target_trade_date,
                    status=plan.status,
                    current_price=current_price,
                    pct_chg=pct_chg,
                    trigger_price=_optional_number(plan.trigger_price),
                    tracking_note=plan.tracking_note,
                )
            )

        session.commit()
        return results


def update_trade_plan_status(
    engine: Engine,
    plan_id: int,
    status: str,
    trigger_price: Optional[float] = None,
    note: str = "",
) -> TradePlanResult:
    allowed_statuses = {"待触发", "已触发", "未触发", "取消"}
    if status not in allowed_statuses:
        raise ValueError(f"Unsupported trade plan status: {status}")

    with Session(engine) as session:
        plan = session.get(TradePlan, plan_id)
        if plan is None:
            raise ValueError(f"trade plan not found: {plan_id}")
        plan.status = status
        plan.tracking_note = note
        if trigger_price is not None:
            plan.trigger_price = round(float(trigger_price), 4)
            plan.trigger_time = datetime.now(timezone.utc)
        elif status != "已触发":
            plan.trigger_price = None
            plan.trigger_time = None
        session.commit()
        session.refresh(plan)
        return _plan_result(plan)


def _evaluate_plan_tracking(
    plan: TradePlan,
    daily: StockDaily,
    mark_untriggered_at_close: bool,
) -> tuple[str, Optional[float], str]:
    open_price = _number(daily.open)
    high = _number(daily.high)
    low = _number(daily.low)
    close = _number(daily.close)
    buy_low = _number(plan.buy_price_low)
    buy_high = _number(plan.buy_price_high)
    stop_loss = _number(plan.stop_loss_price)

    if open_price > buy_high * 1.03:
        return "取消", None, "目标交易日高开超过计划买入上限 3%，按纪律取消追高"
    if open_price < stop_loss or low < stop_loss:
        return "取消", None, "目标交易日跌破计划止损价，按纪律取消计划"
    if low <= buy_high and high >= buy_low:
        trigger_price = round(min(max(open_price, buy_low), buy_high), 4)
        return "已触发", trigger_price, "目标交易日价格触达计划买入区间"
    if mark_untriggered_at_close:
        return "未触发", None, f"收盘价 {close:.2f} 未触达计划买入区间"
    return "待触发", None, "目标交易日尚未触达计划买入区间"


def _plan_result(record: TradePlan) -> TradePlanResult:
    return TradePlanResult(
        id=record.id,
        plan_date=record.plan_date,
        target_trade_date=record.target_trade_date,
        stock_code=record.stock_code,
        stock_name=record.stock_name,
        sector_name=record.sector_name,
        strategy_type=record.strategy_type,
        stock_score=record.stock_score,
        sector_score=record.sector_score,
        market_status=record.market_status,
        buy_condition=record.buy_condition,
        buy_price_low=_number(record.buy_price_low),
        buy_price_high=_number(record.buy_price_high),
        stop_loss_price=_number(record.stop_loss_price),
        take_profit_price=_number(record.take_profit_price),
        position_ratio=_number(record.position_ratio),
        status=record.status,
        risk_note=record.risk_note,
        trigger_price=_optional_number(record.trigger_price),
        trigger_time=record.trigger_time,
        tracking_note=record.tracking_note,
    )


def _select_candidates(
    candidates: list[CandidateStock],
    market_status: str,
    limit: Optional[int],
) -> list[CandidateStock]:
    max_new = _max_new_positions(market_status)
    if limit is not None:
        max_new = min(max_new, limit)
    selected: list[CandidateStock] = []
    used_stocks: set[str] = set()
    used_sectors: set[str] = set()

    for candidate in candidates:
        if candidate.stock_code in used_stocks:
            continue
        if market_status == "强势" and candidate.sector_name in used_sectors and len(used_sectors) < 3:
            continue
        selected.append(candidate)
        used_stocks.add(candidate.stock_code)
        used_sectors.add(candidate.sector_name)
        if len(selected) >= max_new:
            break
    return selected


def _build_plan(
    candidate: CandidateStock,
    history: list[StockDaily],
    market_status: str,
    plan_date: date,
    target_trade_date: date,
) -> Optional[TradePlanResult]:
    closes = [_number(row.close) for row in history]
    highs = [_number(row.high) for row in history]
    ma5 = _ma(closes, 5)
    ma10 = _ma(closes, 10)
    ma20 = _ma(closes, 20)
    close = closes[-1]
    previous_high = highs[-1]
    atr14 = _atr14(history)

    if candidate.strategy_type == "趋势强势":
        buy_low = min(ma10, ma5)
        buy_high = max(close, ma5)
        technical_stop = min(ma10, ma20)
        condition = "次日盘中回踩 MA5/MA10 附近不破，或放量突破前一日高点，且板块继续维持强势"
    elif candidate.strategy_type == "放量突破":
        buy_low = previous_high
        buy_high = previous_high * 1.03
        technical_stop = max(ma10, previous_high * 0.97)
        condition = "次日低开不超过 3%，盘中放量突破前一日高点，且板块排名仍在前列"
    elif candidate.strategy_type == "强势回踩":
        buy_low = min(ma20, ma10)
        buy_high = max(ma20, ma10)
        technical_stop = ma20
        condition = "次日盘中不跌破 MA20，出现放量反包或重新站回 MA5，且大盘不是风险状态"
    else:
        return None

    buy_low, buy_high = sorted((round(buy_low, 4), round(buy_high, 4)))
    buy_reference = buy_high
    fixed_stop = buy_reference * 0.95
    atr_stop = buy_reference - 1.5 * atr14
    stop_loss = round(max(technical_stop, fixed_stop, atr_stop), 4)
    if stop_loss <= 0 or stop_loss >= buy_reference:
        return None

    return TradePlanResult(
        plan_date=plan_date,
        target_trade_date=target_trade_date,
        stock_code=candidate.stock_code,
        stock_name=candidate.stock_name,
        sector_name=candidate.sector_name,
        strategy_type=candidate.strategy_type,
        stock_score=candidate.stock_score,
        sector_score=candidate.sector_score,
        market_status=market_status,
        buy_condition=condition,
        buy_price_low=buy_low,
        buy_price_high=buy_high,
        stop_loss_price=stop_loss,
        take_profit_price=round(buy_reference * 1.2, 4),
        position_ratio=_position_ratio(market_status, candidate.stock_score),
        status="待触发",
        risk_note=_risk_note(candidate, market_status),
    )


def _next_open_trade_date(session: Session, plan_date: date) -> date:
    next_open = session.scalar(
        select(TradingCalendar.trade_date)
        .where(TradingCalendar.trade_date > plan_date, TradingCalendar.is_open.is_(True))
        .order_by(TradingCalendar.trade_date)
        .limit(1)
    )
    return next_open or plan_date + timedelta(days=1)


def _max_new_positions(market_status: str) -> int:
    if market_status == "强势":
        return 3
    if market_status == "中性":
        return 2
    if market_status == "弱势":
        return 1
    return 0


def _position_ratio(market_status: str, stock_score: int) -> float:
    if market_status == "强势":
        return 0.5
    if market_status == "中性":
        return 0.4 if stock_score >= 95 else 0.2
    if market_status == "弱势":
        return 0.1
    return 0.0


def _risk_note(candidate: CandidateStock, market_status: str) -> str:
    return (
        f"市场状态：{market_status}；单票仓位按市场状态控制。"
        f"{candidate.risk_note}；若次日高开过多、跌破关键均线或板块退潮，应取消计划。"
    )


def _ma(values: list[float], window: int) -> float:
    return sum(values[-window:]) / window


def _atr14(history: list[StockDaily]) -> float:
    recent = history[-14:]
    true_ranges: list[float] = []
    for row in recent:
        high = _number(row.high)
        low = _number(row.low)
        previous_close = _number(row.pre_close)
        true_ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    return sum(true_ranges) / len(true_ranges)


def _optional_number(value) -> Optional[float]:
    if value is None:
        return None
    return _number(value)


def _number(value) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return float(value or 0)
