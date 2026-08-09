import pytest

from app.config import Settings


LEGAL_CONFIGURATION = {
    "LEGAL_OWNER_NAME": "EnergyForecast Test",
    "LEGAL_CONTACT_EMAIL": "legal@example.test",
    "SUPPORT_EMAIL": "support@example.test",
    "LEGAL_EFFECTIVE_DATE": "2026-07-23",
}


def test_production_rejects_placeholder_secrets():
    settings = Settings(
        _env_file=None,
        DEBUG=False,
        JWT_SECRET_KEY="super-secret-key-change-in-production",
        ADMIN_PASSWORD="admin123_secure_change_me",
        **LEGAL_CONFIGURATION,
    )

    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY, ADMIN_PASSWORD"):
        settings.validate_secrets()


def test_production_accepts_strong_secrets():
    settings = Settings(
        _env_file=None,
        DEBUG=False,
        JWT_SECRET_KEY="fP7m2zQ9vN4cR8xL6kT3wY1sH5jD0bG7eA2uC9iM",  # gitleaks:allow -- deterministic test-only value
        ADMIN_PASSWORD="initial-admin-V8f2qW7p",
        **LEGAL_CONFIGURATION,
    )

    settings.validate_secrets()


def test_product_v1_capabilities_default_to_disabled():
    settings = Settings(
        _env_file=None,
        DEBUG=False,
        JWT_SECRET_KEY="fP7m2zQ9vN4cR8xL6kT3wY1sH5jD0bG7eA2uC9iM",  # gitleaks:allow -- deterministic test-only value
        ADMIN_PASSWORD="initial-admin-V8f2qW7p",
        **LEGAL_CONFIGURATION,
    )

    settings.validate_secrets()
    assert settings.FORECAST_168H_ENABLED is False
    assert settings.EMAIL_DELIVERY_ENABLED is False
    assert settings.GOOGLE_AUTH_ENABLED is False


def test_enabled_email_rejects_incomplete_configuration_without_values():
    settings = Settings(
        _env_file=None,
        DEBUG=False,
        JWT_SECRET_KEY="fP7m2zQ9vN4cR8xL6kT3wY1sH5jD0bG7eA2uC9iM",  # gitleaks:allow -- deterministic test-only value
        ADMIN_PASSWORD="initial-admin-V8f2qW7p",
        EMAIL_DELIVERY_ENABLED=True,
        SMTP_PASSWORD="do-not-print-this-value",
        **LEGAL_CONFIGURATION,
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
        JWT_SECRET_KEY="fP7m2zQ9vN4cR8xL6kT3wY1sH5jD0bG7eA2uC9iM",  # gitleaks:allow -- deterministic test-only value
        ADMIN_PASSWORD="initial-admin-V8f2qW7p",
        GOOGLE_AUTH_ENABLED=True,
        PUBLIC_FRONTEND_URL="https://energy.example.com",
        GOOGLE_CLIENT_ID="public-client-id",
        **LEGAL_CONFIGURATION,
    )

    settings.validate_secrets()


def test_enabled_google_requires_public_frontend_and_browser_client_id():
    settings = Settings(
        _env_file=None,
        DEBUG=False,
        JWT_SECRET_KEY="fP7m2zQ9vN4cR8xL6kT3wY1sH5jD0bG7eA2uC9iM",  # gitleaks:allow -- deterministic test-only value
        ADMIN_PASSWORD="initial-admin-V8f2qW7p",
        GOOGLE_AUTH_ENABLED=True,
        **LEGAL_CONFIGURATION,
    )

    with pytest.raises(RuntimeError) as caught:
        settings.validate_secrets()

    assert "PUBLIC_FRONTEND_URL" in str(caught.value)
    assert "GOOGLE_CLIENT_ID" in str(caught.value)


def test_production_rejects_missing_legal_identity():
    settings = Settings(
        _env_file=None,
        DEBUG=False,
        JWT_SECRET_KEY="fP7m2zQ9vN4cR8xL6kT3wY1sH5jD0bG7eA2uC9iM",  # gitleaks:allow -- deterministic test-only value
        ADMIN_PASSWORD="initial-admin-V8f2qW7p",
        LEGAL_OWNER_NAME="",
        LEGAL_CONTACT_EMAIL="",
        SUPPORT_EMAIL="",
        LEGAL_EFFECTIVE_DATE="",
    )

    with pytest.raises(RuntimeError, match="public legal configuration"):
        settings.validate_secrets()
