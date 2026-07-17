"""Add canonical meter ingestion metadata.

Revision ID: d9e1f7c2a4b6
Revises: c4f2a9d18b70
Create Date: 2026-07-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d9e1f7c2a4b6"
down_revision: Union[str, None] = "c4f2a9d18b70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("meters") as batch_op:
        batch_op.add_column(sa.Column("ingestion_key_hash", sa.String(length=64), nullable=True))

    op.create_table(
        "ingestion_batches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("meter_id", sa.Integer(), sa.ForeignKey("meters.id"), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=True),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("meter_id", "idempotency_key", name="uq_ingestion_batches_meter_key"),
    )
    op.create_index("ix_ingestion_batches_meter_id", "ingestion_batches", ["meter_id"])

    with op.batch_alter_table("smart_meter_readings") as batch_op:
        batch_op.add_column(sa.Column("ingestion_batch_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("energy_kwh", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("source", sa.String(length=20), nullable=False, server_default="legacy"))
        batch_op.add_column(sa.Column("quality", sa.String(length=20), nullable=False, server_default="validated"))
        batch_op.create_foreign_key(
            "fk_smart_meter_readings_ingestion_batch_id",
            "ingestion_batches", ["ingestion_batch_id"], ["id"],
        )
    op.create_index("ix_smart_meter_readings_ingestion_batch_id", "smart_meter_readings", ["ingestion_batch_id"])


def downgrade() -> None:
    op.drop_index("ix_smart_meter_readings_ingestion_batch_id", table_name="smart_meter_readings")
    with op.batch_alter_table("smart_meter_readings") as batch_op:
        batch_op.drop_constraint("fk_smart_meter_readings_ingestion_batch_id", type_="foreignkey")
        batch_op.drop_column("quality")
        batch_op.drop_column("source")
        batch_op.drop_column("energy_kwh")
        batch_op.drop_column("ingestion_batch_id")
    op.drop_index("ix_ingestion_batches_meter_id", table_name="ingestion_batches")
    op.drop_table("ingestion_batches")
    with op.batch_alter_table("meters") as batch_op:
        batch_op.drop_column("ingestion_key_hash")
