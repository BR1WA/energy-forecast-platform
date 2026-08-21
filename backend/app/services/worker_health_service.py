"""Database-backed liveness for durable worker processes."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import WorkerHeartbeat


WORKER_INTERVALS = {
    "simulation": "SIMULATION_WORKER_INTERVAL_SECONDS",
    "alerts": "ALERT_WORKER_INTERVAL_SECONDS",
    "email": "EMAIL_WORKER_POLL_SECONDS",
    "avatar_cleanup": "AVATAR_CLEANUP_POLL_SECONDS",
}

# Workers and the API normally share a server/database clock. This small
# boundary tolerance prevents a tick-level false negative without treating a
# genuinely future-dated success as healthy.
MAX_FUTURE_CLOCK_SKEW_SECONDS = 5


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _stale_after_seconds(worker_name: str) -> int:
    interval = int(getattr(get_settings(), WORKER_INTERVALS[worker_name]))
    return max(60, interval * 3)


def record_worker_success(
    db: Session, worker_name: str, *, now: datetime | None = None
) -> WorkerHeartbeat:
    if worker_name not in WORKER_INTERVALS:
        raise ValueError(f"Unknown worker: {worker_name}")
    heartbeat = db.get(WorkerHeartbeat, worker_name)
    if heartbeat is None:
        heartbeat = WorkerHeartbeat(worker_name=worker_name)
        db.add(heartbeat)
    heartbeat.last_success_at = _as_utc(now or datetime.now(timezone.utc))
    return heartbeat


def worker_status(
    db: Session, worker_name: str, *, now: datetime | None = None
) -> dict:
    if worker_name not in WORKER_INTERVALS:
        raise ValueError(f"Unknown worker: {worker_name}")
    heartbeat = db.get(WorkerHeartbeat, worker_name)
    observed_at = _as_utc(now or datetime.now(timezone.utc))
    last_success_at = (
        _as_utc(heartbeat.last_success_at) if heartbeat is not None else None
    )
    stale_after_seconds = _stale_after_seconds(worker_name)
    age_seconds = (
        (observed_at - last_success_at).total_seconds()
        if last_success_at is not None
        else None
    )
    operational = bool(
        age_seconds is not None
        and -MAX_FUTURE_CLOCK_SKEW_SECONDS <= age_seconds <= stale_after_seconds
    )
    return {
        "status": "operational" if operational else "unavailable",
        "operational": operational,
        "last_success_at": last_success_at,
        "stale_after_seconds": stale_after_seconds,
    }


def worker_statuses(db: Session, *, now: datetime | None = None) -> dict[str, dict]:
    return {name: worker_status(db, name, now=now) for name in WORKER_INTERVALS}
