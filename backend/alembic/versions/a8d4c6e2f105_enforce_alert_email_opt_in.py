"""Enforce opt-in defaults for critical-alert email.

Revision ID: a8d4c6e2f105
Revises: f5c7a2d1e013
Create Date: 2026-07-22
"""
from alembic import op
import sqlalchemy as sa


revision = "a8d4c6e2f105"
down_revision = "f5c7a2d1e013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE alert_configs SET email_enabled = false WHERE email_enabled IS NULL")
    with op.batch_alter_table("alert_configs") as batch:
        batch.alter_column(
            "email_enabled",
            existing_type=sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        )


def downgrade() -> None:
    with op.batch_alter_table("alert_configs") as batch:
        batch.alter_column(
            "email_enabled",
            existing_type=sa.Boolean(),
            nullable=True,
            server_default=None,
        )
