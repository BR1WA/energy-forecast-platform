from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

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


def test_calendar_week_and_timeframe_boundaries_across_timezones_and_dst():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        user = User(email="week-test@example.com", password_hash=hash_password("password123"), role="user", is_active=True)
        db.add(user)
        db.commit()
        site = ensure_default_site(db, user.id)
        site.timezone = "Europe/London"
        meter = get_default_meter(db, user.id)

        # 1. Monday at 10:00 BST (2026-07-20 09:00 UTC) -> period starts Monday 00:00 BST (2026-07-19 23:00 UTC)
        now_mon = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)
        sum_mon = consumption_service.get_period_summary(db, user.id, "7d", now=now_mon)
        assert sum_mon["period_start"] == "2026-07-19T23:00:00+00:00"
        assert sum_mon["period_end"] == "2026-07-20T09:00:00+00:00"

        # Also verify the 'week' alias produces the exact same calendar week boundaries
        sum_mon_alias = consumption_service.get_period_summary(db, user.id, "week", now=now_mon)
        assert sum_mon_alias["period_start"] == "2026-07-19T23:00:00+00:00"

        # 2. Wednesday at 14:00 BST (2026-07-22 13:00 UTC) -> period starts Monday 00:00 BST (2026-07-19 23:00 UTC)
        now_wed = datetime(2026, 7, 22, 13, 0, tzinfo=timezone.utc)
        sum_wed = consumption_service.get_period_summary(db, user.id, "7d", now=now_wed)
        assert sum_wed["period_start"] == "2026-07-19T23:00:00+00:00"

        # 3. Sunday at 23:00 BST (2026-07-26 22:00 UTC) -> period still starts same Monday 00:00 BST (2026-07-19 23:00 UTC)
        now_sun = datetime(2026, 7, 26, 22, 0, tzinfo=timezone.utc)
        sum_sun = consumption_service.get_period_summary(db, user.id, "7d", now=now_sun)
        assert sum_sun["period_start"] == "2026-07-19T23:00:00+00:00"

        # 4. Year boundary: Thursday Jan 1, 2026 at 10:00 UTC (10:00 GMT) -> Monday belongs to previous year (Dec 29, 2025)
        now_jan1 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        sum_jan1 = consumption_service.get_period_summary(db, user.id, "7d", now=now_jan1)
        assert sum_jan1["period_start"] == "2025-12-29T00:00:00+00:00"

        # 5. Site timezone respect: Asia/Tokyo (UTC+9)
        site.timezone = "Asia/Tokyo"
        # Wednesday July 22, 2026 at 15:00 JST (06:00 UTC) -> Monday July 20 at 00:00 JST (2026-07-19 15:00 UTC)
        now_tokyo = datetime(2026, 7, 22, 6, 0, tzinfo=timezone.utc)
        sum_tokyo = consumption_service.get_period_summary(db, user.id, "7d", now=now_tokyo)
        assert sum_tokyo["period_start"] == "2026-07-19T15:00:00+00:00"
        assert sum_tokyo["timezone"] == "Asia/Tokyo"

        # 6. DST transition week: Europe/London on Sunday March 29, 2026 at 12:00 BST (11:00 UTC)
        site.timezone = "Europe/London"
        now_dst = datetime(2026, 3, 29, 11, 0, tzinfo=timezone.utc)
        sum_dst = consumption_service.get_period_summary(db, user.id, "7d", now=now_dst)
        # Monday March 23 was GMT (UTC+0) -> 2026-03-23T00:00:00+00:00
        assert sum_dst["period_start"] == "2026-03-23T00:00:00+00:00"

        # 7. Verify today, month, year are intact
        sum_today = consumption_service.get_period_summary(db, user.id, "today", now=now_mon)
        assert sum_today["period_start"] == "2026-07-19T23:00:00+00:00"  # today local midnight

        sum_month = consumption_service.get_period_summary(db, user.id, "month", now=now_mon)
        assert sum_month["period_start"] == "2026-06-30T23:00:00+00:00"  # July 1st 00:00 BST

        sum_year = consumption_service.get_period_summary(db, user.id, "year", now=now_mon)
        assert sum_year["period_start"] == "2026-01-01T00:00:00+00:00"  # Jan 1st 00:00 GMT (UTC+0)
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_populated_dst_weeks_project_exact_167_and_169_hour_periods():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()

    def add_hourly_site(email: str, start: datetime, now: datetime) -> User:
        user = User(email=email, password_hash=hash_password("password123"), role="user", is_active=True)
        db.add(user)
        db.commit()
        site = ensure_default_site(db, user.id)
        site.timezone = "Europe/London"
        meter = get_default_meter(db, user.id)
        meter.expected_interval_seconds = 3600
        settings = db.query(SiteSettings).filter(SiteSettings.site_id == site.id).one()
        settings.peak_rate = 1.0
        settings.off_peak_rate = 1.0
        cursor = start
        while cursor <= now:
            db.add(SmartMeterReading(
                meter_id=meter.id, timestamp=cursor, gap=1.0, grp=0.0, voltage=230,
                intensity=4.3, sub_metering_1=0, sub_metering_2=0, sub_metering_3=0,
                source="csv", quality="validated",
            ))
            cursor += timedelta(hours=1)
        db.commit()
        return user

    try:
        spring_start = datetime(2026, 3, 23, 0, 0, tzinfo=timezone.utc)
        spring_now = datetime(2026, 3, 29, 11, 0, tzinfo=timezone.utc)
        spring_user = add_hourly_site("spring-dst@example.com", spring_start, spring_now)
        spring = consumption_service.get_period_summary(db, spring_user.id, "7d", now=spring_now)

        assert spring["period_start"] == "2026-03-23T00:00:00+00:00"
        assert spring["coverage_pct"] == 100.0
        assert spring["total_kwh"] == 155.0
        assert spring["projection"]["is_available"] is True
        assert spring["projection"]["projected_kwh"] == 167.0
        assert spring["projection"]["projected_cost"] == 167.0

        autumn_start = datetime(2026, 10, 18, 23, 0, tzinfo=timezone.utc)
        autumn_now = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
        autumn_user = add_hourly_site("autumn-dst@example.com", autumn_start, autumn_now)
        autumn = consumption_service.get_period_summary(db, autumn_user.id, "7d", now=autumn_now)

        assert autumn["period_start"] == "2026-10-18T23:00:00+00:00"
        assert autumn["coverage_pct"] == 100.0
        assert autumn["total_kwh"] == 157.0
        assert autumn["projection"]["is_available"] is True
        assert autumn["projection"]["projected_kwh"] == 169.0
        assert autumn["projection"]["projected_cost"] == 169.0
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_deterministic_end_of_period_projections():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        user = User(email="projections@example.com", password_hash=hash_password("password123"), role="user", is_active=True)
        db.add(user)
        db.commit()
        site = ensure_default_site(db, user.id)
        site.timezone = "UTC"
        meter = get_default_meter(db, user.id)
        settings = db.query(SiteSettings).filter(SiteSettings.site_id == site.id).one()
        settings.peak_rate = 2.0
        settings.off_peak_rate = 1.0
        settings.peak_start_hour = 6
        settings.peak_end_hour = 22
        settings.currency = "MAD"
        budget = EnergyBudget(user_id=user.id, site_id=site.id, monthly_budget_mad=100.0)
        db.add(budget)
        db.commit()

        # 1. Early period gate for Today (< 2 hours elapsed)
        now_early_today = datetime(2026, 7, 15, 1, 30, tzinfo=timezone.utc)
        sum_early_today = consumption_service.get_period_summary(db, user.id, "today", now=now_early_today)
        assert sum_early_today["projection"]["is_available"] is False
        assert sum_early_today["projection"]["reason"] == "early_period"

        # 2. No readings recorded in period
        now_noon_today = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
        sum_no_readings = consumption_service.get_period_summary(db, user.id, "today", now=now_noon_today)
        assert sum_no_readings["projection"]["is_available"] is False
        assert sum_no_readings["projection"]["reason"] == "no_readings"

        # 3. Add readings for Today: 12 hours elapsed (00:00 to 12:00), 100% coverage, steady 2.0 kW load
        # In UTC: 00:00 to 06:00 is off-peak (6h * 2kW = 12 kWh, cost = 12 * 1.0 = 12 MAD)
        # 06:00 to 12:00 is peak (6h * 2kW = 12 kWh, cost = 12 * 2.0 = 24 MAD)
        # Total so far: 24 kWh, 36 MAD.
        # Remaining Today: 12:00 to 22:00 is peak (10h * 2kW = 20 kWh, cost = 20 * 2.0 = 40 MAD)
        # 22:00 to 24:00 is off-peak (2h * 2kW = 4 kWh, cost = 4 * 1.0 = 4 MAD)
        # Estimated remaining: 24 kWh, 44 MAD.
        # Projected day total: 48 kWh, 80 MAD.
        for h in range(13):
            ts = datetime(2026, 7, 15, h, 0, tzinfo=timezone.utc)
            db.add(SmartMeterReading(
                meter_id=meter.id, timestamp=ts, gap=2.0, grp=0.1, voltage=230,
                intensity=8.7, sub_metering_1=0, sub_metering_2=0, sub_metering_3=0,
                source="csv", quality="validated",
            ))
        db.commit()

        sum_today = consumption_service.get_period_summary(db, user.id, "today", now=now_noon_today)
        assert sum_today["projection"]["is_available"] is True
        assert sum_today["projection"]["reason"] is None
        assert abs(sum_today["total_kwh"] - 24.0) < 0.01
        assert abs(sum_today["estimated_cost"] - 36.0) < 0.01
        assert abs(sum_today["projection"]["projected_kwh"] - 48.0) < 0.01
        assert abs(sum_today["projection"]["projected_cost"] - 80.0) < 0.01
        assert sum_today["projection"]["currency"] == "MAD"

        # 4. Partial hour tariff boundary crossing:
        # If period_end is 21:30 (crosses peak boundary at 22:00 with remaining 2.5h until midnight)
        # Remaining: 21:30 to 22:00 (0.5h peak = 1 kWh * 2.0 = 2 MAD) + 22:00 to 24:00 (2h off-peak = 4 kWh * 1.0 = 4 MAD) = 6 MAD remaining.
        now_partial = datetime(2026, 7, 15, 21, 30, tzinfo=timezone.utc)
        db.add(SmartMeterReading(
            meter_id=meter.id, timestamp=now_partial, gap=2.0, grp=0.1, voltage=230,
            intensity=8.7, sub_metering_1=0, sub_metering_2=0, sub_metering_3=0,
            source="csv", quality="validated",
        ))
        db.commit()
        sum_partial = consumption_service.get_period_summary(db, user.id, "today", now=now_partial)
        assert sum_partial["projection"]["is_available"] is True
        # Remaining cost from 21:30 to 24:00 is exactly 6.0 MAD
        expected_remaining_cost = (0.5 * 2.0 * 2.0) + (2.0 * 2.0 * 1.0)
        assert abs((sum_partial["projection"]["projected_cost"] - sum_partial["estimated_cost"]) - expected_remaining_cost) < 0.01

        # 5. Valid zero consumption with real coverage
        # Create a zero-load user
        user_zero = User(email="zero@example.com", password_hash=hash_password("password123"), role="user", is_active=True)
        db.add(user_zero)
        db.commit()
        site_zero = ensure_default_site(db, user_zero.id)
        meter_zero = get_default_meter(db, user_zero.id)
        for h in range(13):
            ts = datetime(2026, 7, 15, h, 0, tzinfo=timezone.utc)
            db.add(SmartMeterReading(
                meter_id=meter_zero.id, timestamp=ts, gap=0.0, grp=0.0, voltage=230,
                intensity=0.0, sub_metering_1=0, sub_metering_2=0, sub_metering_3=0,
                source="csv", quality="validated",
            ))
        db.commit()
        sum_zero = consumption_service.get_period_summary(db, user_zero.id, "today", now=now_noon_today)
        assert sum_zero["projection"]["is_available"] is True
        assert sum_zero["projection"]["projected_kwh"] == 0.0
        assert sum_zero["projection"]["projected_cost"] == 0.0

        # 6. Insufficient coverage (< 50%)
        # User with 1-hour coverage in a 10-hour period (gap > MAX_POWER_GAP_SECONDS)
        user_gap = User(email="gap@example.com", password_hash=hash_password("password123"), role="user", is_active=True)
        db.add(user_gap)
        db.commit()
        site_gap = ensure_default_site(db, user_gap.id)
        meter_gap = get_default_meter(db, user_gap.id)
        db.add_all([
            SmartMeterReading(meter_id=meter_gap.id, timestamp=datetime(2026, 7, 15, 0, 0, tzinfo=timezone.utc), gap=2.0, grp=0.0, voltage=230, intensity=8.7, sub_metering_1=0, sub_metering_2=0, sub_metering_3=0, source="csv", quality="validated"),
            SmartMeterReading(meter_id=meter_gap.id, timestamp=datetime(2026, 7, 15, 1, 0, tzinfo=timezone.utc), gap=2.0, grp=0.0, voltage=230, intensity=8.7, sub_metering_1=0, sub_metering_2=0, sub_metering_3=0, source="csv", quality="validated"),
        ])
        db.commit()
        # Query at 10:00 (10 hours elapsed, but only 1 hour covered -> coverage 10% < 50%)
        now_10am = datetime(2026, 7, 15, 10, 0, tzinfo=timezone.utc)
        sum_gap = consumption_service.get_period_summary(db, user_gap.id, "today", now=now_10am)
        assert sum_gap["projection"]["is_available"] is False
        assert sum_gap["projection"]["reason"] == "insufficient_coverage"

        # 7. Week projection and DST week (Europe/London 167h / 169h)
        site.timezone = "Europe/London"
        # Sunday March 29, 2026 at 12:00 BST (DST change occurred on Sunday 01:00 GMT -> 02:00 BST, week is 167 hours)
        now_dst_sun = datetime(2026, 3, 29, 11, 0, tzinfo=timezone.utc)
        sum_week_dst = consumption_service.get_period_summary(db, user.id, "7d", now=now_dst_sun)
        # Since user has no readings in March 2026, reason is no_readings
        assert sum_week_dst["projection"]["is_available"] is False
        assert sum_week_dst["projection"]["reason"] == "no_readings"

        # 8. Month budget status: within_budget, projected_to_exceed, no_budget
        # Add 3 days of readings to month (July 1 to July 4, 72 hours elapsed >= 24h gate)
        for h in range(73):
            ts = datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc) + timedelta(hours=h)
            db.add(SmartMeterReading(
                meter_id=meter.id, timestamp=ts, gap=1.0, grp=0.1, voltage=230,
                intensity=4.3, sub_metering_1=0, sub_metering_2=0, sub_metering_3=0,
                source="csv", quality="validated",
            ))
        db.commit()
        site.timezone = "UTC"
        now_july4 = datetime(2026, 7, 4, 0, 0, tzinfo=timezone.utc)
        budget.monthly_budget_mad = 2000.0
        db.commit()
        sum_month_within = consumption_service.get_period_summary(db, user.id, "month", now=now_july4)
        assert sum_month_within["projection"]["is_available"] is True
        assert sum_month_within["projection"]["budget_status"] == "within_budget"
        assert sum_month_within["projection"]["budget_target"] == 2000.0

        # Now set budget to low amount so it is projected to exceed
        budget.monthly_budget_mad = 50.0
        db.commit()
        sum_month_exceed = consumption_service.get_period_summary(db, user.id, "month", now=now_july4)
        assert sum_month_exceed["projection"]["is_available"] is True
        assert sum_month_exceed["projection"]["budget_status"] == "projected_to_exceed"

        # Now remove budget
        db.delete(budget)
        db.commit()
        sum_month_nobudget = consumption_service.get_period_summary(db, user.id, "month", now=now_july4)
        assert sum_month_nobudget["projection"]["is_available"] is True
        assert sum_month_nobudget["projection"]["budget_status"] == "no_budget"

        # 9. Month duration across 28, 29, 30, and 31-day months
        # Test helper directly for various months
        proj_feb28 = consumption_service._calculate_projection(
            "month", 10.0, 10.0, 86400, datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 2, 2, 0, 0, tzinfo=timezone.utc), ZoneInfo("UTC"), settings, None,
        )
        # 1 day elapsed (10 kWh), 27 days remaining at 10 kWh/day -> 280 kWh projected total
        assert abs(proj_feb28["projected_kwh"] - 280.0) < 0.01

        proj_feb29 = consumption_service._calculate_projection(
            "month", 10.0, 10.0, 86400, datetime(2028, 2, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2028, 2, 2, 0, 0, tzinfo=timezone.utc), ZoneInfo("UTC"), settings, None,
        )
        # Leap year 2028: 1 day elapsed (10 kWh), 28 days remaining at 10 kWh/day -> 290 kWh projected total
        assert abs(proj_feb29["projected_kwh"] - 290.0) < 0.01

        proj_apr30 = consumption_service._calculate_projection(
            "month", 10.0, 10.0, 86400, datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 2, 0, 0, tzinfo=timezone.utc), ZoneInfo("UTC"), settings, None,
        )
        assert abs(proj_apr30["projected_kwh"] - 300.0) < 0.01

        proj_jul31 = consumption_service._calculate_projection(
            "month", 10.0, 10.0, 86400, datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 7, 2, 0, 0, tzinfo=timezone.utc), ZoneInfo("UTC"), settings, None,
        )
        assert abs(proj_jul31["projected_kwh"] - 310.0) < 0.01

        # 10. Single source of truth: Usage month projection == Dashboard monthly budget calculation
        # When called with identical period bounds, load, and settings, _calculate_projection produces identical values.
        budget_truth = EnergyBudget(user_id=user.id, site_id=site.id, monthly_budget_mad=2000.0)
        proj_usage = consumption_service._calculate_projection(
            "month", sum_month_within["total_kwh"], sum_month_within["estimated_cost"],
            72 * 3600, datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc),
            now_july4, ZoneInfo("UTC"), settings, budget_truth,
        )
        assert proj_usage["is_available"] is True
        assert proj_usage["budget_status"] == "within_budget"
        assert abs(sum_month_within["projection"]["projected_cost"] - proj_usage["projected_cost"]) < 0.01

        # When month is fully elapsed with only 3 days of readings (coverage 9.8% < 50%), Dashboard marks projection_available as False with reason "insufficient_coverage"
        sum_dash_month = consumption_service.get_monthly_summary(db, user.id, "2026-07")
        assert sum_dash_month["budget"]["projection_available"] is False
        assert sum_dash_month["budget"]["projection_reason"] == "insufficient_coverage"
        assert sum_dash_month["budget"]["projected_mad"] is None
        assert sum_dash_month["budget"]["spent_mad"] == sum_dash_month["total_cost"]

        # 11. Dashboard behavior when projection is unavailable:
        # A. early_period (e.g. July 1 at 10:00 -> 10 hours elapsed < 24h gate)
        # Note: readings start at July 1 00:00. At 10:00, 10 hours elapsed.
        now_dash_early = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
        # We test via _calculate_projection directly for July 1 10:00
        proj_dash_early = consumption_service._calculate_projection(
            "month", 10.0, 15.0, 36000, datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc),
            now_dash_early, ZoneInfo("UTC"), settings, None,
        )
        assert proj_dash_early["is_available"] is False
        assert proj_dash_early["reason"] == "early_period"

        # B. insufficient_coverage (< 50%)
        proj_dash_lowcov = consumption_service._calculate_projection(
            "month", 10.0, 15.0, 36000, datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 7, 5, 0, 0, tzinfo=timezone.utc), ZoneInfo("UTC"), settings, None,
        )
        assert proj_dash_lowcov["is_available"] is False
        assert proj_dash_lowcov["reason"] == "insufficient_coverage"

        # C. no_readings
        empty_dash_month = consumption_service._empty_month("2026-07")
        assert empty_dash_month["budget"]["projected_mad"] is None
        assert empty_dash_month["budget"]["projection_available"] is False
        assert empty_dash_month["budget"]["projection_reason"] == "no_readings"
        assert empty_dash_month["budget"]["spent_mad"] == 0.0

        # 12. Year and All return unsupported_timeframe
        sum_year = consumption_service.get_period_summary(db, user.id, "year", now=now_july4)
        assert sum_year["projection"]["is_available"] is False
        assert sum_year["projection"]["reason"] == "unsupported_timeframe"

        sum_all = consumption_service.get_period_summary(db, user.id, "all", now=now_july4)
        assert sum_all["projection"]["is_available"] is False
        assert sum_all["projection"]["reason"] == "unsupported_timeframe"
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
