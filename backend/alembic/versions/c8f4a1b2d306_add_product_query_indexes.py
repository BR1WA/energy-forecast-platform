"""Add indexes justified by Product V1 query measurements.

Revision ID: c8f4a1b2d306
Revises: b7e3f9a1c204
Create Date: 2026-07-23
"""
from alembic import op


revision = "c8f4a1b2d306"
down_revision = "b7e3f9a1c204"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_forecasts_user_created",
        "forecasts",
        ["user_id", "created_at", "id"],
    )
    op.create_index(
        "ix_alerts_user_created",
        "alerts",
        ["user_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_alerts_user_created", table_name="alerts")
    op.drop_index("ix_forecasts_user_created", table_name="forecasts")
