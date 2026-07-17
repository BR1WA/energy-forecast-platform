import pytest

from app.config import Settings


def test_production_rejects_placeholder_secrets():
    settings = Settings(
        _env_file=None,
        DEBUG=False,
        JWT_SECRET_KEY="super-secret-key-change-in-production",
        ADMIN_PASSWORD="admin123_secure_change_me",
    )

    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY, ADMIN_PASSWORD"):
        settings.validate_secrets()


def test_production_accepts_strong_secrets():
    settings = Settings(
        _env_file=None,
        DEBUG=False,
        JWT_SECRET_KEY="fP7m2zQ9vN4cR8xL6kT3wY1sH5jD0bG7eA2uC9iM",
        ADMIN_PASSWORD="initial-admin-V8f2qW7p",
    )

    settings.validate_secrets()
