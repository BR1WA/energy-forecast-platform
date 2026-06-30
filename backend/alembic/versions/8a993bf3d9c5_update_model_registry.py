"""update_model_registry

Revision ID: 8a993bf3d9c5
Revises: f337072baa67
Create Date: 2026-06-30 22:53:19.466308

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '8a993bf3d9c5'
down_revision: Union[str, None] = 'f337072baa67'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the old model_registry table (schema from initial migration)
    op.drop_table('model_registry')

    # Recreate with the new schema (database-agnostic, works on both Postgres and SQLite)
    op.create_table(
        'model_registry',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('version', sa.String(length=20), nullable=False),
        sa.Column('experiment_path', sa.String(length=512), nullable=False),
        sa.Column('model_fingerprint', sa.String(length=64), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('mae', sa.Float(), nullable=True),
        sa.Column('rmse', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_model_registry_id'), 'model_registry', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_model_registry_id'), table_name='model_registry')
    op.drop_table('model_registry')

    # Restore the original schema
    op.create_table(
        'model_registry',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('horizon', sa.Integer(), nullable=False),
        sa.Column('model_name', sa.String(length=50), nullable=False),
        sa.Column('version', sa.String(length=20), nullable=False),
        sa.Column('checkpoint_path', sa.String(length=255), nullable=True),
        sa.Column('metrics', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_model_registry_id', 'model_registry', ['id'], unique=False)
