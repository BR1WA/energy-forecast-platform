from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.database import Base, get_db
from app.main import app
from app.models import Alert, AlertConfig, EmailOutbox, SmartMeterReading, User
from app.schemas import MeterSample
from app.services.auth_service import create_access_token, hash_password
from app.services.worker_health_service import record_worker_success
from app.services.email_providers import CapturingMailProvider
from app.services.email_service import process_due_email
from app.services.email_templates import render_email
from app.services.ingestion_service import ingestion_service
from app.services.site_service import ensure_default_site, get_default_meter


alert_module = importlib.import_module("app.services.alert_service")


def _settings(*, enabled: bool = True, max_attempts: int = 3) -> Settings:
    return Settings(
        DEBUG=True,
        JWT_SECRET_KEY="critical-email-test-secret-with-more-than-32-characters",
        ADMIN_PASSWORD="critical-email-admin-password",
        EMAIL_DELIVERY_ENABLED=enabled,
        PUBLIC_FRONTEND_URL="https://app.example.test",
        EMAIL_FROM_ADDRESS="alerts@example.test",
        SMTP_HOST="smtp.example.test",
        SMTP_USERNAME="smtp-user",
        SMTP_PASSWORD="smtp-password",
        EMAIL_MAX_ATTEMPTS=max_attempts,
        EMAIL_RETRY_BASE_SECONDS=1,
    )


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def _account(db, *, email: str, verified: bool, email_enabled: bool):
    user = User(
        email=email,
        password_hash=hash_password("password123"),
        role="user",
        is_active=True,
        email_verified_at=datetime.now(timezone.utc) if verified else None,
    )
    db.add(user)
    db.flush()
    site = ensure_default_site(db, user.id)
    config = AlertConfig(
        user_id=user.id,
        site_id=site.id,
        threshold_kw=2.0,
        cooldown_minutes=5,
        missing_data_minutes=15,
        email_enabled=email_enabled,
    )
    db.add(config)
    db.commit()
    return user, site, get_default_meter(db, user.id), config


def _reading(db, meter_id: int, *, observed_at: datetime, kw: float) -> SmartMeterReading:
    reading = SmartMeterReading(
        meter_id=meter_id,
        timestamp=observed_at,
        gap=kw,
        grp=0.1,
        voltage=230,
        intensity=5.0,
        sub_metering_1=0,
        sub_metering_2=0,
        sub_metering_3=0,
        source="push",
        quality="validated",
    )
    db.add(reading)
    db.flush()
    return reading


def _config_payload(*, email_enabled: bool) -> dict:
    return {
        "threshold_kw": 2.0,
        "cooldown_minutes": 5,
        "missing_data_minutes": 15,
        "email_enabled": email_enabled,
    }


def test_one_critical_incident_enqueues_one_evidence_backed_email(db, monkeypatch):
    settings = _settings()
    monkeypatch.setattr(alert_module, "get_settings", lambda: settings)
    user, site, meter, _ = _account(
        db,
        email="critical@example.com",
        verified=True,
        email_enabled=True,
    )
    site.timezone = "Africa/Casablanca"
    observed_at = datetime(2026, 7, 22, 10, 0, tzinfo=timezone.utc)

    first = alert_module.alert_service.evaluate_reading(
        db,
        meter,
        _reading(db, meter.id, observed_at=observed_at, kw=2.6),
    )
    duplicate = alert_module.alert_service.evaluate_reading(
        db,
        meter,
        _reading(db, meter.id, observed_at=observed_at + timedelta(minutes=1), kw=2.7),
    )
    db.commit()

    assert first is not None and first.severity == "critical"
    assert duplicate is None
    row = db.query(EmailOutbox).one()
    assert row.dedup_key == f"critical-alert:{first.id}:{user.id}"
    assert row.payload["evidence"] == first.evidence_json
    assert row.payload["url"] == f"https://app.example.test/actions#action-{first.id}"

    rendered = render_email(row, settings)
    assert "Observed load: 2.600 kW" in rendered.text_body
    assert "Configured threshold: 2.000 kW" in rendered.text_body
    assert "2026-07-22T11:00:00+01:00 (Africa/Casablanca)" in rendered.text_body
    assert "Source: Meter push API" in rendered.text_body
    assert "cause" not in rendered.text_body.lower()
    assert "savings" not in rendered.text_body.lower()
    assert "control" not in rendered.text_body.lower()


def test_medium_alert_does_not_enqueue_email(db, monkeypatch):
    settings = _settings()
    monkeypatch.setattr(alert_module, "get_settings", lambda: settings)
    _, site, _, config = _account(
        db,
        email="medium@example.com",
        verified=True,
        email_enabled=True,
    )
    now = datetime.now(timezone.utc)
    alert = alert_module.alert_service._create_if_due(
        db,
        site=site,
        config=config,
        rule_key="medium:test",
        alert_type="high_consumption",
        severity="medium",
        message="Measured 1.500 kW against a 2.000 kW threshold.",
        peak_kw=1.5,
        evidence={
            "meter_name": "Primary meter",
            "observed_at": now.isoformat(),
            "observed_kw": 1.5,
            "threshold_kw": 2.0,
            "source": "push",
        },
        now=now,
    )
    db.commit()

    assert alert is not None and alert.severity == "medium"
    assert db.query(EmailOutbox).count() == 0


def test_resolved_critical_alert_respects_cooldown_before_new_email(db, monkeypatch):
    settings = _settings()
    monkeypatch.setattr(alert_module, "get_settings", lambda: settings)
    _, _, meter, _ = _account(
        db,
        email="cooldown@example.com",
        verified=True,
        email_enabled=True,
    )
    now = datetime.now(timezone.utc)
    first = alert_module.alert_service.evaluate_reading(
        db,
        meter,
        _reading(db, meter.id, observed_at=now, kw=2.6),
    )
    alert_module.alert_service.evaluate_reading(
        db,
        meter,
        _reading(db, meter.id, observed_at=now + timedelta(minutes=1), kw=1.0),
    )
    blocked = alert_module.alert_service.evaluate_reading(
        db,
        meter,
        _reading(db, meter.id, observed_at=now + timedelta(minutes=2), kw=2.7),
    )
    after_cooldown = alert_module.alert_service.evaluate_reading(
        db,
        meter,
        _reading(db, meter.id, observed_at=now + timedelta(minutes=6), kw=2.8),
    )
    db.commit()

    assert first is not None and first.resolved_at is not None
    assert blocked is None
    assert after_cooldown is not None
    assert db.query(EmailOutbox).count() == 2


@pytest.mark.parametrize(
    ("mail_enabled", "verified", "preference", "kw"),
    [
        (False, True, True, 2.6),
        (True, False, True, 2.6),
        (True, True, False, 2.6),
        (True, True, True, 2.2),
    ],
)
def test_ineligible_or_noncritical_alerts_do_not_enqueue(
    db,
    monkeypatch,
    mail_enabled,
    verified,
    preference,
    kw,
):
    settings = _settings(enabled=mail_enabled)
    monkeypatch.setattr(alert_module, "get_settings", lambda: settings)
    _, _, meter, _ = _account(
        db,
        email=f"case-{mail_enabled}-{verified}-{preference}-{kw}@example.com",
        verified=verified,
        email_enabled=preference,
    )
    now = datetime.now(timezone.utc)
    alert = alert_module.alert_service.evaluate_reading(
        db,
        meter,
        _reading(db, meter.id, observed_at=now, kw=kw),
    )
    db.commit()

    assert alert is not None
    assert db.query(EmailOutbox).count() == 0


def test_config_exposes_eligibility_and_rejects_invalid_opt_in(db, monkeypatch):
    settings = _settings(enabled=False)
    monkeypatch.setattr(alert_module, "get_settings", lambda: settings)
    verified, _, _, _ = _account(
        db,
        email="verified@example.com",
        verified=True,
        email_enabled=False,
    )
    unverified, _, _, _ = _account(
        db,
        email="unverified@example.com",
        verified=False,
        email_enabled=False,
    )

    Session = sessionmaker(bind=db.get_bind())

    def override_get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        verified_headers = {"Authorization": f"Bearer {create_access_token({'sub': str(verified.id)})}"}
        unverified_headers = {"Authorization": f"Bearer {create_access_token({'sub': str(unverified.id)})}"}

        disabled = client.get("/api/v1/alerts/config", headers=verified_headers)
        assert disabled.status_code == 200
        assert disabled.json()["email_enabled"] is False
        assert disabled.json()["email_delivery_available"] is False
        assert disabled.json()["email_delivery_unavailable_reason"] == "mail_disabled"
        rejected = client.post(
            "/api/v1/alerts/config",
            headers=verified_headers,
            json=_config_payload(email_enabled=True),
        )
        assert rejected.status_code == 409
        assert rejected.json()["detail"]["code"] == "alert_email_delivery_unavailable"

        settings.EMAIL_DELIVERY_ENABLED = True
        unverified_result = client.get("/api/v1/alerts/config", headers=unverified_headers)
        assert unverified_result.json()["email_delivery_unavailable_reason"] == "email_unverified"
        rejected = client.post(
            "/api/v1/alerts/config",
            headers=unverified_headers,
            json=_config_payload(email_enabled=True),
        )
        assert rejected.status_code == 409
        assert rejected.json()["detail"]["code"] == "alert_email_delivery_unavailable"

        record_worker_success(db, "email")
        db.commit()
        enabled = client.post(
            "/api/v1/alerts/config",
            headers=verified_headers,
            json=_config_payload(email_enabled=True),
        )
        assert enabled.status_code == 200
        assert enabled.json()["email_enabled"] is True
        assert enabled.json()["email_delivery_available"] is True
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_alert_collection_paths_are_direct_under_https_proxy_headers(db):
    user, _, _, _ = _account(
        db,
        email="canonical-alerts@example.com",
        verified=True,
        email_enabled=False,
    )
    Session = sessionmaker(bind=db.get_bind())

    def override_get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    headers = {
        "Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}",
        "X-Forwarded-Proto": "https",
        "Host": "api.example.test",
    }
    try:
        for path in ("/api/v1/alerts", "/api/v1/alerts/"):
            response = client.get(path, headers=headers, follow_redirects=False)
            assert response.status_code == 200
            assert "location" not in response.headers
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_acknowledge_resolve_and_reopen_do_not_resend(db, monkeypatch):
    settings = _settings()
    monkeypatch.setattr(alert_module, "get_settings", lambda: settings)
    user, _, meter, _ = _account(
        db,
        email="lifecycle@example.com",
        verified=True,
        email_enabled=True,
    )
    alert = alert_module.alert_service.evaluate_reading(
        db,
        meter,
        _reading(db, meter.id, observed_at=datetime.now(timezone.utc), kw=2.6),
    )
    db.commit()
    assert alert is not None

    Session = sessionmaker(bind=db.get_bind())

    def override_get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}
    try:
        assert client.patch(f"/api/v1/alerts/{alert.id}/acknowledge", headers=headers).status_code == 200
        assert client.patch(f"/api/v1/alerts/{alert.id}/resolve", headers=headers).status_code == 200
        assert client.patch(f"/api/v1/alerts/{alert.id}/reopen", headers=headers).status_code == 200
        assert db.query(EmailOutbox).count() == 1
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_ingestion_commits_while_provider_is_unavailable(db, monkeypatch):
    settings = _settings(max_attempts=2)
    monkeypatch.setattr(alert_module, "get_settings", lambda: settings)
    _, _, meter, _ = _account(
        db,
        email="outage@example.com",
        verified=True,
        email_enabled=True,
    )
    observed_at = datetime.now(timezone.utc)

    result = ingestion_service.ingest(
        db,
        meter,
        [MeterSample(timestamp=observed_at, active_power_kw=2.6)],
        source="push",
        idempotency_key="critical-provider-outage",
    )
    db.commit()

    assert result["accepted_rows"] == 1
    assert db.query(Alert).count() == 1
    assert db.query(EmailOutbox).count() == 1
    provider = CapturingMailProvider(failure=RuntimeError("SMTP unavailable"))
    assert process_due_email(db, provider=provider, settings=settings, worker_id="g5-outage") == 1

    assert db.query(Alert).count() == 1
    assert db.query(SmartMeterReading).count() == 1
    row = db.query(EmailOutbox).one()
    assert row.status == "retry"
    assert row.last_error == "builtins.RuntimeError"


def test_alert_email_is_owner_scoped_and_other_user_cannot_mutate_it(db, monkeypatch):
    settings = _settings()
    monkeypatch.setattr(alert_module, "get_settings", lambda: settings)
    owner, _, meter, _ = _account(
        db,
        email="owner@example.com",
        verified=True,
        email_enabled=True,
    )
    other, _, _, _ = _account(
        db,
        email="other@example.com",
        verified=True,
        email_enabled=True,
    )
    alert = alert_module.alert_service.evaluate_reading(
        db,
        meter,
        _reading(db, meter.id, observed_at=datetime.now(timezone.utc), kw=2.6),
    )
    db.commit()
    row = db.query(EmailOutbox).one()
    assert row.user_id == owner.id
    assert row.recipient == owner.email

    Session = sessionmaker(bind=db.get_bind())

    def override_get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    other_headers = {"Authorization": f"Bearer {create_access_token({'sub': str(other.id)})}"}
    try:
        assert client.patch(f"/api/v1/alerts/{alert.id}/resolve", headers=other_headers).status_code == 404
        assert db.query(EmailOutbox).count() == 1
    finally:
        app.dependency_overrides.pop(get_db, None)
