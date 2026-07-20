"""Read-only live monitoring for committed push and simulation readings."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

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

        user = db.query(User).filter(User.id == user_id).one_or_none()
        if user is None or not user.is_active:
            await _close(websocket, "User is unavailable")
            return
        meter = get_primary_meter(db, user.id)
        if meter is None:
            await _close(websocket, "No primary meter is configured")
            return

        requested_cursor = auth_message.get("last_reading_id")
        try:
            cursor = max(0, int(requested_cursor or 0))
        except (TypeError, ValueError):
            await _close(websocket, "Invalid reading cursor")
            return
        latest = (
            db.query(SmartMeterReading)
            .filter(
                SmartMeterReading.meter_id == meter.id,
                SmartMeterReading.source.in_(LIVE_SOURCES),
            )
            .order_by(SmartMeterReading.id.desc())
            .first()
        )
        await websocket.send_json(
            {
                "type": "snapshot",
                "meter_id": meter.id,
                "expected_interval_seconds": meter.expected_interval_seconds,
                "reading": _reading_event(latest) if latest else None,
            }
        )
        if requested_cursor is None and latest is not None:
            cursor = latest.id

        while True:
            db.expire_all()
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
            for reading in rows:
                await websocket.send_json(
                    {"type": "reading", "reading": _reading_event(reading)}
                )
                cursor = reading.id
            await asyncio.sleep(1)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        return
    except Exception:
        try:
            await _close(websocket, "Live monitoring authentication or stream failed")
        except RuntimeError:
            return
