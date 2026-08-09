from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import AuditEvent, SimulationSession, SmartMeterReading, User
from app.services.auth_service import hash_password
from app.services.simulation_service import (
    BOOTSTRAP_INTERVAL_SECONDS,
    MAX_CATCHUP_POINTS,
    SimulationService,
    simulation_service,
)
from app.services.site_service import ensure_user_site, get_primary_meter


def _database():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine, sessionmaker(bind=engine)()


def _account(db, email: str = "persistent-simulation@example.com"):
    user = User(
        email=email,
        password_hash=hash_password("password123"),
        role="user",
        is_active=True,
    )
    db.add(user)
    db.commit()
    ensure_user_site(db, user.id)
    db.commit()
    return user, get_primary_meter(db, user.id)


def _reading(meter_id: int, timestamp: datetime, source: str, power: float = 1.0):
    return SmartMeterReading(
        meter_id=meter_id,
        timestamp=timestamp,
        gap=power,
        grp=power * 0.08,
        voltage=230.0,
        intensity=power * 1000 / 230.0,
        sub_metering_1=0.0,
        sub_metering_2=0.0,
        sub_metering_3=0.0,
        source=source,
        quality="simulated" if source == "simulation" else "validated",
    )


def test_household_profile_is_deterministic_and_has_expected_daily_shapes():
    service = SimulationService()
    config = {"base_load_kw": 1.2, "variation_percent": 10, "_seed": 42}
    weekday_overnight = datetime(2026, 8, 10, 2, tzinfo=timezone.utc)
    weekday_morning = datetime(2026, 8, 10, 7, 30, tzinfo=timezone.utc)
    weekday_late_morning = datetime(2026, 8, 10, 10, tzinfo=timezone.utc)
    weekend_late_morning = datetime(2026, 8, 15, 10, tzinfo=timezone.utc)

    first = service.reading_for_configuration(config, timestamp=weekday_morning, seed=42)
    second = service.reading_for_configuration(config, timestamp=weekday_morning, seed=42)

    assert first == second
    assert first["active_power_kw"] > service.reading_for_configuration(
        config, timestamp=weekday_overnight, seed=42,
    )["active_power_kw"]
    assert service.reading_for_configuration(
        config, timestamp=weekend_late_morning, seed=42,
    )["active_power_kw"] > service.reading_for_configuration(
        config, timestamp=weekday_late_morning, seed=42,
    )["active_power_kw"]


def test_first_start_bootstraps_thirty_days_with_truthful_source_and_no_duplicates():
    engine, db = _database()
    try:
        user, meter = _account(db)
        first = simulation_service.start_simulation(db, user.id)
        second = simulation_service.start_simulation(db, user.id)

        count = db.query(SmartMeterReading).filter(SmartMeterReading.meter_id == meter.id).count()
        distinct_count = db.query(func.count(func.distinct(SmartMeterReading.timestamp))).filter(
            SmartMeterReading.meter_id == meter.id,
        ).scalar()
        earliest, latest = db.query(
            func.min(SmartMeterReading.timestamp), func.max(SmartMeterReading.timestamp),
        ).filter(SmartMeterReading.meter_id == meter.id).one()

        assert first["history_action"] == "bootstrapped_empty_meter"
        assert first["bootstrap_accepted_rows"] == 2_881
        assert first["history_ready_for_forecast"] is True
        assert first["history_span_hours"] >= 720
        assert second["history_action"] == "preserved_existing_simulation_history"
        assert count == distinct_count
        assert (latest - earliest).total_seconds() >= 720 * 3600
        assert db.query(SmartMeterReading).filter(
            SmartMeterReading.meter_id == meter.id,
            SmartMeterReading.source != "simulation",
        ).count() == 0
        assert db.query(SmartMeterReading).filter(
            SmartMeterReading.meter_id == meter.id,
            SmartMeterReading.quality != "simulated",
        ).count() == 0
        assert db.query(AuditEvent).filter(AuditEvent.event_type == "simulation.started").count() == 2
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_start_preserves_real_history_instead_of_backfilling_its_gap():
    engine, db = _database()
    try:
        user, meter = _account(db, "preserve-real-gap@example.com")
        now = datetime.now(timezone.utc).replace(microsecond=0)
        db.add_all([
            _reading(meter.id, now - timedelta(hours=24), "csv", 0.8),
            _reading(meter.id, now - timedelta(hours=12), "push", 1.4),
        ])
        db.commit()

        result = simulation_service.start_simulation(db, user.id)

        assert result["history_action"] == "preserved_existing_meter_history"
        assert db.query(SmartMeterReading).filter(
            SmartMeterReading.meter_id == meter.id,
            SmartMeterReading.source.in_(["csv", "push"]),
        ).count() == 2
        assert db.query(SmartMeterReading).filter(
            SmartMeterReading.meter_id == meter.id,
            SmartMeterReading.source == "simulation",
            SmartMeterReading.timestamp < now - timedelta(minutes=1),
        ).count() == 0
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_legacy_gap_is_preserved_then_later_wake_is_caught_up_idempotently():
    engine, db = _database()
    try:
        user, meter = _account(db, "legacy-gap@example.com")
        session = simulation_service._session(db, user.id)
        session.is_running = True
        session.started_at = datetime(2026, 8, 1, tzinfo=timezone.utc)
        session.configuration = {"base_load_kw": 1.2, "variation_percent": 10}
        old_timestamp = datetime(2026, 8, 8, 0, tzinfo=timezone.utc)
        deployment_wake = datetime(2026, 8, 8, 12, tzinfo=timezone.utc)
        db.add(_reading(meter.id, old_timestamp, "simulation"))
        db.commit()

        boundary = simulation_service.advance_session(db, session, now=deployment_wake)
        db.commit()
        assert boundary["continuity_initialized"] is True
        assert boundary["catch_up_points"] == 0
        assert db.query(SmartMeterReading).filter(
            SmartMeterReading.meter_id == meter.id,
            SmartMeterReading.source == "simulation",
            SmartMeterReading.timestamp > old_timestamp,
            SmartMeterReading.timestamp < deployment_wake,
        ).count() == 0

        next_wake = deployment_wake + timedelta(hours=2)
        caught_up = simulation_service.advance_session(db, session, now=next_wake)
        db.commit()
        before_replay = db.query(SmartMeterReading).filter(
            SmartMeterReading.meter_id == meter.id,
            SmartMeterReading.source == "simulation",
        ).count()
        replay = simulation_service.advance_session(db, session, now=next_wake)
        db.commit()

        assert caught_up["catch_up_points"] == 8
        assert replay["catch_up_points"] == 0
        assert db.query(SmartMeterReading).filter(
            SmartMeterReading.meter_id == meter.id,
            SmartMeterReading.source == "simulation",
        ).count() == before_replay
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_exceptional_catch_up_is_coarsened_and_hard_limited():
    gap = timedelta(days=365 * 10).total_seconds()
    interval, limited = simulation_service._catch_up_interval(gap)
    start = datetime(2016, 8, 9, tzinfo=timezone.utc)
    timestamps = simulation_service._catch_up_timestamps(
        start,
        start + timedelta(seconds=gap),
        interval,
    )

    assert limited is True
    assert interval > BOOTSTRAP_INTERVAL_SECONDS
    assert len(timestamps) <= MAX_CATCHUP_POINTS
    assert timestamps[-1] <= start + timedelta(seconds=gap)


def test_reset_replaces_only_simulation_rows_and_leaves_feed_stopped():
    engine, db = _database()
    try:
        user, meter = _account(db, "reset-isolated@example.com")
        preserved_at = datetime.now(timezone.utc) - timedelta(days=45)
        db.add_all([
            _reading(meter.id, preserved_at, "csv", 0.7),
            _reading(meter.id, preserved_at + timedelta(hours=1), "simulation", 1.1),
        ])
        db.commit()

        result = simulation_service.reset_simulation(db, user.id)

        assert result["status"] == "reset"
        assert result["deleted_simulation_readings"] == 1
        assert result["preserved_non_simulation_data"] is True
        assert result["is_running"] is False
        assert result["history_span_hours"] >= 720
        assert db.query(SmartMeterReading).filter(
            SmartMeterReading.meter_id == meter.id,
            SmartMeterReading.timestamp == preserved_at,
            SmartMeterReading.source == "csv",
        ).count() == 1
        assert db.query(SimulationSession).filter(
            SimulationSession.site_id == meter.site_id,
            SimulationSession.is_running.is_(True),
        ).count() == 0
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
