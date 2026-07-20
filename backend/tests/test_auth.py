import unittest
import os
import hashlib
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.database import Base, get_db
from app.main import app
from app.models import Meter, RefreshToken, Site, User
from app.services.auth_service import hash_password, create_access_token

from sqlalchemy.pool import StaticPool
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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
        Base.metadata.create_all(bind=engine)
        self.db = TestingSessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)
        if get_db in app.dependency_overrides:
            del app.dependency_overrides[get_db]

    def test_register_flow_persists_refresh_token(self):
        payload = {
            "email": " NewUser@Example.COM ",
            "password": "testpassword123",
            "full_name": "New User"
        }
        res = client.post("/api/v1/auth/register", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)

        # Verify token is persisted in DB
        refresh_token = data["refresh_token"]
        token_hash = hashlib.sha256(refresh_token.encode('utf-8')).hexdigest()
        db_token = self.db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
        self.assertIsNotNone(db_token)
        self.assertEqual(db_token.is_revoked, False)
        user = self.db.query(User).filter(User.email == "newuser@example.com").one()
        site = self.db.query(Site).filter(Site.user_id == user.id).one()
        meter = self.db.query(Meter).filter(
            Meter.site_id == site.id, Meter.is_primary.is_(True)
        ).one()
        self.assertEqual(meter.name, "Primary meter")

    def test_registration_rejects_short_password(self):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "weak@example.com",
                "password": "short",
                "full_name": "Weak Password",
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_database_rejects_a_second_site_for_one_user(self):
        user = User(
            email="one-site@example.com",
            password_hash=hash_password("password123"),
            full_name="One Site",
            role="user",
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        self.db.add(Site(user_id=user.id, name="First"))
        self.db.commit()
        self.db.add(Site(user_id=user.id, name="Second"))
        with self.assertRaises(IntegrityError):
            self.db.flush()
        self.db.rollback()

    def test_login_flow_persists_refresh_token(self):
        # Create a user first
        user = User(
            email="loginuser@example.com",
            password_hash=hash_password("loginpassword123"),
            full_name="Login User",
            role="user",
            is_active=True
        )
        self.db.add(user)
        self.db.commit()

        # Login
        payload = {
            "email": "loginuser@example.com",
            "password": "loginpassword123"
        }
        res = client.post("/api/v1/auth/login", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)

        # Verify token in DB
        refresh_token = data["refresh_token"]
        token_hash = hashlib.sha256(refresh_token.encode('utf-8')).hexdigest()
        db_token = self.db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
        self.assertIsNotNone(db_token)
        self.assertEqual(db_token.is_revoked, False)

    def test_refresh_token_rotation_and_replay_prevention(self):
        user = User(
            email="refreshuser@example.com",
            password_hash=hash_password("refreshpassword123"),
            full_name="Refresh User",
            role="user",
            is_active=True
        )
        self.db.add(user)
        self.db.commit()

        # Login to get initial tokens
        login_res = client.post("/api/v1/auth/login", json={"email": "refreshuser@example.com", "password": "refreshpassword123"})
        self.assertEqual(login_res.status_code, 200)
        tokens = login_res.json()
        first_refresh = tokens["refresh_token"]

        # 1. Refresh using first token
        refresh_res = client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
        self.assertEqual(refresh_res.status_code, 200)
        refresh_data = refresh_res.json()
        self.assertIn("access_token", refresh_data)
        self.assertIn("refresh_token", refresh_data)
        
        second_refresh = refresh_data["refresh_token"]
        self.assertNotEqual(first_refresh, second_refresh)

        # Verify first token is revoked in DB, second is active
        first_hash = hashlib.sha256(first_refresh.encode('utf-8')).hexdigest()
        second_hash = hashlib.sha256(second_refresh.encode('utf-8')).hexdigest()

        first_db = self.db.query(RefreshToken).filter(RefreshToken.token_hash == first_hash).first()
        second_db = self.db.query(RefreshToken).filter(RefreshToken.token_hash == second_hash).first()

        self.assertIsNotNone(first_db)
        self.assertEqual(first_db.is_revoked, True)
        self.assertIsNotNone(second_db)
        self.assertEqual(second_db.is_revoked, False)

        # 2. Replay prevention: try to refresh using first_refresh again -> should fail
        replay_res = client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
        self.assertEqual(replay_res.status_code, 401)

        # 3. Refresh using second_refresh -> should succeed
        refresh_res2 = client.post("/api/v1/auth/refresh", json={"refresh_token": second_refresh})
        self.assertEqual(refresh_res2.status_code, 200)

    def test_logout_revokes_tokens(self):
        user = User(
            email="logoutuser@example.com",
            password_hash=hash_password("logoutpassword123"),
            full_name="Logout User",
            role="user",
            is_active=True
        )
        self.db.add(user)
        self.db.commit()

        # Login
        login_res = client.post("/api/v1/auth/login", json={"email": "logoutuser@example.com", "password": "logoutpassword123"})
        tokens = login_res.json()
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        token_hash = hashlib.sha256(refresh_token.encode('utf-8')).hexdigest()

        # Logout with token in body
        logout_res = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
            headers={"Authorization": f"Bearer {access_token}"}
        )
        self.assertEqual(logout_res.status_code, 200)

        # Verify revoked in DB
        db_token = self.db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
        self.assertEqual(db_token.is_revoked, True)

        # Try to refresh -> should fail
        refresh_res = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        self.assertEqual(refresh_res.status_code, 401)

    def test_logout_without_body_revokes_all_user_sessions(self):
        user = User(
            email="logoutall@example.com",
            password_hash=hash_password("logoutpassword123"),
            full_name="Logout All",
            role="user",
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        first = client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "logoutpassword123"},
        ).json()
        second = client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "logoutpassword123"},
        ).json()

        response = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {first['access_token']}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": second["refresh_token"]},
            ).status_code,
            401,
        )

    def test_final_active_admin_cannot_be_disabled_or_demoted(self):
        admin = User(
            email="only-admin@example.com",
            password_hash=hash_password("adminpassword123"),
            full_name="Only Admin",
            role="admin",
            is_active=True,
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

    def test_password_change_revokes_existing_refresh_tokens(self):
        user = User(
            email="passworduser@example.com",
            password_hash=hash_password("oldpassword123"),
            full_name="Password User",
            role="user",
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()

        login_res = client.post("/api/v1/auth/login", json={"email": user.email, "password": "oldpassword123"})
        self.assertEqual(login_res.status_code, 200)
        tokens = login_res.json()
        change_res = client.put(
            "/api/v1/auth/password",
            json={"current_password": "oldpassword123", "new_password": "newpassword123"},
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        self.assertEqual(change_res.status_code, 200)
        self.assertIn("Sign in again", change_res.json()["message"])
        self.assertTrue(all(token.is_revoked for token in self.db.query(RefreshToken).filter(RefreshToken.user_id == user.id).all()))
        self.assertEqual(client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code, 401)
