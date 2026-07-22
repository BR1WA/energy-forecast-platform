from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import SmartMeterReading, User
from app.services.auth_service import create_access_token, hash_password
from app.services.product_forecast_service import product_forecast_service
from app.services.site_service import ensure_default_site, get_default_meter


def test_forecast_api_persists_an_owned_explicit_fallback(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    db = TestingSession()
    try:
        owner = User(
            email="forecast-owner@example.com",
            password_hash=hash_password("password123"),
            role="user",
            is_active=True,
        )
        other = User(
            email="forecast-other@example.com",
            password_hash=hash_password("password123"),
            role="user",
            is_active=True,
        )
        db.add_all([owner, other])
        db.commit()
        site = ensure_default_site(db, owner.id)
        site.timezone = "UTC"
        ensure_default_site(db, other.id)
        meter = get_default_meter(db, owner.id)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        db.add_all(
            [
                SmartMeterReading(
                    meter_id=meter.id,
                    timestamp=start + timedelta(hours=index),
                    gap=1.0 + (index % 24) / 20,
                    grp=0.0,
                    voltage=230.0,
                    intensity=4.3,
                    sub_metering_1=0.0,
                    sub_metering_2=0.0,
                    sub_metering_3=0.0,
                    source="csv",
                    quality="validated",
                )
                for index in range(337)
            ]
        )
        db.commit()
        monkeypatch.setattr(
            product_forecast_service,
            "model_status",
            lambda: {
                "available": False,
                "name": "global_tft_24h",
                "display_name": "Global TFT 24-hour",
                "version": "1.0.0",
                "artifact_fingerprint": None,
                "error": "Test runtime has no inference engine.",
            },
        )
        client = TestClient(app)
        owner_headers = {
            "Authorization": f"Bearer {create_access_token({'sub': str(owner.id)})}"
        }
        other_headers = {
            "Authorization": f"Bearer {create_access_token({'sub': str(other.id)})}"
        }

        readiness = client.get("/api/v1/forecast/readiness", headers=owner_headers)
        assert readiness.status_code == 200
        assert readiness.json()["status"] == "fallback_ready"
        assert readiness.json()["horizon_hours"] == 24

        capabilities = client.get("/api/v1/forecast/capabilities", headers=owner_headers)
        assert capabilities.status_code == 200
        assert [item["horizon_hours"] for item in capabilities.json()["capabilities"]] == [24]

        disabled_week = client.post(
            "/api/v1/forecast/run",
            headers=owner_headers,
            json={"horizon_hours": 168},
        )
        assert disabled_week.status_code == 404
        assert disabled_week.json()["detail"]["code"] == "FORECAST_CAPABILITY_DISABLED"

        generated = client.post("/api/v1/forecast/run", headers=owner_headers)
        assert generated.status_code == 201
        payload = generated.json()
        assert payload["method"] == "seasonal_naive"
        assert payload["fallback_reason"] == "Test runtime has no inference engine."
        assert payload["horizon_hours"] == 24
        assert len(payload["points"]) == 24
        assert all(point["p10_kwh"] is None and point["p90_kwh"] is None for point in payload["points"])

        assert client.get("/api/v1/forecast/latest", headers=owner_headers).json()["id"] == payload["id"]
        assert client.get("/api/v1/forecast/latest", headers=other_headers).json() is None
        assert client.get("/api/v1/forecast/history", headers=other_headers).json() == []

        monkeypatch.setattr(product_forecast_service, "_forecast_168h_enabled", True)
        monkeypatch.setattr(
            product_forecast_service,
            "warmup",
            lambda horizon_hours=24: {
                "available": True,
                "enabled": True,
                "warmed": True,
                "horizon_hours": horizon_hours,
                "name": f"global_tft_{horizon_hours}h",
                "display_name": f"Global TFT {horizon_hours}-hour",
                "version": "1.0.0",
                "artifact_fingerprint": f"fingerprint-{horizon_hours}",
                "error": None,
            },
        )
        monkeypatch.setattr(
            product_forecast_service,
            "_predict_tft",
            lambda prepared, country, mean, standard_deviation, horizon_hours: (
                np.full(horizon_hours, 0.8),
                np.full(horizon_hours, 1.0),
                np.full(horizon_hours, 1.2),
            ),
        )

        enabled_capabilities = client.get("/api/v1/forecast/capabilities", headers=owner_headers)
        assert [item["horizon_hours"] for item in enabled_capabilities.json()["capabilities"]] == [24, 168]
        generated_week = client.post(
            "/api/v1/forecast/run",
            headers=owner_headers,
            json={"horizon_hours": 168},
        )
        assert generated_week.status_code == 201
        week_payload = generated_week.json()
        assert week_payload["method"] == "global_tft"
        assert week_payload["horizon_hours"] == 168
        assert len(week_payload["points"]) == 168
        assert client.get(
            "/api/v1/forecast/latest?horizon_hours=168",
            headers=owner_headers,
        ).json()["id"] == week_payload["id"]
        week_history = client.get(
            "/api/v1/forecast/history?horizon_hours=168",
            headers=owner_headers,
        ).json()
        assert len(week_history) == 1
        assert week_history[0]["horizon_hours"] == 168
        assert client.get(
            "/api/v1/forecast/latest?horizon_hours=168",
            headers=other_headers,
        ).json() is None
    finally:
        db.close()
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
