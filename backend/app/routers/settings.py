from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Literal
from app.database import get_db
from app.models import EnergyBudget, Site, SiteSettings, User
from app.services.auth_service import get_current_user
from app.services.site_service import ensure_default_site
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

MOROCCO_COUNTRY = "Morocco"
MOROCCO_CURRENCY = "MAD"
MOROCCO_TIMEZONE = "Africa/Casablanca"
MoroccoRegion = Literal[
    "Tanger-Tétouan-Al Hoceïma",
    "Oriental",
    "Fès-Meknès",
    "Rabat-Salé-Kénitra",
    "Béni Mellal-Khénifra",
    "Casablanca-Settat",
    "Marrakech-Safi",
    "Drâa-Tafilalet",
    "Souss-Massa",
    "Guelmim-Oued Noun",
    "Laâyoune-Sakia El Hamra",
    "Dakhla-Oued Ed-Dahab",
]


class SetupPayload(BaseModel):
    model_config = {"extra": "forbid"}

    site_name: str | None = Field(default=None, min_length=1, max_length=120)
    region: MoroccoRegion
    peak_rate: float = Field(ge=0, le=100)
    off_peak_rate: float = Field(ge=0, le=100)
    peak_start_hour: int = Field(ge=0, le=23)
    peak_end_hour: int = Field(ge=0, le=23)
    sensor_type: Literal["csv", "push", "simulator"]

class PreferencesPayload(BaseModel):
    model_config = {"extra": "forbid"}

    theme: Literal["light", "dark", "system"] | None = None
    language: Literal["en", "fr", "ar"] | None = None

class BudgetPayload(BaseModel):
    monthly_budget_mad: float = Field(ge=0, le=10_000_000)
    monthly_budget_kwh: float | None = Field(default=None, ge=0, le=10_000_000)

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
    site = ensure_default_site(db, current_user.id)
    settings = db.query(SiteSettings).filter(SiteSettings.site_id == site.id).first()
    if not settings:
        return {
            "country": MOROCCO_COUNTRY,
            "region": "Casablanca-Settat",
            "electricity_provider": None,
            "currency": MOROCCO_CURRENCY,
            "peak_rate": 1.1,
            "off_peak_rate": 0.8,
            "peak_start_hour": 6,
            "peak_end_hour": 22,
            "sensor_type": "simulator",
        }
    return settings

@router.post("/setup")
def save_setup(
    payload: SetupPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    site = ensure_default_site(db, current_user.id)
    if payload.site_name is not None:
        site.name = payload.site_name.strip() or "Default site"
    site.region = payload.region
    site.timezone = MOROCCO_TIMEZONE
    settings = db.query(SiteSettings).filter(SiteSettings.site_id == site.id).first()
    if not settings:
        settings = SiteSettings(site_id=site.id)
        db.add(settings)

    settings.country = MOROCCO_COUNTRY
    settings.region = payload.region
    settings.electricity_provider = None
    settings.currency = MOROCCO_CURRENCY
    settings.peak_rate = payload.peak_rate
    settings.off_peak_rate = payload.off_peak_rate
    settings.peak_start_hour = payload.peak_start_hour
    settings.peak_end_hour = payload.peak_end_hour
    settings.sensor_type = payload.sensor_type
    
    # Also update the user's specific setup complete status
    current_user.is_setup_complete = True
    record_audit_event(
        db,
        "settings.site_updated",
        actor_user_id=current_user.id,
        site_id=site.id,
        target=f"site:{site.id}",
        metadata={"currency": settings.currency, "peak_rate": settings.peak_rate, "off_peak_rate": settings.off_peak_rate},
    )
    
    db.commit()
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
    site = ensure_default_site(db, current_user.id)
    budget = db.query(EnergyBudget).filter(EnergyBudget.user_id == current_user.id).first()
    if not budget:
        budget = EnergyBudget(user_id=current_user.id, site_id=site.id)
        db.add(budget)
    elif budget.site_id is None:
        budget.site_id = site.id
    
    budget.monthly_budget_mad = payload.monthly_budget_mad
    budget.monthly_budget_kwh = payload.monthly_budget_kwh
    record_audit_event(
        db,
        "budget.updated",
        actor_user_id=current_user.id,
        site_id=site.id,
        target=f"budget:{budget.id or 'new'}",
        metadata=payload.model_dump(),
    )
    
    db.commit()
    db.refresh(budget)
    return budget
