from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models.settings import SystemSettings
from app.models.models import User, EnergyBudget
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

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

class PreferencesPayload(BaseModel):
    theme: str | None = None
    language: str | None = None
    email_alerts: bool | None = None
    push_alerts: bool | None = None
    default_model_24: str | None = None
    default_model_168: str | None = None
    default_model_720: str | None = None

class BudgetPayload(BaseModel):
    monthly_budget_mad: float
    monthly_budget_kwh: float | None = None

@router.get("/setup-status")
def get_setup_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return {"is_setup_complete": current_user.is_setup_complete}

@router.get("")
def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    settings = db.query(SystemSettings).first()
    if not settings:
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
def save_setup(
    payload: SetupPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    settings = db.query(SystemSettings).first()
    settings_created_or_updated = False
    
    if not settings:
        settings = SystemSettings()
        db.add(settings)
        settings_created_or_updated = True
    elif current_user.role == "admin":
        settings_created_or_updated = True
        
    if settings_created_or_updated:
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
    
    # Also update the user's specific setup complete status
    current_user.is_setup_complete = True
    
    db.commit()
    if settings_created_or_updated:
        db.refresh(settings)
    else:
        settings = db.query(SystemSettings).first()
        
    db.refresh(current_user)
    return {"message": "Setup completed successfully", "settings": settings}

@router.put("/preferences")
def update_preferences(
    payload: PreferencesPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.preferences is None:
        current_user.preferences = {}
        
    prefs = dict(current_user.preferences)
    if payload.theme is not None:
        prefs["theme"] = payload.theme
    if payload.language is not None:
        prefs["language"] = payload.language
    if payload.email_alerts is not None:
        prefs["email_alerts"] = payload.email_alerts
    if payload.push_alerts is not None:
        prefs["push_alerts"] = payload.push_alerts
    if payload.default_model_24 is not None:
        prefs["default_model_24"] = payload.default_model_24
    if payload.default_model_168 is not None:
        prefs["default_model_168"] = payload.default_model_168
    if payload.default_model_720 is not None:
        prefs["default_model_720"] = payload.default_model_720
        
    current_user.preferences = prefs
    db.commit()
    db.refresh(current_user)
    return {"message": "Preferences updated successfully", "preferences": current_user.preferences}

@router.get("/budget")
def get_budget(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    budget = db.query(EnergyBudget).filter(EnergyBudget.user_id == current_user.id).first()
    if not budget:
        return None
    return budget

@router.put("/budget")
def update_budget(
    payload: BudgetPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    budget = db.query(EnergyBudget).filter(EnergyBudget.user_id == current_user.id).first()
    if not budget:
        budget = EnergyBudget(user_id=current_user.id)
        db.add(budget)
    
    budget.monthly_budget_mad = payload.monthly_budget_mad
    budget.monthly_budget_kwh = payload.monthly_budget_kwh
    
    db.commit()
    db.refresh(budget)
    return budget
