from __future__ import annotations

import hashlib
import importlib.util
import math
import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import SmartMeterReading, User
from app.services.auth_service import hash_password
from app.services.product_forecast_service import (
    ARTIFACT_DIR,
    ARTIFACT_SPECS,
    LOOKBACK_HOURS,
    ProductForecastService,
)
from app.services.site_service import ensure_default_site, get_default_meter


def build_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine, sessionmaker(bind=engine)()


def add_complete_history(db, user_id: int, *, power: float = 2.0):
    site = ensure_default_site(db, user_id)
    site.timezone = "UTC"
    meter = get_default_meter(db, user_id)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    db.add_all(
        [
            SmartMeterReading(
                meter_id=meter.id,
                timestamp=start + timedelta(hours=index),
                gap=power + (index % 24) / 10,
                grp=0.0,
                voltage=230.0,
                intensity=5.0,
                sub_metering_1=0.0,
                sub_metering_2=0.0,
                sub_metering_3=0.0,
                source="csv",
                quality="validated",
            )
            for index in range(LOOKBACK_HOURS + 1)
        ]
    )
    db.commit()
    return site, meter


def test_packaged_checkpoint_matches_the_production_manifest():
    manifest = json.loads((ARTIFACT_DIR / "manifest.json").read_text(encoding="utf-8"))
    checkpoint = ARTIFACT_DIR / manifest["checkpoint_file"]
    assert checkpoint.stat().st_size == manifest["checkpoint_size_bytes"]
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest() == manifest["checkpoint_sha256"]
    assert manifest["lookback_hours"] == 336
    assert manifest["horizon_hours"] == 24
    assert manifest["quantiles"] == [0.1, 0.5, 0.9]


def test_packaged_week_checkpoint_matches_its_independent_manifest():
    artifact_dir = ARTIFACT_SPECS[168].artifact_dir
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    checkpoint = artifact_dir / manifest["checkpoint_file"]
    assert checkpoint.stat().st_size == manifest["checkpoint_size_bytes"] == 5_600_105
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest() == manifest["checkpoint_sha256"]
    assert manifest["checkpoint_sha256"] == "80af16b25af9b912019c6e40cfdc491e2cf5173e5743144596801e28df695f93"
    assert manifest["lookback_hours"] == 336
    assert manifest["horizon_hours"] == 168
    assert manifest["quantiles"] == [0.1, 0.5, 0.9]
    assert manifest["training"]["cold_start_mae_improvement_percent"] > 0
    assert manifest["training"]["cold_start_households_beating_seasonal_percent"] >= 75


def test_week_capability_is_hidden_by_default():
    capabilities = ProductForecastService(forecast_168h_enabled=False).capabilities()
    assert [item["horizon_hours"] for item in capabilities["capabilities"]] == [24]


def test_readiness_accepts_a_complete_primary_meter_window():
    engine, db = build_session()
    try:
        user = User(
            email="forecast-ready@example.com",
            password_hash=hash_password("password123"),
            role="user",
            is_active=True,
        )
        db.add(user)
        db.commit()
        add_complete_history(db, user.id)

        prepared = ProductForecastService().prepare_input(db, user.id)
        assert prepared.ready
        assert prepared.coverage_percent == 100.0
        assert prepared.observed_hours == 336
        assert prepared.maximum_gap_hours == 0
        assert prepared.values is not None
        assert prepared.values.shape == (336,)
        assert np.isfinite(prepared.values).all()
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_readiness_rejects_incomplete_history_instead_of_padding_it():
    engine, db = build_session()
    try:
        user = User(
            email="forecast-short@example.com",
            password_hash=hash_password("password123"),
            role="user",
            is_active=True,
        )
        db.add(user)
        db.commit()
        site = ensure_default_site(db, user.id)
        meter = get_default_meter(db, user.id)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        db.add_all(
            [
                SmartMeterReading(
                    meter_id=meter.id,
                    timestamp=start + timedelta(hours=index),
                    gap=1.0,
                    grp=0.0,
                    voltage=230.0,
                    intensity=4.3,
                    sub_metering_1=0.0,
                    sub_metering_2=0.0,
                    sub_metering_3=0.0,
                    source="csv",
                    quality="validated",
                )
                for index in range(25)
            ]
        )
        db.commit()

        prepared = ProductForecastService().prepare_input(db, user.id)
        assert not prepared.ready
        assert prepared.values is None
        assert prepared.coverage_percent < 95
        assert any("at least 95%" in reason for reason in prepared.reasons)
        assert any("maximum is 3 hours" in reason for reason in prepared.reasons)
        assert site.id is not None
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_declared_seasonal_fallback_has_no_fake_interval(monkeypatch):
    engine, db = build_session()
    try:
        user = User(
            email="forecast-fallback@example.com",
            password_hash=hash_password("password123"),
            role="user",
            is_active=True,
        )
        db.add(user)
        db.commit()
        add_complete_history(db, user.id)
        service = ProductForecastService()
        monkeypatch.setattr(
            service,
            "model_status",
            lambda: {
                "available": False,
                "error": "Runtime intentionally unavailable.",
                "artifact_fingerprint": None,
            },
        )

        result = service.generate(db, user.id)
        prepared = service.prepare_input(db, user.id)
        assert result["method"] == "seasonal_naive"
        assert result["fallback_reason"] == "Runtime intentionally unavailable."
        assert all(row[1:] == [None, None] for row in result["prediction_rows"])
        assert np.allclose(
            [row[0] for row in result["prediction_rows"]],
            prepared.values[168:192],
        )
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_week_fallback_uses_the_previous_168_hours_without_fake_interval(monkeypatch):
    engine, db = build_session()
    try:
        user = User(
            email="forecast-week-fallback@example.com",
            password_hash=hash_password("password123"),
            role="user",
            is_active=True,
        )
        db.add(user)
        db.commit()
        add_complete_history(db, user.id)
        service = ProductForecastService(forecast_168h_enabled=True)
        monkeypatch.setattr(
            service,
            "warmup",
            lambda horizon_hours=24: {
                "available": True,
                "warmed": True,
                "enabled": True,
                "horizon_hours": horizon_hours,
                "name": ARTIFACT_SPECS[horizon_hours].model_name,
                "display_name": ARTIFACT_SPECS[horizon_hours].display_name,
                "version": "1.0.0",
                "artifact_fingerprint": "test-fingerprint",
                "error": None,
            },
        )

        def fail_inference(*args, **kwargs):
            raise RuntimeError("Week inference failed after readiness.")

        monkeypatch.setattr(service, "_predict_tft", fail_inference)
        result = service.generate(db, user.id, 168)
        prepared = service.prepare_input(db, user.id)
        assert result["method"] == "seasonal_naive"
        assert result["fallback_reason"] == "Week inference failed after readiness."
        assert len(result["prediction_rows"]) == 168
        assert all(row[1:] == [None, None] for row in result["prediction_rows"])
        assert np.allclose(
            [row[0] for row in result["prediction_rows"]],
            prepared.values[168:336],
        )
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.mark.skipif(importlib.util.find_spec("torch") is None, reason="PyTorch is optional in the CI test image")
def test_packaged_tft_returns_ordered_24_hour_quantiles():
    engine, db = build_session()
    try:
        user = User(
            email="forecast-tft@example.com",
            password_hash=hash_password("password123"),
            role="user",
            is_active=True,
        )
        db.add(user)
        db.commit()
        add_complete_history(db, user.id)

        result = ProductForecastService().generate(db, user.id)
        repeated = ProductForecastService().generate(db, user.id)
        assert result["method"] == "global_tft"
        assert len(result["prediction_rows"]) == 24
        assert result["prediction_rows"] == repeated["prediction_rows"]
        assert math.isfinite(result["inference_seconds"])
        assert result["inference_seconds"] >= 0
        for median, lower, upper in result["prediction_rows"]:
            assert 0 <= lower <= median <= upper
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.mark.skipif(importlib.util.find_spec("torch") is None, reason="PyTorch is optional in the CI test image")
def test_packaged_tft_returns_ordered_168_hour_quantiles():
    engine, db = build_session()
    try:
        user = User(
            email="forecast-week-tft@example.com",
            password_hash=hash_password("password123"),
            role="user",
            is_active=True,
        )
        db.add(user)
        db.commit()
        add_complete_history(db, user.id)

        result = ProductForecastService(forecast_168h_enabled=True).generate(db, user.id, 168)
        repeated = ProductForecastService(forecast_168h_enabled=True).generate(db, user.id, 168)
        assert result["method"] == "global_tft"
        assert result["horizon_hours"] == 168
        assert len(result["prediction_rows"]) == 168
        assert result["prediction_rows"] == repeated["prediction_rows"]
        assert math.isfinite(result["inference_seconds"])
        for median, lower, upper in result["prediction_rows"]:
            assert 0 <= lower <= median <= upper
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.mark.skipif(importlib.util.find_spec("torch") is None, reason="PyTorch is optional in the CI test image")
def test_packaged_week_checkpoint_matches_the_deterministic_smoke_fingerprint():
    import torch

    service = ProductForecastService(forecast_168h_enabled=True)
    model = service._load_model(168)
    batch = {
        "x": torch.linspace(-1, 1, 336).reshape(1, 336, 1),
        "x_calendar": torch.zeros(1, 336, 9),
        "y_calendar": torch.zeros(1, 168, 9),
    }
    with torch.inference_mode():
        output = model(batch)["quantiles"].cpu().numpy()
        repeated = model(batch)["quantiles"].cpu().numpy()
    assert output.shape == (1, 168, 3)
    assert np.isfinite(output).all()
    assert np.allclose(output, repeated, atol=1e-5)
    assert np.allclose(
        output[0, [0, 83, 167], :],
        np.asarray(
            [
                [0.45621, 0.799188, 1.374814],
                [-0.524265, 0.560203, 1.250402],
                [-0.965335, -0.108819, 1.116019],
            ]
        ),
        atol=1e-5,
    )
