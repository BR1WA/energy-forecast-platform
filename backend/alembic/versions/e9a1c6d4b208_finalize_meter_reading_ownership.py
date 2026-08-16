"""Finalize the non-null telemetry ownership contract.

Revision ID: e9a1c6d4b208
Revises: c8f4a1b2d306
Create Date: 2026-08-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e9a1c6d4b208"
down_revision: Union[str, None] = "c8f4a1b2d306"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    orphan_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM smart_meter_readings WHERE meter_id IS NULL")
    ).scalar_one()
    if orphan_count:
        raise RuntimeError(
            "Cannot make smart_meter_readings.meter_id non-null while orphaned "
            f"rows remain ({orphan_count} found)."
        )

    with op.batch_alter_table("smart_meter_readings") as batch_op:
        batch_op.alter_column(
            "meter_id",
            existing_type=sa.Integer(),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("smart_meter_readings") as batch_op:
        batch_op.alter_column(
            "meter_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
