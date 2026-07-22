from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Alert, User
from app.services.auth_service import create_access_token, hash_password
from app.services.site_service import ensure_default_site


def test_alert_lifecycle_filters_and_ownership():
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
        owner = User(email="alert-owner@example.com", password_hash=hash_password("password123"), role="user", is_active=True)
        other = User(email="alert-other@example.com", password_hash=hash_password("password123"), role="user", is_active=True)
        db.add_all([owner, other])
        db.commit()
        site = ensure_default_site(db, owner.id)
        ensure_default_site(db, other.id)
        alert = Alert(
            user_id=owner.id,
            site_id=site.id,
            alert_type="high_consumption",
            rule_key="high_load:test",
            severity="high",
            message="Measured evidence",
            evidence_json={"observed_kw": 4.0, "threshold_kw": 3.0},
            created_at=datetime.now(timezone.utc),
        )
        db.add(alert)
        db.commit()
        owner_headers = {"Authorization": f"Bearer {create_access_token({'sub': str(owner.id)})}"}
        other_headers = {"Authorization": f"Bearer {create_access_token({'sub': str(other.id)})}"}
        client = TestClient(app)

        listed = client.get("/api/v1/alerts?state=open", headers=owner_headers)
        assert listed.status_code == 200
        assert listed.json()[0]["state"] == "open"
        alert_id = listed.json()[0]["id"]
        assert client.get("/api/v1/alerts", headers=other_headers).json() == []
        assert client.patch(f"/api/v1/alerts/{alert_id}/resolve", headers=other_headers).status_code == 404

        acknowledged = client.patch(f"/api/v1/alerts/{alert_id}/acknowledge", headers=owner_headers)
        assert acknowledged.status_code == 200
        assert acknowledged.json()["state"] == "acknowledged"
        assert client.get("/api/v1/alerts?state=open", headers=owner_headers).json() == []

        resolved = client.patch(f"/api/v1/alerts/{alert_id}/resolve", headers=owner_headers)
        assert resolved.json()["state"] == "resolved"
        assert len(client.get("/api/v1/alerts?state=resolved", headers=owner_headers).json()) == 1
        assert client.get("/api/v1/alerts/unacknowledged", headers=owner_headers).json() == []

        reopened = client.patch(f"/api/v1/alerts/{alert_id}/reopen", headers=owner_headers)
        assert reopened.json()["state"] == "open"
        assert reopened.json()["is_acknowledged"] is False

        config = client.get("/api/v1/alerts/config", headers=owner_headers)
        assert config.status_code == 200
        assert config.json()["email_enabled"] is False
    finally:
        db.close()
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
