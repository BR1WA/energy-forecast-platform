from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import AccountActionToken, EmailOutbox, RefreshToken, User
from app.routers import auth as auth_router
from app.services.account_action_service import consume_action_token, issue_action_token, unseal_action_token
from app.services.auth_service import hash_password


engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _db_override():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _client():
    app.dependency_overrides[get_db] = _db_override
    return TestClient(app)


def _user(db, email="person@example.com", password="oldpassword123"):
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


def setup_function():
    Base.metadata.create_all(engine)
    auth_router.settings.EMAIL_DELIVERY_ENABLED = True
    auth_router.settings.DEBUG = True


def teardown_function():
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(engine)


def test_verification_is_single_use_and_cross_purpose_safe():
    db = SessionLocal()
    user = User(email="waiting@example.com", password_hash=hash_password("password123"), role="user", is_active=True)
    db.add(user)
    db.commit()
    issued = issue_action_token(db, user.id, "verify_email")
    db.commit()

    client = _client()
    wrong = client.post("/api/v1/auth/password-reset/confirm", json={"token": issued.raw_token, "new_password": "replacement123"})
    assert wrong.status_code == 400
    assert wrong.json()["detail"]["code"] == "reset_token_invalid"
    verified = client.post("/api/v1/auth/verification/confirm", json={"token": issued.raw_token})
    assert verified.status_code == 200
    replay = client.post("/api/v1/auth/verification/confirm", json={"token": issued.raw_token})
    assert replay.status_code == 400
    db.expire_all()
    assert db.get(User, user.id).email_verified_at is not None
    db.close()


def test_expired_and_rotated_tokens_fail_without_consuming_the_replacement():
    db = SessionLocal()
    user = _user(db)
    expired = issue_action_token(db, user.id, "reset_password", expires_in_minutes=-1)
    replacement = issue_action_token(db, user.id, "reset_password")
    db.commit()
    assert consume_action_token(db, expired.raw_token, "reset_password") is None
    assert consume_action_token(db, replacement.raw_token, "reset_password") is not None
    db.commit()
    assert consume_action_token(db, replacement.raw_token, "reset_password") is None
    db.close()


def test_resend_rotates_after_cooldown_and_deduplicates_during_cooldown():
    db = SessionLocal()
    user = User(email="waiting@example.com", password_hash=hash_password("password123"), role="user", is_active=True)
    db.add(user)
    db.commit()
    client = _client()

    first = client.post("/api/v1/auth/verification/resend", json={"email": user.email})
    second = client.post("/api/v1/auth/verification/resend", json={"email": user.email})
    assert first.status_code == second.status_code == 202
    assert first.json() == second.json()
    assert db.query(AccountActionToken).filter_by(user_id=user.id, purpose="verify_email").count() == 1
    assert db.query(EmailOutbox).filter_by(user_id=user.id, template="verify_email").count() == 1

    token = db.query(AccountActionToken).filter_by(user_id=user.id, purpose="verify_email").one()
    token.created_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
    db.commit()
    third = client.post("/api/v1/auth/verification/resend", json={"email": user.email})
    assert third.status_code == 202
    rows = db.query(AccountActionToken).filter_by(user_id=user.id, purpose="verify_email").order_by(AccountActionToken.id).all()
    assert len(rows) == 2
    assert rows[0].revoked_at is not None
    db.close()


def test_password_reset_request_is_neutral_and_reset_revokes_all_sessions():
    db = SessionLocal()
    user = _user(db, "reset@example.com")
    client = _client()
    login = client.post("/api/v1/auth/login", json={"email": user.email, "password": "oldpassword123"})
    assert login.status_code == 200
    known = client.post("/api/v1/auth/password-reset/request", json={"email": user.email})
    unknown = client.post("/api/v1/auth/password-reset/request", json={"email": "missing@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()

    outbox = db.query(EmailOutbox).filter_by(user_id=user.id, template="password_reset").one()
    raw = unseal_action_token(outbox.payload["sealed_token"])
    reset = client.post("/api/v1/auth/password-reset/confirm", json={"token": raw, "new_password": "newpassword123"})
    assert reset.status_code == 200
    assert all(row.is_revoked for row in db.query(RefreshToken).filter_by(user_id=user.id).all())
    replay = client.post("/api/v1/auth/password-reset/confirm", json={"token": raw, "new_password": "anotherpassword123"})
    assert replay.status_code == 400
    db.close()
