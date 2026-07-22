"""Harden Product V1 identity and email outbox contracts.

Revision ID: f5c7a2d1e013
Revises: e4b6f1a0c901
Create Date: 2026-07-22
"""
from alembic import op
import sqlalchemy as sa

revision = "f5c7a2d1e013"
down_revision = "e4b6f1a0c901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE account_action_tokens SET purpose = 'reset_password' WHERE purpose = 'password_reset'"))
    bind.execute(sa.text("UPDATE email_outbox SET status = 'dead' WHERE status = 'failed'"))

    with op.batch_alter_table("account_action_tokens") as batch:
        batch.add_column(sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_check_constraint(
            "ck_account_action_tokens_purpose",
            "purpose IN ('verify_email', 'reset_password')",
        )
    # Terra's partial implementation stored raw action-token URLs in JSON. They
    # cannot be safely transformed without re-exposing the token, so remove the
    # affected delivery rows and revoke every outstanding legacy action token.
    # Users can request a fresh link through the sealed render-time flow.
    bind.execute(sa.text(
        "UPDATE account_action_tokens SET revoked_at = CURRENT_TIMESTAMP "
        "WHERE used_at IS NULL AND revoked_at IS NULL"
    ))
    bind.execute(sa.text(
        "DELETE FROM email_outbox WHERE template IN ('verify_email', 'password_reset')"
    ))

    with op.batch_alter_table("auth_identities") as batch:
        batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
        batch.create_unique_constraint("uq_auth_identity_user_provider", ["user_id", "provider"])

    op.create_table(
        "oauth_challenges",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("nonce_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("action IN ('login', 'link')", name="ck_oauth_challenges_action"),
    )
    op.create_index("ix_oauth_challenges_user_id", "oauth_challenges", ["user_id"])
    op.create_index("ix_oauth_challenges_state_hash", "oauth_challenges", ["state_hash"], unique=True)
    op.create_index("ix_oauth_challenges_expiry", "oauth_challenges", ["expires_at", "used_at"])

    with op.batch_alter_table("email_outbox") as batch:
        batch.add_column(sa.Column("template_version", sa.String(length=20), nullable=False, server_default="v1"))
        batch.add_column(sa.Column("lease_owner", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("provider_message_id", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
        batch.create_check_constraint(
            "ck_email_outbox_status",
            "status IN ('pending', 'processing', 'sent', 'retry', 'dead')",
        )
    op.drop_index("ix_email_outbox_due", table_name="email_outbox")
    op.create_index(
        "ix_email_outbox_due",
        "email_outbox",
        ["status", "next_attempt_at", "lease_expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_email_outbox_due", table_name="email_outbox")
    with op.batch_alter_table("email_outbox") as batch:
        batch.drop_constraint("ck_email_outbox_status", type_="check")
        batch.drop_column("updated_at")
        batch.drop_column("provider_message_id")
        batch.drop_column("lease_expires_at")
        batch.drop_column("lease_owner")
        batch.drop_column("template_version")
    op.create_index("ix_email_outbox_due", "email_outbox", ["status", "next_attempt_at"])
    with op.batch_alter_table("auth_identities") as batch:
        batch.drop_constraint("uq_auth_identity_user_provider", type_="unique")
        batch.drop_column("updated_at")
    op.drop_table("oauth_challenges")
    with op.batch_alter_table("account_action_tokens") as batch:
        batch.drop_constraint("ck_account_action_tokens_purpose", type_="check")
        batch.drop_column("revoked_at")
