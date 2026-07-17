import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import SmartMeterReading, User
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


class TestMeterIngestion(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.create_all(bind=engine)
        self.db = TestingSessionLocal()
        self.user = User(email="ingestion@example.com", password_hash=hash_password("password123"), role="user", is_active=True)
        self.other_user = User(email="other@example.com", password_hash=hash_password("password123"), role="user", is_active=True)
        self.db.add_all([self.user, self.other_user])
        self.db.commit()
        ensure_default_site(self.db, self.user.id)
        ensure_default_site(self.db, self.other_user.id)
        self.db.commit()
        self.meter = get_default_meter(self.db, self.user.id)
        self.other_meter = get_default_meter(self.db, self.other_user.id)
        self.headers = {"Authorization": f"Bearer {create_access_token({'sub': str(self.user.id)})}"}

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)
        app.dependency_overrides.pop(get_db, None)

    def _push_key(self) -> str:
        response = client.post(f"/api/v1/ingestion/meters/{self.meter.id}/push-key", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        return response.json()["api_key"]

    def test_push_rejects_unknown_key_and_replays_idempotently(self):
        payload = {
            "idempotency_key": "device-batch-0001",
            "samples": [{
                "timestamp": "2026-07-01T10:00:00Z",
                "active_power_kw": 1.2,
                "reactive_power_kvar": 0.1,
                "voltage_v": 230,
                "sub_metering_1_wh": 10,
            }],
        }
        denied = client.post(f"/api/v1/ingestion/meters/{self.meter.id}/samples", json=payload, headers={"X-Meter-Key": "wrong"})
        self.assertEqual(denied.status_code, 401)

        key = self._push_key()
        first = client.post(f"/api/v1/ingestion/meters/{self.meter.id}/samples", json=payload, headers={"X-Meter-Key": key})
        second = client.post(f"/api/v1/ingestion/meters/{self.meter.id}/samples", json=payload, headers={"X-Meter-Key": key})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["accepted_rows"], 1)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["accepted_rows"], 1)
        self.assertEqual(self.db.query(SmartMeterReading).count(), 1)

    def test_csv_preview_import_and_meter_ownership(self):
        csv_body = b"timestamp,active_power_kw,voltage_v\n2026-07-01T10:00:00Z,0.8,231\n2026-07-01T10:05:00Z,not-a-number,230\n"
        denied = client.post(
            f"/api/v1/ingestion/meters/{self.other_meter.id}/csv/preview",
            headers=self.headers,
            files={"file": ("readings.csv", csv_body, "text/csv")},
        )
        self.assertEqual(denied.status_code, 404)

        preview = client.post(
            f"/api/v1/ingestion/meters/{self.meter.id}/csv/preview",
            headers=self.headers,
            files={"file": ("readings.csv", csv_body, "text/csv")},
        )
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()["valid_rows"], 1)
        self.assertEqual(preview.json()["rejected_rows"], 1)

        imported = client.post(
            f"/api/v1/ingestion/meters/{self.meter.id}/csv/import",
            headers=self.headers,
            files={"file": ("readings.csv", csv_body, "text/csv")},
        )
        self.assertEqual(imported.status_code, 200)
        self.assertEqual(imported.json()["accepted_rows"], 1)
        self.assertEqual(imported.json()["rejected_rows"], 1)

    def test_push_requires_timezone_aware_timestamp(self):
        key = self._push_key()
        response = client.post(
            f"/api/v1/ingestion/meters/{self.meter.id}/samples",
            headers={"X-Meter-Key": key},
            json={"samples": [{"timestamp": "2026-07-01T10:00:00", "active_power_kw": 1.2}]},
        )
        self.assertEqual(response.status_code, 422)
