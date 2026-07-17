"""Add user-owned sites and meters and remove subscription schema.

Revision ID: c4f2a9d18b70
Revises: bf09bfef2e1e
Create Date: 2026-07-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4f2a9d18b70"
down_revision: Union[str, None] = "bf09bfef2e1e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LEGACY_EMAIL = "legacy-data@energyai.invalid"


def upgrade() -> None:
    op.create_table(
        "sites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("region", sa.String(length=100), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Africa/Casablanca"),
        sa.Column("provider", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_sites_user_id", "sites", ["user_id"])

    op.create_table(
        "meters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("external_id", sa.String(length=100), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("meter_type", sa.String(length=50), nullable=False, server_default="electricity"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("source_type", sa.String(length=20), nullable=False, server_default="simulation"),
        sa.Column("expected_interval_seconds", sa.Integer(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_meters_site_id", "meters", ["site_id"])
    op.create_index("ix_meters_external_id", "meters", ["external_id"])

    op.create_table(
        "site_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=False, server_default="Morocco"),
        sa.Column("region", sa.String(length=100), nullable=True),
        sa.Column("electricity_provider", sa.String(length=100), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="MAD"),
        sa.Column("peak_rate", sa.Float(), nullable=False, server_default="1.1"),
        sa.Column("off_peak_rate", sa.Float(), nullable=False, server_default="0.8"),
        sa.Column("peak_start_hour", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("peak_end_hour", sa.Integer(), nullable=False, server_default="22"),
        sa.Column("sensor_type", sa.String(length=50), nullable=False, server_default="simulator"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_site_settings_site_id", "site_settings", ["site_id"], unique=True)

    op.create_table(
        "simulation_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("is_running", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("site_id", name="uq_simulation_sessions_site_id"),
    )
    op.create_index("ix_simulation_sessions_site_id", "simulation_sessions", ["site_id"])
    op.create_index("ix_simulation_sessions_user_id", "simulation_sessions", ["user_id"])

    for table_name, column_name in (
        ("forecasts", "site_id"),
        ("alert_configs", "site_id"),
        ("alerts", "site_id"),
        ("energy_budgets", "site_id"),
    ):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(sa.Column(column_name, sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                f"fk_{table_name}_{column_name}", "sites", [column_name], ["id"]
            )
        op.create_index(f"ix_{table_name}_{column_name}", table_name, [column_name])

    with op.batch_alter_table("smart_meter_readings") as batch_op:
        batch_op.add_column(sa.Column("meter_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_smart_meter_readings_meter_id", "meters", ["meter_id"], ["id"]
        )
    op.create_index("ix_smart_meter_readings_meter_id", "smart_meter_readings", ["meter_id"])
    op.create_index(
        "ix_smart_meter_readings_meter_timestamp",
        "smart_meter_readings",
        ["meter_id", "timestamp"],
    )

    bind = op.get_bind()
    users = sa.table("users", sa.column("id"), sa.column("email"), sa.column("role"))
    sites = sa.table("sites", sa.column("id"), sa.column("user_id"), sa.column("name"))
    meters = sa.table(
        "meters",
        sa.column("id"),
        sa.column("site_id"),
        sa.column("external_id"),
        sa.column("name"),
        sa.column("source_type"),
    )
    site_settings = sa.table(
        "site_settings",
        sa.column("site_id"),
        sa.column("country"),
        sa.column("region"),
        sa.column("electricity_provider"),
        sa.column("currency"),
        sa.column("peak_rate"),
        sa.column("off_peak_rate"),
        sa.column("peak_start_hour"),
        sa.column("peak_end_hour"),
        sa.column("sensor_type"),
    )
    readings = sa.table("smart_meter_readings", sa.column("id"), sa.column("meter_id"))

    bind.execute(
        users.update()
        .where(users.c.role.not_in(["admin", "user"]))
        .values(role="user")
    )

    settings_row = bind.execute(
        sa.text(
            "SELECT country, region, electricity_provider, currency, peak_rate, "
            "off_peak_rate, peak_start_hour, peak_end_hour, sensor_type "
            "FROM system_settings ORDER BY id LIMIT 1"
        )
    ).mappings().first()
    settings_values = {
        "country": (settings_row or {}).get("country") or "Morocco",
        "region": (settings_row or {}).get("region"),
        "electricity_provider": (settings_row or {}).get("electricity_provider"),
        "currency": (settings_row or {}).get("currency") or "MAD",
        "peak_rate": (settings_row or {}).get("peak_rate") or 1.1,
        "off_peak_rate": (settings_row or {}).get("off_peak_rate") or 0.8,
        "peak_start_hour": (settings_row or {}).get("peak_start_hour") or 6,
        "peak_end_hour": (settings_row or {}).get("peak_end_hour") or 22,
        "sensor_type": "simulator",
    }

    user_site_ids: dict[int, int] = {}
    for user_id in bind.execute(sa.select(users.c.id)).scalars():
        site_id = bind.execute(
            sa.select(sites.c.id).where(sites.c.user_id == user_id).order_by(sites.c.id)
        ).scalar()
        if site_id is None:
            bind.execute(sites.insert().values(user_id=user_id, name="Default site"))
            site_id = bind.execute(
                sa.select(sites.c.id).where(sites.c.user_id == user_id).order_by(sites.c.id)
            ).scalar_one()
        user_site_ids[user_id] = site_id

        if bind.execute(sa.select(meters.c.id).where(meters.c.site_id == site_id)).scalar() is None:
            bind.execute(
                meters.insert().values(
                    site_id=site_id,
                    external_id=f"default-{user_id}",
                    name="Default meter",
                )
            )
        if bind.execute(sa.select(site_settings.c.site_id).where(site_settings.c.site_id == site_id)).scalar() is None:
            bind.execute(site_settings.insert().values(site_id=site_id, **settings_values))

    for table_name in ("forecasts", "alert_configs", "alerts", "energy_budgets"):
        table = sa.table(table_name, sa.column("user_id"), sa.column("site_id"))
        for user_id, site_id in user_site_ids.items():
            bind.execute(
                table.update()
                .where(table.c.user_id == user_id)
                .where(table.c.site_id.is_(None))
                .values(site_id=site_id)
            )

    if bind.execute(sa.select(sa.func.count()).select_from(readings).where(readings.c.meter_id.is_(None))).scalar():
        legacy_user_id = bind.execute(
            sa.select(users.c.id).where(users.c.email == LEGACY_EMAIL)
        ).scalar()
        if legacy_user_id is None:
            bind.execute(
                sa.text(
                    "INSERT INTO users (email, password_hash, full_name, role, is_active, "
                    "is_setup_complete, data_mode) VALUES "
                    "(:email, :password_hash, :full_name, :role, :is_active, :is_setup_complete, :data_mode)"
                ),
                {
                    "email": LEGACY_EMAIL,
                    "password_hash": "legacy-data-no-login",
                    "full_name": "Legacy imported data",
                    "role": "user",
                    "is_active": False,
                    "is_setup_complete": True,
                    "data_mode": "HISTORICAL",
                },
            )
            legacy_user_id = bind.execute(
                sa.select(users.c.id).where(users.c.email == LEGACY_EMAIL)
            ).scalar_one()
        bind.execute(sites.insert().values(user_id=legacy_user_id, name="Legacy imported data"))
        legacy_site_id = bind.execute(
            sa.select(sites.c.id).where(sites.c.user_id == legacy_user_id).order_by(sites.c.id.desc())
        ).scalar_one()
        bind.execute(
            meters.insert().values(
                site_id=legacy_site_id,
                external_id="legacy-import",
                name="Legacy imported meter",
                source_type="legacy",
            )
        )
        legacy_meter_id = bind.execute(
            sa.select(meters.c.id).where(meters.c.site_id == legacy_site_id).order_by(meters.c.id.desc())
        ).scalar_one()
        bind.execute(site_settings.insert().values(site_id=legacy_site_id, **settings_values))
        bind.execute(readings.update().where(readings.c.meter_id.is_(None)).values(meter_id=legacy_meter_id))

    op.drop_table("subscriptions")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("subscription_tier")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("subscription_tier", sa.String(length=50), nullable=False, server_default="free"))
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tier", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("checkout_ref", sa.String(length=100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])
    op.create_index("ix_subscriptions_checkout_ref", "subscriptions", ["checkout_ref"])

    for table_name, column_name in (
        ("forecasts", "site_id"),
        ("alert_configs", "site_id"),
        ("alerts", "site_id"),
        ("energy_budgets", "site_id"),
    ):
        op.drop_index(f"ix_{table_name}_{column_name}", table_name=table_name)
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(f"fk_{table_name}_{column_name}", type_="foreignkey")
            batch_op.drop_column(column_name)

    op.drop_index("ix_smart_meter_readings_meter_timestamp", table_name="smart_meter_readings")
    op.drop_index("ix_smart_meter_readings_meter_id", table_name="smart_meter_readings")
    with op.batch_alter_table("smart_meter_readings") as batch_op:
        batch_op.drop_constraint("fk_smart_meter_readings_meter_id", type_="foreignkey")
        batch_op.drop_column("meter_id")

    op.drop_index("ix_simulation_sessions_user_id", table_name="simulation_sessions")
    op.drop_index("ix_simulation_sessions_site_id", table_name="simulation_sessions")
    op.drop_table("simulation_sessions")
    op.drop_index("ix_site_settings_site_id", table_name="site_settings")
    op.drop_table("site_settings")
    op.drop_index("ix_meters_external_id", table_name="meters")
    op.drop_index("ix_meters_site_id", table_name="meters")
    op.drop_table("meters")
    op.drop_index("ix_sites_user_id", table_name="sites")
    op.drop_table("sites")
