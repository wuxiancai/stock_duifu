"""add simulation trading tables

Revision ID: 0005_simulation_trading_tables
Revises: 0004_trade_plan_tracking_fields
Create Date: 2026-06-21 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_simulation_trading_tables"
down_revision: Union[str, None] = "0004_trade_plan_tracking_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "simulation_account",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_name", sa.String(length=100), nullable=False),
        sa.Column("initial_cash", sa.Numeric(20, 4), nullable=False),
        sa.Column("available_cash", sa.Numeric(20, 4), nullable=False),
        sa.Column("frozen_cash", sa.Numeric(20, 4), nullable=False),
        sa.Column("market_value", sa.Numeric(20, 4), nullable=False),
        sa.Column("total_assets", sa.Numeric(20, 4), nullable=False),
        sa.Column("total_profit", sa.Numeric(20, 4), nullable=False),
        sa.Column("total_return", sa.Numeric(10, 4), nullable=False),
        sa.Column("max_drawdown", sa.Numeric(10, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_simulation_account")),
        sa.UniqueConstraint("account_name", name="uq_simulation_account_account_name"),
    )
    op.create_table(
        "simulation_position",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("trade_plan_id", sa.Integer(), nullable=False),
        sa.Column("stock_code", sa.String(length=20), nullable=False),
        sa.Column("stock_name", sa.String(length=100), nullable=False),
        sa.Column("sector_name", sa.String(length=100), nullable=False),
        sa.Column("strategy_type", sa.String(length=40), nullable=False),
        sa.Column("buy_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("current_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("market_value", sa.Numeric(20, 4), nullable=False),
        sa.Column("cost_amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("unrealized_profit", sa.Numeric(20, 4), nullable=False),
        sa.Column("unrealized_return", sa.Numeric(10, 4), nullable=False),
        sa.Column("stop_loss_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("take_profit_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("position_status", sa.String(length=20), nullable=False),
        sa.Column("buy_reason", sa.Text(), nullable=False),
        sa.Column("sell_reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["simulation_account.id"], name=op.f("fk_simulation_position_account_id_simulation_account"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trade_plan_id"], ["trade_plan.id"], name=op.f("fk_simulation_position_trade_plan_id_trade_plan"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_simulation_position")),
        sa.UniqueConstraint("account_id", "trade_plan_id", name="uq_sim_position_account_plan"),
    )
    op.create_index("ix_simulation_position_account_id", "simulation_position", ["account_id"])
    op.create_index("ix_simulation_position_stock_code", "simulation_position", ["stock_code"])
    op.create_index("ix_simulation_position_status", "simulation_position", ["position_status"])
    op.create_table(
        "simulation_trade",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("trade_plan_id", sa.Integer(), nullable=False),
        sa.Column("stock_code", sa.String(length=20), nullable=False),
        sa.Column("stock_name", sa.String(length=100), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("trade_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trade_type", sa.String(length=20), nullable=False),
        sa.Column("price", sa.Numeric(12, 4), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("commission", sa.Numeric(12, 4), nullable=False),
        sa.Column("stamp_tax", sa.Numeric(12, 4), nullable=False),
        sa.Column("transfer_fee", sa.Numeric(12, 4), nullable=False),
        sa.Column("total_fee", sa.Numeric(12, 4), nullable=False),
        sa.Column("net_amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("cash_after", sa.Numeric(20, 4), nullable=False),
        sa.Column("position_ratio_after", sa.Numeric(10, 4), nullable=False),
        sa.Column("profit_loss", sa.Numeric(20, 4), nullable=True),
        sa.Column("profit_loss_return", sa.Numeric(10, 4), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["simulation_account.id"], name=op.f("fk_simulation_trade_account_id_simulation_account"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trade_plan_id"], ["trade_plan.id"], name=op.f("fk_simulation_trade_trade_plan_id_trade_plan"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_simulation_trade")),
    )
    op.create_index("ix_simulation_trade_account_id", "simulation_trade", ["account_id"])
    op.create_index("ix_simulation_trade_trade_date", "simulation_trade", ["trade_date"])
    op.create_index("ix_simulation_trade_stock_code", "simulation_trade", ["stock_code"])
    op.create_table(
        "simulation_equity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("available_cash", sa.Numeric(20, 4), nullable=False),
        sa.Column("market_value", sa.Numeric(20, 4), nullable=False),
        sa.Column("total_assets", sa.Numeric(20, 4), nullable=False),
        sa.Column("daily_profit", sa.Numeric(20, 4), nullable=False),
        sa.Column("daily_return", sa.Numeric(10, 4), nullable=False),
        sa.Column("max_drawdown", sa.Numeric(10, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["simulation_account.id"], name=op.f("fk_simulation_equity_account_id_simulation_account"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_simulation_equity")),
        sa.UniqueConstraint("account_id", "trade_date", name="uq_simulation_equity_account_trade_date"),
    )
    op.create_index("ix_simulation_equity_trade_date", "simulation_equity", ["trade_date"])


def downgrade() -> None:
    op.drop_index("ix_simulation_equity_trade_date", table_name="simulation_equity")
    op.drop_table("simulation_equity")
    op.drop_index("ix_simulation_trade_stock_code", table_name="simulation_trade")
    op.drop_index("ix_simulation_trade_trade_date", table_name="simulation_trade")
    op.drop_index("ix_simulation_trade_account_id", table_name="simulation_trade")
    op.drop_table("simulation_trade")
    op.drop_index("ix_simulation_position_status", table_name="simulation_position")
    op.drop_index("ix_simulation_position_stock_code", table_name="simulation_position")
    op.drop_index("ix_simulation_position_account_id", table_name="simulation_position")
    op.drop_table("simulation_position")
    op.drop_table("simulation_account")
