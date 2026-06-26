"""Add stock pool ranking and virtual trading tables.

Revision ID: 0012_stock_pool_virtual
Revises: 0011_candidate_nine_turn
"""

from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "0012_stock_pool_virtual"
down_revision: Union[str, None] = "0011_candidate_nine_turn"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "candidate_stock",
        sa.Column("sector_category", sa.String(length=40), nullable=False, server_default=""),
    )
    op.add_column("candidate_stock", sa.Column("stock_pool_rank", sa.Integer(), nullable=True))
    op.create_index("ix_candidate_stock_stock_pool_rank", "candidate_stock", ["stock_pool_rank"])
    op.alter_column("candidate_stock", "sector_category", server_default=None)

    op.create_table(
        "virtual_position",
        sa.Column("id", sa.Integer(), nullable=False),
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
        sa.Column("unrealized_profit", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("unrealized_return", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("stop_loss_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("take_profit_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("first_take_profit_touched", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("first_take_profit_high", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("first_take_profit_protect_price", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("position_status", sa.String(length=20), nullable=False, server_default="持仓中"),
        sa.Column("buy_reason", sa.Text(), nullable=False),
        sa.Column("sell_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["trade_plan_id"], ["trade_plan.id"], name=op.f("fk_virtual_position_trade_plan_id_trade_plan")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_virtual_position")),
        sa.UniqueConstraint("trade_plan_id", name="uq_virtual_position_plan"),
    )
    op.create_index("ix_virtual_position_stock_code", "virtual_position", ["stock_code"])
    op.create_index("ix_virtual_position_status", "virtual_position", ["position_status"])

    op.create_table(
        "virtual_trade",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trade_plan_id", sa.Integer(), nullable=False),
        sa.Column("stock_code", sa.String(length=20), nullable=False),
        sa.Column("stock_name", sa.String(length=100), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("trade_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trade_type", sa.String(length=20), nullable=False),
        sa.Column("price", sa.Numeric(12, 4), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("commission", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("stamp_tax", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("transfer_fee", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("total_fee", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("net_amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("cash_after", sa.Numeric(20, 4), nullable=False),
        sa.Column("position_ratio_after", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("profit_loss", sa.Numeric(20, 4), nullable=True),
        sa.Column("profit_loss_return", sa.Numeric(10, 4), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["trade_plan_id"], ["trade_plan.id"], name=op.f("fk_virtual_trade_trade_plan_id_trade_plan")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_virtual_trade")),
    )
    op.create_index("ix_virtual_trade_stock_code", "virtual_trade", ["stock_code"])
    op.create_index("ix_virtual_trade_trade_date", "virtual_trade", ["trade_date"])


def downgrade() -> None:
    op.drop_index("ix_virtual_trade_trade_date", table_name="virtual_trade")
    op.drop_index("ix_virtual_trade_stock_code", table_name="virtual_trade")
    op.drop_table("virtual_trade")
    op.drop_index("ix_virtual_position_status", table_name="virtual_position")
    op.drop_index("ix_virtual_position_stock_code", table_name="virtual_position")
    op.drop_table("virtual_position")
    op.drop_index("ix_candidate_stock_stock_pool_rank", table_name="candidate_stock")
    op.drop_column("candidate_stock", "stock_pool_rank")
    op.drop_column("candidate_stock", "sector_category")
