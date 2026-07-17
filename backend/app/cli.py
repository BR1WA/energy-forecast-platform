"""Management commands for migrations and initial administrator creation."""

from __future__ import annotations

import argparse

from app.config import get_settings
from app.database import SessionLocal
from app.migrations import run_migrations
from app.models import User
from app.services.auth_service import hash_password


def create_admin() -> None:
    settings = get_settings()
    run_migrations()

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
        if existing:
            raise SystemExit(f"User already exists: {settings.ADMIN_EMAIL}")

        admin = User(
            email=settings.ADMIN_EMAIL,
            password_hash=hash_password(settings.ADMIN_PASSWORD),
            full_name="System Administrator",
            role="admin",
            is_active=True,
        )
        db.add(admin)
        db.commit()
        print(f"Administrator created: {settings.ADMIN_EMAIL}")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="EnergyForecast management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("migrate", help="Upgrade the database to Alembic head")
    subparsers.add_parser(
        "create-admin",
        help="Create the administrator configured by ADMIN_EMAIL and ADMIN_PASSWORD",
    )
    args = parser.parse_args()

    if args.command == "migrate":
        run_migrations()
        print("Database is at Alembic head.")
    elif args.command == "create-admin":
        create_admin()


if __name__ == "__main__":
    main()
