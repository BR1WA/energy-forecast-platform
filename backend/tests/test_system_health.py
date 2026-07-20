from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.routers.system import build_readiness
from app.services.product_forecast_service import product_forecast_service


def make_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def model_status(*, available: bool, warmed: bool, error: str | None = None) -> dict:
    return {
        "available": available,
        "warmed": warmed,
        "name": "global_tft_24h",
        "display_name": "Global TFT 24-hour",
        "version": "1.0.0",
        "artifact_fingerprint": "abc123",
        "error": error,
    }


def test_readiness_requires_the_packaged_runtime(monkeypatch):
    db = make_session()
    try:
        monkeypatch.setattr(
            product_forecast_service,
            "warmup",
            lambda: model_status(available=False, warmed=False, error="PyTorch unavailable"),
        )
        result = build_readiness(db)
        assert result["ready"] is False
        assert result["database"]["status"] == "ready"
        assert result["forecast"]["status"] == "not_ready"
        assert result["forecast"]["error"] == "PyTorch unavailable"
    finally:
        db.close()


def test_readiness_reports_a_warmed_fixed_artifact(monkeypatch):
    db = make_session()
    try:
        monkeypatch.setattr(
            product_forecast_service,
            "warmup",
            lambda: model_status(available=True, warmed=True),
        )
        result = build_readiness(db)
        assert result["ready"] is True
        assert result["forecast"]["status"] == "ready"
        assert result["forecast"]["name"] == "global_tft_24h"
        assert result["forecast"]["artifact_fingerprint"] == "abc123"
    finally:
        db.close()


def test_readiness_rejects_an_artifact_that_cannot_warm(monkeypatch):
    db = make_session()
    try:
        monkeypatch.setattr(
            product_forecast_service,
            "warmup",
            lambda: model_status(available=False, warmed=False, error="State dict mismatch"),
        )
        result = build_readiness(db)
        assert result["ready"] is False
        assert result["forecast"]["warmed"] is False
        assert result["forecast"]["error"] == "State dict mismatch"
    finally:
        db.close()
