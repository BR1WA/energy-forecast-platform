from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import AuthIdentity, EmailOutbox, User
from app.routers import auth as auth_router
from app.services.account_action_service import unseal_action_token
from app.services.auth_service import create_access_token, hash_password


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
ORIGINAL_EMAIL_DELIVERY_ENABLED = auth_router.settings.EMAIL_DELIVERY_ENABLED
ORIGINAL_DEBUG = auth_router.settings.DEBUG


def _override_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return {"Authorization": f"Bearer {token}"}


def _user(
    db,
    email: str,
    *,
    role: str = "user",
    verified: bool = True,
    active: bool = True,
) -> User:
    user = User(
        email=email,
        password_hash=hash_password("testpassword123"),
        full_name=email.split("@", 1)[0].replace("-", " ").title(),
        role=role,
        is_active=active,
        email_verified_at=datetime.now(timezone.utc) if verified else None,
    )
    db.add(user)
    db.commit()
    return user


def setup_function():
    Base.metadata.create_all(engine)
    app.dependency_overrides[get_db] = _override_db
    app.state.limiter._storage.reset()
    auth_router.settings.EMAIL_DELIVERY_ENABLED = True
    auth_router.settings.DEBUG = True


def teardown_function():
    app.dependency_overrides.pop(get_db, None)
    app.state.limiter._storage.reset()
    auth_router.settings.EMAIL_DELIVERY_ENABLED = ORIGINAL_EMAIL_DELIVERY_ENABLED
    auth_router.settings.DEBUG = ORIGINAL_DEBUG
    Base.metadata.drop_all(engine)


def test_registration_verification_and_admin_actions_preserve_security_gate():
    db = SessionLocal()
    admin = _user(db, "admin@example.com", role="admin")
    client = TestClient(app)

    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": "waiting@example.com",
            "password": "testpassword123",
            "full_name": "Waiting User",
        },
    )
    assert registration.status_code == 201
    pending = db.query(User).filter_by(email="waiting@example.com").one()
    assert pending.email_verified_at is None

    listed = client.get("/api/v1/admin/users", headers=_headers(admin))
    assert listed.status_code == 200
    pending_payload = next(item for item in listed.json() if item["id"] == pending.id)
    assert pending_payload["lifecycle_status"] == "pending_verification"
    assert "password_hash" not in pending_payload
    assert "verification_token" not in pending_payload

    rejected = client.post(
        "/api/v1/auth/login",
        json={"email": pending.email, "password": "testpassword123"},
    )
    assert rejected.status_code == 403
    assert rejected.json()["detail"]["code"] == "email_verification_required"

    disabled = client.put(
        f"/api/v1/admin/users/{pending.id}",
        json={"is_active": False},
        headers=_headers(admin),
    )
    assert disabled.status_code == 200
    assert disabled.json()["lifecycle_status"] == "pending_verification"
    assert disabled.json()["is_active"] is False

    enabled = client.put(
        f"/api/v1/admin/users/{pending.id}",
        json={"is_active": True},
        headers=_headers(admin),
    )
    assert enabled.status_code == 200
    assert enabled.json()["lifecycle_status"] == "pending_verification"

    still_rejected = client.post(
        "/api/v1/auth/login",
        json={"email": pending.email, "password": "testpassword123"},
    )
    assert still_rejected.status_code == 403
    assert still_rejected.json()["detail"]["code"] == "email_verification_required"

    resend = client.post(
        "/api/v1/auth/verification/resend",
        json={"email": pending.email},
    )
    assert resend.status_code == 202
    assert db.query(EmailOutbox).filter_by(user_id=pending.id, template="verify_email").count() == 1

    outbox = db.query(EmailOutbox).filter_by(user_id=pending.id, template="verify_email").one()
    raw_token = unseal_action_token(outbox.payload["sealed_token"])
    verified = client.post(
        "/api/v1/auth/verification/confirm",
        json={"token": raw_token},
    )
    assert verified.status_code == 200

    active_payload = next(
        item
        for item in client.get("/api/v1/admin/users", headers=_headers(admin)).json()
        if item["id"] == pending.id
    )
    assert active_payload["lifecycle_status"] == "active"
    login = client.post(
        "/api/v1/auth/login",
        json={"email": pending.email, "password": "testpassword123"},
    )
    assert login.status_code == 200
    db.close()


def test_admin_statistics_are_exhaustive_and_google_verified_user_is_active():
    db = SessionLocal()
    admin = _user(db, "admin@example.com", role="admin")
    pending = _user(db, "pending@example.com", verified=False, active=False)
    disabled = _user(db, "disabled@example.com", verified=True, active=False)
    google_user = _user(db, "google@example.com")
    db.add(AuthIdentity(
        user_id=google_user.id,
        provider="google",
        subject="google-subject",
        email=google_user.email,
    ))
    db.commit()
    client = TestClient(app)

    users_response = client.get("/api/v1/admin/users", headers=_headers(admin))
    assert users_response.status_code == 200
    users = {item["id"]: item for item in users_response.json()}
    assert users[pending.id]["lifecycle_status"] == "pending_verification"
    assert users[disabled.id]["lifecycle_status"] == "disabled"
    assert users[google_user.id]["lifecycle_status"] == "active"

    stats = client.get("/api/v1/admin/stats", headers=_headers(admin))
    assert stats.status_code == 200
    counts = stats.json()
    assert counts["total_users"] == 4
    assert counts["active_users"] == 2
    assert counts["pending_users"] == 1
    assert counts["disabled_users"] == 1
    assert counts["total_users"] == (
        counts["active_users"] + counts["pending_users"] + counts["disabled_users"]
    )

    warmup = {
        "available": True,
        "warmed": True,
        "error": None,
        "display_name": "Test model",
        "version": "test",
        "artifact_fingerprint": "test-fingerprint",
    }
    with patch("app.routers.admin.product_forecast_service.warmup", return_value=warmup):
        health = client.get("/api/v1/admin/health", headers=_headers(admin))
    assert health.status_code == 200
    for field in ("total_users", "active_users", "pending_users", "disabled_users"):
        assert health.json()[field] == counts[field]
    db.close()


def test_admin_authorization_and_final_verified_admin_protection_remain_enforced():
    db = SessionLocal()
    admin = _user(db, "only-verified-admin@example.com", role="admin")
    unverified_admin = _user(
        db,
        "unverified-admin@example.com",
        role="admin",
        verified=False,
    )
    ordinary_user = _user(db, "ordinary@example.com")
    client = TestClient(app)

    assert client.get("/api/v1/admin/users").status_code == 401
    assert client.get("/api/v1/admin/users", headers=_headers(ordinary_user)).status_code == 403

    final_admin = client.put(
        f"/api/v1/admin/users/{admin.id}",
        json={"is_active": False},
        headers=_headers(admin),
    )
    assert final_admin.status_code == 409
    assert db.get(User, admin.id).is_active is True
    assert db.get(User, unverified_admin.id).email_verified_at is None
    db.close()
