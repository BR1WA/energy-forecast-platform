"""Enforce telemetry and model integrity and add audit events.

Revision ID: f4d2e8a6b7c1
Revises: e2a7b4f1c9d0
Create Date: 2026-07-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f4d2e8a6b7c1"
down_revision: Union[str, None] = "e2a7b4f1c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Keep the oldest imported reading when legacy data contains an exact duplicate.
    op.execute(
        "DELETE FROM smart_meter_readings WHERE id NOT IN "
        "(SELECT MIN(id) FROM smart_meter_readings GROUP BY meter_id, timestamp)"
    )
    with op.batch_alter_table("smart_meter_readings") as batch_op:
        batch_op.create_unique_constraint(
            "uq_smart_meter_readings_meter_timestamp", ["meter_id", "timestamp"]
        )

    # Existing registries may contain multiple active entries from before the
    # promotion contract. Retain the newest row in each dataset/horizon pair.
    op.execute(
        "UPDATE model_registry SET active = false WHERE id IN ("
        "SELECT id FROM ("
        "SELECT id, ROW_NUMBER() OVER (PARTITION BY dataset, horizon ORDER BY updated_at DESC, id DESC) AS row_num "
        "FROM model_registry WHERE active = true"
        ") ranked WHERE row_num > 1)"
    )
    op.create_index(
        "uq_model_registry_active_dataset_horizon",
        "model_registry",
        ["dataset", "horizon"],
        unique=True,
        postgresql_where=sa.text("active IS TRUE"),
        sqlite_where=sa.text("active = 1"),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("target_user_id", sa.Integer(), nullable=True),
        sa.Column("site_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("target", sa.String(length=160), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"])
    op.create_index("ix_audit_events_target_user_id", "audit_events", ["target_user_id"])
    op.create_index("ix_audit_events_site_id", "audit_events", ["site_id"])
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_event_type", table_name="audit_events")
    op.drop_index("ix_audit_events_site_id", table_name="audit_events")
    op.drop_index("ix_audit_events_target_user_id", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_user_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("uq_model_registry_active_dataset_horizon", table_name="model_registry")
    with op.batch_alter_table("smart_meter_readings") as batch_op:
        batch_op.drop_constraint("uq_smart_meter_readings_meter_timestamp", type_="unique")
