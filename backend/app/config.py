"""
Application configuration — environment variables and settings.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import warnings


# Sentinel values that are safe ONLY for local development. If any of these are
# still in place while DEBUG is disabled, startup validation will refuse to run
# (see Settings.validate_secrets). See audit C3.
INSECURE_JWT_SECRET = "dev-secret-key-for-local-testing-only"
INSECURE_ADMIN_PASSWORD = "admin123"


def _looks_insecure(value: str, *, minimum_length: int, sentinels: set[str]) -> bool:
    normalized = (value or "").strip().lower().replace("_", "-")
    normalized_sentinels = {item.lower().replace("_", "-") for item in sentinels}
    placeholder_markers = (
        "change-me",
        "change-this",
        "change-in-production",
        "replace-with",
        "placeholder",
        "your-super-secret",
        "secure-change-me",
    )
    return (
        len(value or "") < minimum_length
        or normalized in normalized_sentinels
        or any(marker in normalized for marker in placeholder_markers)
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    # Application
    APP_NAME: str = "EnergyForecast API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "sqlite:///./energy_forecast.db"

    # JWT
    # No secure default: must be supplied via environment / .env. The insecure
    # sentinel is used only to detect a missing/placeholder value at startup.
    JWT_SECRET_KEY: str = INSECURE_JWT_SECRET
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Admin Seeding
    ADMIN_EMAIL: str = "admin@energyforecast.com"
    ADMIN_PASSWORD: str = INSECURE_ADMIN_PASSWORD

    # CORS
    FRONTEND_URL: str = "http://localhost:3000"

    # Rate Limiting
    RATE_LIMIT: str = "10/minute"

    # Alert worker
    ALERT_WORKER_INTERVAL_SECONDS: int = 60

    # Product V1 capabilities. New integrations stay invisible until an operator
    # explicitly enables them and supplies their complete configuration.
    FORECAST_168H_ENABLED: bool = False
    EMAIL_DELIVERY_ENABLED: bool = False
    GOOGLE_AUTH_ENABLED: bool = False

    # Product V1 integration contract. Delivery and identity services are
    # implemented in later gates, but G0 validates configuration atomically now.
    PUBLIC_FRONTEND_URL: str = ""
    EMAIL_FROM_ADDRESS: str = ""
    EMAIL_FROM_NAME: str = "EnergyForecast"
    EMAIL_REPLY_TO: str = ""
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_TIMEOUT_SECONDS: int = 20
    EMAIL_WORKER_POLL_SECONDS: int = 30
    EMAIL_LEASE_SECONDS: int = 120
    EMAIL_RETRY_BASE_SECONDS: int = 60
    EMAIL_MAX_ATTEMPTS: int = 5
    AVATAR_STORAGE_DIR: str = "static/avatars"
    REFRESH_COOKIE_DOMAIN: str = ""
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_CHALLENGE_EXPIRE_MINUTES: int = 10

    def validate_enabled_integrations(self) -> None:
        """Reject partially configured capabilities without exposing secrets."""
        missing: dict[str, list[str]] = {}
        if self.EMAIL_DELIVERY_ENABLED:
            required = {
                "PUBLIC_FRONTEND_URL": self.PUBLIC_FRONTEND_URL,
                "EMAIL_FROM_ADDRESS": self.EMAIL_FROM_ADDRESS,
                "SMTP_HOST": self.SMTP_HOST,
                "SMTP_USERNAME": self.SMTP_USERNAME,
                "SMTP_PASSWORD": self.SMTP_PASSWORD,
            }
            absent = [name for name, value in required.items() if not value.strip()]
            if absent:
                missing["email"] = absent
        if self.GOOGLE_AUTH_ENABLED:
            required = {
                "PUBLIC_FRONTEND_URL": self.PUBLIC_FRONTEND_URL,
                "GOOGLE_CLIENT_ID": self.GOOGLE_CLIENT_ID,
                "GOOGLE_CLIENT_SECRET": self.GOOGLE_CLIENT_SECRET,
            }
            absent = [name for name, value in required.items() if not value.strip()]
            if absent:
                missing["google"] = absent
        if missing:
            summary = "; ".join(
                f"{integration}: {', '.join(names)}"
                for integration, names in missing.items()
            )
            raise RuntimeError(
                "Refusing to start: enabled Product V1 integration configuration "
                f"is incomplete ({summary})."
            )

    def validate_secrets(self) -> None:
        """Fail fast on insecure secrets outside of local development.

        When DEBUG is True we only emit warnings so local setup stays
        frictionless. When DEBUG is False (any deployed/non-dev run) the
        presence of a placeholder/insecure secret is fatal. See audit C3.
        """
        self.validate_enabled_integrations()
        insecure: list[str] = []

        if _looks_insecure(
            self.JWT_SECRET_KEY,
            minimum_length=32,
            sentinels={INSECURE_JWT_SECRET},
        ):
            insecure.append("JWT_SECRET_KEY")
        if _looks_insecure(
            self.ADMIN_PASSWORD,
            minimum_length=12,
            sentinels={INSECURE_ADMIN_PASSWORD},
        ):
            insecure.append("ADMIN_PASSWORD")

        if not insecure:
            return

        joined = ", ".join(insecure)
        if self.DEBUG:
            warnings.warn(
                f"Insecure default(s) in use for: {joined}. This is allowed only "
                "because DEBUG is enabled. Set strong values via environment "
                "variables before deploying.",
                stacklevel=2,
            )
        else:
            raise RuntimeError(
                f"Refusing to start: insecure/placeholder secret(s) detected for: "
                f"{joined}. Set them via environment variables (e.g. in .env) "
                "because DEBUG is disabled."
            )


@lru_cache()
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_secrets()
    return settings
