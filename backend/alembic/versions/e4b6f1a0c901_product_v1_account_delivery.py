"""Add Product V1 account recovery, identity and email delivery records.

Revision ID: e4b6f1a0c901
Revises: d3a9f6c1b208
Create Date: 2026-07-22
"""
from alembic import op
import sqlalchemy as sa

revision = "e4b6f1a0c901"
down_revision = "d3a9f6c1b208"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
        batch.alter_column("password_hash", existing_type=sa.String(length=255), nullable=True)
    # Existing password accounts pre-date verification and remain usable after upgrade.
    op.execute("UPDATE users SET email_verified_at = CURRENT_TIMESTAMP WHERE email_verified_at IS NULL")
    # Email delivery is opt-in; older UI versions could not express consent.
    op.execute("UPDATE alert_configs SET email_enabled = false")
    op.create_table(
        "account_action_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("purpose", sa.String(length=40), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_account_action_tokens_user_id", "account_action_tokens", ["user_id"])
    op.create_index("ix_account_action_tokens_token_hash", "account_action_tokens", ["token_hash"])
    op.create_index("ix_action_tokens_user_purpose", "account_action_tokens", ["user_id", "purpose"])
    op.create_table(
        "auth_identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("provider", "subject", name="uq_auth_identity_provider_subject"),
    )
    op.create_index("ix_auth_identities_user_id", "auth_identities", ["user_id"])
    op.create_table(
        "email_outbox",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("recipient", sa.String(length=255), nullable=False),
        sa.Column("template", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("dedup_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("dedup_key", name="uq_email_outbox_dedup_key"),
    )
    op.create_index("ix_email_outbox_user_id", "email_outbox", ["user_id"])
    op.create_index("ix_email_outbox_due", "email_outbox", ["status", "next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_email_outbox_due", table_name="email_outbox")
    op.drop_table("email_outbox")
    op.drop_table("auth_identities")
    op.drop_table("account_action_tokens")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("email_verified_at")
