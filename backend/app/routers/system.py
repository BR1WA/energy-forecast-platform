"""Process, database, and packaged forecast-artifact health."""
import time

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.product_forecast_service import product_forecast_service
from app.config import get_settings
from app.models import EmailOutbox
from app.services.worker_health_service import worker_statuses


router = APIRouter(prefix="/api/v1/system", tags=["System"])
START_TIME = time.time()


def build_readiness(db: Session) -> dict:
    settings = get_settings()
    database_ready = True
    database_error = None
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        database_ready = False
        database_error = type(exc).__name__

    forecast = product_forecast_service.warmup()
    forecast_ready = bool(forecast["available"] and forecast.get("warmed"))
    ready = database_ready and forecast_ready
    forecast_artifacts = {"24": forecast}
    if product_forecast_service.is_enabled(168):
        forecast_artifacts["168"] = product_forecast_service.warmup(168)
    if product_forecast_service.is_enabled(720):
        forecast_artifacts["720"] = product_forecast_service.warmup(720)
    mail_counts = {"processing": 0, "retry": 0, "dead": 0}
    if settings.EMAIL_DELIVERY_ENABLED:
        for state in mail_counts:
            mail_counts[state] = db.query(EmailOutbox).filter(EmailOutbox.status == state).count()
    workers = worker_statuses(db)
    email_status = (
        "disabled"
        if not settings.EMAIL_DELIVERY_ENABLED
        else (
            "unavailable"
            if not workers["email"]["operational"]
            else "degraded"
            if mail_counts["dead"]
            else "ready"
        )
    )
    return {
        "status": "ready" if ready else "not_ready",
        "ready": ready,
        "database": {
            "status": "ready" if database_ready else "unavailable",
            "error": database_error,
        },
        "forecast": {
            "status": "ready" if forecast_ready else "not_ready",
            "name": forecast["name"],
            "display_name": forecast["display_name"],
            "version": forecast["version"],
            "artifact_fingerprint": forecast["artifact_fingerprint"],
            "warmed": bool(forecast.get("warmed")),
            "error": forecast["error"],
        },
        "forecast_artifacts": forecast_artifacts,
        "email": {
            "enabled": settings.EMAIL_DELIVERY_ENABLED,
            "status": email_status,
            **mail_counts,
        },
        "workers": workers,
        "uptime_seconds": int(time.time() - START_TIME),
    }


@router.get("/live")
def get_liveness():
    return {"status": "alive", "uptime_seconds": int(time.time() - START_TIME)}


@router.get("/ready")
def get_readiness(response: Response, db: Session = Depends(get_db)):
    result = build_readiness(db)
    if not result["ready"]:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result


@router.get("/health")
def get_health(db: Session = Depends(get_db)):
    readiness = build_readiness(db)
    return {
        "backend": "healthy",
        "database": readiness["database"]["status"],
        "forecast": readiness["forecast"]["status"],
        "email": readiness["email"],
        "workers": readiness["workers"],
        "ready": readiness["ready"],
        "uptime": readiness["uptime_seconds"],
    }


@router.get("/version")
def get_version():
    return {"version": "1.0.0"}


@router.get("/legal")
def get_legal_configuration():
    settings = get_settings()
    configured = not settings.legal_configuration_errors()
    return {
        "configured": configured,
        "owner_name": settings.LEGAL_OWNER_NAME if configured else None,
        "contact_email": settings.LEGAL_CONTACT_EMAIL if configured else None,
        "support_email": settings.SUPPORT_EMAIL if configured else None,
        "effective_date": settings.LEGAL_EFFECTIVE_DATE if configured else None,
    }
