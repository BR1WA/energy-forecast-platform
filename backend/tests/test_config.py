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


def test_product_v1_capabilities_default_to_disabled():
    settings = Settings(
        _env_file=None,
        DEBUG=False,
        JWT_SECRET_KEY="fP7m2zQ9vN4cR8xL6kT3wY1sH5jD0bG7eA2uC9iM",
        ADMIN_PASSWORD="initial-admin-V8f2qW7p",
    )

    settings.validate_secrets()
    assert settings.FORECAST_168H_ENABLED is False
    assert settings.EMAIL_DELIVERY_ENABLED is False
    assert settings.GOOGLE_AUTH_ENABLED is False


def test_enabled_email_rejects_incomplete_configuration_without_values():
    settings = Settings(
        _env_file=None,
        DEBUG=False,
        JWT_SECRET_KEY="fP7m2zQ9vN4cR8xL6kT3wY1sH5jD0bG7eA2uC9iM",
        ADMIN_PASSWORD="initial-admin-V8f2qW7p",
        EMAIL_DELIVERY_ENABLED=True,
        SMTP_PASSWORD="do-not-print-this-value",
    )

    with pytest.raises(RuntimeError) as caught:
        settings.validate_secrets()
    message = str(caught.value)
    assert "PUBLIC_FRONTEND_URL" in message
    assert "SMTP_HOST" in message
    assert "do-not-print-this-value" not in message


def test_enabled_google_accepts_complete_configuration():
    settings = Settings(
        _env_file=None,
        DEBUG=False,
        JWT_SECRET_KEY="fP7m2zQ9vN4cR8xL6kT3wY1sH5jD0bG7eA2uC9iM",
        ADMIN_PASSWORD="initial-admin-V8f2qW7p",
        GOOGLE_AUTH_ENABLED=True,
        PUBLIC_FRONTEND_URL="https://energy.example.com",
        GOOGLE_CLIENT_ID="public-client-id",
        GOOGLE_CLIENT_SECRET="private-client-secret",
    )

    settings.validate_secrets()
