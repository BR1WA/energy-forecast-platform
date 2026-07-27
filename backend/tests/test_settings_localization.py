from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Site, SiteSettings, User
from app.services.auth_service import create_access_token, hash_password


def test_setup_enforces_morocco_mad_and_region_options():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        session = testing_session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    db = testing_session()
    try:
        user = User(
            email="morocco-settings@example.com",
            password_hash=hash_password("password123"),
            role="user",
            is_active=True,
        )
        db.add(user)
        db.commit()
        headers = {
            "Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"
        }
        client = TestClient(app)
        payload = {
            "site_name": "Rabat office",
            "region": "Rabat-Salé-Kénitra",
            "peak_rate": 1.1,
            "off_peak_rate": 0.8,
            "peak_start_hour": 6,
            "peak_end_hour": 22,
            "sensor_type": "csv",
        }

        response = client.post(
            "/api/v1/settings/setup",
            headers=headers,
            json=payload,
        )
        assert response.status_code == 200

        db.expire_all()
        site = db.query(Site).filter(Site.user_id == user.id).one()
        settings = (
            db.query(SiteSettings)
            .filter(SiteSettings.site_id == site.id)
            .one()
        )
        assert site.name == "Rabat office"
        assert site.region == "Rabat-Salé-Kénitra"
        assert site.timezone == "Africa/Casablanca"
        assert settings.country == "Morocco"
        assert settings.region == "Rabat-Salé-Kénitra"
        assert settings.currency == "MAD"
        assert settings.electricity_provider is None

        invalid_region = client.post(
            "/api/v1/settings/setup",
            headers=headers,
            json={**payload, "region": "Free-form region"},
        )
        assert invalid_region.status_code == 422

        irrelevant_fields = client.post(
            "/api/v1/settings/setup",
            headers=headers,
            json={
                **payload,
                "country": "France",
                "currency": "EUR",
                "electricity_provider": "Example provider",
            },
        )
        assert irrelevant_fields.status_code == 422
    finally:
        db.close()
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
