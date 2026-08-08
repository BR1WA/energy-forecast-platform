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


def test_calendar_aware_daily_and_monthly_bucketing_and_dst_transitions():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        user = User(email="calendar@example.com", password_hash=hash_password("password123"), role="user", is_active=True)
        db.add(user)
        db.commit()
        site = ensure_default_site(db, user.id)
        site.timezone = "Europe/London"
        meter = get_default_meter(db, user.id)

        # 1. First reading at 14:37 UTC on July 21, 2026 (local 15:37 BST)
        # Daily bucket must map to local midnight 00:00:00 BST (2026-07-20T23:00:00Z in UTC)
        # and not fabricate missing measurements for unobserved morning hours.
        readings_daily = [
            (datetime(2026, 7, 21, 14, 37, tzinfo=timezone.utc), 2.0),
            (datetime(2026, 7, 21, 15, 37, tzinfo=timezone.utc), 2.0),
            (datetime(2026, 7, 22, 10, 0, tzinfo=timezone.utc), 1.5),
            (datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc), 1.5),
        ]
        for ts, power in readings_daily:
            db.add(SmartMeterReading(
                meter_id=meter.id, timestamp=ts, gap=power, grp=0.0, voltage=230,
                intensity=4.3, sub_metering_1=0, sub_metering_2=0, sub_metering_3=0,
                source="csv", quality="validated",
            ))
        db.commit()

        summary_daily = consumption_service.get_period_summary(db, user.id, "all")
        assert summary_daily["granularity"] == "day"
        # First bucket should be July 21 local midnight (which in BST is 2026-07-20T23:00:00+00:00)
        assert summary_daily["points"][0]["timestamp"] == "2026-07-20T23:00:00+00:00"
        assert summary_daily["points"][1]["timestamp"] == "2026-07-21T23:00:00+00:00"
        # Total kWh only accounts for elapsed interval between readings (1h * 2kW = 2.0 kWh), no fake morning energy
        assert summary_daily["points"][0]["energy_kwh"] == 2.0
        assert summary_daily["points"][0]["sample_count"] == 2

        # 2. DST spring forward transition (March 29, 2026 in Europe/London)
        # Mar 28 is GMT (UTC+0), Mar 29 springs forward to BST (UTC+1), Mar 30 is BST
        # Span must exceed 14 days to select day granularity.
        db.query(SmartMeterReading).delete()
        dst_readings = [
            (datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc), 1.0),
            (datetime(2026, 3, 28, 12, 0, tzinfo=timezone.utc), 1.0),
            (datetime(2026, 3, 29, 12, 0, tzinfo=timezone.utc), 1.0),
            (datetime(2026, 3, 30, 12, 0, tzinfo=timezone.utc), 1.0),
            (datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc), 1.0),
        ]
        for ts, power in dst_readings:
            db.add(SmartMeterReading(
                meter_id=meter.id, timestamp=ts, gap=power, grp=0.0, voltage=230,
                intensity=4.3, sub_metering_1=0, sub_metering_2=0, sub_metering_3=0,
                source="csv", quality="validated",
            ))
        db.commit()

        summary_dst = consumption_service.get_period_summary(db, user.id, "all")
        assert summary_dst["granularity"] == "day"
        # Mar 28 00:00 GMT -> UTC 2026-03-28T00:00:00+00:00
        # Mar 29 00:00 GMT -> UTC 2026-03-29T00:00:00+00:00
        # Mar 30 00:00 BST -> UTC 2026-03-29T23:00:00+00:00
        dst_timestamps = [p["timestamp"] for p in summary_dst["points"]]
        assert "2026-03-28T00:00:00+00:00" in dst_timestamps
        assert "2026-03-29T00:00:00+00:00" in dst_timestamps
        assert "2026-03-29T23:00:00+00:00" in dst_timestamps

        # 3. Calendar months across Jan -> Feb -> Mar, Leap-year Feb 2024, and Dec -> Jan
        db.query(SmartMeterReading).delete()
        multi_year_readings = [
            (datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc), 1.0),
            (datetime(2024, 2, 29, 10, 0, tzinfo=timezone.utc), 1.0),  # Leap year Feb 29
            (datetime(2024, 3, 15, 10, 0, tzinfo=timezone.utc), 1.0),
            (datetime(2025, 1, 10, 10, 0, tzinfo=timezone.utc), 1.0),
            (datetime(2025, 2, 28, 10, 0, tzinfo=timezone.utc), 1.0),  # Non-leap year Feb 28
            (datetime(2025, 3, 10, 10, 0, tzinfo=timezone.utc), 1.0),
            (datetime(2025, 12, 31, 23, 0, tzinfo=timezone.utc), 1.0),
            (datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc), 1.0),
            (datetime(2027, 1, 1, 0, 0, tzinfo=timezone.utc), 1.0),  # > 2 years forces month granularity
        ]
        for ts, power in multi_year_readings:
            db.add(SmartMeterReading(
                meter_id=meter.id, timestamp=ts, gap=power, grp=0.0, voltage=230,
                intensity=4.3, sub_metering_1=0, sub_metering_2=0, sub_metering_3=0,
                source="csv", quality="validated",
            ))
        db.commit()

        summary_monthly = consumption_service.get_period_summary(db, user.id, "all")
        assert summary_monthly["granularity"] == "month"
        month_timestamps = [p["timestamp"] for p in summary_monthly["points"]]
        # Verify exact 1st of month calendar alignment
        assert "2024-01-01T00:00:00+00:00" in month_timestamps
        assert "2024-02-01T00:00:00+00:00" in month_timestamps
        assert "2024-03-01T00:00:00+00:00" in month_timestamps
        assert "2025-01-01T00:00:00+00:00" in month_timestamps
        assert "2025-02-01T00:00:00+00:00" in month_timestamps
        assert "2025-03-01T00:00:00+00:00" in month_timestamps
        assert "2025-12-01T00:00:00+00:00" in month_timestamps
        assert "2026-01-01T00:00:00+00:00" in month_timestamps

        # 4. Rolling-week anchor remains exactly tied to the original first reading
        db.query(SmartMeterReading).delete()
        first_reading_ts = datetime(2026, 1, 10, 14, 37, tzinfo=timezone.utc)
        week_readings = [
            (first_reading_ts, 1.0),
            (first_reading_ts + timedelta(days=3), 1.0),
            (first_reading_ts + timedelta(days=8), 1.0),
            (first_reading_ts + timedelta(days=15), 1.0),
            (first_reading_ts + timedelta(days=120), 1.0),  # Span 120 days -> week granularity
        ]
        for ts, power in week_readings:
            db.add(SmartMeterReading(
                meter_id=meter.id, timestamp=ts, gap=power, grp=0.0, voltage=230,
                intensity=4.3, sub_metering_1=0, sub_metering_2=0, sub_metering_3=0,
                source="csv", quality="validated",
            ))
        db.commit()

        summary_weekly = consumption_service.get_period_summary(db, user.id, "all")
        assert summary_weekly["granularity"] == "week"
        assert summary_weekly["period_start"] == first_reading_ts.isoformat()
        # Weekly buckets should be anchored to first_reading_ts in 7-day increments
        assert summary_weekly["points"][0]["timestamp"] == first_reading_ts.isoformat()
        assert summary_weekly["points"][1]["timestamp"] == (first_reading_ts + timedelta(days=7)).isoformat()
        assert summary_weekly["points"][2]["timestamp"] == (first_reading_ts + timedelta(days=14)).isoformat()
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
