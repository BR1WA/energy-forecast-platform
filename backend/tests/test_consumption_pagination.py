from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import SmartMeterReading, User
from app.services.auth_service import create_access_token, hash_password
from app.services.site_service import ensure_default_site, get_default_meter


def test_raw_reading_keyset_pagination_is_owned_and_bounded():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    db = Session()
    try:
        owner = User(email="pages-owner@example.com", password_hash=hash_password("password123"), role="user", is_active=True)
        other = User(email="pages-other@example.com", password_hash=hash_password("password123"), role="user", is_active=True)
        db.add_all([owner, other])
        db.commit()
        owner_site = ensure_default_site(db, owner.id)
        owner_site.timezone = "UTC"
        other_site = ensure_default_site(db, other.id)
        other_site.timezone = "UTC"
        owner_meter = get_default_meter(db, owner.id)
        other_meter = get_default_meter(db, other.id)
        start = datetime.now(timezone.utc) - timedelta(hours=1)

        def reading(meter_id: int, index: int, power: float):
            return SmartMeterReading(
                meter_id=meter_id,
                timestamp=start + timedelta(minutes=index),
                gap=power,
                grp=0.0,
                voltage=230.0,
                intensity=power * 1000 / 230,
                sub_metering_1=0.0,
                sub_metering_2=0.0,
                sub_metering_3=0.0,
                source="push",
                quality="validated",
            )

        db.add_all([reading(owner_meter.id, index, 1.0 + index) for index in range(5)])
        db.add(reading(other_meter.id, 10, 99.0))
        db.commit()
        headers = {"Authorization": f"Bearer {create_access_token({'sub': str(owner.id)})}"}
        client = TestClient(app)

        first = client.get("/api/v1/consumption/readings?timeframe=today&limit=2", headers=headers)
        assert first.status_code == 200
        first_payload = first.json()
        assert [item["active_power_kw"] for item in first_payload["items"]] == [5.0, 4.0]
        assert first_payload["next_cursor"]

        second = client.get(
            "/api/v1/consumption/readings",
            params={"timeframe": "today", "limit": 2, "cursor": first_payload["next_cursor"]},
            headers=headers,
        )
        assert second.status_code == 200
        assert [item["active_power_kw"] for item in second.json()["items"]] == [3.0, 2.0]
        assert all(item["active_power_kw"] != 99.0 for item in first_payload["items"] + second.json()["items"])
        assert client.get("/api/v1/consumption/readings?limit=201", headers=headers).status_code == 400
        assert client.get("/api/v1/consumption/readings?cursor=not-valid", headers=headers).status_code == 400
    finally:
        db.close()
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
