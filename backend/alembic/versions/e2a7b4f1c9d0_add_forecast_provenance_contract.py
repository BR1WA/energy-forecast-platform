"""Add forecast provenance and artifact contract metadata.

Revision ID: e2a7b4f1c9d0
Revises: d9e1f7c2a4b6
Create Date: 2026-07-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e2a7b4f1c9d0"
down_revision: Union[str, None] = "d9e1f7c2a4b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("model_registry") as batch_op:
        batch_op.add_column(sa.Column("artifact_contract", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("contract_validated_at", sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table("forecasts") as batch_op:
        batch_op.add_column(sa.Column("model_registry_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("horizon", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("input_source", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("input_snapshot", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("confidence_method", sa.String(length=120), nullable=True))
        batch_op.create_foreign_key("fk_forecasts_model_registry_id", "model_registry", ["model_registry_id"], ["id"])
    op.create_index("ix_forecasts_model_registry_id", "forecasts", ["model_registry_id"])


def downgrade() -> None:
    op.drop_index("ix_forecasts_model_registry_id", table_name="forecasts")
    with op.batch_alter_table("forecasts") as batch_op:
        batch_op.drop_constraint("fk_forecasts_model_registry_id", type_="foreignkey")
        batch_op.drop_column("confidence_method")
        batch_op.drop_column("input_snapshot")
        batch_op.drop_column("input_source")
        batch_op.drop_column("horizon")
        batch_op.drop_column("model_registry_id")
    with op.batch_alter_table("model_registry") as batch_op:
        batch_op.drop_column("contract_validated_at")
        batch_op.drop_column("artifact_contract")
