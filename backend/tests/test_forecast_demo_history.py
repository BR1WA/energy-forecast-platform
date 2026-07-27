from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import AuditEvent, SmartMeterReading, User
from app.services.auth_service import create_access_token, hash_password
from app.services.site_service import ensure_user_site, get_primary_meter


def test_prepare_demo_history_is_owned_non_destructive_and_idempotent():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        session = testing_session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    db = testing_session()
    try:
        owner = User(
            email="demo-history-owner@example.com",
            password_hash=hash_password("password123"),
            role="user",
            is_active=True,
        )
        other = User(
            email="demo-history-other@example.com",
            password_hash=hash_password("password123"),
            role="user",
            is_active=True,
        )
        db.add_all([owner, other])
        db.commit()
        ensure_user_site(db, owner.id)
        ensure_user_site(db, other.id)
        owner_meter = get_primary_meter(db, owner.id)
        other_meter = get_primary_meter(db, other.id)
        owner_meter.expected_interval_seconds = 5
        real_timestamp = datetime.now(timezone.utc) - timedelta(days=30)
        db.add(
            SmartMeterReading(
                meter_id=owner_meter.id,
                timestamp=real_timestamp,
                gap=1.25,
                grp=0.1,
                voltage=230.0,
                intensity=5.43,
                sub_metering_1=0.0,
                sub_metering_2=0.0,
                sub_metering_3=0.0,
                source="csv",
                quality="validated",
            )
        )
        db.commit()

        headers = {
            "Authorization": f"Bearer {create_access_token({'sub': str(owner.id)})}"
        }
        client = TestClient(app)
        first = client.post(
            "/api/v1/forecast/prepare-demo-history",
            headers=headers,
        )
        assert first.status_code == 200
        payload = first.json()
        assert payload["status"] == "ready"
        assert payload["synthetic_source"] == "forecast_demo"
        assert payload["required_hours"] == 336
        assert payload["accepted_rows"] == 337
        assert payload["coverage_percent"] >= 95
        assert payload["observed_hours"] >= 335
        assert payload["maximum_gap_hours"] <= 1

        owner_count = (
            db.query(SmartMeterReading)
            .filter(SmartMeterReading.meter_id == owner_meter.id)
            .count()
        )
        assert owner_count == 338
        assert (
            db.query(SmartMeterReading)
            .filter(
                SmartMeterReading.meter_id == owner_meter.id,
                SmartMeterReading.timestamp == real_timestamp,
                SmartMeterReading.source == "csv",
            )
            .count()
            == 1
        )
        assert (
            db.query(SmartMeterReading)
            .filter(SmartMeterReading.meter_id == other_meter.id)
            .count()
            == 0
        )
        db.refresh(owner_meter)
        assert owner_meter.expected_interval_seconds == 5

        second = client.post(
            "/api/v1/forecast/prepare-demo-history",
            headers=headers,
        )
        assert second.status_code == 200
        assert second.json()["status"] == "ready"
        assert (
            db.query(SmartMeterReading)
            .filter(SmartMeterReading.meter_id == owner_meter.id)
            .count()
            == owner_count
        )
        assert (
            db.query(AuditEvent)
            .filter(
                AuditEvent.actor_user_id == owner.id,
                AuditEvent.event_type == "forecast.demo_history_prepared",
            )
            .count()
            == 2
        )
    finally:
        db.close()
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
