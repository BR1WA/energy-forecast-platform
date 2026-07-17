from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Meter, Site, SmartMeterReading, User
from app.services.auth_service import get_current_user

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
        data.append({
            "id": str(site.id),
            "name": site.name,
            "meterId": meter.external_id if meter and meter.external_id else (str(meter.id) if meter else None),
            "status": meter.status.title() if meter else "No meter",
            "load": latest.gap if latest else 0.0,
            "dailyConsumption": 0.0,
            "peakPower": latest.gap if latest else 0.0,
            "monthlyCost": 0.0,
            "circuits": [],
        })
    return {"data": data}
