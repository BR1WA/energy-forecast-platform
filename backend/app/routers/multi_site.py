from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from app.database import get_db
from datetime import datetime, timezone

from app.models import Meter, Site, SmartMeterReading, User
from app.services.auth_service import get_current_user
from app.services.consumption_service import consumption_service

router = APIRouter(prefix="/api/v1/multi-site", tags=["multi-site"])


@router.get("")
def get_multi_site_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return only the authenticated user's sites and meter summaries."""
    sites = db.query(Site).filter(Site.user_id == current_user.id).order_by(Site.id).all()
    data = []
    for site in sites:
        meter = db.query(Meter).filter(Meter.site_id == site.id).order_by(Meter.id).first()
        latest = (
            db.query(SmartMeterReading)
            .join(Meter, SmartMeterReading.meter_id == Meter.id)
            .filter(Meter.site_id == site.id)
            .order_by(SmartMeterReading.timestamp.desc())
            .first()
        )
        summary = consumption_service.get_monthly_summary(db, current_user.id, site_id=site.id)
        try:
            site_date = datetime.now(ZoneInfo(site.timezone)).date().isoformat()
        except Exception:
            site_date = datetime.now(timezone.utc).date().isoformat()
        today = next((day["kwh"] for day in summary["daily"] if day["date"] == site_date), 0.0)
        latest_at = latest.timestamp.replace(tzinfo=timezone.utc) if latest and latest.timestamp.tzinfo is None else (latest.timestamp if latest else None)
        age_seconds = int((datetime.now(timezone.utc) - latest_at).total_seconds()) if latest_at else None
        data.append({
            "id": str(site.id),
            "name": site.name,
            "meterId": meter.external_id if meter and meter.external_id else (str(meter.id) if meter else None),
            "status": meter.status.title() if meter else "No meter",
            "load": latest.gap if latest else 0.0,
            "dailyConsumption": today,
            "peakPower": summary["peak_kw"],
            "monthlyCost": summary["total_cost"],
            "currency": summary["tariff"].get("currency", "MAD"),
            "source": latest.source if latest else None,
            "lastSeenAt": latest_at.isoformat() if latest_at else None,
            "ageSeconds": max(0, age_seconds) if age_seconds is not None else None,
        })
    return {"data": data}
