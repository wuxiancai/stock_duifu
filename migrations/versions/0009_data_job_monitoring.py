"""add data job monitoring tables

Revision ID: 0009_data_job_monitoring
Revises: 0008_preserve_simulation_records
Create Date: 2026-06-23 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0009_data_job_monitoring"
down_revision: Union[str, None] = "0008_preserve_simulation_records"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "data_job_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_name", sa.String(length=80), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("command", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_job_run")),
    )
    op.create_index("ix_data_job_run_started_at", "data_job_run", ["started_at"])
    op.create_index("ix_data_job_run_trade_date", "data_job_run", ["trade_date"])

    op.create_table(
        "data_job_step",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("step_name", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rows_count", sa.Integer(), nullable=False),
        sa.Column("summary_json", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["data_job_run.id"],
            name=op.f("fk_data_job_step_run_id_data_job_run"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_job_step")),
    )
    op.create_index("ix_data_job_step_run_id", "data_job_step", ["run_id"])
    op.create_index("ix_data_job_step_status", "data_job_step", ["status"])


def downgrade() -> None:
    op.drop_index("ix_data_job_step_status", table_name="data_job_step")
    op.drop_index("ix_data_job_step_run_id", table_name="data_job_step")
    op.drop_table("data_job_step")
    op.drop_index("ix_data_job_run_trade_date", table_name="data_job_run")
    op.drop_index("ix_data_job_run_started_at", table_name="data_job_run")
    op.drop_table("data_job_run")
