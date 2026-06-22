"""preserve simulation records when trade plans are regenerated

Revision ID: 0008_preserve_simulation_records
Revises: 0007_market_limit_up_height
Create Date: 2026-06-22 00:00:00
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0008_preserve_simulation_records"
down_revision: Union[str, None] = "0007_market_limit_up_height"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "fk_simulation_position_trade_plan_id_trade_plan",
        "simulation_position",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_simulation_position_trade_plan_id_trade_plan"),
        "simulation_position",
        "trade_plan",
        ["trade_plan_id"],
        ["id"],
    )
    op.drop_constraint(
        "fk_simulation_trade_trade_plan_id_trade_plan",
        "simulation_trade",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_simulation_trade_trade_plan_id_trade_plan"),
        "simulation_trade",
        "trade_plan",
        ["trade_plan_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_simulation_position_trade_plan_id_trade_plan",
        "simulation_position",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_simulation_position_trade_plan_id_trade_plan"),
        "simulation_position",
        "trade_plan",
        ["trade_plan_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint(
        "fk_simulation_trade_trade_plan_id_trade_plan",
        "simulation_trade",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_simulation_trade_trade_plan_id_trade_plan"),
        "simulation_trade",
        "trade_plan",
        ["trade_plan_id"],
        ["id"],
        ondelete="CASCADE",
    )
