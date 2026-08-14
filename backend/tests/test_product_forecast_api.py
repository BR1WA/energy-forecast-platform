from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import SmartMeterReading, User
from app.services.auth_service import create_access_token, hash_password
from app.services.product_forecast_service import (
    ARTIFACT_SPECS,
    MONTH_HORIZON_HOURS,
    MONTH_LOOKBACK_HOURS,
    product_forecast_service,
)
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
            lambda horizon_hours=24: {
                "available": False,
                "enabled": True,
                "warmed": False,
                "horizon_hours": horizon_hours,
                "name": f"global_tft_{horizon_hours}h",
                "display_name": f"Global TFT {horizon_hours}-hour",
                "version": "1.0.0",
                "artifact_fingerprint": None,
                "error": "Test runtime has no inference engine.",
            },
        )
        monkeypatch.setattr(product_forecast_service, "_forecast_168h_enabled", False)
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

        capabilities = client.get(
            "/api/v1/forecast/capabilities", headers=owner_headers
        )
        assert capabilities.status_code == 200
        assert [
            item["horizon_hours"] for item in capabilities.json()["capabilities"]
        ] == [24]

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
        assert payload["model_name"] == "seasonal_naive_168h"
        assert len(payload["points"]) == 24
        day_timestamps = [
            datetime.fromisoformat(point["timestamp"]) for point in payload["points"]
        ]
        assert all(
            right - left == timedelta(hours=1)
            for left, right in zip(day_timestamps, day_timestamps[1:])
        )
        assert all(
            point["p10_kwh"] is None and point["p90_kwh"] is None
            for point in payload["points"]
        )

        assert (
            client.get("/api/v1/forecast/latest", headers=owner_headers).json()["id"]
            == payload["id"]
        )
        assert (
            client.get("/api/v1/forecast/latest", headers=other_headers).json() is None
        )
        assert (
            client.get("/api/v1/forecast/history", headers=other_headers).json() == []
        )

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

        enabled_capabilities = client.get(
            "/api/v1/forecast/capabilities", headers=owner_headers
        )
        assert [
            item["horizon_hours"]
            for item in enabled_capabilities.json()["capabilities"]
        ] == [24, 168]
        generated_week = client.post(
            "/api/v1/forecast/run",
            headers=owner_headers,
            json={"horizon_hours": 168},
        )
        assert generated_week.status_code == 201
        week_payload = generated_week.json()
        assert week_payload["method"] == "global_tft"
        assert week_payload["model_name"] == "global_tft_168h"
        assert week_payload["horizon_hours"] == 168
        assert len(week_payload["points"]) == 168
        week_timestamps = [
            datetime.fromisoformat(point["timestamp"])
            for point in week_payload["points"]
        ]
        assert all(
            right - left == timedelta(hours=1)
            for left, right in zip(week_timestamps, week_timestamps[1:])
        )
        assert week_timestamps[-1] - week_timestamps[0] == timedelta(hours=167)
        assert (
            client.get(
                "/api/v1/forecast/latest?horizon_hours=168",
                headers=owner_headers,
            ).json()["id"]
            == week_payload["id"]
        )
        week_history = client.get(
            "/api/v1/forecast/history?horizon_hours=168",
            headers=owner_headers,
        ).json()
        assert len(week_history) == 1
        assert week_history[0]["horizon_hours"] == 168
        assert (
            client.get(
                "/api/v1/forecast/latest?horizon_hours=168",
                headers=other_headers,
            ).json()
            is None
        )
    finally:
        db.close()
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)


@pytest.mark.skipif(
    importlib.util.find_spec("torch") is None,
    reason="PyTorch is required for the real dual-horizon API test",
)
def test_real_dual_horizon_api_uses_packaged_models_and_preserves_ownership(
    monkeypatch,
):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    db = TestingSession()
    try:
        owner = User(
            email="real-forecast-owner@example.com",
            password_hash=hash_password("password123"),
            role="user",
            is_active=True,
        )
        other = User(
            email="real-forecast-other@example.com",
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
        start = datetime(2026, 2, 1, tzinfo=timezone.utc)
        db.add_all(
            [
                SmartMeterReading(
                    meter_id=meter.id,
                    timestamp=start + timedelta(hours=index),
                    gap=0.8 + (index % 24) / 18,
                    grp=0.0,
                    voltage=230.0,
                    intensity=5.0,
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

        monkeypatch.setattr(product_forecast_service, "_forecast_168h_enabled", True)
        product_forecast_service._models.clear()
        product_forecast_service._manifests.clear()
        product_forecast_service._artifact_errors.clear()

        client = TestClient(app)
        owner_headers = {
            "Authorization": f"Bearer {create_access_token({'sub': str(owner.id)})}"
        }
        other_headers = {
            "Authorization": f"Bearer {create_access_token({'sub': str(other.id)})}"
        }

        capabilities = client.get(
            "/api/v1/forecast/capabilities", headers=owner_headers
        )
        assert capabilities.status_code == 200
        capability_rows = capabilities.json()["capabilities"]
        assert [row["horizon_hours"] for row in capability_rows] == [24, 168]
        assert [row["model"]["name"] for row in capability_rows] == [
            "global_tft_24h",
            "global_tft_168h",
        ]
        assert all(
            row["model"]["available"] and row["model"]["warmed"]
            for row in capability_rows
        )

        generated = {}
        for horizon, model_name, fingerprint in (
            (
                24,
                "global_tft_24h",
                "60fedcdee375dc0b2973e55b9f4ec752da69c2a7e390e1f951ed5cbb7bc5a04d",
            ),
            (
                168,
                "global_tft_168h",
                "80af16b25af9b912019c6e40cfdc491e2cf5173e5743144596801e28df695f93",
            ),
        ):
            readiness = client.get(
                f"/api/v1/forecast/readiness?horizon_hours={horizon}",
                headers=owner_headers,
            )
            assert readiness.status_code == 200
            assert readiness.json()["status"] == "ready"
            assert readiness.json()["model"]["name"] == model_name

            response = client.post(
                "/api/v1/forecast/run",
                headers=owner_headers,
                json={"horizon_hours": horizon},
            )
            assert response.status_code == 201
            payload = response.json()
            generated[horizon] = payload
            assert payload["method"] == "global_tft"
            assert payload["fallback_reason"] is None
            assert payload["model_name"] == model_name
            assert payload["artifact_fingerprint"] == fingerprint
            assert payload["horizon_hours"] == horizon
            assert len(payload["points"]) == horizon
            timestamps = [
                datetime.fromisoformat(point["timestamp"])
                for point in payload["points"]
            ]
            assert all(
                right - left == timedelta(hours=1)
                for left, right in zip(timestamps, timestamps[1:])
            )
            assert datetime.fromisoformat(
                payload["forecast_end"]
            ) - datetime.fromisoformat(payload["forecast_start"]) == timedelta(
                hours=horizon
            )

            latest = client.get(
                f"/api/v1/forecast/latest?horizon_hours={horizon}",
                headers=owner_headers,
            )
            assert latest.status_code == 200
            assert latest.json()["id"] == payload["id"]
            assert (
                client.get(
                    f"/api/v1/forecast/latest?horizon_hours={horizon}",
                    headers=other_headers,
                ).json()
                is None
            )

        assert generated[24]["id"] != generated[168]["id"]
    finally:
        product_forecast_service._models.clear()
        product_forecast_service._manifests.clear()
        product_forecast_service._artifact_errors.clear()
        db.close()
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)


def test_month_api_persists_and_reloads_30_daily_targets(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    db = TestingSession()
    try:
        owner = User(
            email="month-api-owner@example.com",
            password_hash=hash_password("password123"),
            role="user",
            is_active=True,
        )
        db.add(owner)
        db.commit()
        site = ensure_default_site(db, owner.id)
        site.timezone = "UTC"
        meter = get_default_meter(db, owner.id)
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        db.bulk_save_objects(
            [
                SmartMeterReading(
                    meter_id=meter.id,
                    timestamp=start + timedelta(hours=index),
                    gap=1.2 + (index % 24) / 20,
                    grp=0.0,
                    voltage=230.0,
                    intensity=5.0,
                    sub_metering_1=0.0,
                    sub_metering_2=0.0,
                    sub_metering_3=0.0,
                    source="csv",
                    quality="validated",
                )
                for index in range(MONTH_LOOKBACK_HOURS + 1)
            ]
        )
        db.commit()

        monkeypatch.setattr(product_forecast_service, "_forecast_30d_enabled", True)
        monkeypatch.setattr(
            product_forecast_service,
            "warmup",
            lambda horizon_hours=24: {
                "available": True,
                "enabled": True,
                "warmed": True,
                "horizon_hours": horizon_hours,
                "name": ARTIFACT_SPECS[horizon_hours].model_name,
                "display_name": ARTIFACT_SPECS[horizon_hours].display_name,
                "version": "3.0.0" if horizon_hours == 720 else "1.0.0",
                "artifact_fingerprint": f"fingerprint-{horizon_hours}",
                "error": None,
            },
        )
        monkeypatch.setattr(
            product_forecast_service,
            "_predict_month",
            lambda prepared: (
                np.full(30, 18.0),
                np.full(30, 22.0),
                np.full(30, 27.0),
            ),
        )

        client = TestClient(app)
        headers = {
            "Authorization": f"Bearer {create_access_token({'sub': str(owner.id)})}"
        }
        capabilities = client.get("/api/v1/forecast/capabilities", headers=headers)
        assert capabilities.status_code == 200
        monthly = next(
            item
            for item in capabilities.json()["capabilities"]
            if item["horizon_hours"] == MONTH_HORIZON_HOURS
        )
        assert monthly["target_count"] == 30
        assert monthly["target_interval_hours"] == 24
        assert monthly["resolution"] == "daily"

        response = client.post(
            "/api/v1/forecast/run",
            headers=headers,
            json={"horizon_hours": MONTH_HORIZON_HOURS},
        )
        assert response.status_code == 201
        payload = response.json()
        assert payload["method"] == "chronos2_lora"
        assert payload["horizon_hours"] == 720
        assert payload["target_count"] == 30
        assert payload["target_interval_hours"] == 24
        assert payload["resolution"] == "daily"
        assert len(payload["points"]) == 30
        timestamps = [
            datetime.fromisoformat(point["timestamp"]) for point in payload["points"]
        ]
        assert all(
            right - left == timedelta(days=1)
            for left, right in zip(timestamps, timestamps[1:])
        )

        latest = client.get(
            "/api/v1/forecast/latest?horizon_hours=720", headers=headers
        )
        assert latest.status_code == 200
        assert latest.json()["points"] == payload["points"]
        assert latest.json()["resolution"] == "daily"
    finally:
        db.close()
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
