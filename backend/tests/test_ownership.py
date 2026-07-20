import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Meter, Site, SmartMeterReading, User
from app.services.auth_service import create_access_token, hash_password
from app.services.site_service import ensure_default_site, get_default_meter

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


client = TestClient(app)


class TestUserOwnedEnergyData(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.create_all(bind=engine)
        self.db = TestingSessionLocal()

        self.user_a = User(email="a@example.com", password_hash=hash_password("password123"), role="user", is_active=True)
        self.user_b = User(email="b@example.com", password_hash=hash_password("password123"), role="user", is_active=True)
        self.db.add_all([self.user_a, self.user_b])
        self.db.commit()
        ensure_default_site(self.db, self.user_a.id)
        ensure_default_site(self.db, self.user_b.id)
        self.db.commit()

        meter_a = get_default_meter(self.db, self.user_a.id)
        meter_b = get_default_meter(self.db, self.user_b.id)
        self.db.add_all([
            SmartMeterReading(meter_id=meter_a.id, timestamp=datetime.now(timezone.utc), gap=1.25, grp=0.1, voltage=230, intensity=5.4, sub_metering_1=10, sub_metering_2=10, sub_metering_3=10),
            SmartMeterReading(meter_id=meter_b.id, timestamp=datetime.now(timezone.utc), gap=9.75, grp=0.2, voltage=230, intensity=42.4, sub_metering_1=20, sub_metering_2=20, sub_metering_3=20),
        ])
        self.db.commit()
        self.headers_a = {"Authorization": f"Bearer {create_access_token({'sub': str(self.user_a.id)})}"}
        self.headers_b = {"Authorization": f"Bearer {create_access_token({'sub': str(self.user_b.id)})}"}

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)
        app.dependency_overrides.pop(get_db, None)

    def test_consumption_is_scoped_to_the_authenticated_user(self):
        response_a = client.get("/api/v1/consumption/current", headers=self.headers_a)
        response_b = client.get("/api/v1/consumption/current", headers=self.headers_b)

        self.assertEqual(response_a.status_code, 200)
        self.assertEqual(response_b.status_code, 200)
        self.assertEqual(response_a.json()["kw"], 1.25)
        self.assertEqual(response_b.json()["kw"], 9.75)

    def test_multi_site_endpoint_is_removed(self):
        response = client.get("/api/v1/multi-site", headers=self.headers_a)
        self.assertEqual(response.status_code, 404)

    def test_simulator_configuration_is_not_shared_between_users(self):
        response = client.post(
            "/api/v1/simulation/configure",
            json={"base_load_kw": 5, "variation_percent": 25},
            headers=self.headers_a,
        )
        self.assertEqual(response.status_code, 200)

        state_a = client.get("/api/v1/simulation/status", headers=self.headers_a).json()
        state_b = client.get("/api/v1/simulation/status", headers=self.headers_b).json()
        self.assertEqual(state_a["base_load_kw"], 5)
        self.assertEqual(state_a["variation_percent"], 25)
        self.assertEqual(state_b["base_load_kw"], 1.2)
        self.assertEqual(state_b["variation_percent"], 10)
