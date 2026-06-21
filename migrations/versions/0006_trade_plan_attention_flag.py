"""add trade plan attention flag

Revision ID: 0006_trade_plan_attention_flag
Revises: 0005_simulation_trading_tables
Create Date: 2026-06-21 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_trade_plan_attention_flag"
down_revision: Union[str, None] = "0005_simulation_trading_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "trade_plan",
        sa.Column("is_watched", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("trade_plan", "is_watched", server_default=None)


def downgrade() -> None:
    op.drop_column("trade_plan", "is_watched")
