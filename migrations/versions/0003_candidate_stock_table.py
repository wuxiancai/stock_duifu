"""create candidate stock table

Revision ID: 0003_candidate_stock_table
Revises: 0002_market_data_tables
Create Date: 2026-06-21 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_candidate_stock_table"
down_revision: Union[str, None] = "0002_market_data_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "candidate_stock",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("stock_code", sa.String(length=20), nullable=False),
        sa.Column("stock_name", sa.String(length=100), nullable=False),
        sa.Column("sector_name", sa.String(length=100), nullable=False),
        sa.Column("sector_rank", sa.Integer(), nullable=False),
        sa.Column("strategy_type", sa.String(length=40), nullable=False),
        sa.Column("stock_score", sa.Integer(), nullable=False),
        sa.Column("sector_score", sa.Integer(), nullable=False),
        sa.Column("close_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("amount", sa.Numeric(24, 4), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("risk_note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidate_stock")),
        sa.UniqueConstraint(
            "trade_date",
            "stock_code",
            "strategy_type",
            name="uq_candidate_stock_trade_date_stock_strategy",
        ),
    )
    op.create_index("ix_candidate_stock_trade_date", "candidate_stock", ["trade_date"])
    op.create_index("ix_candidate_stock_stock_code", "candidate_stock", ["stock_code"])
    op.create_index("ix_candidate_stock_strategy_type", "candidate_stock", ["strategy_type"])


def downgrade() -> None:
    op.drop_index("ix_candidate_stock_strategy_type", table_name="candidate_stock")
    op.drop_index("ix_candidate_stock_stock_code", table_name="candidate_stock")
    op.drop_index("ix_candidate_stock_trade_date", table_name="candidate_stock")
    op.drop_table("candidate_stock")
