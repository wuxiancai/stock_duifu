from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import delete, desc, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.app.db.models import CandidateStock, MarketDaily, StockDaily, TradePlan, TradeReview, TradingCalendar


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


@dataclass(frozen=True)
class TradePlanRetargetResult:
    old_target_trade_date: date
    target_is_open: Optional[bool]
    new_target_trade_date: Optional[date]
    plan_dates: list[date]
    closed_plan_count: int
    generated_plan_count: int
    skipped_reason: str
    items: list[TradePlanResult]


@dataclass(frozen=True)
class TradeReviewResult:
    id: Optional[int]
    trade_plan_id: int
    trade_date: date
    stock_code: str
    stock_name: str
    sector_name: str
    strategy_type: str
    triggered: bool
    trigger_price: Optional[float]
    close_price: Optional[float]
    day_return: Optional[float]
    t5_return: Optional[float]
    max_profit: Optional[float]
    max_loss: Optional[float]
    result: str
    failure_reason: Optional[str]
    discipline_check: bool
    note: str


@dataclass(frozen=True)
class ReviewGroupStats:
    name: str
    total_count: int
    triggered_count: int
    win_count: int
    win_rate: float
    avg_day_return: Optional[float]
    avg_t5_return: Optional[float]


@dataclass(frozen=True)
class TradeReviewSummary:
    review_date: date
    total_count: int
    triggered_count: int
    win_count: int
    win_rate: float
    avg_day_return: Optional[float]
    avg_t5_return: Optional[float]
    strategy_stats: list[ReviewGroupStats]
    sector_stats: list[ReviewGroupStats]
    items: list[TradeReviewResult]


def generate_trade_plans(
    engine: Engine,
    plan_date: date,
    target_trade_date: Optional[date] = None,
    limit: Optional[int] = None,
) -> list[TradePlanResult]:
    with Session(engine) as session:
        target = target_trade_date or _next_open_trade_date(session, plan_date)
        plans = calculate_trade_plans(session, plan_date, target, limit=limit)
        _replace_trade_plans(session, plan_date, target, plans)
        session.commit()
        return plans


def retarget_closed_trade_plans(
    engine: Engine,
    target_trade_date: date,
    limit: Optional[int] = None,
) -> TradePlanRetargetResult:
    with Session(engine) as session:
        target_is_open = _target_is_open(session, target_trade_date)
        plans = session.scalars(
            select(TradePlan)
            .where(TradePlan.target_trade_date == target_trade_date)
            .order_by(TradePlan.plan_date, desc(TradePlan.stock_score), TradePlan.stock_code)
        ).all()
        plan_dates = sorted({plan.plan_date for plan in plans})

        if target_is_open is None:
            return TradePlanRetargetResult(
                old_target_trade_date=target_trade_date,
                target_is_open=None,
                new_target_trade_date=None,
                plan_dates=plan_dates,
                closed_plan_count=len(plans),
                generated_plan_count=0,
                skipped_reason="目标交易日缺少交易日历，需先采集或回补交易日历",
                items=[],
            )
        if target_is_open:
            return TradePlanRetargetResult(
                old_target_trade_date=target_trade_date,
                target_is_open=True,
                new_target_trade_date=None,
                plan_dates=plan_dates,
                closed_plan_count=len(plans),
                generated_plan_count=0,
                skipped_reason="目标交易日是开市日，无需顺延",
                items=[],
            )
        if not plans:
            return TradePlanRetargetResult(
                old_target_trade_date=target_trade_date,
                target_is_open=False,
                new_target_trade_date=None,
                plan_dates=[],
                closed_plan_count=0,
                generated_plan_count=0,
                skipped_reason="目标交易日没有交易计划，无需顺延",
                items=[],
            )

        new_target = _next_open_trade_date_after(session, target_trade_date)
        if new_target is None:
            return TradePlanRetargetResult(
                old_target_trade_date=target_trade_date,
                target_is_open=False,
                new_target_trade_date=None,
                plan_dates=plan_dates,
                closed_plan_count=len(plans),
                generated_plan_count=0,
                skipped_reason="目标交易日之后缺少下一开市日历，需先采集更晚的交易日历",
                items=[],
            )

        generated: list[TradePlanResult] = []
        for plan_date in plan_dates:
            next_plans = calculate_trade_plans(session, plan_date, new_target, limit=limit)
            _replace_trade_plans(session, plan_date, new_target, next_plans)
            generated.extend(next_plans)

        note = f"目标交易日不是开市日，已重新生成到 {new_target.isoformat()}"
        for plan in plans:
            plan.status = "取消"
            plan.tracking_note = note

        session.commit()
        return TradePlanRetargetResult(
            old_target_trade_date=target_trade_date,
            target_is_open=False,
            new_target_trade_date=new_target,
            plan_dates=plan_dates,
            closed_plan_count=len(plans),
            generated_plan_count=len(generated),
            skipped_reason="",
            items=generated,
        )


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
        target_is_open = _target_is_open(session, target_trade_date)

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
            elif daily is None and (
                not plan.tracking_note or plan.tracking_note == "目标交易日暂无日线数据，保持待触发状态"
            ):
                if target_is_open is False:
                    plan.tracking_note = "目标交易日不是开市日，未产生行情数据，计划需重新生成到下一开市日"
                else:
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


def generate_trade_reviews(engine: Engine, trade_date: date) -> TradeReviewSummary:
    with Session(engine) as session:
        plans = session.scalars(
            select(TradePlan)
            .where(TradePlan.target_trade_date == trade_date)
            .order_by(desc(TradePlan.stock_score), TradePlan.stock_code)
        ).all()
        session.execute(
            delete(TradeReview).where(
                TradeReview.trade_plan_id.in_([plan.id for plan in plans] or [-1]),
                TradeReview.trade_date == trade_date,
            )
        )
        session.flush()

        for plan in plans:
            review = _build_trade_review(session, plan, trade_date)
            session.add(review)

        session.commit()
        return _load_trade_review_summary(session, trade_date)


def load_latest_trade_reviews(engine: Engine) -> Optional[TradeReviewSummary]:
    with Session(engine) as session:
        latest_trade_date = session.scalar(select(func.max(TradeReview.trade_date)))
        if latest_trade_date is None:
            return None
        return _load_trade_review_summary(session, latest_trade_date)


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


def _build_trade_review(session: Session, plan: TradePlan, trade_date: date) -> TradeReview:
    history = session.scalars(
        select(StockDaily)
        .where(StockDaily.stock_code == plan.stock_code, StockDaily.trade_date >= trade_date)
        .order_by(StockDaily.trade_date)
        .limit(5)
    ).all()
    target_daily = next((row for row in history if row.trade_date == trade_date), None)
    triggered = plan.status == "已触发" and plan.trigger_price is not None
    trigger_price = _optional_number(plan.trigger_price) if triggered else None
    close_price = _optional_number(target_daily.close) if target_daily else None

    day_return: Optional[float] = None
    t5_return: Optional[float] = None
    max_profit: Optional[float] = None
    max_loss: Optional[float] = None
    result = "观察"
    failure_reason: Optional[str] = None
    discipline_check = True
    note = plan.tracking_note or ""

    if not triggered:
        result = "取消" if plan.status == "取消" else "未触发"
        failure_reason = plan.tracking_note or "计划未触发"
        note = note or "未产生实际触发价格，收益字段不计算"
    elif not target_daily:
        result = "观察"
        failure_reason = "缺少目标交易日日线"
        discipline_check = False
        note = note or "缺少目标交易日日线，暂不能复盘"
    elif trigger_price and trigger_price > 0:
        day_return = _pct_return(close_price, trigger_price)
        t5_return = _pct_return(_number(history[-1].close), trigger_price) if len(history) >= 5 else None
        max_profit = round((max(_number(row.high) for row in history) - trigger_price) / trigger_price, 4)
        max_loss = round((min(_number(row.low) for row in history) - trigger_price) / trigger_price, 4)

        if min(_number(row.low) for row in history) <= _number(plan.stop_loss_price):
            result = "止损"
            failure_reason = "触及计划止损价"
        elif max(_number(row.high) for row in history) >= _number(plan.take_profit_price):
            result = "止盈"
        elif day_return is not None and day_return > 0:
            result = "盈利"
        else:
            result = "亏损"
            failure_reason = _failure_reason(plan, day_return)
        note = note or "按目标交易日及后续已入库日线自动生成复盘"

    return TradeReview(
        trade_plan_id=plan.id,
        trade_date=trade_date,
        stock_code=plan.stock_code,
        stock_name=plan.stock_name,
        strategy_type=plan.strategy_type,
        triggered=triggered,
        trigger_price=trigger_price,
        close_price=close_price,
        day_return=day_return,
        t5_return=t5_return,
        max_profit=max_profit,
        max_loss=max_loss,
        result=result,
        failure_reason=failure_reason,
        discipline_check=discipline_check,
        note=note,
    )


def _load_trade_review_summary(session: Session, trade_date: date) -> TradeReviewSummary:
    rows = session.execute(
        select(TradeReview, TradePlan)
        .join(TradePlan, TradePlan.id == TradeReview.trade_plan_id)
        .where(TradeReview.trade_date == trade_date)
        .order_by(desc(TradeReview.triggered), desc(TradeReview.day_return), TradeReview.stock_code)
    ).all()
    items = [_review_result(review, plan) for review, plan in rows]
    return TradeReviewSummary(
        review_date=trade_date,
        total_count=len(items),
        triggered_count=sum(1 for item in items if item.triggered),
        win_count=sum(1 for item in items if _is_win(item)),
        win_rate=_win_rate(items),
        avg_day_return=_average([item.day_return for item in items if item.day_return is not None]),
        avg_t5_return=_average([item.t5_return for item in items if item.t5_return is not None]),
        strategy_stats=_group_stats(items, lambda item: item.strategy_type),
        sector_stats=_group_stats(items, lambda item: item.sector_name),
        items=items,
    )


def _review_result(record: TradeReview, plan: TradePlan) -> TradeReviewResult:
    return TradeReviewResult(
        id=record.id,
        trade_plan_id=record.trade_plan_id,
        trade_date=record.trade_date,
        stock_code=record.stock_code,
        stock_name=record.stock_name,
        sector_name=plan.sector_name,
        strategy_type=record.strategy_type,
        triggered=record.triggered,
        trigger_price=_optional_number(record.trigger_price),
        close_price=_optional_number(record.close_price),
        day_return=_optional_number(record.day_return),
        t5_return=_optional_number(record.t5_return),
        max_profit=_optional_number(record.max_profit),
        max_loss=_optional_number(record.max_loss),
        result=record.result,
        failure_reason=record.failure_reason,
        discipline_check=record.discipline_check,
        note=record.note,
    )


def _group_stats(items: list[TradeReviewResult], key_fn) -> list[ReviewGroupStats]:
    groups: dict[str, list[TradeReviewResult]] = {}
    for item in items:
        groups.setdefault(key_fn(item), []).append(item)
    return [
        ReviewGroupStats(
            name=name,
            total_count=len(group),
            triggered_count=sum(1 for item in group if item.triggered),
            win_count=sum(1 for item in group if _is_win(item)),
            win_rate=_win_rate(group),
            avg_day_return=_average([item.day_return for item in group if item.day_return is not None]),
            avg_t5_return=_average([item.t5_return for item in group if item.t5_return is not None]),
        )
        for name, group in sorted(groups.items(), key=lambda row: (-sum(1 for item in row[1] if _is_win(item)), row[0]))
    ]


def _failure_reason(plan: TradePlan, day_return: Optional[float]) -> str:
    if plan.market_status in {"弱势", "风险"}:
        return "大盘弱"
    if plan.strategy_type == "放量突破":
        return "假突破"
    if day_return is not None and day_return < -0.03:
        return "追高"
    return "板块退潮"


def _pct_return(price: Optional[float], base: float) -> Optional[float]:
    if price is None or base <= 0:
        return None
    return round((price - base) / base, 4)


def _is_win(item: TradeReviewResult) -> bool:
    return item.triggered and item.day_return is not None and item.day_return > 0


def _win_rate(items: list[TradeReviewResult]) -> float:
    triggered_count = sum(1 for item in items if item.triggered)
    if triggered_count == 0:
        return 0.0
    return round(sum(1 for item in items if _is_win(item)) / triggered_count, 4)


def _average(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _target_is_open(session: Session, target_trade_date: date) -> Optional[bool]:
    calendar = session.scalar(
        select(TradingCalendar).where(TradingCalendar.trade_date == target_trade_date)
    )
    return calendar.is_open if calendar is not None else None


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


def _replace_trade_plans(
    session: Session,
    plan_date: date,
    target_trade_date: date,
    plans: list[TradePlanResult],
) -> None:
    session.execute(
        delete(TradePlan).where(
            TradePlan.plan_date == plan_date,
            TradePlan.target_trade_date == target_trade_date,
        )
    )
    session.flush()
    for plan in plans:
        payload = {key: value for key, value in plan.__dict__.items() if key != "id"}
        session.add(TradePlan(**payload))


def _next_open_trade_date(session: Session, plan_date: date) -> date:
    next_open = _next_open_trade_date_after(session, plan_date)
    return next_open or plan_date + timedelta(days=1)


def _next_open_trade_date_after(session: Session, after_date: date) -> Optional[date]:
    return session.scalar(
        select(TradingCalendar.trade_date)
        .where(TradingCalendar.trade_date > after_date, TradingCalendar.is_open.is_(True))
        .order_by(TradingCalendar.trade_date)
        .limit(1)
    )


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
