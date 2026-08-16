"""Read-only live monitoring for committed push and simulation readings."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_db
from app.models import Meter, Site, SmartMeterReading, User
from app.services.auth_service import decode_token
from app.services.site_service import get_primary_meter


router = APIRouter(prefix="/api/v1/monitoring", tags=["Monitoring"])
LIVE_SOURCES = ("push", "simulation")


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _reading_event(reading: SmartMeterReading) -> dict:
    return {
        "reading_id": reading.id,
        "timestamp": _as_utc(reading.timestamp).isoformat(),
        "active_power_kw": reading.gap,
        "voltage_v": reading.voltage,
        "current_a": reading.intensity,
        "source": reading.source,
        "quality": reading.quality,
    }


def _load_snapshot(session_factory: sessionmaker, user_id: int) -> dict:
    """Load one owned snapshot in a short-lived synchronous session."""
    with session_factory() as db:
        user = db.query(User).filter(User.id == user_id).one_or_none()
        if user is None or not user.is_active:
            raise PermissionError("User is unavailable")
        meter = get_primary_meter(db, user.id)
        if meter is None:
            raise PermissionError("No primary meter is configured")
        latest = (
            db.query(SmartMeterReading)
            .filter(
                SmartMeterReading.meter_id == meter.id,
                SmartMeterReading.source.in_(LIVE_SOURCES),
            )
            .order_by(SmartMeterReading.id.desc())
            .first()
        )
        return {
            "meter_id": meter.id,
            "expected_interval_seconds": meter.expected_interval_seconds,
            "reading": _reading_event(latest) if latest else None,
        }


def _load_readings(session_factory: sessionmaker, user_id: int, cursor: int) -> list[dict]:
    """Fetch a bounded page without holding a connection between polls."""
    with session_factory() as db:
        rows = (
            db.query(SmartMeterReading)
            .join(Meter, SmartMeterReading.meter_id == Meter.id)
            .join(Site, Meter.site_id == Site.id)
            .filter(
                Site.user_id == user_id,
                Meter.is_primary.is_(True),
                SmartMeterReading.id > cursor,
                SmartMeterReading.source.in_(LIVE_SOURCES),
            )
            .order_by(SmartMeterReading.id.asc())
            .limit(100)
            .all()
        )
        return [_reading_event(reading) for reading in rows]


async def _close(websocket: WebSocket, reason: str) -> None:
    await websocket.close(code=1008, reason=reason)


@router.websocket("/live")
async def live_monitoring(
    websocket: WebSocket,
    db: Session = Depends(get_db),
):
    """Stream committed live-source rows without creating or modifying data."""
    await websocket.accept()
    try:
        auth_message = await asyncio.wait_for(websocket.receive_json(), timeout=10)
        token = auth_message.get("access_token")
        payload = decode_token(token) if token else {}
        if payload.get("type") != "access" or not payload.get("sub"):
            await _close(websocket, "Invalid access token")
            return

        try:
            user_id = int(payload["sub"])
        except (TypeError, ValueError):
            await _close(websocket, "Invalid access token")
            return

        # Preserve dependency overrides (notably isolated test databases), then
        # release the request-scoped session before the long-lived socket loop.
        session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=db.get_bind(),
        )
        db.close()

        requested_cursor = auth_message.get("last_reading_id")
        try:
            cursor = max(0, int(requested_cursor or 0))
        except (TypeError, ValueError):
            await _close(websocket, "Invalid reading cursor")
            return
        try:
            snapshot = await asyncio.to_thread(_load_snapshot, session_factory, user_id)
        except PermissionError as exc:
            await _close(websocket, str(exc))
            return
        await websocket.send_json(
            {
                "type": "snapshot",
                **snapshot,
            }
        )
        if requested_cursor is None and snapshot["reading"] is not None:
            cursor = snapshot["reading"]["reading_id"]

        while True:
            rows = await asyncio.to_thread(
                _load_readings,
                session_factory,
                user_id,
                cursor,
            )
            for reading in rows:
                await websocket.send_json(
                    {"type": "reading", "reading": reading}
                )
                cursor = reading["reading_id"]
            await asyncio.sleep(1)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        return
    except Exception:
        try:
            await _close(websocket, "Live monitoring authentication or stream failed")
        except RuntimeError:
            return
