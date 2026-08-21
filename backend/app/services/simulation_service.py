"""Persistent, deterministic, site-owned demo simulation."""
from __future__ import annotations

import hashlib
import math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import IngestionBatch, Meter, SimulationSession, SmartMeterReading
from app.schemas import MeterSample
from app.services.audit_service import record_audit_event
from app.services.ingestion_service import ingestion_service
from app.services.site_service import ensure_user_site, get_primary_meter
from app.services.worker_health_service import worker_status


PROFILE_VERSION = "household_v1"
BOOTSTRAP_DAYS = 365
BOOTSTRAP_INTERVAL_SECONDS = 60 * 60
LIVE_INTERVAL_SECONDS = 5
MINIMUM_FORECAST_HISTORY_HOURS = 336
MINIMUM_MONTH_FORECAST_HISTORY_DAYS = 270
MAX_CATCHUP_POINTS = 5_000
CATCHUP_INTERVALS_SECONDS = (
    15 * 60,
    30 * 60,
    60 * 60,
    2 * 60 * 60,
    6 * 60 * 60,
    12 * 60 * 60,
    24 * 60 * 60,
    7 * 24 * 60 * 60,
)

DEFAULT_CONFIGURATION = {
    "base_load_kw": 1.2,
    "variation_percent": 10,
}


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _floor_timestamp(value: datetime, interval_seconds: int) -> datetime:
    value_utc = _as_utc(value)
    epoch = int(value_utc.timestamp())
    return datetime.fromtimestamp(epoch - epoch % interval_seconds, tz=timezone.utc)


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return _as_utc(datetime.fromisoformat(value))
    except ValueError:
        return None


def _stable_unit(seed: int, timestamp: datetime, channel: str) -> float:
    """Return a stable number in [-1, 1] without process-global randomness."""
    payload = f"{seed}:{_as_utc(timestamp).isoformat()}:{channel}".encode("utf-8")
    integer = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
    return integer / ((1 << 64) - 1) * 2.0 - 1.0


def _daily_unit(seed: int, local_timestamp: datetime, channel: str) -> float:
    payload = f"{seed}:{local_timestamp.date().isoformat()}:{channel}".encode("utf-8")
    integer = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
    return integer / ((1 << 64) - 1) * 2.0 - 1.0


def _cyclic_peak(hour: float, center: float, width: float) -> float:
    distance = abs(hour - center)
    distance = min(distance, 24.0 - distance)
    return math.exp(-0.5 * (distance / width) ** 2)


class SimulationService:
    @staticmethod
    def _seed_for_site(site_id: int) -> int:
        return 20_260_809 + site_id * 7_919

    def _normalise_configuration(self, session: SimulationSession) -> dict:
        stored = dict(session.configuration or {})
        for key, default in DEFAULT_CONFIGURATION.items():
            stored[key] = stored.get(key, default)
        stored["_seed"] = int(stored.get("_seed") or self._seed_for_site(session.site_id))
        stored["_profile_version"] = PROFILE_VERSION
        return stored

    def _session(self, db: Session, user_id: int) -> SimulationSession:
        site = ensure_user_site(db, user_id)
        session = (
            db.query(SimulationSession)
            .filter(SimulationSession.site_id == site.id)
            .first()
        )
        if session is None:
            session = SimulationSession(
                site_id=site.id,
                user_id=user_id,
                configuration={
                    **DEFAULT_CONFIGURATION,
                    "_seed": self._seed_for_site(site.id),
                    "_profile_version": PROFILE_VERSION,
                },
            )
            db.add(session)
            db.flush()
        return session

    @staticmethod
    def _history_stats(db: Session, meter_id: int) -> dict:
        count, earliest, latest = (
            db.query(
                func.count(SmartMeterReading.id),
                func.min(SmartMeterReading.timestamp),
                func.max(SmartMeterReading.timestamp),
            )
            .filter(
                SmartMeterReading.meter_id == meter_id,
                SmartMeterReading.source == "simulation",
            )
            .one()
        )
        earliest_utc = _as_utc(earliest) if earliest is not None else None
        latest_utc = _as_utc(latest) if latest is not None else None
        span_hours = (
            max(0.0, (latest_utc - earliest_utc).total_seconds() / 3600.0)
            if earliest_utc is not None and latest_utc is not None
            else 0.0
        )
        return {
            "history_points": int(count or 0),
            "history_start_at": earliest_utc,
            "history_end_at": latest_utc,
            "history_span_hours": round(span_hours, 1),
            "history_ready_for_forecast": span_hours >= MINIMUM_FORECAST_HISTORY_HOURS,
            "history_ready_for_month_forecast": span_hours >= MINIMUM_MONTH_FORECAST_HISTORY_DAYS * 24,
        }

    def get_state(self, db: Session, user_id: int) -> dict:
        session = self._session(db, user_id)
        config = self._normalise_configuration(session)
        uptime = 0.0
        if session.is_running and session.started_at:
            uptime = max(0.0, (datetime.now(timezone.utc) - _as_utc(session.started_at)).total_seconds())
        meter = get_primary_meter(db, user_id)
        history = self._history_stats(db, meter.id) if meter is not None else {
            "history_points": 0,
            "history_start_at": None,
            "history_end_at": None,
            "history_span_hours": 0.0,
            "history_ready_for_forecast": False,
            "history_ready_for_month_forecast": False,
        }
        return {
            "is_running": session.is_running,
            "uptime": uptime,
            "site_id": session.site_id,
            "profile": PROFILE_VERSION,
            "is_reproducible": True,
            "bootstrap_days": BOOTSTRAP_DAYS,
            "bootstrap_interval_minutes": BOOTSTRAP_INTERVAL_SECONDS // 60,
            "minimum_forecast_history_hours": MINIMUM_FORECAST_HISTORY_HOURS,
            "minimum_month_forecast_history_days": MINIMUM_MONTH_FORECAST_HISTORY_DAYS,
            "continuity_enabled_at": _parse_timestamp(config.get("_continuity_started_at")),
            "last_catch_up_at": _parse_timestamp(config.get("_last_catch_up_at")),
            "last_catch_up_points": int(config.get("_last_catch_up_points") or 0),
            "last_catch_up_interval_minutes": (
                int(config["_last_catch_up_interval_seconds"]) // 60
                if config.get("_last_catch_up_interval_seconds")
                else None
            ),
            "last_catch_up_was_limited": bool(config.get("_last_catch_up_was_limited", False)),
            "worker": worker_status(db, "simulation"),
            **history,
            **{key: config[key] for key in DEFAULT_CONFIGURATION},
        }

    def configure_simulation(self, db: Session, user_id: int, config: dict) -> dict:
        session = self._session(db, user_id)
        stored = self._normalise_configuration(session)
        stored.update({key: config.get(key, default) for key, default in DEFAULT_CONFIGURATION.items()})
        session.configuration = stored
        record_audit_event(
            db,
            "simulation.configuration_updated",
            actor_user_id=user_id,
            site_id=session.site_id,
            target=f"simulation:{session.id}",
            metadata={key: stored[key] for key in DEFAULT_CONFIGURATION},
        )
        db.commit()
        return {"status": "configured", **self.get_state(db, user_id)}

    def _bootstrap_history(
        self,
        db: Session,
        session: SimulationSession,
        meter: Meter,
        *,
        now: datetime,
    ) -> dict:
        config = self._normalise_configuration(session)
        anchor = _floor_timestamp(now, BOOTSTRAP_INTERVAL_SECONDS)
        start = anchor - timedelta(days=BOOTSTRAP_DAYS)
        sample_count = BOOTSTRAP_DAYS * 24 * 3600 // BOOTSTRAP_INTERVAL_SECONDS + 1
        samples = [
            MeterSample.model_validate(
                self.reading_for_configuration(
                    config,
                    timestamp=start + timedelta(seconds=index * BOOTSTRAP_INTERVAL_SECONDS),
                    timezone_name=meter.site.timezone,
                    seed=int(config["_seed"]),
                )
            )
            for index in range(sample_count)
        ]
        result = ingestion_service.ingest(
            db,
            meter,
            samples,
            source="simulation",
            idempotency_key=f"simulation-bootstrap-{meter.id}-{int(config['_seed'])}-{int(anchor.timestamp())}",
        )
        meter.expected_interval_seconds = BOOTSTRAP_INTERVAL_SECONDS
        return result

    def start_simulation(self, db: Session, user_id: int) -> dict:
        now = datetime.now(timezone.utc)
        session = self._session(db, user_id)
        meter = get_primary_meter(db, user_id)
        if meter is None:
            raise RuntimeError("A primary meter could not be prepared.")

        config = self._normalise_configuration(session)
        was_running = bool(session.is_running)
        if not was_running:
            session.started_at = now
            # A deliberate stop/start is not an outage. It establishes a new
            # boundary so the intentionally stopped interval stays visible.
            config["_continuity_started_at"] = now.isoformat()
        session.is_running = True
        session.configuration = config
        meter.source_type = "simulation"
        meter.expected_interval_seconds = LIVE_INTERVAL_SECONDS

        simulation_count = (
            db.query(func.count(SmartMeterReading.id))
            .filter(
                SmartMeterReading.meter_id == meter.id,
                SmartMeterReading.source == "simulation",
            )
            .scalar()
            or 0
        )
        total_count = (
            db.query(func.count(SmartMeterReading.id))
            .filter(SmartMeterReading.meter_id == meter.id)
            .scalar()
            or 0
        )
        bootstrap_result = None
        if simulation_count == 0 and total_count == 0:
            bootstrap_result = self._bootstrap_history(db, session, meter, now=now)
            history_action = "bootstrapped_empty_meter"
        elif simulation_count == 0:
            # Do not turn holes in imported or measured history into synthetic data.
            history_action = "preserved_existing_meter_history"
        else:
            history_action = "preserved_existing_simulation_history"

        record_audit_event(
            db,
            "simulation.started",
            actor_user_id=user_id,
            site_id=session.site_id,
            target=f"simulation:{session.id}",
            metadata={
                "history_action": history_action,
                "bootstrap_accepted_rows": (bootstrap_result or {}).get("accepted_rows", 0),
                "catch_up_points": 0,
            },
        )
        db.commit()
        return {
            "status": "started",
            "history_action": history_action,
            "bootstrap_accepted_rows": (bootstrap_result or {}).get("accepted_rows", 0),
            **self.get_state(db, user_id),
        }

    def stop_simulation(self, db: Session, user_id: int) -> dict:
        session = self._session(db, user_id)
        session.is_running = False
        config = self._normalise_configuration(session)
        config["_continuity_started_at"] = None
        session.configuration = config
        record_audit_event(
            db,
            "simulation.stopped",
            actor_user_id=user_id,
            site_id=session.site_id,
            target=f"simulation:{session.id}",
        )
        db.commit()
        return {"status": "stopped", **self.get_state(db, user_id)}

    def reset_simulation(self, db: Session, user_id: int) -> dict:
        """Replace only simulator-owned data with a clean deterministic history."""
        now = datetime.now(timezone.utc)
        session = self._session(db, user_id)
        meter = get_primary_meter(db, user_id)
        if meter is None:
            raise RuntimeError("A primary meter could not be prepared.")

        deleted_readings = (
            db.query(SmartMeterReading)
            .filter(
                SmartMeterReading.meter_id == meter.id,
                SmartMeterReading.source == "simulation",
            )
            .delete(synchronize_session=False)
        )
        db.flush()
        db.query(IngestionBatch).filter(
            IngestionBatch.meter_id == meter.id,
            IngestionBatch.source == "simulation",
        ).delete(synchronize_session=False)

        latest_preserved = (
            db.query(SmartMeterReading)
            .filter(SmartMeterReading.meter_id == meter.id)
            .order_by(SmartMeterReading.timestamp.desc())
            .first()
        )
        meter.last_seen_at = latest_preserved.timestamp if latest_preserved is not None else None
        meter.source_type = "simulation"
        session.is_running = False
        session.started_at = None
        session.configuration = {
            **DEFAULT_CONFIGURATION,
            "_seed": self._seed_for_site(session.site_id),
            "_profile_version": PROFILE_VERSION,
            "_continuity_started_at": None,
        }
        bootstrap = self._bootstrap_history(db, session, meter, now=now)
        record_audit_event(
            db,
            "simulation.data_reset",
            actor_user_id=user_id,
            site_id=session.site_id,
            target=f"simulation:{session.id}",
            metadata={
                "deleted_simulation_readings": deleted_readings,
                "accepted_simulation_readings": bootstrap["accepted_rows"],
                "duplicate_preserved_timestamps": bootstrap["duplicate_rows"],
                "preserved_non_simulation_readings": latest_preserved is not None,
            },
        )
        db.commit()
        return {
            "status": "reset",
            "deleted_simulation_readings": deleted_readings,
            "bootstrap_accepted_rows": bootstrap["accepted_rows"],
            "preserved_non_simulation_data": latest_preserved is not None,
            **self.get_state(db, user_id),
        }

    @staticmethod
    def _catch_up_interval(gap_seconds: float) -> tuple[int, bool]:
        for interval in CATCHUP_INTERVALS_SECONDS:
            if math.floor(gap_seconds / interval) <= MAX_CATCHUP_POINTS:
                return interval, interval > BOOTSTRAP_INTERVAL_SECONDS
        interval = math.ceil(gap_seconds / MAX_CATCHUP_POINTS / BOOTSTRAP_INTERVAL_SECONDS)
        return max(BOOTSTRAP_INTERVAL_SECONDS, interval * BOOTSTRAP_INTERVAL_SECONDS), True

    @staticmethod
    def _catch_up_timestamps(start: datetime, end: datetime, interval_seconds: int) -> list[datetime]:
        start_epoch = int(_as_utc(start).timestamp())
        end_epoch = int(_as_utc(end).timestamp())
        first_epoch = (start_epoch // interval_seconds + 1) * interval_seconds
        if first_epoch > end_epoch:
            return []
        count = (end_epoch - first_epoch) // interval_seconds + 1
        return [
            datetime.fromtimestamp(first_epoch + index * interval_seconds, tz=timezone.utc)
            for index in range(min(count, MAX_CATCHUP_POINTS))
        ]

    def advance_session(self, db: Session, session: SimulationSession, *, now: datetime | None = None) -> dict:
        """Catch up one running session, then persist the current live sample."""
        now_utc = _as_utc(now or datetime.now(timezone.utc))
        meter = (
            db.query(Meter)
            .filter(Meter.site_id == session.site_id, Meter.is_primary.is_(True))
            .one_or_none()
        )
        if meter is None or not session.is_running:
            return {"catch_up_points": 0, "catch_up_interval_seconds": None, "continuity_initialized": False}

        config = self._normalise_configuration(session)
        continuity = _parse_timestamp(config.get("_continuity_started_at"))
        continuity_initialized = continuity is None
        if continuity is None:
            # This is the deployment boundary for sessions created by the old
            # simulator. Historical gaps before it remain visible by design.
            continuity = now_utc
            config["_continuity_started_at"] = continuity.isoformat()
            session.configuration = config

        latest = (
            db.query(SmartMeterReading)
            .filter(
                SmartMeterReading.meter_id == meter.id,
                SmartMeterReading.source == "simulation",
            )
            .order_by(SmartMeterReading.timestamp.desc())
            .first()
        )
        catch_up_points = 0
        catch_up_interval = None
        was_limited = False
        if latest is not None and not continuity_initialized:
            catch_up_start = max(_as_utc(latest.timestamp), continuity)
            gap_seconds = max(0.0, (now_utc - catch_up_start).total_seconds())
            catch_up_interval, was_limited = self._catch_up_interval(gap_seconds)
            timestamps = self._catch_up_timestamps(catch_up_start, now_utc, catch_up_interval)
            if timestamps:
                samples = [
                    MeterSample.model_validate(
                        self.reading_for_configuration(
                            config,
                            timestamp=timestamp,
                            timezone_name=meter.site.timezone,
                            seed=int(config["_seed"]),
                        )
                    )
                    for timestamp in timestamps
                ]
                catch_up = ingestion_service.ingest(
                    db,
                    meter,
                    samples,
                    source="simulation",
                    idempotency_key=(
                        f"simulation-catchup-{meter.id}-{int(catch_up_start.timestamp())}-"
                        f"{int(_floor_timestamp(now_utc, catch_up_interval).timestamp())}-{catch_up_interval}"
                    ),
                )
                catch_up_points = catch_up["accepted_rows"]
                config["_last_catch_up_at"] = now_utc.isoformat()
                config["_last_catch_up_points"] = catch_up_points
                config["_last_catch_up_interval_seconds"] = catch_up_interval
                config["_last_catch_up_was_limited"] = was_limited
                session.configuration = config

        live_timestamp = _floor_timestamp(now_utc, LIVE_INTERVAL_SECONDS)
        live_sample = MeterSample.model_validate(
            self.reading_for_configuration(
                config,
                timestamp=live_timestamp,
                timezone_name=meter.site.timezone,
                seed=int(config["_seed"]),
            )
        )
        ingestion_service.ingest(db, meter, [live_sample], source="simulation")
        meter.source_type = "simulation"
        meter.expected_interval_seconds = LIVE_INTERVAL_SECONDS
        return {
            "catch_up_points": catch_up_points,
            "catch_up_interval_seconds": catch_up_interval if catch_up_points else None,
            "continuity_initialized": continuity_initialized,
            "catch_up_was_limited": was_limited,
        }

    @staticmethod
    def reading_for_configuration(
        config: dict,
        *,
        timestamp: datetime | None = None,
        timezone_name: str = "UTC",
        seed: int | None = None,
    ) -> dict:
        """Generate one reproducible household sample for an exact timestamp."""
        observed_at = _as_utc(timestamp or datetime.now(timezone.utc))
        try:
            zone = ZoneInfo(timezone_name)
        except (KeyError, ValueError):
            zone = ZoneInfo("UTC")
        local = observed_at.astimezone(zone)
        household_seed = int(seed if seed is not None else config.get("_seed", 20_260_809))
        base_load = float(config.get("base_load_kw", DEFAULT_CONFIGURATION["base_load_kw"]))
        variation = float(config.get("variation_percent", DEFAULT_CONFIGURATION["variation_percent"])) / 100.0
        hour = local.hour + local.minute / 60.0 + local.second / 3600.0
        weekend = local.weekday() >= 5

        if weekend:
            shape = (
                0.42
                + 0.50 * _cyclic_peak(hour, 9.5, 2.0)
                + 0.22 * _cyclic_peak(hour, 14.0, 4.0)
                + 0.88 * _cyclic_peak(hour, 20.0, 2.6)
            )
        else:
            shape = (
                0.38
                + 0.58 * _cyclic_peak(hour, 7.5, 1.5)
                + 0.14 * _cyclic_peak(hour, 13.0, 3.8)
                + 0.96 * _cyclic_peak(hour, 19.5, 2.2)
            )

        daily_shift = 1.0 + _daily_unit(household_seed, local, "daily") * variation * 0.35
        point_shift = 1.0 + _stable_unit(household_seed, observed_at, "load") * variation * 0.65
        active_power = max(0.02, base_load * shape * daily_shift * point_shift)
        voltage = 230.0 + _stable_unit(household_seed, observed_at, "voltage") * 1.8
        reactive_ratio = 0.08 + _stable_unit(household_seed, observed_at, "reactive") * 0.008
        return {
            "active_power_kw": round(active_power, 3),
            "reactive_power_kvar": round(max(0.0, active_power * reactive_ratio), 3),
            "voltage_v": round(voltage, 1),
            "current_a": round((active_power * 1000.0) / voltage, 2),
            "timestamp": observed_at,
        }


simulation_service = SimulationService()
