from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from time import sleep
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import delete, desc, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.db.models import (
    MarketDaily,
    SectorDaily,
    SimulationAccount,
    SimulationEquity,
    SimulationPosition,
    SimulationTrade,
    StockDaily,
    TradePlan,
    TradingCalendar,
)
from backend.app.trade.service import TradePlanTrackingResult, track_trade_plans

DEFAULT_ACCOUNT_NAME = "默认模拟账户"
DEFAULT_INITIAL_CASH = 1_000_000.0
TRADING_TZ = ZoneInfo("Asia/Shanghai")
TRADING_START = time(9, 30)
TRADING_MORNING_END = time(11, 30)
TRADING_AFTERNOON_START = time(13, 0)
TRADING_END = time(15, 0)
DEFAULT_LOOP_INTERVAL_SECONDS = 300
MAX_HOLDING_DAYS = 5
SECOND_TAKE_PROFIT_MULTIPLIER = 1.5
ACTIVE_POSITION_STATUSES = ("持仓中", "部分止盈", "待卖出")


@dataclass(frozen=True)
class SimulationAccountSnapshot:
    id: int
    account_name: str
    initial_cash: float
    available_cash: float
    frozen_cash: float
    market_value: float
    total_assets: float
    total_profit: float
    total_return: float
    max_drawdown: float


@dataclass(frozen=True)
class SimulationPositionSnapshot:
    id: int
    stock_code: str
    stock_name: str
    sector_name: str
    strategy_type: str
    buy_price: float
    current_price: float
    quantity: int
    market_value: float
    cost_amount: float
    unrealized_profit: float
    unrealized_return: float
    stop_loss_price: float
    take_profit_price: float
    position_status: str
    buy_reason: str
    sell_reason: str


@dataclass(frozen=True)
class SimulationTradeSnapshot:
    id: int
    trade_plan_id: int
    stock_code: str
    stock_name: str
    trade_date: date
    trade_time: datetime
    trade_type: str
    price: float
    quantity: int
    amount: float
    commission: float
    stamp_tax: float
    transfer_fee: float
    total_fee: float
    net_amount: float
    cash_after: float
    position_ratio_after: float
    profit_loss: Optional[float]
    profit_loss_return: Optional[float]
    reason: str


@dataclass(frozen=True)
class SimulationEquityPoint:
    trade_date: date
    available_cash: float
    market_value: float
    total_assets: float
    daily_profit: float
    daily_return: float
    max_drawdown: float


@dataclass(frozen=True)
class SimulationRiskSnapshot:
    max_drawdown: float
    position_count: int
    position_ratio: float
    win_rate: float = 0.0
    profit_loss_ratio: Optional[float] = None


@dataclass(frozen=True)
class SimulationSummary:
    as_of_date: date
    account: SimulationAccountSnapshot
    positions: list[SimulationPositionSnapshot]
    trades: list[SimulationTradeSnapshot]
    equity_curve: list[SimulationEquityPoint]
    risk: SimulationRiskSnapshot
    messages: list[str]


@dataclass(frozen=True)
class SimulationWorkflowSummary:
    target_trade_date: date
    tracking: list[TradePlanTrackingResult]
    simulation: SimulationSummary


@dataclass(frozen=True)
class SimulationLoopSummary:
    target_trade_date: date
    iterations: int
    started: bool
    messages: list[str]


def run_simulation_workflow(
    engine: Engine,
    trade_date: date,
    mark_untriggered_at_close: bool = False,
) -> SimulationWorkflowSummary:
    with Session(engine) as session:
        target_trade_date = _resolve_open_trade_date(session, trade_date)
    tracking = track_trade_plans(engine, target_trade_date, mark_untriggered_at_close=mark_untriggered_at_close)
    simulation = run_simulation(engine, target_trade_date)
    return SimulationWorkflowSummary(target_trade_date=target_trade_date, tracking=tracking, simulation=simulation)


def run_trading_loop(
    engine: Engine,
    trade_date: date,
    interval_seconds: int = DEFAULT_LOOP_INTERVAL_SECONDS,
    max_iterations: Optional[int] = None,
) -> SimulationLoopSummary:
    iterations = 0
    messages: list[str] = []
    with Session(engine) as session:
        target_trade_date = _resolve_open_trade_date(session, trade_date)
    while True:
        now = datetime.now(TRADING_TZ)
        if not _is_trading_time(now):
            if iterations == 0:
                messages.append("当前不在交易时段 09:30-15:00，未启动模拟交易轮询")
            break
        run_simulation_workflow(engine, target_trade_date)
        iterations += 1
        if max_iterations is not None and iterations >= max_iterations:
            break
        sleep(max(1, interval_seconds))
    return SimulationLoopSummary(
        target_trade_date=target_trade_date,
        iterations=iterations,
        started=iterations > 0,
        messages=messages,
    )


def run_simulation(engine: Engine, trade_date: date) -> SimulationSummary:
    with Session(engine) as session:
        trade_date = _resolve_open_trade_date(session, trade_date)
        account = _get_or_create_account(session)
        messages: list[str] = []

        _sell_positions(session, account, trade_date, messages)
        _buy_triggered_plans(session, account, trade_date, messages)
        _mark_to_market(session, account, trade_date)
        _save_equity(session, account, trade_date)
        session.commit()
        return _load_summary(session, account.id, trade_date, messages)


def load_latest_simulation(engine: Engine) -> Optional[SimulationSummary]:
    with Session(engine) as session:
        account = session.scalar(select(SimulationAccount).where(SimulationAccount.account_name == DEFAULT_ACCOUNT_NAME))
        if account is None:
            return None
        if _has_no_positions_or_trades(session, account.id):
            return None
        latest_date = _latest_open_equity_date(session, account.id)
        if latest_date is None:
            return None
        _mark_to_market(session, account, latest_date)
        _save_equity(session, account, latest_date)
        session.commit()
        return _load_summary(session, account.id, latest_date, [])


def _get_or_create_account(session: Session) -> SimulationAccount:
    account = session.scalar(select(SimulationAccount).where(SimulationAccount.account_name == DEFAULT_ACCOUNT_NAME))
    if account is not None:
        _reset_orphan_account(session, account)
        return account
    account = SimulationAccount(
        account_name=DEFAULT_ACCOUNT_NAME,
        initial_cash=DEFAULT_INITIAL_CASH,
        available_cash=DEFAULT_INITIAL_CASH,
        frozen_cash=0,
        market_value=0,
        total_assets=DEFAULT_INITIAL_CASH,
        total_profit=0,
        total_return=0,
        max_drawdown=0,
    )
    session.add(account)
    session.flush()
    return account


def _reset_orphan_account(session: Session, account: SimulationAccount) -> None:
    if not _has_no_positions_or_trades(session, account.id):
        return
    account.available_cash = _number(account.initial_cash)
    account.frozen_cash = 0
    account.market_value = 0
    account.total_assets = _number(account.initial_cash)
    account.total_profit = 0
    account.total_return = 0
    account.max_drawdown = 0
    session.execute(delete(SimulationEquity).where(SimulationEquity.account_id == account.id))
    session.flush()


def _has_no_positions_or_trades(session: Session, account_id: int) -> bool:
    position_count = session.scalar(
        select(func.count()).select_from(SimulationPosition).where(SimulationPosition.account_id == account_id)
    )
    trade_count = session.scalar(
        select(func.count()).select_from(SimulationTrade).where(SimulationTrade.account_id == account_id)
    )
    return not position_count and not trade_count


def _sell_positions(session: Session, account: SimulationAccount, trade_date: date, messages: list[str]) -> None:
    positions = session.scalars(
        select(SimulationPosition)
        .where(SimulationPosition.account_id == account.id, SimulationPosition.position_status.in_(ACTIVE_POSITION_STATUSES))
        .order_by(SimulationPosition.stock_code)
    ).all()
    trade_time = _simulation_trade_time(trade_date)
    for position in positions:
        daily = session.scalar(
            select(StockDaily).where(StockDaily.stock_code == position.stock_code, StockDaily.trade_date == trade_date)
        )
        if daily is None:
            messages.append(f"{position.stock_code} 持仓缺少目标交易日日线，暂不卖出")
            continue
        if _number(daily.pct_chg) <= -9.8:
            messages.append(f"{position.stock_code} 目标交易日跌停，按保守成交规则不卖出")
            continue
        sell_action = _sell_action(session, position, daily, trade_date)
        if sell_action is None:
            _refresh_position_price(position, _number(daily.close))
            continue
        quantity, price, reason, final_status = sell_action
        _execute_sell(
            session=session,
            account=account,
            position=position,
            trade_date=trade_date,
            trade_time=trade_time,
            price=price,
            quantity=quantity,
            reason=reason,
            final_status=final_status,
        )


def _buy_triggered_plans(session: Session, account: SimulationAccount, trade_date: date, messages: list[str]) -> None:
    plans = session.scalars(
        select(TradePlan)
        .where(TradePlan.target_trade_date == trade_date, TradePlan.status == "已触发", TradePlan.trigger_price.is_not(None))
        .order_by(desc(TradePlan.stock_score), TradePlan.stock_code)
    ).all()
    trade_time = _simulation_trade_time(trade_date)
    for plan in plans:
        if _number(plan.stop_loss_price) <= 0:
            messages.append(f"{plan.stock_code} 计划缺少有效止损价，按纪律不买入")
            continue
        existing_position = session.scalar(
            select(SimulationPosition).where(
                SimulationPosition.account_id == account.id,
                SimulationPosition.trade_plan_id == plan.id,
                SimulationPosition.position_status == "持仓中",
            )
        )
        existing_buy = session.scalar(
            select(SimulationTrade).where(
                SimulationTrade.account_id == account.id,
                SimulationTrade.trade_plan_id == plan.id,
                SimulationTrade.trade_type == "买入",
            )
        )
        if existing_position is not None or existing_buy is not None:
            continue
        daily = session.scalar(
            select(StockDaily).where(StockDaily.stock_code == plan.stock_code, StockDaily.trade_date == trade_date)
        )
        if daily is None:
            messages.append(f"{plan.stock_code} 计划触发但缺少目标交易日日线，未模拟买入")
            continue
        if _number(daily.pct_chg) >= 9.8:
            messages.append(f"{plan.stock_code} 计划触发但目标交易日涨停，按保守成交规则不买入")
            continue
        if _number(daily.open) > _number(plan.buy_price_high) * 1.03 and _number(daily.low) > _number(plan.buy_price_high):
            messages.append(f"{plan.stock_code} 目标交易日高开超过计划买入上限 3%，且盘中未回落触达买入区间，取消模拟买入")
            continue
        if _number(daily.close) < _number(plan.stop_loss_price) and _number(daily.high) < _number(plan.buy_price_low):
            messages.append(f"{plan.stock_code} 当前/收盘仍低于计划止损价且未重新触达买入区间，取消模拟买入")
            continue

        price = round(_number(plan.trigger_price), 4)
        target_amount = min(_number(account.total_assets) * _number(plan.position_ratio), _number(account.available_cash))
        quantity = int(target_amount // (price * 100)) * 100
        while quantity >= 100:
            amount = round(price * quantity, 4)
            fee = _fees(amount, "买入")
            cost = round(amount + fee["total_fee"], 4)
            if cost <= _number(account.available_cash):
                break
            quantity -= 100
        if quantity < 100:
            messages.append(f"{plan.stock_code} 可用现金不足 100 股，未模拟买入")
            continue

        amount = round(price * quantity, 4)
        fee = _fees(amount, "买入")
        cost = round(amount + fee["total_fee"], 4)
        account.available_cash = round(_number(account.available_cash) - cost, 4)
        reason = plan.tracking_note or plan.buy_condition
        position = SimulationPosition(
            account_id=account.id,
            trade_plan_id=plan.id,
            stock_code=plan.stock_code,
            stock_name=plan.stock_name,
            sector_name=plan.sector_name,
            strategy_type=plan.strategy_type,
            buy_price=price,
            current_price=_number(daily.close),
            quantity=quantity,
            market_value=round(_number(daily.close) * quantity, 4),
            cost_amount=cost,
            unrealized_profit=round(_number(daily.close) * quantity - cost, 4),
            unrealized_return=round((_number(daily.close) * quantity - cost) / cost, 4),
            stop_loss_price=_number(plan.stop_loss_price),
            take_profit_price=_number(plan.take_profit_price),
            position_status="持仓中",
            buy_reason=reason,
            sell_reason="",
        )
        session.add(position)
        session.flush()
        position_ratio_after = _position_ratio_after(account, session)
        session.add(
            SimulationTrade(
                account_id=account.id,
                trade_plan_id=plan.id,
                stock_code=plan.stock_code,
                stock_name=plan.stock_name,
                trade_date=trade_date,
                trade_time=trade_time,
                trade_type="买入",
                price=price,
                quantity=quantity,
                amount=amount,
                commission=fee["commission"],
                stamp_tax=fee["stamp_tax"],
                transfer_fee=fee["transfer_fee"],
                total_fee=fee["total_fee"],
                net_amount=-cost,
                cash_after=_number(account.available_cash),
                position_ratio_after=position_ratio_after,
                profit_loss=None,
                profit_loss_return=None,
                reason=reason,
            )
        )


def _mark_to_market(session: Session, account: SimulationAccount, trade_date: date) -> None:
    positions = session.scalars(
        select(SimulationPosition).where(
            SimulationPosition.account_id == account.id,
            SimulationPosition.position_status.in_(ACTIVE_POSITION_STATUSES),
        )
    ).all()
    for position in positions:
        daily = session.scalar(
            select(StockDaily).where(StockDaily.stock_code == position.stock_code, StockDaily.trade_date == trade_date)
        )
        if daily is not None:
            _refresh_position_price(position, _number(daily.close))
    market_value = round(sum(_number(position.market_value) for position in positions), 4)
    account.market_value = market_value
    account.total_assets = round(_number(account.available_cash) + market_value, 4)
    account.total_profit = round(_number(account.total_assets) - _number(account.initial_cash), 4)
    account.total_return = round(_number(account.total_profit) / _number(account.initial_cash), 4)
    account.max_drawdown = _max_drawdown(session, account, _number(account.total_assets))


def _save_equity(session: Session, account: SimulationAccount, trade_date: date) -> None:
    previous = session.scalar(
        select(SimulationEquity)
        .where(SimulationEquity.account_id == account.id, SimulationEquity.trade_date < trade_date)
        .order_by(desc(SimulationEquity.trade_date))
        .limit(1)
    )
    previous_assets = _number(previous.total_assets) if previous else _number(account.initial_cash)
    daily_profit = round(_number(account.total_assets) - previous_assets, 4)
    daily_return = round(daily_profit / previous_assets, 4) if previous_assets > 0 else 0
    equity = session.scalar(
        select(SimulationEquity).where(SimulationEquity.account_id == account.id, SimulationEquity.trade_date == trade_date)
    )
    payload = {
        "available_cash": _number(account.available_cash),
        "market_value": _number(account.market_value),
        "total_assets": _number(account.total_assets),
        "daily_profit": daily_profit,
        "daily_return": daily_return,
        "max_drawdown": _number(account.max_drawdown),
    }
    if equity is None:
        session.add(SimulationEquity(account_id=account.id, trade_date=trade_date, **payload))
    else:
        for key, value in payload.items():
            setattr(equity, key, value)


def _load_summary(session: Session, account_id: int, as_of_date: date, messages: list[str]) -> SimulationSummary:
    account = session.get(SimulationAccount, account_id)
    positions = session.scalars(
        select(SimulationPosition)
        .where(SimulationPosition.account_id == account_id, SimulationPosition.position_status.in_(ACTIVE_POSITION_STATUSES))
        .order_by(SimulationPosition.stock_code)
    ).all()
    trades = session.scalars(
        select(SimulationTrade)
        .where(SimulationTrade.account_id == account_id)
        .order_by(desc(SimulationTrade.trade_date), desc(SimulationTrade.trade_time), desc(SimulationTrade.id))
    ).all()
    equity = session.scalars(
        _simulation_equity_query(session, account_id)
    ).all()
    position_ratio = round(_number(account.market_value) / _number(account.total_assets), 4) if _number(account.total_assets) > 0 else 0
    risk_stats = _risk_stats(session, account_id)
    return SimulationSummary(
        as_of_date=as_of_date,
        account=_account_snapshot(account),
        positions=[_position_snapshot(item) for item in positions],
        trades=[_trade_snapshot(item) for item in trades],
        equity_curve=[_equity_point(item) for item in equity],
        risk=SimulationRiskSnapshot(
            max_drawdown=_number(account.max_drawdown),
            position_count=len(positions),
            position_ratio=position_ratio,
            win_rate=risk_stats["win_rate"],
            profit_loss_ratio=risk_stats["profit_loss_ratio"],
        ),
        messages=messages,
    )


def _resolve_open_trade_date(session: Session, requested_date: date) -> date:
    calendar = session.scalar(select(TradingCalendar).where(TradingCalendar.trade_date == requested_date))
    if calendar is None or calendar.is_open:
        return requested_date
    next_open = session.scalar(
        select(TradingCalendar.trade_date)
        .where(TradingCalendar.trade_date > requested_date, TradingCalendar.is_open.is_(True))
        .order_by(TradingCalendar.trade_date)
        .limit(1)
    )
    return next_open or requested_date


def _latest_open_equity_date(session: Session, account_id: int) -> Optional[date]:
    query = select(func.max(SimulationEquity.trade_date)).select_from(SimulationEquity).where(SimulationEquity.account_id == account_id)
    if _calendar_has_rows(session):
        query = (
            query.join(TradingCalendar, TradingCalendar.trade_date == SimulationEquity.trade_date)
            .where(TradingCalendar.is_open.is_(True))
        )
    return session.scalar(query)


def _simulation_equity_query(session: Session, account_id: int):
    query = select(SimulationEquity).where(SimulationEquity.account_id == account_id)
    if _calendar_has_rows(session):
        query = query.join(TradingCalendar, TradingCalendar.trade_date == SimulationEquity.trade_date).where(
            TradingCalendar.is_open.is_(True)
        )
    return query.order_by(SimulationEquity.trade_date).limit(30)


def _calendar_has_rows(session: Session) -> bool:
    return bool(session.scalar(select(func.count()).select_from(TradingCalendar)))


def _refresh_position_price(position: SimulationPosition, price: float) -> None:
    position.current_price = price
    position.market_value = round(price * position.quantity, 4)
    position.unrealized_profit = round(_number(position.market_value) - _number(position.cost_amount), 4)
    position.unrealized_return = round(_number(position.unrealized_profit) / _number(position.cost_amount), 4)


def _position_ratio_after(account: SimulationAccount, session: Session) -> float:
    market_value = session.scalar(
        select(func.sum(SimulationPosition.market_value)).where(
            SimulationPosition.account_id == account.id,
            SimulationPosition.position_status.in_(ACTIVE_POSITION_STATUSES),
        )
    )
    total_assets = _number(account.available_cash) + _number(market_value)
    return round(_number(market_value) / total_assets, 4) if total_assets > 0 else 0


def _sell_action(
    session: Session,
    position: SimulationPosition,
    daily: StockDaily,
    trade_date: date,
) -> Optional[tuple[int, float, str, str]]:
    quantity = int(position.quantity)
    if quantity <= 0:
        return None
    if _number(daily.low) <= _number(position.stop_loss_price):
        return quantity, round(min(_number(daily.open), _number(position.stop_loss_price)), 4), "跌破计划止损价，模拟全仓止损", "已清仓"
    if _market_is_risk(session, trade_date):
        return quantity, _sell_at_close(daily), "大盘转风险，模拟卖出剩余仓位", "已清仓"
    if _sector_is_fading(session, position, trade_date):
        return quantity, _sell_at_close(daily), "板块退潮，模拟卖出剩余仓位", "已清仓"
    if _number(daily.pct_chg) <= -7:
        return quantity, _sell_at_close(daily), "快速跳水，按当前价模拟卖出剩余仓位并记录滑点", "已清仓"
    if not _has_sell_reason(session, position, "达到第一止盈位") and _number(daily.high) >= _number(position.take_profit_price):
        sell_quantity = _lot_floor(quantity * 0.5)
        if sell_quantity > 0:
            return sell_quantity, _number(position.take_profit_price), "达到第一止盈位，模拟卖出 50%", "部分止盈"
    if _has_sell_reason(session, position, "达到第一止盈位") and not _has_sell_reason(session, position, "达到第二止盈位"):
        second_take_profit = _second_take_profit_price(position)
        if _number(daily.high) >= second_take_profit:
            sell_quantity = _lot_floor(quantity * 0.6)
            if sell_quantity > 0:
                return sell_quantity, second_take_profit, "达到第二止盈位，模拟再卖出 30%", "部分止盈"
    if _breaks_ma5(session, position.stock_code, trade_date, _number(daily.close)):
        return quantity, _sell_at_close(daily), "跌破 MA5，模拟卖出剩余仓位", "已清仓"
    if _holding_days(session, position, trade_date) >= MAX_HOLDING_DAYS:
        return quantity, _sell_at_close(daily), "持仓超期，按收盘价模拟卖出剩余仓位", "已清仓"
    return None


def _execute_sell(
    session: Session,
    account: SimulationAccount,
    position: SimulationPosition,
    trade_date: date,
    trade_time: datetime,
    price: float,
    quantity: int,
    reason: str,
    final_status: str,
) -> None:
    quantity = min(quantity, int(position.quantity))
    if quantity <= 0:
        return
    original_quantity = int(position.quantity)
    original_cost = _number(position.cost_amount)
    amount = round(price * quantity, 4)
    fee = _fees(amount, "卖出")
    net_amount = round(amount - fee["total_fee"], 4)
    sold_cost = round(original_cost * quantity / original_quantity, 4) if original_quantity > 0 else 0
    profit_loss = round(net_amount - sold_cost, 4)
    profit_loss_return = round(profit_loss / sold_cost, 4) if sold_cost > 0 else None
    account.available_cash = round(_number(account.available_cash) + net_amount, 4)

    remaining_quantity = original_quantity - quantity
    position.sell_reason = reason
    position.current_price = price
    if remaining_quantity <= 0:
        position.position_status = "已清仓"
        position.quantity = 0
        position.market_value = 0
        position.cost_amount = 0
        position.unrealized_profit = 0
        position.unrealized_return = 0
    else:
        position.position_status = final_status
        position.quantity = remaining_quantity
        position.cost_amount = round(original_cost - sold_cost, 4)
        _refresh_position_price(position, price)

    session.flush()
    session.add(
        SimulationTrade(
            account_id=account.id,
            trade_plan_id=position.trade_plan_id,
            stock_code=position.stock_code,
            stock_name=position.stock_name,
            trade_date=trade_date,
            trade_time=trade_time,
            trade_type="卖出",
            price=price,
            quantity=quantity,
            amount=amount,
            commission=fee["commission"],
            stamp_tax=fee["stamp_tax"],
            transfer_fee=fee["transfer_fee"],
            total_fee=fee["total_fee"],
            net_amount=net_amount,
            cash_after=_number(account.available_cash),
            position_ratio_after=_position_ratio_after(account, session),
            profit_loss=profit_loss,
            profit_loss_return=profit_loss_return,
            reason=reason,
        )
    )


def _fees(amount: float, side: str) -> dict[str, float]:
    settings = get_settings()
    commission = max(round(amount * settings.simulation_commission_rate, 4), settings.simulation_min_commission)
    stamp_tax = round(amount * settings.simulation_stamp_tax_rate, 4) if side == "卖出" else 0.0
    transfer_fee = round(amount * settings.simulation_transfer_fee_rate, 4)
    total_fee = round(commission + stamp_tax + transfer_fee, 4)
    return {"commission": commission, "stamp_tax": stamp_tax, "transfer_fee": transfer_fee, "total_fee": total_fee}


def _max_drawdown(session: Session, account: SimulationAccount, current_assets: float) -> float:
    previous_peak = session.scalar(
        select(func.max(SimulationEquity.total_assets)).where(SimulationEquity.account_id == account.id)
    )
    peak = max(_number(previous_peak), current_assets, _number(account.initial_cash))
    drawdown = round((peak - current_assets) / peak, 4) if peak > 0 else 0
    return max(_number(account.max_drawdown), drawdown)


def _risk_stats(session: Session, account_id: int) -> dict[str, Optional[float]]:
    sells = session.scalars(
        select(SimulationTrade).where(
            SimulationTrade.account_id == account_id,
            SimulationTrade.trade_type == "卖出",
            SimulationTrade.profit_loss.is_not(None),
        )
    ).all()
    if not sells:
        return {"win_rate": 0.0, "profit_loss_ratio": None}
    profits = [_number(item.profit_loss) for item in sells]
    wins = [item for item in profits if item > 0]
    losses = [item for item in profits if item < 0]
    win_rate = round(len(wins) / len(profits), 4)
    if not wins or not losses:
        return {"win_rate": win_rate, "profit_loss_ratio": None}
    avg_win = sum(wins) / len(wins)
    avg_loss = abs(sum(losses) / len(losses))
    profit_loss_ratio = round(avg_win / avg_loss, 4) if avg_loss > 0 else None
    return {"win_rate": win_rate, "profit_loss_ratio": profit_loss_ratio}


def _account_snapshot(record: SimulationAccount) -> SimulationAccountSnapshot:
    return SimulationAccountSnapshot(
        id=record.id,
        account_name=record.account_name,
        initial_cash=_number(record.initial_cash),
        available_cash=_number(record.available_cash),
        frozen_cash=_number(record.frozen_cash),
        market_value=_number(record.market_value),
        total_assets=_number(record.total_assets),
        total_profit=_number(record.total_profit),
        total_return=_number(record.total_return),
        max_drawdown=_number(record.max_drawdown),
    )


def _position_snapshot(record: SimulationPosition) -> SimulationPositionSnapshot:
    return SimulationPositionSnapshot(
        id=record.id,
        stock_code=record.stock_code,
        stock_name=record.stock_name,
        sector_name=record.sector_name,
        strategy_type=record.strategy_type,
        buy_price=_number(record.buy_price),
        current_price=_number(record.current_price),
        quantity=record.quantity,
        market_value=_number(record.market_value),
        cost_amount=_number(record.cost_amount),
        unrealized_profit=_number(record.unrealized_profit),
        unrealized_return=_number(record.unrealized_return),
        stop_loss_price=_number(record.stop_loss_price),
        take_profit_price=_number(record.take_profit_price),
        position_status=record.position_status,
        buy_reason=record.buy_reason,
        sell_reason=record.sell_reason,
    )


def _trade_snapshot(record: SimulationTrade) -> SimulationTradeSnapshot:
    return SimulationTradeSnapshot(
        id=record.id,
        trade_plan_id=record.trade_plan_id,
        stock_code=record.stock_code,
        stock_name=record.stock_name,
        trade_date=record.trade_date,
        trade_time=record.trade_time,
        trade_type=record.trade_type,
        price=_number(record.price),
        quantity=record.quantity,
        amount=_number(record.amount),
        commission=_number(record.commission),
        stamp_tax=_number(record.stamp_tax),
        transfer_fee=_number(record.transfer_fee),
        total_fee=_number(record.total_fee),
        net_amount=_number(record.net_amount),
        cash_after=_number(record.cash_after),
        position_ratio_after=_number(record.position_ratio_after),
        profit_loss=_optional_number(record.profit_loss),
        profit_loss_return=_optional_number(record.profit_loss_return),
        reason=record.reason,
    )


def _equity_point(record: SimulationEquity) -> SimulationEquityPoint:
    return SimulationEquityPoint(
        trade_date=record.trade_date,
        available_cash=_number(record.available_cash),
        market_value=_number(record.market_value),
        total_assets=_number(record.total_assets),
        daily_profit=_number(record.daily_profit),
        daily_return=_number(record.daily_return),
        max_drawdown=_number(record.max_drawdown),
    )


def _optional_number(value) -> Optional[float]:
    if value is None:
        return None
    return _number(value)


def _number(value) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return float(value or 0)


def _sell_at_close(daily: StockDaily) -> float:
    return round(_number(daily.close), 4)


def _lot_floor(quantity: float) -> int:
    return int(quantity // 100) * 100


def _has_sell_reason(session: Session, position: SimulationPosition, reason_prefix: str) -> bool:
    existing = session.scalar(
        select(SimulationTrade.id).where(
            SimulationTrade.account_id == position.account_id,
            SimulationTrade.trade_plan_id == position.trade_plan_id,
            SimulationTrade.trade_type == "卖出",
            SimulationTrade.reason.like(f"{reason_prefix}%"),
        )
    )
    return existing is not None


def _second_take_profit_price(position: SimulationPosition) -> float:
    first_gap = _number(position.take_profit_price) - _number(position.buy_price)
    return round(_number(position.buy_price) + first_gap * SECOND_TAKE_PROFIT_MULTIPLIER, 4)


def _market_is_risk(session: Session, trade_date: date) -> bool:
    market = session.scalar(select(MarketDaily).where(MarketDaily.trade_date == trade_date))
    return market is not None and market.market_status == "风险"


def _sector_is_fading(session: Session, position: SimulationPosition, trade_date: date) -> bool:
    sector = session.scalar(
        select(SectorDaily).where(
            SectorDaily.trade_date == trade_date,
            SectorDaily.sector_name == position.sector_name,
        )
    )
    if sector is None:
        return False
    return _number(sector.daily_return) <= -3 or _number(sector.sector_score) < 40 or int(sector.strong_stock_count) == 0


def _breaks_ma5(session: Session, stock_code: str, trade_date: date, close_price: float) -> bool:
    closes = session.scalars(
        select(StockDaily.close)
        .where(StockDaily.stock_code == stock_code, StockDaily.trade_date <= trade_date)
        .order_by(desc(StockDaily.trade_date))
        .limit(5)
    ).all()
    if len(closes) < 5:
        return False
    ma5 = sum(_number(item) for item in closes) / 5
    return close_price < ma5


def _holding_days(session: Session, position: SimulationPosition, trade_date: date) -> int:
    first_buy_date = session.scalar(
        select(func.min(SimulationTrade.trade_date)).where(
            SimulationTrade.account_id == position.account_id,
            SimulationTrade.trade_plan_id == position.trade_plan_id,
            SimulationTrade.trade_type == "买入",
        )
    )
    if first_buy_date is None:
        return 0
    return (trade_date - first_buy_date).days


def _is_trading_time(now: datetime) -> bool:
    local_now = now.astimezone(TRADING_TZ)
    current_time = local_now.time()
    return (TRADING_START <= current_time <= TRADING_MORNING_END) or (
        TRADING_AFTERNOON_START <= current_time <= TRADING_END
    )


def _simulation_trade_time(trade_date: date) -> datetime:
    local_now = datetime.now(TRADING_TZ)
    if local_now.date() != trade_date:
        return _local_trade_datetime(trade_date, TRADING_START)

    current_time = local_now.time()
    if _is_trading_time(local_now):
        return local_now
    if current_time < TRADING_START:
        return _local_trade_datetime(trade_date, TRADING_START)
    if current_time < TRADING_AFTERNOON_START:
        return _local_trade_datetime(trade_date, TRADING_MORNING_END)
    return _local_trade_datetime(trade_date, TRADING_END)


def _local_trade_datetime(trade_date: date, trade_time: time) -> datetime:
    return datetime.combine(trade_date, trade_time).replace(tzinfo=TRADING_TZ)
