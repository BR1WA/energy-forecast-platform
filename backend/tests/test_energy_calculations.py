from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import EnergyBudget, SiteSettings, SmartMeterReading, User
from app.services.auth_service import hash_password
from app.services.consumption_service import consumption_service
from app.services.site_service import ensure_default_site, get_default_meter


def test_interval_energy_tariff_budget_and_long_gap_handling():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        user = User(email="energy@example.com", password_hash=hash_password("password123"), role="user", is_active=True)
        db.add(user)
        db.commit()
        site = ensure_default_site(db, user.id)
        meter = get_default_meter(db, user.id)
        settings = db.query(SiteSettings).filter(SiteSettings.site_id == site.id).one()
        settings.peak_rate = 2.0
        settings.off_peak_rate = 1.0
        settings.peak_start_hour = 0
        settings.peak_end_hour = 23
        site.timezone = "UTC"
        db.add(EnergyBudget(user_id=user.id, site_id=site.id, monthly_budget_mad=20.0))

        start = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
        samples = [
            (start, 2.0, None),
            (start + timedelta(seconds=5), 2.0, None),
            (start + timedelta(minutes=15, seconds=5), 2.0, None),
            (start + timedelta(hours=1, minutes=15, seconds=5), 2.0, None),
            # Four hours is too long to infer energy from power alone.
            (start + timedelta(hours=5, minutes=15, seconds=5), 2.0, 100.0),
            # Direct cumulative energy remains valid even when the interval is long.
            (start + timedelta(hours=9, minutes=15, seconds=5), 2.0, 101.0),
        ]
        for timestamp, power, energy in samples:
            db.add(SmartMeterReading(
                meter_id=meter.id, timestamp=timestamp, gap=power, grp=0.1, voltage=230,
                intensity=power * 1000 / 230, sub_metering_1=0, sub_metering_2=0,
                sub_metering_3=0, energy_kwh=energy, source="csv", quality="validated",
            ))
        db.commit()

        summary = consumption_service.get_monthly_summary(db, user.id, "2026-07")
        expected_kwh = (2 * 5 / 3600) + (2 * 900 / 3600) + (2 * 3600 / 3600) + 1
        assert abs(summary["total_kwh"] - expected_kwh) < 0.0001
        assert abs(summary["total_cost"] - expected_kwh * 2) < 0.01
        assert summary["budget"]["target_mad"] == 20.0
        assert summary["budget"]["spent_mad"] == summary["total_cost"]
        assert summary["coverage_pct"] > 0
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
