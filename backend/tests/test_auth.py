import unittest
import os
import hashlib
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import User, RefreshToken
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
            "email": "newuser@example.com",
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

    def test_login_flow_persists_refresh_token(self):
        # Create a user first
        user = User(
            email="loginuser@example.com",
            password_hash=hash_password("loginpassword123"),
            full_name="Login User",
            role="viewer",
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
            role="viewer",
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
            role="viewer",
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
