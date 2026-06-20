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


metadata = Base.metadata
