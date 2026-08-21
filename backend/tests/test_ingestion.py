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
from app.services.worker_health_service import record_worker_success


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

    def test_push_rejects_samples_older_than_the_latest_meter_reading(self):
        key = self._push_key()
        newest = client.post(
            f"/api/v1/ingestion/meters/{self.meter.id}/samples",
            headers={"X-Meter-Key": key},
            json={"idempotency_key": "newest-sample", "samples": [{
                "timestamp": "2026-07-02T10:00:00Z", "active_power_kw": 1.2,
            }]},
        )
        older = client.post(
            f"/api/v1/ingestion/meters/{self.meter.id}/samples",
            headers={"X-Meter-Key": key},
            json={"idempotency_key": "older-sample", "samples": [{
                "timestamp": "2026-07-02T09:00:00Z", "active_power_kw": 1.1,
            }]},
        )
        self.assertEqual(newest.status_code, 200)
        self.assertEqual(older.status_code, 200)
        self.assertEqual(older.json()["accepted_rows"], 0)
        self.assertEqual(older.json()["rejected_rows"], 1)
        self.assertEqual(self.db.query(SmartMeterReading).count(), 1)

    def test_primary_meter_metadata_and_interval_configuration(self):
        listed = client.get("/api/v1/ingestion/meters", headers=self.headers)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()), 1)
        self.assertTrue(listed.json()[0]["is_primary"])
        self.assertFalse(listed.json()[0]["push_key_configured"])

        configured = client.patch(
            f"/api/v1/ingestion/meters/{self.meter.id}",
            headers=self.headers,
            json={"expected_interval_seconds": 30},
        )
        self.assertEqual(configured.status_code, 200)
        listed = client.get("/api/v1/ingestion/meters", headers=self.headers)
        self.assertEqual(listed.json()[0]["expected_interval_seconds"], 30)

    def test_push_and_explicit_simulator_cannot_write_concurrently(self):
        key = self._push_key()
        record_worker_success(self.db, "simulation")
        self.db.commit()
        started = client.post("/api/v1/simulation/start", headers=self.headers)
        self.assertEqual(started.status_code, 200)

        blocked = client.post(
            f"/api/v1/ingestion/meters/{self.meter.id}/samples",
            headers={"X-Meter-Key": key},
            json={"samples": [{"timestamp": "2026-07-20T18:00:00Z", "active_power_kw": 1.2}]},
        )
        self.assertEqual(blocked.status_code, 409)

        rotated = client.post(
            f"/api/v1/ingestion/meters/{self.meter.id}/push-key",
            headers=self.headers,
        )
        self.assertEqual(rotated.status_code, 200)
        status_response = client.get("/api/v1/simulation/status", headers=self.headers)
        self.assertFalse(status_response.json()["is_running"])

    def test_simulator_start_is_unavailable_without_a_recent_worker_heartbeat(self):
        response = client.post("/api/v1/simulation/start", headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "simulation_worker_unavailable")

    def test_simulator_configuration_is_strict_and_bounded(self):
        excessive_load = client.post(
            "/api/v1/simulation/configure",
            headers=self.headers,
            json={"base_load_kw": 99},
        )
        unknown_field = client.post(
            "/api/v1/simulation/configure",
            headers=self.headers,
            json={"unsupported": True},
        )
        self.assertEqual(excessive_load.status_code, 422)
        self.assertEqual(unknown_field.status_code, 422)
