from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import EnergyBudget, Meter, Site, SiteSettings, SmartMeterReading, User
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


def test_monthly_summary_uses_the_user_site_timezone_and_tariff():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        user = User(email="single-site@example.com", password_hash=hash_password("password123"), role="user", is_active=True)
        db.add(user)
        db.commit()
        site = ensure_default_site(db, user.id)
        site.timezone = "Asia/Tokyo"
        settings = db.query(SiteSettings).filter(SiteSettings.site_id == site.id).one()
        settings.peak_rate = 3.0
        settings.off_peak_rate = 1.0
        settings.peak_start_hour = 7
        settings.peak_end_hour = 8
        meter = get_default_meter(db, user.id)

        start = datetime(2026, 7, 1, 22, 0, tzinfo=timezone.utc)
        db.add_all([
            SmartMeterReading(meter_id=meter.id, timestamp=start, gap=1.0, grp=0.0, voltage=230, intensity=4.3, sub_metering_1=0, sub_metering_2=0, sub_metering_3=0, source="csv", quality="validated"),
            SmartMeterReading(meter_id=meter.id, timestamp=start + timedelta(hours=1), gap=1.0, grp=0.0, voltage=230, intensity=4.3, sub_metering_1=0, sub_metering_2=0, sub_metering_3=0, source="csv", quality="validated"),
        ])
        db.commit()

        summary = consumption_service.get_monthly_summary(db, user.id, "2026-07")
        assert summary["total_kwh"] == 1.0
        assert summary["total_cost"] == 3.0
        assert summary["off_peak_kwh"] == 0.0
        assert summary["peak_kwh"] == 1.0
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_period_summary_uses_exact_site_local_boundaries_and_tariff():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        user = User(email="period@example.com", password_hash=hash_password("password123"), role="user", is_active=True)
        db.add(user)
        db.commit()
        site = ensure_default_site(db, user.id)
        site.timezone = "Asia/Tokyo"
        meter = get_default_meter(db, user.id)
        meter.expected_interval_seconds = 3600
        settings = db.query(SiteSettings).filter(SiteSettings.site_id == site.id).one()
        settings.peak_rate = 2.0
        settings.off_peak_rate = 2.0

        # Tokyo midnight is 15:00 UTC on the previous calendar date.
        for timestamp in (
            datetime(2026, 7, 19, 14, tzinfo=timezone.utc),
            datetime(2026, 7, 19, 15, tzinfo=timezone.utc),
            datetime(2026, 7, 19, 16, tzinfo=timezone.utc),
            datetime(2026, 7, 19, 17, tzinfo=timezone.utc),
        ):
            db.add(SmartMeterReading(
                meter_id=meter.id, timestamp=timestamp, gap=1.0, grp=0.0, voltage=230,
                intensity=4.3, sub_metering_1=0, sub_metering_2=0, sub_metering_3=0,
                source="csv", quality="validated",
            ))
        db.commit()

        now = datetime(2026, 7, 19, 17, tzinfo=timezone.utc)
        summary = consumption_service.get_period_summary(db, user.id, "today", now=now)

        assert summary["period_start"] == "2026-07-19T15:00:00+00:00"
        assert summary["period_end"] == "2026-07-19T17:00:00+00:00"
        assert summary["total_kwh"] == 2.0
        assert summary["estimated_cost"] == 4.0
        assert summary["coverage_pct"] == 100.0
        assert summary["freshness"]["status"] == "historical"
        assert summary["sources"] == [{"source": "csv", "count": 3}]
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_all_and_custom_periods_are_real_ranges_not_fixed_one_year_windows():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        user = User(email="all-time@example.com", password_hash=hash_password("password123"), role="user", is_active=True)
        db.add(user)
        db.commit()
        site = ensure_default_site(db, user.id)
        site.timezone = "UTC"
        meter = get_default_meter(db, user.id)
        for timestamp in (
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 7, 19, 15, tzinfo=timezone.utc),
            datetime(2026, 7, 19, 16, tzinfo=timezone.utc),
            datetime(2026, 7, 19, 17, tzinfo=timezone.utc),
        ):
            db.add(SmartMeterReading(
                meter_id=meter.id, timestamp=timestamp, gap=1.0, grp=0.0, voltage=230,
                intensity=4.3, sub_metering_1=0, sub_metering_2=0, sub_metering_3=0,
                source="csv", quality="validated",
            ))
        db.commit()

        all_time = consumption_service.get_period_summary(
            db, user.id, "all", now=datetime(2026, 7, 20, tzinfo=timezone.utc)
        )
        custom = consumption_service.get_period_summary(
            db,
            user.id,
            "custom",
            start=datetime(2026, 7, 19, 15, 30, tzinfo=timezone.utc),
            end=datetime(2026, 7, 19, 16, 30, tzinfo=timezone.utc),
        )

        assert all_time["period_start"] == "2024-01-01T00:00:00+00:00"
        assert all_time["period_end"] == "2026-07-19T17:00:00+00:00"
        assert custom["total_kwh"] == 1.0
        assert custom["sample_count"] == 1
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
