"""Privacy controls: portable export and irreversible self-service deletion."""
from __future__ import annotations

import json
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Site, Meter, SmartMeterReading, Forecast, Alert, Recommendation, EnergyBudget, RefreshToken
from app.schemas import AccountDeletionRequest
from app.services.auth_service import get_current_user, verify_password
from app.services.audit_service import record_audit_event
from app.config import get_settings

router = APIRouter(prefix="/api/v1/account", tags=["Account"])


def _jsonable(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


@router.get("/export")
def export_account(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return the account's owned data only; secrets and token hashes never leave the server."""
    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "user": {"id": current_user.id, "email": current_user.email, "full_name": current_user.full_name, "created_at": _jsonable(current_user.created_at), "preferences": current_user.preferences},
        "sites": [],
        "forecasts": [],
        "alerts": [],
        "recommendations": [],
        "budget": None,
    }
    for site in db.query(Site).filter(Site.user_id == current_user.id).all():
        meters = []
        for meter in db.query(Meter).filter(Meter.site_id == site.id).all():
            readings = [{"timestamp": _jsonable(r.timestamp), "active_power_kw": r.gap, "voltage_v": r.voltage, "source": r.source} for r in db.query(SmartMeterReading).filter(SmartMeterReading.meter_id == meter.id).order_by(SmartMeterReading.timestamp).all()]
            meters.append({"id": meter.id, "name": meter.name, "source_type": meter.source_type, "readings": readings})
        payload["sites"].append({"id": site.id, "name": site.name, "region": site.region, "timezone": site.timezone, "meters": meters})
    payload["forecasts"] = [{"id": x.id, "model_name": x.model_name, "predictions": x.predictions, "created_at": _jsonable(x.created_at)} for x in db.query(Forecast).filter(Forecast.user_id == current_user.id).all()]
    payload["alerts"] = [{"id": x.id, "type": x.alert_type, "severity": x.severity, "message": x.message, "created_at": _jsonable(x.created_at)} for x in db.query(Alert).filter(Alert.user_id == current_user.id).all()]
    payload["recommendations"] = [{"id": x.id, "title": x.title, "message": x.message, "status": x.status, "created_at": _jsonable(x.created_at)} for x in db.query(Recommendation).filter(Recommendation.user_id == current_user.id).all()]
    budget = db.query(EnergyBudget).filter(EnergyBudget.user_id == current_user.id).first()
    if budget:
        payload["budget"] = {"monthly_budget_mad": budget.monthly_budget_mad, "monthly_budget_kwh": budget.monthly_budget_kwh}
    return Response(json.dumps(payload, default=_jsonable), media_type="application/json", headers={"Content-Disposition": "attachment; filename=energyforecast-account-export.json"})


@router.delete("")
def delete_account(data: AccountDeletionRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.password_hash or not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    avatar = current_user.avatar_url
    record_audit_event(db, "account.deleted", actor_user_id=current_user.id, target_user_id=current_user.id, target=f"user:{current_user.id}")
    db.query(RefreshToken).filter(RefreshToken.user_id == current_user.id).delete()
    db.delete(current_user)
    db.commit()
    if avatar and avatar.startswith("/static/avatars/"):
        path = os.path.join(get_settings().AVATAR_STORAGE_DIR, os.path.basename(avatar))
        if os.path.isfile(path):
            os.remove(path)
    return {"message": "Account deleted"}
