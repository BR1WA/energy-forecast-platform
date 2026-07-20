"""Enforce one site per user and one primary meter per site.

Revision ID: d3a9f6c1b208
Revises: c2f8b3d7e914
Create Date: 2026-07-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d3a9f6c1b208"
down_revision: Union[str, None] = "c2f8b3d7e914"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    duplicate_users = bind.execute(
        sa.text(
            "SELECT user_id FROM sites GROUP BY user_id HAVING COUNT(*) > 1 "
            "ORDER BY user_id"
        )
    ).scalars().all()
    if duplicate_users:
        raise RuntimeError(
            "Cannot enforce one site per user while duplicate sites exist for "
            f"user IDs: {duplicate_users}. Resolve ownership explicitly first."
        )

    users = sa.table("users", sa.column("id"))
    sites = sa.table(
        "sites",
        sa.column("id"),
        sa.column("user_id"),
        sa.column("name"),
    )
    meters = sa.table(
        "meters",
        sa.column("id"),
        sa.column("site_id"),
        sa.column("external_id"),
        sa.column("name"),
        sa.column("source_type"),
    )
    site_settings = sa.table("site_settings", sa.column("site_id"))

    for user_id in bind.execute(sa.select(users.c.id)).scalars():
        site_id = bind.execute(
            sa.select(sites.c.id).where(sites.c.user_id == user_id)
        ).scalar()
        if site_id is None:
            bind.execute(
                sites.insert().values(user_id=user_id, name="Default site")
            )
            site_id = bind.execute(
                sa.select(sites.c.id).where(sites.c.user_id == user_id)
            ).scalar_one()

        if bind.execute(
            sa.select(meters.c.id).where(meters.c.site_id == site_id)
        ).scalar() is None:
            bind.execute(
                meters.insert().values(
                    site_id=site_id,
                    external_id=f"default-{user_id}",
                    name="Primary meter",
                    source_type="simulation",
                )
            )
        if bind.execute(
            sa.select(site_settings.c.site_id).where(
                site_settings.c.site_id == site_id
            )
        ).scalar() is None:
            bind.execute(site_settings.insert().values(site_id=site_id))

    with op.batch_alter_table("sites") as batch_op:
        batch_op.create_unique_constraint("uq_sites_user_id", ["user_id"])

    with op.batch_alter_table("meters") as batch_op:
        batch_op.add_column(
            sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    op.execute(
        "UPDATE meters SET is_primary = true WHERE id IN "
        "(SELECT MIN(id) FROM meters GROUP BY site_id)"
    )
    op.create_index(
        "uq_meters_primary_site",
        "meters",
        ["site_id"],
        unique=True,
        postgresql_where=sa.text("is_primary IS TRUE"),
        sqlite_where=sa.text("is_primary = 1"),
    )


def downgrade() -> None:
    op.drop_index("uq_meters_primary_site", table_name="meters")
    with op.batch_alter_table("meters") as batch_op:
        batch_op.drop_column("is_primary")
    with op.batch_alter_table("sites") as batch_op:
        batch_op.drop_constraint("uq_sites_user_id", type_="unique")
