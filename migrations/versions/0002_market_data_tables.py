"""create market data source tables

Revision ID: 0002_market_data_tables
Revises: 0001_core_mvp_tables
Create Date: 2026-06-20 00:00:01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_market_data_tables"
down_revision: Union[str, None] = "0001_core_mvp_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "trading_calendar",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("is_open", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trading_calendar")),
        sa.UniqueConstraint("trade_date", name="uq_trading_calendar_trade_date"),
    )

    op.create_table(
        "stock_basic",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stock_code", sa.String(length=20), nullable=False),
        sa.Column("stock_name", sa.String(length=100), nullable=False),
        sa.Column("market", sa.String(length=20), nullable=False),
        sa.Column("list_date", sa.Date(), nullable=True),
        sa.Column("is_st", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_basic")),
        sa.UniqueConstraint("stock_code", name="uq_stock_basic_stock_code"),
    )

    op.create_table(
        "index_daily",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("index_code", sa.String(length=20), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(12, 4), nullable=False),
        sa.Column("high", sa.Numeric(12, 4), nullable=False),
        sa.Column("low", sa.Numeric(12, 4), nullable=False),
        sa.Column("close", sa.Numeric(12, 4), nullable=False),
        sa.Column("volume", sa.Numeric(20, 4), nullable=False),
        sa.Column("amount", sa.Numeric(24, 4), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_index_daily")),
        sa.UniqueConstraint("index_code", "trade_date", name="uq_index_daily_index_code_trade_date"),
    )
    op.create_index("ix_index_daily_trade_date", "index_daily", ["trade_date"])

    op.create_table(
        "stock_daily",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stock_code", sa.String(length=20), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(12, 4), nullable=False),
        sa.Column("high", sa.Numeric(12, 4), nullable=False),
        sa.Column("low", sa.Numeric(12, 4), nullable=False),
        sa.Column("close", sa.Numeric(12, 4), nullable=False),
        sa.Column("pre_close", sa.Numeric(12, 4), nullable=False),
        sa.Column("change", sa.Numeric(12, 4), nullable=False),
        sa.Column("pct_chg", sa.Numeric(10, 4), nullable=False),
        sa.Column("volume", sa.Numeric(20, 4), nullable=False),
        sa.Column("amount", sa.Numeric(24, 4), nullable=False),
        sa.Column("turnover_rate", sa.Numeric(10, 4), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_daily")),
        sa.UniqueConstraint("stock_code", "trade_date", name="uq_stock_daily_stock_code_trade_date"),
    )
    op.create_index("ix_stock_daily_stock_code", "stock_daily", ["stock_code"])
    op.create_index("ix_stock_daily_trade_date", "stock_daily", ["trade_date"])

    op.create_table(
        "limit_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("stock_code", sa.String(length=20), nullable=False),
        sa.Column("stock_name", sa.String(length=100), nullable=False),
        sa.Column("close_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("pct_chg", sa.Numeric(10, 4), nullable=False),
        sa.Column("limit_status", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Numeric(24, 4), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_limit_snapshot")),
        sa.UniqueConstraint(
            "trade_date",
            "stock_code",
            "limit_status",
            name="uq_limit_snapshot_trade_date_stock_code_limit_status",
        ),
    )
    op.create_index("ix_limit_snapshot_trade_date", "limit_snapshot", ["trade_date"])

    op.create_table(
        "data_ingest_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("trading_calendar_rows", sa.Integer(), nullable=False),
        sa.Column("stock_basic_rows", sa.Integer(), nullable=False),
        sa.Column("index_daily_rows", sa.Integer(), nullable=False),
        sa.Column("stock_daily_rows", sa.Integer(), nullable=False),
        sa.Column("limit_snapshot_rows", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_ingest_run")),
    )
    op.create_index("ix_data_ingest_run_trade_date", "data_ingest_run", ["trade_date"])


def downgrade() -> None:
    op.drop_index("ix_data_ingest_run_trade_date", table_name="data_ingest_run")
    op.drop_table("data_ingest_run")
    op.drop_index("ix_limit_snapshot_trade_date", table_name="limit_snapshot")
    op.drop_table("limit_snapshot")
    op.drop_index("ix_stock_daily_trade_date", table_name="stock_daily")
    op.drop_index("ix_stock_daily_stock_code", table_name="stock_daily")
    op.drop_table("stock_daily")
    op.drop_index("ix_index_daily_trade_date", table_name="index_daily")
    op.drop_table("index_daily")
    op.drop_table("stock_basic")
    op.drop_table("trading_calendar")
