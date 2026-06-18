"""
Application configuration — environment variables and settings.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
import secrets
import warnings


# Sentinel values that are safe ONLY for local development. If any of these are
# still in place while DEBUG is disabled, startup validation will refuse to run
# (see Settings.validate_secrets). See audit C3.
INSECURE_JWT_SECRET = "dev-secret-key-for-local-testing-only"
INSECURE_ADMIN_PASSWORD = "admin123"


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "EnergyForecast API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

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

    # ML Models
    MODELS_DIR: str = "../models"

    # Rate Limiting
    RATE_LIMIT: str = "10/minute"

    # SMTP Settings
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@energyforecast.com"
    SMTP_TLS: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True

    def validate_secrets(self) -> None:
        """Fail fast on insecure secrets outside of local development.

        When DEBUG is True we only emit warnings so local setup stays
        frictionless. When DEBUG is False (any deployed/non-dev run) the
        presence of a placeholder/insecure secret is fatal. See audit C3.
        """
        insecure: list[str] = []

        if self.JWT_SECRET_KEY == INSECURE_JWT_SECRET or not self.JWT_SECRET_KEY:
            insecure.append("JWT_SECRET_KEY")
        if self.ADMIN_PASSWORD == INSECURE_ADMIN_PASSWORD or not self.ADMIN_PASSWORD:
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
