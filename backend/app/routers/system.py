"""Process, database, and packaged forecast-artifact health."""
import time

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.product_forecast_service import product_forecast_service


router = APIRouter(prefix="/api/v1/system", tags=["System"])
START_TIME = time.time()


def build_readiness(db: Session) -> dict:
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
        "ready": readiness["ready"],
        "uptime": readiness["uptime_seconds"],
    }


@router.get("/version")
def get_version():
    return {"version": "1.0.0"}
