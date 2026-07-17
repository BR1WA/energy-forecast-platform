from pathlib import Path
import time

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.models import ModelRegistry
from app.services.forecast_service import get_forecast_service

router = APIRouter(prefix="/api/v1/system", tags=["System"])

START_TIME = time.time()
REQUIRED_MODEL_FILES = ("model.pt", "pipeline.pkl", "config.yaml")


def build_readiness(db: Session) -> dict:
    database_ready = True
    database_error = None
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        database_ready = False
        database_error = type(exc).__name__

    active_model = None
    missing_artifacts: list[str] = []
    if database_ready:
        active_model = (
            db.query(ModelRegistry)
            .filter(ModelRegistry.active.is_(True))
            .first()
        )

    if active_model:
        model_dir = Path(active_model.experiment_path)
        missing_artifacts = [
            filename
            for filename in REQUIRED_MODEL_FILES
            if not (model_dir / filename).is_file()
        ]
        if not missing_artifacts:
            contract_violations = get_forecast_service().validate_artifact_contract(active_model)
            missing_artifacts = contract_violations
        if not missing_artifacts:
            try:
                get_forecast_service().warm_model(active_model)
            except Exception as exc:
                missing_artifacts = [f"model warm-up failed: {type(exc).__name__}"]

    model_ready = active_model is not None and not missing_artifacts
    ready = database_ready and model_ready
    return {
        "status": "ready" if ready else "not_ready",
        "ready": ready,
        "database": {
            "status": "ready" if database_ready else "unavailable",
            "error": database_error,
        },
        "forecast": {
            "status": "ready" if model_ready else "not_ready",
            "active_model_id": active_model.id if active_model else None,
            "active_model": active_model.name if active_model else None,
            "missing_artifacts": missing_artifacts,
        },
        "uptime_seconds": int(time.time() - START_TIME),
    }


@router.get("/live")
def get_liveness():
    """Return process liveness without checking external dependencies."""
    return {
        "status": "alive",
        "uptime_seconds": int(time.time() - START_TIME),
    }


@router.get("/ready")
def get_readiness(response: Response, db: Session = Depends(get_db)):
    """Return dependency readiness and use HTTP 503 while unavailable."""
    result = build_readiness(db)
    if not result["ready"]:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result

@router.get("/health")
def get_health(db: Session = Depends(get_db)):
    """Backward-compatible health summary backed by real readiness checks."""
    readiness = build_readiness(db)
    return {
        "backend": "healthy",
        "database": readiness["database"]["status"],
        "forecast": readiness["forecast"]["status"],
        "weather": "not_checked",
        "ready": readiness["ready"],
        "uptime": readiness["uptime_seconds"],
    }

@router.get("/version")
def get_version():
    """
    Returns system version.
    """
    return {
        "version": "1.0.0"
    }
