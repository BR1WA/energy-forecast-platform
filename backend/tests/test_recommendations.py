import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import AlertConfig, User
from app.services.alert_service import alert_service
from app.services.auth_service import create_access_token, hash_password
from app.services.site_service import ensure_default_site, get_default_meter
from app.models import SmartMeterReading


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


class TestRecommendationsApi(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.create_all(bind=engine)
        self.db = TestingSessionLocal()
        self.user = User(email="recommendations@example.com", password_hash=hash_password("password123"), role="user", is_active=True)
        self.other_user = User(email="other-recommendations@example.com", password_hash=hash_password("password123"), role="user", is_active=True)
        self.db.add_all([self.user, self.other_user])
        self.db.commit()
        self.site = ensure_default_site(self.db, self.user.id)
        meter = get_default_meter(self.db, self.user.id)
        self.db.add(AlertConfig(user_id=self.user.id, site_id=self.site.id, threshold_kw=2.0))
        self.db.flush()
        reading = SmartMeterReading(
            meter_id=meter.id,
            timestamp=datetime.now(timezone.utc),
            gap=2.5,
            grp=0.1,
            voltage=230,
            intensity=5,
            sub_metering_1=0,
            sub_metering_2=0,
            sub_metering_3=0,
            source="push",
        )
        self.db.add(reading)
        self.db.flush()
        alert_service.evaluate_reading(self.db, meter, reading)
        self.db.commit()
        self.headers = {"Authorization": f"Bearer {create_access_token({'sub': str(self.user.id), 'role': 'user'})}"}
        self.other_headers = {"Authorization": f"Bearer {create_access_token({'sub': str(self.other_user.id), 'role': 'user'})}"}

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)
        app.dependency_overrides.pop(get_db, None)

    def test_list_update_and_ownership(self):
        listed = client.get("/api/v1/recommendations", headers=self.headers)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()), 1)
        recommendation_id = listed.json()[0]["id"]

        denied = client.patch(
            f"/api/v1/recommendations/{recommendation_id}",
            json={"status": "dismissed"},
            headers=self.other_headers,
        )
        self.assertEqual(denied.status_code, 404)

        completed = client.patch(
            f"/api/v1/recommendations/{recommendation_id}",
            json={"status": "completed"},
            headers=self.headers,
        )
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()["status"], "completed")
        self.assertEqual(client.get("/api/v1/recommendations", headers=self.headers).json(), [])
