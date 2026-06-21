"""add trade plan tracking fields

Revision ID: 0004_trade_plan_tracking_fields
Revises: 0003_candidate_stock_table
Create Date: 2026-06-21 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_trade_plan_tracking_fields"
down_revision: Union[str, None] = "0003_candidate_stock_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("trade_plan", sa.Column("trigger_price", sa.Numeric(12, 4), nullable=True))
    op.add_column("trade_plan", sa.Column("trigger_time", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "trade_plan",
        sa.Column("tracking_note", sa.Text(), nullable=False, server_default=""),
    )
    op.alter_column("trade_plan", "tracking_note", server_default=None)


def downgrade() -> None:
    op.drop_column("trade_plan", "tracking_note")
    op.drop_column("trade_plan", "trigger_time")
    op.drop_column("trade_plan", "trigger_price")
