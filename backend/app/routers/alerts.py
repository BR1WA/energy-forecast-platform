"""
Alerts router — alert management and configuration.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import User, Alert, AlertConfig
from app.schemas import AlertResponse, AlertConfigCreate, AlertConfigResponse, AlertAcknowledge
from app.services.auth_service import get_current_user
from app.services.alert_service import alert_service
from app.services.audit_service import record_audit_event
from app.services.site_service import ensure_default_site

router = APIRouter(prefix="/api/v1/alerts", tags=["Alerts"])


@router.get("/", response_model=List[AlertResponse])
def list_alerts(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List alerts for the current user."""
    alerts = (
        db.query(Alert)
        .filter(Alert.user_id == current_user.id)
        .order_by(Alert.created_at.desc())
        .limit(limit)
        .all()
    )
    return [AlertResponse.model_validate(a) for a in alerts]


@router.get("/unacknowledged", response_model=List[AlertResponse])
def list_unacknowledged(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List unacknowledged alerts."""
    alerts = (
        db.query(Alert)
        .filter(Alert.user_id == current_user.id, Alert.is_acknowledged == False)
        .order_by(Alert.created_at.desc())
        .all()
    )
    return [AlertResponse.model_validate(a) for a in alerts]


@router.post("/acknowledge")
def acknowledge_alert(
    data: AlertAcknowledge,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Acknowledge an alert."""
    alert = db.query(Alert).filter(
        Alert.id == data.alert_id,
        Alert.user_id == current_user.id
    ).first()

    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    alert.is_acknowledged = True
    alert.acknowledged_at = datetime.now(timezone.utc)
    record_audit_event(
        db,
        "alert.acknowledged",
        actor_user_id=current_user.id,
        site_id=alert.site_id,
        target=f"alert:{alert.id}",
        metadata={"alert_type": alert.alert_type, "rule_key": alert.rule_key},
    )
    db.commit()
    return {"message": "Alert acknowledged", "alert_id": data.alert_id}


@router.get("/config", response_model=AlertConfigResponse)
def get_alert_config(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the user's alert configuration."""
    site = ensure_default_site(db, current_user.id)
    config = alert_service.config_for_site(db, site)
    db.commit()
    db.refresh(config)
    return AlertConfigResponse.model_validate(config)


@router.post("/config", response_model=AlertConfigResponse)
def update_alert_config(
    data: AlertConfigCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update alert threshold configuration."""
    site = ensure_default_site(db, current_user.id)
    config = alert_service.config_for_site(db, site)
    config.threshold_kw = data.threshold_kw
    config.cooldown_minutes = data.cooldown_minutes
    config.missing_data_minutes = data.missing_data_minutes
    config.email_enabled = data.email_enabled
    record_audit_event(
        db,
        "alert.config_updated",
        actor_user_id=current_user.id,
        site_id=site.id,
        target=f"alert-config:{config.id or 'new'}",
        metadata=data.model_dump(),
    )

    db.commit()
    db.refresh(config)
    return AlertConfigResponse.model_validate(config)

