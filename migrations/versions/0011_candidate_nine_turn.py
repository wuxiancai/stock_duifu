"""add candidate nine turn fields

Revision ID: 0011_candidate_nine_turn
Revises: 0010_trailing_take_profit
Create Date: 2026-06-26 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0011_candidate_nine_turn"
down_revision: Union[str, None] = "0010_trailing_take_profit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("candidate_stock", sa.Column("nine_turn_signal", sa.String(length=10), nullable=False, server_default=""))
    op.add_column("candidate_stock", sa.Column("nine_turn_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("candidate_stock", sa.Column("nine_turn_score", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("candidate_stock", "nine_turn_score")
    op.drop_column("candidate_stock", "nine_turn_count")
    op.drop_column("candidate_stock", "nine_turn_signal")
