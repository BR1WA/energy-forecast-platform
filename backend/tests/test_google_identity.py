from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import AuthIdentity, RefreshToken, User
from app.routers import auth as auth_router
from app.services.auth_service import create_access_token, hash_password


engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
ORIGIN = "http://localhost:3000"
CREDENTIAL = "controlled-google-credential-value"


def _override_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def setup_function():
    Base.metadata.create_all(engine)
    app.dependency_overrides[get_db] = _override_db
    auth_router.settings.DEBUG = True
    auth_router.settings.GOOGLE_AUTH_ENABLED = True
    auth_router.settings.GOOGLE_CLIENT_ID = "browser-client.apps.example.test"


def teardown_function():
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(engine)


def _local_user(db, email="local@example.com", password="localpassword123"):
    user = User(
        email=email,
        password_hash=hash_password(password),
        role="user",
        is_active=True,
        email_verified_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    return user


def _headers(user):
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id), 'role': user.role})}", "Origin": ORIGIN}


def _claims(nonce, email="local@example.com", subject="google-subject-1"):
    return {
        "iss": "https://accounts.google.com",
        "aud": auth_router.settings.GOOGLE_CLIENT_ID,
        "nonce": nonce,
        "email_verified": True,
        "email": email,
        "sub": subject,
        "name": "Google User",
    }


def test_matching_email_cannot_silently_merge_on_google_login():
    db = SessionLocal()
    _local_user(db)
    client = TestClient(app)
    challenge = client.post("/api/v1/auth/google/challenge", headers={"Origin": ORIGIN}).json()
    with patch.object(auth_router, "_unverified_google_nonce", return_value=challenge["nonce"]), patch.object(
        auth_router, "_verified_google_identity", return_value=_claims(challenge["nonce"])
    ):
        response = client.post(
            "/api/v1/auth/google",
            headers={"Origin": ORIGIN},
            json={"credential": CREDENTIAL, "state": challenge["state"]},
        )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "google_link_required"
    assert db.query(AuthIdentity).count() == 0
    db.close()


def test_link_requires_password_matching_email_and_rejects_duplicate_subject():
    db = SessionLocal()
    user = _local_user(db)
    other = _local_user(db, "other@example.com")
    db.add(AuthIdentity(user_id=other.id, provider="google", subject="owned-subject", email=other.email))
    db.commit()
    client = TestClient(app)
    headers = _headers(user)
    challenge = client.post("/api/v1/auth/google/link/challenge", headers=headers).json()

    wrong_password = client.post(
        "/api/v1/auth/google/link",
        headers=headers,
        json={"credential": CREDENTIAL, "state": challenge["state"], "current_password": "wrong"},
    )
    assert wrong_password.status_code == 403
    assert wrong_password.json()["detail"]["code"] == "recent_auth_required"

    with patch.object(auth_router, "_unverified_google_nonce", return_value=challenge["nonce"]), patch.object(
        auth_router, "_verified_google_identity", return_value=_claims(challenge["nonce"], subject="owned-subject")
    ):
        duplicate = client.post(
            "/api/v1/auth/google/link",
            headers=headers,
            json={"credential": CREDENTIAL, "state": challenge["state"], "current_password": "localpassword123"},
        )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "google_subject_in_use"

    challenge = client.post("/api/v1/auth/google/link/challenge", headers=headers).json()
    with patch.object(auth_router, "_unverified_google_nonce", return_value=challenge["nonce"]), patch.object(
        auth_router, "_verified_google_identity", return_value=_claims(challenge["nonce"], email="different@example.com", subject="new-subject")
    ):
        mismatch = client.post(
            "/api/v1/auth/google/link",
            headers=headers,
            json={"credential": CREDENTIAL, "state": challenge["state"], "current_password": "localpassword123"},
        )
    assert mismatch.status_code == 400
    assert mismatch.json()["detail"]["code"] == "google_email_mismatch"
    db.close()


def test_explicit_link_and_unlink_revoke_sessions_and_protect_last_method():
    db = SessionLocal()
    user = _local_user(db)
    client = TestClient(app)
    login = client.post("/api/v1/auth/login", json={"email": user.email, "password": "localpassword123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}", "Origin": ORIGIN}
    challenge = client.post("/api/v1/auth/google/link/challenge", headers=headers).json()
    with patch.object(auth_router, "_unverified_google_nonce", return_value=challenge["nonce"]), patch.object(
        auth_router, "_verified_google_identity", return_value=_claims(challenge["nonce"])
    ):
        linked = client.post(
            "/api/v1/auth/google/link",
            headers=headers,
            json={"credential": CREDENTIAL, "state": challenge["state"], "current_password": "localpassword123"},
        )
    assert linked.status_code == 200
    assert db.query(AuthIdentity).filter_by(user_id=user.id, provider="google").count() == 1

    unlinked = client.request(
        "DELETE",
        "/api/v1/auth/google/link",
        headers=headers,
        json={"current_password": "localpassword123"},
    )
    assert unlinked.status_code == 200
    db.expire_all()
    assert db.query(AuthIdentity).filter_by(user_id=user.id).count() == 0
    assert all(row.is_revoked for row in db.query(RefreshToken).filter_by(user_id=user.id).all())

    google_only = User(email="google-only@example.com", role="user", is_active=True, email_verified_at=datetime.now(timezone.utc))
    db.add(google_only)
    db.flush()
    db.add(AuthIdentity(user_id=google_only.id, provider="google", subject="only-subject", email=google_only.email))
    db.commit()
    protected = client.request("DELETE", "/api/v1/auth/google/link", headers=_headers(google_only), json={})
    assert protected.status_code == 409
    assert protected.json()["detail"]["code"] == "last_login_method"
    db.close()


@pytest.mark.parametrize(
    ("claims", "code"),
    [
        ({"iss": "attacker.example", "aud": "browser-client.apps.example.test", "nonce": "n", "email_verified": True, "email": "x@example.com", "sub": "s"}, "google_issuer_invalid"),
        ({"iss": "accounts.google.com", "aud": "other-client", "nonce": "n", "email_verified": True, "email": "x@example.com", "sub": "s"}, "google_audience_invalid"),
        ({"iss": "accounts.google.com", "aud": "browser-client.apps.example.test", "nonce": "wrong", "email_verified": True, "email": "x@example.com", "sub": "s"}, "google_nonce_invalid"),
        ({"iss": "accounts.google.com", "aud": "browser-client.apps.example.test", "nonce": "n", "email_verified": False, "email": "x@example.com", "sub": "s"}, "google_email_unverified"),
    ],
)
def test_google_claim_validation_rejects_invalid_credentials(claims, code):
    with patch.object(auth_router, "_verify_google_token", return_value=claims):
        with pytest.raises(HTTPException) as exc:
            auth_router._verified_google_identity(CREDENTIAL, expected_nonce="n")
    assert exc.value.detail["code"] == code


def test_google_signature_or_expiration_failure_is_typed():
    with patch.object(auth_router, "_verify_google_token", side_effect=ValueError("expired or invalid signature")):
        with pytest.raises(HTTPException) as exc:
            auth_router._verified_google_identity(CREDENTIAL, expected_nonce="n")
    assert exc.value.detail["code"] == "google_credential_invalid"
