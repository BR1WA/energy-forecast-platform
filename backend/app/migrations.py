"""Alembic migration helpers shared by startup and management commands."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.config import get_settings


BACKEND_DIR = Path(__file__).resolve().parent.parent
PRE_SITE_OWNERSHIP_REVISION = "bf09bfef2e1e"


def _revision_before_site_ownership(database_url: str) -> bool:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            if "alembic_version" not in inspect(connection).get_table_names():
                return True
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
            return revision in {None, "32d14ec8e2b6", "f337072baa67", "8a993bf3d9c5", "b34c1810c744", PRE_SITE_OWNERSHIP_REVISION}
    finally:
        engine.dispose()


def _prepare_legacy_subscription_default(database_url: str) -> None:
    """Let c4 create its legacy-reading owner without rewriting its history."""
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            inspector = inspect(connection)
            if "users" not in inspector.get_table_names():
                return
            user_columns = {column["name"] for column in inspector.get_columns("users")}
            if "subscription_tier" not in user_columns:
                return
            if connection.dialect.name == "sqlite":
                connection.execute(text(
                    "CREATE TRIGGER IF NOT EXISTS c4_subscription_tier_default "
                    "BEFORE INSERT ON users "
                    "WHEN NEW.subscription_tier IS NULL "
                    "BEGIN "
                    "INSERT INTO users (email, password_hash, full_name, role, subscription_tier, is_active, is_setup_complete, data_mode) "
                    "VALUES (NEW.email, NEW.password_hash, NEW.full_name, NEW.role, 'legacy', NEW.is_active, NEW.is_setup_complete, NEW.data_mode); "
                    "SELECT RAISE(IGNORE); "
                    "END"
                ))
            else:
                connection.execute(text("ALTER TABLE users ALTER COLUMN subscription_tier SET DEFAULT 'legacy'"))
    finally:
        engine.dispose()


def run_migrations() -> None:
    """Upgrade the configured database to the latest committed revision."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    database_url = get_settings().DATABASE_URL
    if _revision_before_site_ownership(database_url):
        command.upgrade(config, PRE_SITE_OWNERSHIP_REVISION)
        _prepare_legacy_subscription_default(database_url)
    command.upgrade(config, "head")
