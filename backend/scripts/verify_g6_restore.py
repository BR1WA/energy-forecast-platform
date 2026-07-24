"""Seed or verify the isolated Product V1 database/avatar restore fixture."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from PIL import Image
from sqlalchemy.orm import Session

from app.database import engine
from app.models import EmailOutbox, Forecast, Meter, Site, SmartMeterReading, User
from app.services.auth_service import hash_password
from app.services.site_service import ensure_default_site, get_default_meter


EMAIL = "g6-restore-fixture@example.test"
OBJECT_KEY = os.environ.get(
    "VERIFY_G6_OBJECT_KEY",
    f"{hashlib.sha256(b'g6-verification-object').hexdigest()[:32]}.webp",
)
FINGERPRINT = "g6-restore-forecast-fingerprint"  # gitleaks:allow - deterministic non-secret test marker


def avatar_path() -> Path:
    root = Path(os.environ["AVATAR_STORAGE_DIR"]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root / OBJECT_KEY


def seed() -> None:
    with Session(engine) as db:
        existing = db.query(User).filter(User.email == EMAIL).one_or_none()
        if existing is not None:
            db.delete(existing)
            db.commit()
        user = User(
            email=EMAIL,
            password_hash=hash_password("restore-fixture-password"),
            role="user",
            is_active=True,
            avatar_url=f"/static/avatars/{OBJECT_KEY}",
        )
        db.add(user)
        db.flush()
        site = ensure_default_site(db, user.id)
        meter = get_default_meter(db, user.id)
        db.add(SmartMeterReading(
            meter_id=meter.id,
            gap=1.25,
            grp=.1,
            voltage=230,
            intensity=5,
            sub_metering_1=0,
            sub_metering_2=0,
            sub_metering_3=0,
            source="push",
            quality="validated",
        ))
        db.add(Forecast(
            user_id=user.id,
            site_id=site.id,
            model_name="global_tft_24h",
            horizon=24,
            predictions=[[1.0, .8, 1.2]] * 24,
            input_snapshot={"artifact_fingerprint": FINGERPRINT},
        ))
        db.add(EmailOutbox(
            id=str(uuid.uuid4()),
            user_id=user.id,
            recipient=user.email,
            template="critical_alert",
            payload={"alert_id": 1},
            dedup_key="g6-restore-outbox",
            status="dead",
            attempts=5,
        ))
        db.commit()
    Image.new("RGB", (24, 24), (18, 110, 130)).save(avatar_path(), format="WEBP")
    print(json.dumps(verify()))


def verify() -> dict:
    with Session(engine) as db:
        user = db.query(User).filter(User.email == EMAIL).one()
        site = db.query(Site).filter(Site.user_id == user.id).one()
        meter = db.query(Meter).filter(Meter.site_id == site.id, Meter.is_primary.is_(True)).one()
        forecast = db.query(Forecast).filter(Forecast.user_id == user.id).one()
        outbox = db.query(EmailOutbox).filter(EmailOutbox.user_id == user.id).one()
        path = avatar_path()
        result = {
            "users": db.query(User).filter(User.email == EMAIL).count(),
            "owned_sites": 1 if site.user_id == user.id else 0,
            "owned_readings": db.query(SmartMeterReading).filter(SmartMeterReading.meter_id == meter.id).count(),
            "owned_forecasts": db.query(Forecast).filter(Forecast.user_id == user.id).count(),
            "forecast_fingerprint": (forecast.input_snapshot or {}).get("artifact_fingerprint"),
            "outbox_status": outbox.status,
            "avatar_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "avatar_decodes": False,
        }
        with Image.open(path) as image:
            image.verify()
            result["avatar_decodes"] = True
        assert result["users"] == 1
        assert result["owned_sites"] == 1
        assert result["owned_readings"] == 1
        assert result["owned_forecasts"] == 1
        assert result["forecast_fingerprint"] == FINGERPRINT
        assert result["outbox_status"] == "dead"
        assert result["avatar_decodes"] is True
        return result


if __name__ == "__main__":
    if engine.dialect.name != "postgresql":
        raise SystemExit("Restore verification requires PostgreSQL")
    command = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if command == "seed":
        seed()
    elif command == "verify":
        print(json.dumps(verify()))
    else:
        raise SystemExit("Usage: verify_g6_restore.py [seed|verify]")
