"""add_subscriptions_table

Subscription audit trail / provenance for tier changes (Phase 4, audit C1).

Revision ID: 9fcb5c1e42dc
Revises: a6b26bf4e1e8
Create Date: 2026-06-18 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9fcb5c1e42dc'
down_revision: Union[str, None] = 'a6b26bf4e1e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('tier', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('source', sa.String(length=20), nullable=False, server_default='checkout'),
        sa.Column('checkout_ref', sa.String(length=100), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_subscriptions_id'), 'subscriptions', ['id'], unique=False)
    op.create_index(op.f('ix_subscriptions_user_id'), 'subscriptions', ['user_id'], unique=False)
    op.create_index(op.f('ix_subscriptions_checkout_ref'), 'subscriptions', ['checkout_ref'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_subscriptions_checkout_ref'), table_name='subscriptions')
    op.drop_index(op.f('ix_subscriptions_user_id'), table_name='subscriptions')
    op.drop_index(op.f('ix_subscriptions_id'), table_name='subscriptions')
    op.drop_table('subscriptions')
