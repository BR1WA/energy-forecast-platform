"""Alembic migration helpers shared by startup and management commands."""

from pathlib import Path

from alembic import command
from alembic.config import Config


BACKEND_DIR = Path(__file__).resolve().parent.parent


def run_migrations() -> None:
    """Upgrade the configured database to the latest committed revision."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(config, "head")
