"""
Admin router — user management, model registry, system health.
Restricted to admin role only.
"""
import time
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import User, Forecast, Alert, ModelRegistry
from app.schemas import UserResponse, UserUpdate, SystemHealth
from app.services.auth_service import require_role, get_current_user

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])

# Track server start time
_start_time = time.time()


@router.get("/users", response_model=List[UserResponse])
def list_users(
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """List all users (admin only)."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [UserResponse.model_validate(u) for u in users]


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    data: UserUpdate,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Update a user's role or status (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if data.full_name is not None:
        user.full_name = data.full_name
    if data.role is not None:
        user.role = data.role.value
    if data.is_active is not None:
        user.is_active = data.is_active

    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Delete a user (admin only). Cannot delete yourself."""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    db.delete(user)
    db.commit()
    return {"message": f"User {user.email} deleted"}


@router.get("/health", response_model=SystemHealth)
def system_health(
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Get system health status (admin only)."""
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    return SystemHealth(
        status="operational",
        active_models=3,
        total_users=db.query(User).count(),
        total_forecasts=db.query(Forecast).count(),
        database_status=db_status,
        uptime_seconds=time.time() - _start_time,
    )


@router.get("/stats")
def get_stats(
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Get platform statistics (admin only)."""
    from sqlalchemy import func

    total_users = db.query(User).count()
    total_forecasts = db.query(Forecast).count()
    total_alerts = db.query(Alert).count()

    # Model usage breakdown
    model_usage = (
        db.query(Forecast.model_name, func.count(Forecast.id))
        .group_by(Forecast.model_name)
        .all()
    )

    # Recent activity
    recent_forecasts = (
        db.query(Forecast)
        .order_by(Forecast.created_at.desc())
        .limit(10)
        .all()
    )

    return {
        "total_users": total_users,
        "total_forecasts": total_forecasts,
        "total_alerts": total_alerts,
        "model_usage": {name: count for name, count in model_usage},
        "users_by_role": {
            "admin": db.query(User).filter(User.role == "admin").count(),
            "analyst": db.query(User).filter(User.role == "analyst").count(),
            "viewer": db.query(User).filter(User.role == "viewer").count(),
        },
    }


@router.get("/models")
def list_models(
    current_user: User = Depends(require_role(["admin"])),
):
    """List all registered ML models (admin only)."""
    from app.services.forecast_service import get_forecast_service
    service = get_forecast_service()
    return service.get_available_models()


@router.post("/models/{model_name}/retrain")
def retrain_model_endpoint(
    model_name: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_role(["admin"])),
):
    """Simulate ML model retraining (admin only)."""
    from app.services.forecast_service import get_forecast_service
    service = get_forecast_service()
    try:
        service.retrain_model(model_name, background_tasks)
        return {"message": f"Retraining started for model {model_name}"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

