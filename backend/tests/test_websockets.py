import unittest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import SmartMeterReading, User
from app.services.auth_service import hash_password, create_access_token
from app.services.site_service import ensure_user_site, get_primary_meter

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

class TestWebSocketAuth(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.create_all(bind=engine)
        self.db = TestingSessionLocal()

        self.user_pass = "userpassword"
        self.user1 = User(
            email="user1@example.com",
            password_hash=hash_password(self.user_pass),
            full_name="User One",
            role="user",
            is_active=True,
        )
        self.user2 = User(
            email="user2@example.com",
            password_hash=hash_password(self.user_pass),
            full_name="User Two",
            role="user",
            is_active=True,
        )
        self.db.add(self.user1)
        self.db.add(self.user2)
        self.db.commit()

        self.token1 = create_access_token({"sub": str(self.user1.id)})
        self.token2 = create_access_token({"sub": str(self.user2.id)})

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)
        if get_db in app.dependency_overrides:
            del app.dependency_overrides[get_db]

    def test_live_monitoring_rejects_missing_token(self):
        with client.websocket_connect("/api/v1/monitoring/live") as websocket:
            websocket.send_json({})
            with self.assertRaises(WebSocketDisconnect) as context:
                websocket.receive_json()
            self.assertEqual(context.exception.code, 1008)

    def test_live_monitoring_is_read_only_and_excludes_csv(self):
        ensure_user_site(self.db, self.user1.id)
        meter = get_primary_meter(self.db, self.user1.id)
        self.db.add(
            SmartMeterReading(
                meter_id=meter.id,
                timestamp=datetime(2026, 7, 20, 12, tzinfo=timezone.utc),
                gap=2.5,
                grp=0.1,
                voltage=230,
                intensity=10.9,
                sub_metering_1=0,
                sub_metering_2=0,
                sub_metering_3=0,
                source="csv",
                quality="validated",
            )
        )
        self.db.commit()
        before = self.db.query(SmartMeterReading).count()

        with client.websocket_connect("/api/v1/monitoring/live") as websocket:
            websocket.send_json({"access_token": self.token1})
            snapshot = websocket.receive_json()
            self.assertEqual(snapshot["type"], "snapshot")
            self.assertIsNone(snapshot["reading"])

        self.assertEqual(self.db.query(SmartMeterReading).count(), before)

    def test_live_monitoring_returns_owned_simulation_snapshot(self):
        ensure_user_site(self.db, self.user1.id)
        meter = get_primary_meter(self.db, self.user1.id)
        self.db.add(
            SmartMeterReading(
                meter_id=meter.id,
                timestamp=datetime(2026, 7, 20, 12, tzinfo=timezone.utc),
                gap=1.75,
                grp=0.1,
                voltage=229,
                intensity=7.6,
                sub_metering_1=0,
                sub_metering_2=0,
                sub_metering_3=0,
                source="simulation",
                quality="simulated",
            )
        )
        self.db.commit()

        with client.websocket_connect("/api/v1/monitoring/live") as websocket:
            websocket.send_json({"access_token": self.token1})
            snapshot = websocket.receive_json()
            self.assertEqual(snapshot["reading"]["active_power_kw"], 1.75)
            self.assertEqual(snapshot["reading"]["source"], "simulation")

    def test_live_monitoring_resumes_after_cursor_without_replaying_older_rows(self):
        ensure_user_site(self.db, self.user1.id)
        meter = get_primary_meter(self.db, self.user1.id)
        first = SmartMeterReading(
            meter_id=meter.id, timestamp=datetime(2026, 7, 20, 12, tzinfo=timezone.utc),
            gap=1.0, grp=0.1, voltage=230, intensity=4.3, sub_metering_1=0,
            sub_metering_2=0, sub_metering_3=0, source="push", quality="validated",
        )
        second = SmartMeterReading(
            meter_id=meter.id, timestamp=datetime(2026, 7, 20, 12, 1, tzinfo=timezone.utc),
            gap=2.0, grp=0.1, voltage=230, intensity=8.7, sub_metering_1=0,
            sub_metering_2=0, sub_metering_3=0, source="push", quality="validated",
        )
        self.db.add_all([first, second])
        self.db.commit()

        with client.websocket_connect("/api/v1/monitoring/live") as websocket:
            websocket.send_json({"access_token": self.token1, "last_reading_id": first.id})
            snapshot = websocket.receive_json()
            event = websocket.receive_json()

            self.assertEqual(snapshot["reading"]["reading_id"], second.id)
            self.assertEqual(event["type"], "reading")
            self.assertEqual(event["reading"]["reading_id"], second.id)
