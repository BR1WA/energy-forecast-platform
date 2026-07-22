from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Alert, Forecast, SmartMeterReading, User
from app.services.auth_service import create_access_token, hash_password
from app.services.site_service import ensure_default_site, get_default_meter


def test_owned_report_summary_pdf_and_consumption_csv():
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
        owner = User(email="report-owner@example.com", password_hash=hash_password("password123"), role="user", is_active=True)
        other = User(email="report-other@example.com", password_hash=hash_password("password123"), role="user", is_active=True)
        db.add_all([owner, other])
        db.commit()
        site = ensure_default_site(db, owner.id)
        site.timezone = "UTC"
        other_site = ensure_default_site(db, other.id)
        meter = get_default_meter(db, owner.id)
        start = datetime(2026, 7, 2, 10, 0, tzinfo=timezone.utc)
        db.add_all(
            [
                SmartMeterReading(
                    meter_id=meter.id,
                    timestamp=start + timedelta(hours=index),
                    gap=2.0,
                    grp=0.0,
                    voltage=230.0,
                    intensity=8.7,
                    sub_metering_1=0.0,
                    sub_metering_2=0.0,
                    sub_metering_3=0.0,
                    source="csv",
                    quality="validated",
                )
                for index in range(3)
            ]
        )
        forecast = Forecast(
            user_id=owner.id,
            site_id=site.id,
            model_name="global_tft_24h",
            horizon=24,
            input_source="meter",
            input_start=start - timedelta(hours=336),
            input_end=start,
            predictions=[[1.5, 1.0, 2.0] for _ in range(24)],
            confidence_method="Native model quantiles; not calibrated for this site.",
            input_snapshot={
                "method": "global_tft",
                "model_version": "1.0.0",
                "forecast_origin": start.isoformat(),
                "timezone": "UTC",
                "sources": ["csv"],
                "coverage_percent": 100,
            },
        )
        other_forecast = Forecast(
            user_id=other.id,
            site_id=other_site.id,
            model_name="global_tft_24h",
            horizon=24,
            predictions=[[9.0, 8.0, 10.0] for _ in range(24)],
            input_snapshot={"method": "global_tft", "forecast_origin": start.isoformat()},
        )
        db.add_all(
            [
                forecast,
                other_forecast,
                Alert(user_id=owner.id, site_id=site.id, alert_type="high_consumption", severity="high", message="Open"),
                Alert(user_id=owner.id, site_id=site.id, alert_type="missing_data", severity="high", message="Closed", resolved_at=start),
            ]
        )
        db.commit()
        owner_headers = {"Authorization": f"Bearer {create_access_token({'sub': str(owner.id)})}"}
        other_headers = {"Authorization": f"Bearer {create_access_token({'sub': str(other.id)})}"}
        client = TestClient(app)

        summary = client.get("/api/v1/analytics/summary", headers=owner_headers)
        assert summary.status_code == 200
        payload = summary.json()
        assert payload["total_forecasts"] == 1
        assert payload["open_alerts"] == 1
        assert payload["resolved_alerts"] == 1
        assert payload["recent_forecasts"][0]["total_kwh"] == 36.0
        assert payload["recent_forecasts"][0]["peak_hourly_kwh"] == 1.5

        pdf = client.get(f"/api/v1/analytics/report/pdf?forecast_id={forecast.id}", headers=owner_headers)
        assert pdf.status_code == 200
        assert pdf.headers["content-type"] == "application/pdf"
        assert pdf.content.startswith(b"%PDF")
        assert "energy_forecast_" in pdf.headers["content-disposition"]
        assert client.get(f"/api/v1/analytics/report/pdf?forecast_id={forecast.id}", headers=other_headers).status_code == 404

        csv_response = client.get("/api/v1/consumption/export?month=2026-07", headers=owner_headers)
        assert csv_response.status_code == 200
        csv_text = csv_response.text
        assert "site,Default site" in csv_text
        assert "timezone,UTC" in csv_text
        assert "sources,csv" in csv_text
        assert "date,energy_kwh,estimated_cost,currency" in csv_text
        assert "report-other@example.com" not in csv_text
    finally:
        db.close()
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
