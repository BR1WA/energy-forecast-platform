"""Safe, shared forecast-window and presentation helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo


def as_utc(value: datetime) -> datetime:
    """Treat naive persisted timestamps as UTC and normalize aware values."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def snapshot_datetime(value: Any) -> datetime | None:
    """Parse persisted metadata without letting malformed historic records break APIs."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return None


def positive_int(value: Any, fallback: int) -> int:
    """Read a positive snapshot integer, using a safe fallback for bad values."""
    if isinstance(value, bool):
        return fallback
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def forecast_window(
    snapshot: dict[str, Any], *, fallback_target_count: int = 0
) -> tuple[datetime | None, datetime | None]:
    """Resolve the persisted forecast window, deriving an absent end when possible."""
    start = snapshot_datetime(snapshot.get("forecast_origin"))
    raw_end = snapshot.get("forecast_end")
    if raw_end is not None:
        end = snapshot_datetime(raw_end)
        return (start, end) if start is None or end is None or end > start else (start, None)

    target_count = positive_int(snapshot.get("target_count"), fallback_target_count)
    interval_hours = positive_int(snapshot.get("target_interval_hours"), 1)
    if start is None or target_count <= 0:
        return start, None
    return start, start + timedelta(hours=target_count * interval_hours)


def forecast_freshness_status(
    snapshot: dict[str, Any],
    *,
    fallback_target_count: int = 0,
    now: datetime | None = None,
) -> str:
    """Classify a forecast window while keeping corrupt metadata observable."""
    start, end = forecast_window(snapshot, fallback_target_count=fallback_target_count)
    if start is None or end is None:
        return "unknown"

    observed = as_utc(now or datetime.now(timezone.utc))
    if observed < start:
        return "future"
    if observed >= end:
        return "expired"
    return "partially_elapsed"


def format_forecast_timestamp(value: datetime | None, timezone_name: str) -> str:
    """Render a timestamp in the forecast's persisted presentation timezone."""
    if value is None:
        return "Not recorded"
    try:
        presentation_timezone = ZoneInfo(timezone_name)
    except (KeyError, ValueError):
        presentation_timezone = timezone.utc
    return as_utc(value).astimezone(presentation_timezone).isoformat()
