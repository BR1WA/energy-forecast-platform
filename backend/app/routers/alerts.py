"""Owned in-app alert rules and lifecycle actions."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Alert, AlertConfig, User
from app.schemas import AlertConfigCreate, AlertConfigResponse, AlertResponse
from app.services.alert_service import alert_service, critical_email_delivery_status
from app.services.audit_service import record_audit_event
from app.services.auth_service import get_current_user
from app.services.site_service import ensure_default_site
from app.services.worker_health_service import worker_status


router = APIRouter(prefix="/api/v1/alerts", tags=["Alerts"])


def _email_delivery_status(db: Session, current_user: User) -> tuple[bool, str | None]:
    available, reason = critical_email_delivery_status(current_user)
    if available and not worker_status(db, "email")["operational"]:
        return False, "email_worker_unavailable"
    return available, reason


def _config_response(db: Session, config: AlertConfig, current_user: User) -> AlertConfigResponse:
    available, reason = _email_delivery_status(db, current_user)
    alerts_worker = worker_status(db, "alerts")
    return AlertConfigResponse(
        id=config.id,
        threshold_kw=config.threshold_kw,
        cooldown_minutes=config.cooldown_minutes,
        missing_data_minutes=config.missing_data_minutes,
        email_enabled=bool(config.email_enabled),
        email_delivery_available=available,
        email_delivery_unavailable_reason=reason,
        missing_data_monitoring_available=alerts_worker["operational"],
        missing_data_monitoring_last_success_at=alerts_worker["last_success_at"],
        created_at=config.created_at,
    )


def _state(alert: Alert) -> str:
    if alert.resolved_at is not None:
        return "resolved"
    if alert.is_acknowledged:
        return "acknowledged"
    return "open"


def _serialize(alert: Alert) -> dict:
    return {
        "id": alert.id,
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "message": alert.message,
        "peak_kw": alert.peak_kw,
        "evidence_json": alert.evidence_json,
        "state": _state(alert),
        "is_acknowledged": alert.is_acknowledged,
        "acknowledged_at": alert.acknowledged_at,
        "resolved_at": alert.resolved_at,
        "created_at": alert.created_at,
    }


@router.get("/", response_model=list[AlertResponse], include_in_schema=False)
@router.get("", response_model=list[AlertResponse])
def list_alerts(
    state_filter: Literal["all", "open", "acknowledged", "resolved"] = Query("all", alias="state"),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Alert).filter(Alert.user_id == current_user.id)
    if state_filter == "open":
        query = query.filter(Alert.resolved_at.is_(None), Alert.is_acknowledged.is_(False))
    elif state_filter == "acknowledged":
        query = query.filter(Alert.resolved_at.is_(None), Alert.is_acknowledged.is_(True))
    elif state_filter == "resolved":
        query = query.filter(Alert.resolved_at.is_not(None))
    alerts = query.order_by(Alert.created_at.desc()).limit(limit).all()
    return [_serialize(alert) for alert in alerts]


@router.get("/unacknowledged", response_model=list[AlertResponse])
def list_unacknowledged(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    alerts = (
        db.query(Alert)
        .filter(
            Alert.user_id == current_user.id,
            Alert.is_acknowledged.is_(False),
            Alert.resolved_at.is_(None),
        )
        .order_by(Alert.created_at.desc())
        .limit(100)
        .all()
    )
    return [_serialize(alert) for alert in alerts]


def _owned_alert(db: Session, user_id: int, alert_id: int) -> Alert:
    alert = db.query(Alert).filter(Alert.id == alert_id, Alert.user_id == user_id).first()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return alert


def _record_lifecycle(db: Session, current_user: User, alert: Alert, action: str) -> None:
    record_audit_event(
        db,
        f"alert.{action}",
        actor_user_id=current_user.id,
        site_id=alert.site_id,
        target=f"alert:{alert.id}",
        metadata={"alert_type": alert.alert_type, "rule_key": alert.rule_key},
    )


@router.patch("/{alert_id}/acknowledge", response_model=AlertResponse)
def acknowledge_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    alert = _owned_alert(db, current_user.id, alert_id)
    if alert.resolved_at is None and not alert.is_acknowledged:
        alert.is_acknowledged = True
        alert.acknowledged_at = datetime.now(timezone.utc)
        _record_lifecycle(db, current_user, alert, "acknowledged")
        db.commit()
        db.refresh(alert)
    return _serialize(alert)


@router.patch("/{alert_id}/resolve", response_model=AlertResponse)
def resolve_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    alert = _owned_alert(db, current_user.id, alert_id)
    if alert.resolved_at is None:
        alert.resolved_at = datetime.now(timezone.utc)
        _record_lifecycle(db, current_user, alert, "resolved")
        db.commit()
        db.refresh(alert)
    return _serialize(alert)


@router.patch("/{alert_id}/reopen", response_model=AlertResponse)
def reopen_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    alert = _owned_alert(db, current_user.id, alert_id)
    if alert.resolved_at is not None:
        alert.resolved_at = None
        alert.is_acknowledged = False
        alert.acknowledged_at = None
        _record_lifecycle(db, current_user, alert, "reopened")
        db.commit()
        db.refresh(alert)
    return _serialize(alert)


@router.get("/config", response_model=AlertConfigResponse)
def get_alert_config(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    site = ensure_default_site(db, current_user.id)
    config = alert_service.config_for_site(db, site)
    db.commit()
    db.refresh(config)
    return _config_response(db, config, current_user)


@router.post("/config", response_model=AlertConfigResponse)
def update_alert_config(
    data: AlertConfigCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    site = ensure_default_site(db, current_user.id)
    config = alert_service.config_for_site(db, site)
    email_available, email_unavailable_reason = _email_delivery_status(db, current_user)
    if data.email_enabled and not email_available and not config.email_enabled:
        if email_unavailable_reason == "email_unverified":
            message = "Verify your current email before enabling critical-alert delivery."
        else:
            message = "Critical-alert email delivery is not configured."
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "alert_email_delivery_unavailable", "message": message},
        )
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
    return _config_response(db, config, current_user)
