"""Add evidence-backed client recommendations.

Revision ID: c2f8b3d7e914
Revises: a5e5c8d4f761
Create Date: 2026-07-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2f8b3d7e914"
down_revision: Union[str, None] = "a5e5c8d4f761"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=True),
        sa.Column("alert_id", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("estimated_excess_cost_per_hour_mad", sa.Float(), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"]),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alert_id", name="uq_recommendations_alert_id"),
    )
    op.create_index("ix_recommendations_user_id", "recommendations", ["user_id"], unique=False)
    op.create_index("ix_recommendations_site_id", "recommendations", ["site_id"], unique=False)
    op.create_index("ix_recommendations_alert_id", "recommendations", ["alert_id"], unique=False)
    op.create_index("ix_recommendations_status", "recommendations", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_recommendations_status", table_name="recommendations")
    op.drop_index("ix_recommendations_alert_id", table_name="recommendations")
    op.drop_index("ix_recommendations_site_id", table_name="recommendations")
    op.drop_index("ix_recommendations_user_id", table_name="recommendations")
    op.drop_table("recommendations")
