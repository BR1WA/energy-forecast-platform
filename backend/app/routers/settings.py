from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models.settings import SystemSettings

router = APIRouter(prefix="/settings", tags=["settings"])

class SetupPayload(BaseModel):
    country: str
    region: str
    electricity_provider: str
    currency: str
    peak_rate: float
    off_peak_rate: float
    peak_start_hour: int
    peak_end_hour: int
    sensor_type: str
    sensor_api_url: str | None = None

@router.get("/setup-status")
def get_setup_status(db: Session = Depends(get_db)):
    settings = db.query(SystemSettings).first()
    if not settings:
        return {"is_setup_complete": False}
    return {"is_setup_complete": settings.is_setup_complete}

@router.get("")
def get_settings(db: Session = Depends(get_db)):
    settings = db.query(SystemSettings).first()
    if not settings:
        # Return default if not setup
        return {
            "country": "Morocco",
            "region": "Casablanca-Settat",
            "electricity_provider": "Lydec",
            "currency": "MAD",
            "peak_rate": 1.1,
            "off_peak_rate": 0.8,
            "peak_start_hour": 6,
            "peak_end_hour": 22,
            "sensor_type": "simulator",
            "sensor_api_url": None
        }
    return settings

@router.post("/setup")
def save_setup(payload: SetupPayload, db: Session = Depends(get_db)):
    settings = db.query(SystemSettings).first()
    if not settings:
        settings = SystemSettings()
        db.add(settings)
    
    settings.is_setup_complete = True
    settings.country = payload.country
    settings.region = payload.region
    settings.electricity_provider = payload.electricity_provider
    settings.currency = payload.currency
    settings.peak_rate = payload.peak_rate
    settings.off_peak_rate = payload.off_peak_rate
    settings.peak_start_hour = payload.peak_start_hour
    settings.peak_end_hour = payload.peak_end_hour
    settings.sensor_type = payload.sensor_type
    settings.sensor_api_url = payload.sensor_api_url
    
    db.commit()
    db.refresh(settings)
    return {"message": "Setup completed successfully", "settings": settings}
