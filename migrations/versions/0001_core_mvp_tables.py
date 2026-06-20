"""create core mvp tables

Revision ID: 0001_core_mvp_tables
Revises:
Create Date: 2026-06-20 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_core_mvp_tables"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_daily",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("market_score", sa.Integer(), nullable=False),
        sa.Column("market_status", sa.String(length=20), nullable=False),
        sa.Column("up_count", sa.Integer(), nullable=False),
        sa.Column("down_count", sa.Integer(), nullable=False),
        sa.Column("limit_up_count", sa.Integer(), nullable=False),
        sa.Column("limit_down_count", sa.Integer(), nullable=False),
        sa.Column("total_amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("suggestion", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_market_daily")),
        sa.UniqueConstraint("trade_date", name="uq_market_daily_trade_date"),
    )

    op.create_table(
        "sector_daily",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("sector_name", sa.String(length=100), nullable=False),
        sa.Column("rank_no", sa.Integer(), nullable=False),
        sa.Column("daily_return", sa.Numeric(10, 4), nullable=False),
        sa.Column("five_day_return", sa.Numeric(10, 4), nullable=False),
        sa.Column("amount_change", sa.Numeric(12, 4), nullable=False),
        sa.Column("limit_up_count", sa.Integer(), nullable=False),
        sa.Column("strong_stock_count", sa.Integer(), nullable=False),
        sa.Column("sector_score", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sector_daily")),
        sa.UniqueConstraint("trade_date", "rank_no", name="uq_sector_daily_trade_date_rank_no"),
        sa.UniqueConstraint("trade_date", "sector_name", name="uq_sector_daily_trade_date_sector_name"),
    )
    op.create_index("ix_sector_daily_trade_date", "sector_daily", ["trade_date"])

    op.create_table(
        "trade_plan",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("target_trade_date", sa.Date(), nullable=False),
        sa.Column("stock_code", sa.String(length=20), nullable=False),
        sa.Column("stock_name", sa.String(length=100), nullable=False),
        sa.Column("sector_name", sa.String(length=100), nullable=False),
        sa.Column("strategy_type", sa.String(length=40), nullable=False),
        sa.Column("stock_score", sa.Integer(), nullable=False),
        sa.Column("sector_score", sa.Integer(), nullable=False),
        sa.Column("market_status", sa.String(length=20), nullable=False),
        sa.Column("buy_condition", sa.Text(), nullable=False),
        sa.Column("buy_price_low", sa.Numeric(12, 4), nullable=False),
        sa.Column("buy_price_high", sa.Numeric(12, 4), nullable=False),
        sa.Column("stop_loss_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("take_profit_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("position_ratio", sa.Numeric(8, 4), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("risk_note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trade_plan")),
        sa.UniqueConstraint(
            "plan_date",
            "target_trade_date",
            "stock_code",
            "strategy_type",
            name="uq_trade_plan_plan_target_stock_strategy",
        ),
    )
    op.create_index("ix_trade_plan_plan_date", "trade_plan", ["plan_date"])
    op.create_index("ix_trade_plan_status", "trade_plan", ["status"])
    op.create_index("ix_trade_plan_target_trade_date", "trade_plan", ["target_trade_date"])

    op.create_table(
        "trade_review",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trade_plan_id", sa.Integer(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("stock_code", sa.String(length=20), nullable=False),
        sa.Column("stock_name", sa.String(length=100), nullable=False),
        sa.Column("strategy_type", sa.String(length=40), nullable=False),
        sa.Column("triggered", sa.Boolean(), nullable=False),
        sa.Column("trigger_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("close_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("day_return", sa.Numeric(10, 4), nullable=True),
        sa.Column("t5_return", sa.Numeric(10, 4), nullable=True),
        sa.Column("max_profit", sa.Numeric(10, 4), nullable=True),
        sa.Column("max_loss", sa.Numeric(10, 4), nullable=True),
        sa.Column("result", sa.String(length=20), nullable=False),
        sa.Column("failure_reason", sa.String(length=100), nullable=True),
        sa.Column("discipline_check", sa.Boolean(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["trade_plan_id"], ["trade_plan.id"], name=op.f("fk_trade_review_trade_plan_id_trade_plan"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trade_review")),
        sa.UniqueConstraint("trade_plan_id", "trade_date", name="uq_trade_review_trade_plan_id_trade_date"),
    )
    op.create_index("ix_trade_review_trade_date", "trade_review", ["trade_date"])


def downgrade() -> None:
    op.drop_index("ix_trade_review_trade_date", table_name="trade_review")
    op.drop_table("trade_review")
    op.drop_index("ix_trade_plan_target_trade_date", table_name="trade_plan")
    op.drop_index("ix_trade_plan_status", table_name="trade_plan")
    op.drop_index("ix_trade_plan_plan_date", table_name="trade_plan")
    op.drop_table("trade_plan")
    op.drop_index("ix_sector_daily_trade_date", table_name="sector_daily")
    op.drop_table("sector_daily")
    op.drop_table("market_daily")

