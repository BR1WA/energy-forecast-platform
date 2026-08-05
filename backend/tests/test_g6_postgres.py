"""G6 ownership and cascade checks that require the production database engine."""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import json
import os
import uuid
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import engine
from app.main import app
from app.models import Forecast, SmartMeterReading, User
from app.services.auth_service import create_access_token, hash_password
from app.services.site_service import ensure_default_site, get_default_meter


pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL", "").startswith("postgresql"),
    reason="G6 cascade and ownership verification requires PostgreSQL",
)


def headers(user_id: int) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {create_access_token({'sub': str(user_id)})}",
        "Origin": "http://localhost:3000",
    }


def test_postgres_account_export_isolation_and_irreversible_cascade():
    marker = uuid.uuid4().hex
    client = TestClient(app)
    with Session(engine) as db:
        owner = User(
            email=f"g6-owner-{marker}@example.test",
            password_hash=hash_password("recent-password"),
            role="user",
            is_active=True,
            email_verified_at=datetime.now(timezone.utc),
        )
        other = User(
            email=f"g6-other-{marker}@example.test",
            password_hash=hash_password("recent-password"),
            role="user",
            is_active=True,
        )
        db.add_all([owner, other])
        db.flush()
        owner_id, other_id = owner.id, other.id
        owner_site = ensure_default_site(db, owner_id)
        other_site = ensure_default_site(db, other_id)
        owner_meter = get_default_meter(db, owner_id)
        db.add(SmartMeterReading(
            meter_id=owner_meter.id,
            timestamp=datetime.now(timezone.utc),
            gap=1.5,
            grp=0.1,
            voltage=230,
            intensity=6,
            sub_metering_1=0,
            sub_metering_2=0,
            sub_metering_3=0,
            source="push",
            quality="validated",
        ))
        db.add_all([
            Forecast(user_id=owner_id, site_id=owner_site.id, model_name="global_tft_24h", horizon=24, predictions=[[1, .8, 1.2]] * 24),
            Forecast(user_id=other_id, site_id=other_site.id, model_name="global_tft_24h", horizon=24, predictions=[[9, 8, 10]] * 24),
        ])
        db.commit()

        exported = client.get("/api/v1/account/export", headers=headers(owner_id))
        assert exported.status_code == 200
        with zipfile.ZipFile(BytesIO(exported.content)) as archive:
            archive_text = "\n".join(
                archive.read(name).decode("utf-8")
                for name in archive.namelist()
                if name.endswith((".json", ".ndjson", ".txt"))
            )
            manifest = json.loads(archive.read("manifest.json"))
        assert owner.email in archive_text
        assert other.email not in archive_text
        assert manifest["counts"]["readings"] == 1
        assert manifest["counts"]["forecasts"] == 1
        assert "password_hash" not in archive_text

        deleted = client.request(
            "DELETE",
            "/api/v1/account",
            headers=headers(owner_id),
            json={"confirmation": "DELETE", "current_password": "recent-password"},
        )
        assert deleted.status_code == 200
        db.expire_all()
        assert db.get(User, owner_id) is None
        assert db.get(User, other_id) is not None
        assert db.query(Forecast).filter(Forecast.user_id == owner_id).count() == 0
        assert db.query(Forecast).filter(Forecast.user_id == other_id).count() == 1

        db.delete(db.get(User, other_id))
        db.commit()
