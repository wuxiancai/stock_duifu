"""add simulation trailing take profit state

Revision ID: 0010_simulation_trailing_take_profit
Revises: 0009_data_job_monitoring
Create Date: 2026-06-26 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010_simulation_trailing_take_profit"
down_revision: Union[str, None] = "0009_data_job_monitoring"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "simulation_position",
        sa.Column("first_take_profit_touched", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "simulation_position",
        sa.Column("first_take_profit_high", sa.Numeric(12, 4), nullable=False, server_default="0"),
    )
    op.add_column(
        "simulation_position",
        sa.Column("first_take_profit_protect_price", sa.Numeric(12, 4), nullable=False, server_default="0"),
    )
    op.alter_column("simulation_position", "first_take_profit_touched", server_default=None)
    op.alter_column("simulation_position", "first_take_profit_high", server_default=None)
    op.alter_column("simulation_position", "first_take_profit_protect_price", server_default=None)


def downgrade() -> None:
    op.drop_column("simulation_position", "first_take_profit_protect_price")
    op.drop_column("simulation_position", "first_take_profit_high")
    op.drop_column("simulation_position", "first_take_profit_touched")
