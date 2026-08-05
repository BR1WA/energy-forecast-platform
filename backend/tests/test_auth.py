from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import AccountActionToken, AuditEvent, EmailOutbox, Meter, RefreshToken, Site, User
from app.routers import auth as auth_router
from app.services.account_action_service import hash_action_token, unseal_action_token
from app.services.auth_service import create_access_token, hash_password


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
ORIGIN = "http://localhost:3000"


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


client = TestClient(app)


class TestAuthAndTokens(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_db] = override_get_db
        client.cookies.clear()
        Base.metadata.create_all(bind=engine)
        self.db = TestingSessionLocal()
        self.original_email_delivery = auth_router.settings.EMAIL_DELIVERY_ENABLED
        auth_router.settings.EMAIL_DELIVERY_ENABLED = True
        auth_router.settings.DEBUG = True

    def tearDown(self):
        auth_router.settings.EMAIL_DELIVERY_ENABLED = self.original_email_delivery
        self.db.close()
        Base.metadata.drop_all(bind=engine)
        app.dependency_overrides.pop(get_db, None)

    def _verified_user(self, email: str, password: str = "testpassword123") -> User:
        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name="Verified User",
            role="user",
            is_active=True,
            email_verified_at=datetime.now(timezone.utc),
        )
        self.db.add(user)
        self.db.commit()
        return user

    def _login(self, user: User, password: str = "testpassword123"):
        return client.post("/api/v1/auth/login", json={"email": user.email, "password": password})

    def test_registration_is_unverified_and_has_no_session_or_raw_token_at_rest(self):
        response = client.post(
            "/api/v1/auth/register",
            json={"email": " NewUser@Example.COM ", "password": "testpassword123", "full_name": "New User"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("access_token", response.json())
        self.assertIsNone(response.cookies.get("refresh_token"))
        self.assertEqual(self.db.query(RefreshToken).count(), 0)

        user = self.db.query(User).filter(User.email == "newuser@example.com").one()
        self.assertIsNone(user.email_verified_at)
        action = self.db.query(AccountActionToken).filter_by(user_id=user.id, purpose="verify_email").one()
        outbox = self.db.query(EmailOutbox).filter_by(user_id=user.id, template="verify_email").one()
        raw_token = unseal_action_token(outbox.payload["sealed_token"])
        self.assertEqual(action.token_hash, hash_action_token(raw_token))
        self.assertNotIn(raw_token, str(outbox.payload))
        self.assertNotIn("token=", str(outbox.payload))

        site = self.db.query(Site).filter(Site.user_id == user.id).one()
        meter = self.db.query(Meter).filter(Meter.site_id == site.id, Meter.is_primary.is_(True)).one()
        self.assertEqual(meter.name, "Primary meter")

    def test_unverified_login_uses_typed_public_error(self):
        user = User(
            email="waiting@example.com",
            password_hash=hash_password("testpassword123"),
            role="user",
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        response = self._login(user)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["code"], "email_verification_required")
        self.assertIsNone(response.cookies.get("refresh_token"))

    def test_registration_rejects_short_password(self):
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "weak@example.com", "password": "short", "full_name": "Weak Password"},
        )
        self.assertEqual(response.status_code, 422)

    def test_database_rejects_a_second_site_for_one_user(self):
        user = self._verified_user("one-site@example.com")
        self.db.add(Site(user_id=user.id, name="First"))
        self.db.commit()
        self.db.add(Site(user_id=user.id, name="Second"))
        with self.assertRaises(IntegrityError):
            self.db.flush()
        self.db.rollback()

    def test_login_persists_only_refresh_hash_and_sets_hardened_cookie(self):
        response = self._login(self._verified_user("loginuser@example.com"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.json())
        self.assertNotIn("refresh_token", response.json())
        refresh = response.cookies.get("refresh_token")
        self.assertIsNotNone(refresh)
        stored = self.db.query(RefreshToken).filter_by(token_hash=hashlib.sha256(refresh.encode()).hexdigest()).one()
        self.assertFalse(stored.is_revoked)
        cookie = response.headers["set-cookie"].lower()
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=lax", cookie)
        self.assertIn("path=/api/v1/auth", cookie)

    def test_refresh_requires_origin_rotates_and_rejects_replay(self):
        login = self._login(self._verified_user("refreshuser@example.com"))
        first = login.cookies.get("refresh_token")
        self.assertEqual(client.post("/api/v1/auth/refresh").status_code, 403)

        client.cookies.set("refresh_token", first, path="/api/v1/auth")
        rotated = client.post("/api/v1/auth/refresh", headers={"Origin": ORIGIN})
        self.assertEqual(rotated.status_code, 200)
        second = rotated.cookies.get("refresh_token")
        self.assertNotEqual(first, second)
        self.assertTrue(self.db.query(RefreshToken).filter_by(token_hash=hashlib.sha256(first.encode()).hexdigest()).one().is_revoked)

        client.cookies.set("refresh_token", first, path="/api/v1/auth")
        replay = client.post("/api/v1/auth/refresh", headers={"Origin": ORIGIN})
        self.assertEqual(replay.status_code, 401)
        self.assertEqual(replay.json()["detail"]["code"], "refresh_token_replayed")

    def test_logout_current_and_logout_all_revoke_sessions(self):
        user = self._verified_user("logout@example.com")
        first = self._login(user)
        first_refresh = first.cookies.get("refresh_token")
        first_access = first.json()["access_token"]
        second = self._login(user)
        second_refresh = second.cookies.get("refresh_token")

        client.cookies.set("refresh_token", first_refresh, path="/api/v1/auth")
        logout = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {first_access}", "Origin": ORIGIN},
        )
        self.assertEqual(logout.status_code, 200)
        first_row = self.db.query(RefreshToken).filter_by(token_hash=hashlib.sha256(first_refresh.encode()).hexdigest()).one()
        second_row = self.db.query(RefreshToken).filter_by(token_hash=hashlib.sha256(second_refresh.encode()).hexdigest()).one()
        self.assertTrue(first_row.is_revoked)
        self.assertFalse(second_row.is_revoked)

        client.cookies.set("refresh_token", second_refresh, path="/api/v1/auth")
        logout_all = client.post(
            "/api/v1/auth/logout-all",
            headers={"Authorization": f"Bearer {second.json()['access_token']}", "Origin": ORIGIN},
        )
        self.assertEqual(logout_all.status_code, 200)
        self.db.expire_all()
        self.assertTrue(all(row.is_revoked for row in self.db.query(RefreshToken).filter_by(user_id=user.id).all()))

    def test_final_active_admin_cannot_be_disabled_or_demoted(self):
        admin = User(
            email="only-admin@example.com",
            password_hash=hash_password("adminpassword123"),
            full_name="Only Admin",
            role="admin",
            is_active=True,
            email_verified_at=datetime.now(timezone.utc),
        )
        self.db.add(admin)
        self.db.commit()
        access = create_access_token({"sub": str(admin.id), "role": "admin"})
        for payload in ({"is_active": False}, {"role": "user"}):
            response = client.put(
                f"/api/v1/admin/users/{admin.id}",
                json=payload,
                headers={"Authorization": f"Bearer {access}"},
            )
            self.assertEqual(response.status_code, 409)

    def test_admin_dead_letter_retry_is_explicit_and_audited(self):
        admin = User(
            email="retry-admin@example.com",
            password_hash=hash_password("adminpassword123"),
            role="admin",
            is_active=True,
            email_verified_at=datetime.now(timezone.utc),
        )
        self.db.add(admin)
        self.db.flush()
        row = EmailOutbox(
            id="dead-letter-for-audit",
            recipient="capture@example.test",
            template="critical_alert",
            template_version="v1",
            payload={},
            dedup_key="dead-letter:audit",
            status="dead",
            attempts=5,
        )
        self.db.add(row)
        self.db.commit()
        access = create_access_token({"sub": str(admin.id), "role": "admin"})
        response = client.post(
            f"/api/v1/admin/email-outbox/{row.id}/retry",
            headers={"Authorization": f"Bearer {access}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "retry")
        self.assertEqual(self.db.query(AuditEvent).filter_by(event_type="email.retry_requested").count(), 1)

    def test_password_change_requires_origin_and_revokes_existing_sessions(self):
        user = self._verified_user("passworduser@example.com", "oldpassword123")
        login = self._login(user, "oldpassword123")
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        self.assertEqual(
            client.put(
                "/api/v1/auth/password",
                json={"current_password": "oldpassword123", "new_password": "newpassword123"},
                headers=headers,
            ).status_code,
            403,
        )
        headers["Origin"] = ORIGIN
        changed = client.put(
            "/api/v1/auth/password",
            json={"current_password": "oldpassword123", "new_password": "newpassword123"},
            headers=headers,
        )
        self.assertEqual(changed.status_code, 200)
        self.assertTrue(all(row.is_revoked for row in self.db.query(RefreshToken).filter_by(user_id=user.id).all()))


if __name__ == "__main__":
    unittest.main()
