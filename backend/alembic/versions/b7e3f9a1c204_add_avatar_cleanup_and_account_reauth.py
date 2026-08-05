"""Add retryable avatar cleanup and account-deletion reauthentication.

Revision ID: b7e3f9a1c204
Revises: a8d4c6e2f105
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa


revision = "b7e3f9a1c204"
down_revision = "a8d4c6e2f105"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("oauth_challenges") as batch:
        batch.drop_constraint("ck_oauth_challenges_action", type_="check")
        batch.create_check_constraint(
            "ck_oauth_challenges_action",
            "action IN ('login', 'link', 'delete_account')",
        )

    op.create_table(
        "avatar_cleanup_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("object_key", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_error", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("object_key", name="uq_avatar_cleanup_jobs_object_key"),
        sa.CheckConstraint(
            "status IN ('pending', 'retry', 'dead')",
            name="ck_avatar_cleanup_jobs_status",
        ),
    )
    op.create_index(
        "ix_avatar_cleanup_jobs_due",
        "avatar_cleanup_jobs",
        ["status", "next_attempt_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_avatar_cleanup_jobs_due", table_name="avatar_cleanup_jobs")
    op.drop_table("avatar_cleanup_jobs")
    with op.batch_alter_table("oauth_challenges") as batch:
        batch.drop_constraint("ck_oauth_challenges_action", type_="check")
        batch.create_check_constraint(
            "ck_oauth_challenges_action",
            "action IN ('login', 'link')",
        )
