from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import desc, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.app.db.models import (
    SimulationAccount,
    SimulationEquity,
    SimulationPosition,
    SimulationTrade,
    StockDaily,
    TradePlan,
)

DEFAULT_ACCOUNT_NAME = "默认模拟账户"
DEFAULT_INITIAL_CASH = 1_000_000.0
COMMISSION_RATE = 0.0003
STAMP_TAX_RATE = 0.0005
TRANSFER_FEE_RATE = 0.00001
MIN_COMMISSION = 5.0


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


@dataclass(frozen=True)
class SimulationSummary:
    as_of_date: date
    account: SimulationAccountSnapshot
    positions: list[SimulationPositionSnapshot]
    trades: list[SimulationTradeSnapshot]
    equity_curve: list[SimulationEquityPoint]
    risk: SimulationRiskSnapshot
    messages: list[str]


def run_simulation(engine: Engine, trade_date: date) -> SimulationSummary:
    with Session(engine) as session:
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
        latest_date = session.scalar(
            select(func.max(SimulationEquity.trade_date)).where(SimulationEquity.account_id == account.id)
        )
        if latest_date is None:
            return None
        return _load_summary(session, account.id, latest_date, [])


def _get_or_create_account(session: Session) -> SimulationAccount:
    account = session.scalar(select(SimulationAccount).where(SimulationAccount.account_name == DEFAULT_ACCOUNT_NAME))
    if account is not None:
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


def _sell_positions(session: Session, account: SimulationAccount, trade_date: date, messages: list[str]) -> None:
    positions = session.scalars(
        select(SimulationPosition)
        .where(SimulationPosition.account_id == account.id, SimulationPosition.position_status == "持仓中")
        .order_by(SimulationPosition.stock_code)
    ).all()
    now = datetime.now(timezone.utc)
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
        if _number(daily.low) > _number(position.stop_loss_price):
            _refresh_position_price(position, _number(daily.close))
            continue

        price = round(min(_number(daily.open), _number(position.stop_loss_price)), 4)
        amount = round(price * position.quantity, 4)
        fee = _fees(amount, "卖出")
        net_amount = round(amount - fee["total_fee"], 4)
        profit_loss = round(net_amount - _number(position.cost_amount), 4)
        profit_loss_return = round(profit_loss / _number(position.cost_amount), 4) if _number(position.cost_amount) > 0 else None
        account.available_cash = round(_number(account.available_cash) + net_amount, 4)
        position.sell_reason = "跌破计划止损价，模拟全仓止损"
        position.position_status = "已清仓"
        position.quantity = 0
        position.market_value = 0
        position.unrealized_profit = 0
        position.unrealized_return = 0
        position.current_price = price
        session.add(
            SimulationTrade(
                account_id=account.id,
                trade_plan_id=position.trade_plan_id,
                stock_code=position.stock_code,
                stock_name=position.stock_name,
                trade_date=trade_date,
                trade_time=now,
                trade_type="卖出",
                price=price,
                quantity=position.quantity or int(amount / price),
                amount=amount,
                commission=fee["commission"],
                stamp_tax=fee["stamp_tax"],
                transfer_fee=fee["transfer_fee"],
                total_fee=fee["total_fee"],
                net_amount=net_amount,
                cash_after=_number(account.available_cash),
                position_ratio_after=0,
                profit_loss=profit_loss,
                profit_loss_return=profit_loss_return,
                reason=position.sell_reason,
            )
        )


def _buy_triggered_plans(session: Session, account: SimulationAccount, trade_date: date, messages: list[str]) -> None:
    plans = session.scalars(
        select(TradePlan)
        .where(TradePlan.target_trade_date == trade_date, TradePlan.status == "已触发", TradePlan.trigger_price.is_not(None))
        .order_by(desc(TradePlan.stock_score), TradePlan.stock_code)
    ).all()
    now = datetime.now(timezone.utc)
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
        if _number(daily.open) > _number(plan.buy_price_high) * 1.03:
            messages.append(f"{plan.stock_code} 目标交易日高开超过计划买入上限 3%，取消模拟买入")
            continue
        if _number(daily.open) < _number(plan.stop_loss_price) or _number(daily.low) < _number(plan.stop_loss_price):
            messages.append(f"{plan.stock_code} 目标交易日低开或盘中跌破止损价，取消模拟买入")
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
                trade_time=now,
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
            SimulationPosition.position_status == "持仓中",
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
        .where(SimulationPosition.account_id == account_id, SimulationPosition.position_status == "持仓中")
        .order_by(SimulationPosition.stock_code)
    ).all()
    trades = session.scalars(
        select(SimulationTrade)
        .where(SimulationTrade.account_id == account_id, SimulationTrade.trade_date == as_of_date)
        .order_by(SimulationTrade.id)
    ).all()
    equity = session.scalars(
        select(SimulationEquity)
        .where(SimulationEquity.account_id == account_id)
        .order_by(SimulationEquity.trade_date)
        .limit(30)
    ).all()
    position_ratio = round(_number(account.market_value) / _number(account.total_assets), 4) if _number(account.total_assets) > 0 else 0
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
        ),
        messages=messages,
    )


def _refresh_position_price(position: SimulationPosition, price: float) -> None:
    position.current_price = price
    position.market_value = round(price * position.quantity, 4)
    position.unrealized_profit = round(_number(position.market_value) - _number(position.cost_amount), 4)
    position.unrealized_return = round(_number(position.unrealized_profit) / _number(position.cost_amount), 4)


def _position_ratio_after(account: SimulationAccount, session: Session) -> float:
    market_value = session.scalar(
        select(func.sum(SimulationPosition.market_value)).where(
            SimulationPosition.account_id == account.id,
            SimulationPosition.position_status == "持仓中",
        )
    )
    total_assets = _number(account.available_cash) + _number(market_value)
    return round(_number(market_value) / total_assets, 4) if total_assets > 0 else 0


def _fees(amount: float, side: str) -> dict[str, float]:
    commission = max(round(amount * COMMISSION_RATE, 4), MIN_COMMISSION)
    stamp_tax = round(amount * STAMP_TAX_RATE, 4) if side == "卖出" else 0.0
    transfer_fee = round(amount * TRANSFER_FEE_RATE, 4)
    total_fee = round(commission + stamp_tax + transfer_fee, 4)
    return {"commission": commission, "stamp_tax": stamp_tax, "transfer_fee": transfer_fee, "total_fee": total_fee}


def _max_drawdown(session: Session, account: SimulationAccount, current_assets: float) -> float:
    previous_peak = session.scalar(
        select(func.max(SimulationEquity.total_assets)).where(SimulationEquity.account_id == account.id)
    )
    peak = max(_number(previous_peak), current_assets, _number(account.initial_cash))
    drawdown = round((peak - current_assets) / peak, 4) if peak > 0 else 0
    return max(_number(account.max_drawdown), drawdown)


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
