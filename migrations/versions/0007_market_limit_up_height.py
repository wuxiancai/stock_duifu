"""add market limit up height

Revision ID: 0007_market_limit_up_height
Revises: 0006_trade_plan_attention_flag
Create Date: 2026-06-21 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007_market_limit_up_height"
down_revision: Union[str, None] = "0006_trade_plan_attention_flag"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "market_daily",
        sa.Column("limit_up_height", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("market_daily", "limit_up_height", server_default=None)


def downgrade() -> None:
    op.drop_column("market_daily", "limit_up_height")
