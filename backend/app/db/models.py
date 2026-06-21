from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=convention)


class MarketDaily(Base):
    __tablename__ = "market_daily"
    __table_args__ = (
        UniqueConstraint("trade_date", name="uq_market_daily_trade_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    market_score: Mapped[int] = mapped_column(Integer, nullable=False)
    market_status: Mapped[str] = mapped_column(String(20), nullable=False)
    up_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    down_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    limit_up_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    limit_down_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_amount: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    suggestion: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SectorDaily(Base):
    __tablename__ = "sector_daily"
    __table_args__ = (
        UniqueConstraint(
            "trade_date", "sector_name", name="uq_sector_daily_trade_date_sector_name"
        ),
        UniqueConstraint("trade_date", "rank_no", name="uq_sector_daily_trade_date_rank_no"),
        Index("ix_sector_daily_trade_date", "trade_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    sector_name: Mapped[str] = mapped_column(String(100), nullable=False)
    rank_no: Mapped[int] = mapped_column(Integer, nullable=False)
    daily_return: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    five_day_return: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    amount_change: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    limit_up_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    strong_stock_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sector_score: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CandidateStock(Base):
    __tablename__ = "candidate_stock"
    __table_args__ = (
        UniqueConstraint(
            "trade_date",
            "stock_code",
            "strategy_type",
            name="uq_candidate_stock_trade_date_stock_strategy",
        ),
        Index("ix_candidate_stock_trade_date", "trade_date"),
        Index("ix_candidate_stock_stock_code", "stock_code"),
        Index("ix_candidate_stock_strategy_type", "strategy_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    stock_code: Mapped[str] = mapped_column(String(20), nullable=False)
    stock_name: Mapped[str] = mapped_column(String(100), nullable=False)
    sector_name: Mapped[str] = mapped_column(String(100), nullable=False)
    sector_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    strategy_type: Mapped[str] = mapped_column(String(40), nullable=False)
    stock_score: Mapped[int] = mapped_column(Integer, nullable=False)
    sector_score: Mapped[int] = mapped_column(Integer, nullable=False)
    close_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(24, 4), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    risk_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TradePlan(Base):
    __tablename__ = "trade_plan"
    __table_args__ = (
        UniqueConstraint(
            "plan_date",
            "target_trade_date",
            "stock_code",
            "strategy_type",
            name="uq_trade_plan_plan_target_stock_strategy",
        ),
        Index("ix_trade_plan_plan_date", "plan_date"),
        Index("ix_trade_plan_target_trade_date", "target_trade_date"),
        Index("ix_trade_plan_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    target_trade_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    stock_code: Mapped[str] = mapped_column(String(20), nullable=False)
    stock_name: Mapped[str] = mapped_column(String(100), nullable=False)
    sector_name: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_type: Mapped[str] = mapped_column(String(40), nullable=False)
    stock_score: Mapped[int] = mapped_column(Integer, nullable=False)
    sector_score: Mapped[int] = mapped_column(Integer, nullable=False)
    market_status: Mapped[str] = mapped_column(String(20), nullable=False)
    buy_condition: Mapped[str] = mapped_column(Text, nullable=False)
    buy_price_low: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    buy_price_high: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    stop_loss_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    take_profit_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    position_ratio: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="待触发")
    trigger_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    trigger_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    tracking_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    risk_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class TradeReview(Base):
    __tablename__ = "trade_review"
    __table_args__ = (
        UniqueConstraint(
            "trade_plan_id", "trade_date", name="uq_trade_review_trade_plan_id_trade_date"
        ),
        Index("ix_trade_review_trade_date", "trade_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade_plan_id: Mapped[int] = mapped_column(
        ForeignKey("trade_plan.id", ondelete="CASCADE"), nullable=False
    )
    trade_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    stock_code: Mapped[str] = mapped_column(String(20), nullable=False)
    stock_name: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_type: Mapped[str] = mapped_column(String(40), nullable=False)
    triggered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    trigger_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    close_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    day_return: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    t5_return: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    max_profit: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    max_loss: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    result: Mapped[str] = mapped_column(String(20), nullable=False, default="观察")
    failure_reason: Mapped[Optional[str]] = mapped_column(String(100))
    discipline_check: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TradingCalendar(Base):
    __tablename__ = "trading_calendar"
    __table_args__ = (
        UniqueConstraint("trade_date", name="uq_trading_calendar_trade_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class StockBasic(Base):
    __tablename__ = "stock_basic"
    __table_args__ = (
        UniqueConstraint("stock_code", name="uq_stock_basic_stock_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_code: Mapped[str] = mapped_column(String(20), nullable=False)
    stock_name: Mapped[str] = mapped_column(String(100), nullable=False)
    market: Mapped[str] = mapped_column(String(20), nullable=False)
    list_date: Mapped[Optional[datetime]] = mapped_column(Date)
    is_st: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class IndexDaily(Base):
    __tablename__ = "index_daily"
    __table_args__ = (
        UniqueConstraint("index_code", "trade_date", name="uq_index_daily_index_code_trade_date"),
        Index("ix_index_daily_trade_date", "trade_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    index_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    open: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    volume: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    amount: Mapped[Optional[float]] = mapped_column(Numeric(24, 4))
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class StockDaily(Base):
    __tablename__ = "stock_daily"
    __table_args__ = (
        UniqueConstraint("stock_code", "trade_date", name="uq_stock_daily_stock_code_trade_date"),
        Index("ix_stock_daily_trade_date", "trade_date"),
        Index("ix_stock_daily_stock_code", "stock_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_code: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    open: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    pre_close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    change: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    pct_chg: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    volume: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(24, 4), nullable=False)
    turnover_rate: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class LimitSnapshot(Base):
    __tablename__ = "limit_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "trade_date",
            "stock_code",
            "limit_status",
            name="uq_limit_snapshot_trade_date_stock_code_limit_status",
        ),
        Index("ix_limit_snapshot_trade_date", "trade_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    stock_code: Mapped[str] = mapped_column(String(20), nullable=False)
    stock_name: Mapped[str] = mapped_column(String(100), nullable=False)
    close_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    pct_chg: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    limit_status: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(24, 4), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SimulationAccount(Base):
    __tablename__ = "simulation_account"
    __table_args__ = (UniqueConstraint("account_name", name="uq_simulation_account_account_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_name: Mapped[str] = mapped_column(String(100), nullable=False)
    initial_cash: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    available_cash: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    frozen_cash: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    market_value: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    total_assets: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    total_profit: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    total_return: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False, default=0)
    max_drawdown: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class SimulationPosition(Base):
    __tablename__ = "simulation_position"
    __table_args__ = (
        UniqueConstraint("account_id", "trade_plan_id", name="uq_sim_position_account_plan"),
        Index("ix_simulation_position_account_id", "account_id"),
        Index("ix_simulation_position_stock_code", "stock_code"),
        Index("ix_simulation_position_status", "position_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("simulation_account.id", ondelete="CASCADE"), nullable=False
    )
    trade_plan_id: Mapped[int] = mapped_column(
        ForeignKey("trade_plan.id", ondelete="CASCADE"), nullable=False
    )
    stock_code: Mapped[str] = mapped_column(String(20), nullable=False)
    stock_name: Mapped[str] = mapped_column(String(100), nullable=False)
    sector_name: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_type: Mapped[str] = mapped_column(String(40), nullable=False)
    buy_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    current_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    market_value: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    cost_amount: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    unrealized_profit: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    unrealized_return: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False, default=0)
    stop_loss_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    take_profit_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    position_status: Mapped[str] = mapped_column(String(20), nullable=False, default="持仓中")
    buy_reason: Mapped[str] = mapped_column(Text, nullable=False)
    sell_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class SimulationTrade(Base):
    __tablename__ = "simulation_trade"
    __table_args__ = (
        Index("ix_simulation_trade_account_id", "account_id"),
        Index("ix_simulation_trade_trade_date", "trade_date"),
        Index("ix_simulation_trade_stock_code", "stock_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("simulation_account.id", ondelete="CASCADE"), nullable=False
    )
    trade_plan_id: Mapped[int] = mapped_column(
        ForeignKey("trade_plan.id", ondelete="CASCADE"), nullable=False
    )
    stock_code: Mapped[str] = mapped_column(String(20), nullable=False)
    stock_name: Mapped[str] = mapped_column(String(100), nullable=False)
    trade_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    trade_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trade_type: Mapped[str] = mapped_column(String(20), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    commission: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    stamp_tax: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    transfer_fee: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    total_fee: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    net_amount: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    cash_after: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    position_ratio_after: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False, default=0)
    profit_loss: Mapped[Optional[float]] = mapped_column(Numeric(20, 4))
    profit_loss_return: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SimulationEquity(Base):
    __tablename__ = "simulation_equity"
    __table_args__ = (
        UniqueConstraint("account_id", "trade_date", name="uq_simulation_equity_account_trade_date"),
        Index("ix_simulation_equity_trade_date", "trade_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("simulation_account.id", ondelete="CASCADE"), nullable=False
    )
    trade_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    available_cash: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    market_value: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    total_assets: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    daily_profit: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    daily_return: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False, default=0)
    max_drawdown: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DataIngestRun(Base):
    __tablename__ = "data_ingest_run"
    __table_args__ = (Index("ix_data_ingest_run_trade_date", "trade_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    trade_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    trading_calendar_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stock_basic_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    index_daily_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stock_daily_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    limit_snapshot_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


metadata = Base.metadata
