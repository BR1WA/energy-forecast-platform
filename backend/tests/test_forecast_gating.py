import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import User
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

class TestForecastGating(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.create_all(bind=engine)
        self.db = TestingSessionLocal()

        self.user_pass = "userpassword"

        # Create admin user
        self.admin_user = User(
            email="admin@example.com",
            password_hash=hash_password(self.user_pass),
            full_name="Admin User",
            role="admin",
            is_active=True,
        )
        # Create analyst user
        self.analyst_user = User(
            email="analyst@example.com",
            password_hash=hash_password(self.user_pass),
            full_name="Analyst User",
            role="analyst",
            is_active=True,
        )
        # Create normal viewer user
        self.viewer_user = User(
            email="viewer@example.com",
            password_hash=hash_password(self.user_pass),
            full_name="Viewer User",
            role="viewer",
            is_active=True,
        )
        self.db.add(self.admin_user)
        self.db.add(self.analyst_user)
        self.db.add(self.viewer_user)
        self.db.commit()

        self.admin_token = create_access_token({"sub": str(self.admin_user.id)})
        self.analyst_token = create_access_token({"sub": str(self.analyst_user.id)})
        self.viewer_token = create_access_token({"sub": str(self.viewer_user.id)})

        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        self.analyst_headers = {"Authorization": f"Bearer {self.analyst_token}"}
        self.viewer_headers = {"Authorization": f"Bearer {self.viewer_token}"}

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)
        if get_db in app.dependency_overrides:
            del app.dependency_overrides[get_db]

    def test_viewer_gated_from_sync(self):
        payload = {"model_name": "sota"}
        res = client.post("/api/v1/forecast/smart-meter/sync", json=payload, headers=self.viewer_headers)
        self.assertEqual(res.status_code, 403)
        self.assertIn("Insufficient permissions", res.json()["detail"])

    def test_viewer_gated_from_compare(self):
        res = client.post("/api/v1/forecast/smart-meter/compare", headers=self.viewer_headers)
        self.assertEqual(res.status_code, 403)
        self.assertIn("Insufficient permissions", res.json()["detail"])

    def test_analyst_and_admin_allowed(self):
        # We test that they don't get a 403. They might get other validation errors if models fail to load/predict,
        # but they must bypass the role-based auth filter.
        payload = {"model_name": "sota"}
        
        # Test sync endpoint for admin
        res = client.post("/api/v1/forecast/smart-meter/sync", json=payload, headers=self.admin_headers)
        self.assertNotEqual(res.status_code, 403)
        
        # Test sync endpoint for analyst
        res = client.post("/api/v1/forecast/smart-meter/sync", json=payload, headers=self.analyst_headers)
        self.assertNotEqual(res.status_code, 403)
