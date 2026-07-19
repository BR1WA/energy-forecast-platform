"""Add persisted alert-rule evidence and lifecycle fields.

Revision ID: a5e5c8d4f761
Revises: f4d2e8a6b7c1
Create Date: 2026-07-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a5e5c8d4f761"
down_revision: Union[str, None] = "f4d2e8a6b7c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("alert_configs") as batch_op:
        batch_op.add_column(sa.Column("cooldown_minutes", sa.Integer(), nullable=False, server_default="60"))
        batch_op.add_column(sa.Column("missing_data_minutes", sa.Integer(), nullable=False, server_default="60"))

    with op.batch_alter_table("alerts") as batch_op:
        batch_op.add_column(sa.Column("rule_key", sa.String(length=160), nullable=True))
        batch_op.add_column(sa.Column("evidence_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_alerts_site_rule_created", "alerts", ["site_id", "rule_key", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_alerts_site_rule_created", table_name="alerts")
    with op.batch_alter_table("alerts") as batch_op:
        batch_op.drop_column("resolved_at")
        batch_op.drop_column("acknowledged_at")
        batch_op.drop_column("evidence_json")
        batch_op.drop_column("rule_key")
    with op.batch_alter_table("alert_configs") as batch_op:
        batch_op.drop_column("missing_data_minutes")
        batch_op.drop_column("cooldown_minutes")
