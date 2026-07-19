import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import AlertConfig, Recommendation, SmartMeterReading, User
from app.services.alert_service import alert_service
from app.services.auth_service import hash_password
from app.services.site_service import ensure_default_site, get_default_meter


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class TestAlertRules(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = TestingSessionLocal()
        self.user = User(
            email="alerts@example.com",
            password_hash=hash_password("password123"),
            role="user",
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.site = ensure_default_site(self.db, self.user.id)
        self.meter = get_default_meter(self.db, self.user.id)
        self.config = AlertConfig(
            user_id=self.user.id,
            site_id=self.site.id,
            threshold_kw=2.0,
            cooldown_minutes=60,
            missing_data_minutes=15,
        )
        self.db.add(self.config)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    def _reading(self, timestamp: datetime, gap: float) -> SmartMeterReading:
        reading = SmartMeterReading(
            meter_id=self.meter.id,
            timestamp=timestamp,
            gap=gap,
            grp=0.1,
            voltage=230,
            intensity=5.0,
            sub_metering_1=0,
            sub_metering_2=0,
            sub_metering_3=0,
            source="push",
        )
        self.db.add(reading)
        self.db.flush()
        return reading

    def test_high_load_alert_has_evidence_and_respects_cooldown(self):
        now = datetime.now(timezone.utc)
        first = alert_service.evaluate_reading(self.db, self.meter, self._reading(now, 2.5))
        self.assertIsNotNone(first)
        self.assertEqual(first.alert_type, "high_consumption")
        self.assertEqual(first.evidence_json["threshold_kw"], 2.0)
        recommendation = self.db.query(Recommendation).filter(Recommendation.alert_id == first.id).one()
        self.assertEqual(recommendation.category, "peak_load")
        self.assertEqual(recommendation.status, "open")
        self.assertAlmostEqual(recommendation.evidence_json["excess_kw"], 0.5)

        second = alert_service.evaluate_reading(
            self.db,
            self.meter,
            self._reading(now + timedelta(minutes=1), 2.6),
        )
        self.assertIsNone(second)

    def test_missing_push_data_creates_one_alert_per_cooldown(self):
        now = datetime.now(timezone.utc)
        self.meter.source_type = "push"
        self.meter.last_seen_at = now - timedelta(minutes=20)
        self.db.commit()

        first = alert_service.evaluate_missing_push_data(self.db, now=now)
        second = alert_service.evaluate_missing_push_data(self.db, now=now + timedelta(minutes=1))

        self.assertEqual(len(first), 1)
        self.assertEqual(first[0].alert_type, "missing_data")
        self.assertEqual(first[0].evidence_json["age_minutes"], 20.0)
        recommendation = self.db.query(Recommendation).filter(Recommendation.alert_id == first[0].id).one()
        self.assertEqual(recommendation.category, "data_quality")
        self.assertEqual(second, [])
