"""Record durable worker loop health.

Revision ID: a6b7c8d9e0f1
Revises: e9a1c6d4b208
Create Date: 2026-08-21
"""
from alembic import op
import sqlalchemy as sa


revision = "a6b7c8d9e0f1"
down_revision = "e9a1c6d4b208"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "worker_heartbeats",
        sa.Column("worker_name", sa.String(length=64), primary_key=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("worker_heartbeats")
