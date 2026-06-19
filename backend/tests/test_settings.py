import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import User
from app.models.settings import SystemSettings
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

class TestSettingsSecurity(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.create_all(bind=engine)
        self.db = TestingSessionLocal()

        self.admin_pass = "adminpassword"
        self.user_pass = "userpassword"

        # Create admin user
        self.admin_user = User(
            email="admin@example.com",
            password_hash=hash_password(self.admin_pass),
            full_name="Admin User",
            role="admin",
            is_active=True,
            is_setup_complete=False,
        )
        # Create normal free user (viewer)
        self.free_user = User(
            email="free@example.com",
            password_hash=hash_password(self.user_pass),
            full_name="Free User",
            role="viewer",
            is_active=True,
            is_setup_complete=False,
        )
        self.db.add(self.admin_user)
        self.db.add(self.free_user)
        self.db.commit()

        self.admin_token = create_access_token({"sub": str(self.admin_user.id)})
        self.free_token = create_access_token({"sub": str(self.free_user.id)})

        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        self.free_headers = {"Authorization": f"Bearer {self.free_token}"}

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)
        if get_db in app.dependency_overrides:
            del app.dependency_overrides[get_db]

    def test_unauthenticated_get_settings_blocked(self):
        res = client.get("/api/v1/settings")
        self.assertEqual(res.status_code, 401)

    def test_authenticated_get_settings_allowed(self):
        res = client.get("/api/v1/settings", headers=self.free_headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["country"], "Morocco")

    def test_admin_can_create_and_overwrite_global_settings(self):
        # 1. Admin completes setup first time -> creates settings
        payload = {
            "country": "Morocco",
            "region": "Rabat",
            "electricity_provider": "ONEE",
            "currency": "MAD",
            "peak_rate": 1.5,
            "off_peak_rate": 1.0,
            "peak_start_hour": 18,
            "peak_end_hour": 22,
            "sensor_type": "simulator",
            "sensor_api_url": None
        }
        res = client.post("/api/v1/settings/setup", json=payload, headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        
        # Verify db contains Rabat
        settings = self.db.query(SystemSettings).first()
        self.assertIsNotNone(settings)
        self.assertEqual(settings.region, "Rabat")

        # 2. Admin updates setup -> overwrites settings
        payload["region"] = "Casablanca"
        res = client.post("/api/v1/settings/setup", json=payload, headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        
        self.db.expire_all()
        settings = self.db.query(SystemSettings).first()
        self.assertEqual(settings.region, "Casablanca")

    def test_non_admin_cannot_overwrite_global_settings_but_marks_setup_complete(self):
        # 1. First admin sets up Casablanca
        payload = {
            "country": "Morocco",
            "region": "Casablanca",
            "electricity_provider": "Lydec",
            "currency": "MAD",
            "peak_rate": 1.1,
            "off_peak_rate": 0.8,
            "peak_start_hour": 6,
            "peak_end_hour": 22,
            "sensor_type": "simulator",
            "sensor_api_url": None
        }
        res = client.post("/api/v1/settings/setup", json=payload, headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)

        # 2. Free user (non-admin) runs setup with Rabat
        payload_user = payload.copy()
        payload_user["region"] = "Rabat"
        res = client.post("/api/v1/settings/setup", json=payload_user, headers=self.free_headers)
        self.assertEqual(res.status_code, 200)

        # Verify global settings remained Casablanca (Rabat was ignored)
        self.db.expire_all()
        settings = self.db.query(SystemSettings).first()
        self.assertEqual(settings.region, "Casablanca")

        # Verify the free user's own status is complete
        user = self.db.query(User).filter(User.id == self.free_user.id).first()
        self.assertTrue(user.is_setup_complete)
