"""
Admin router — user management, model registry, system health.
Restricted to admin role only.
"""
import time
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import User, Forecast, Alert, EmailOutbox
from app.schemas import UserResponse, UserUpdate, SystemHealth
from app.services.auth_service import require_role
from app.services.audit_service import record_audit_event
from app.services.product_forecast_service import PRODUCT_MODEL_NAMES, product_forecast_service
from app.services.email_service import retry_dead_email

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])

# Track server start time
_start_time = time.time()


@router.post("/email-outbox/{outbox_id}/retry")
def retry_email_outbox(
    outbox_id: str,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    row = db.query(EmailOutbox).filter(EmailOutbox.id == outbox_id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "email_not_found", "message": "Email outbox item was not found."})
    if row.status != "dead":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "email_not_dead", "message": "Only dead email can be retried."})
    retry_dead_email(db, row)
    record_audit_event(
        db,
        "email.retry_requested",
        actor_user_id=current_user.id,
        target=f"email-outbox:{row.id}",
        metadata={"message_type": row.template},
    )
    db.commit()
    return {"id": row.id, "status": row.status}


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
    """Update a user's role or activation status (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    removing_admin_access = (
        user.role == "admin"
        and (
            (data.role is not None and data.role.value != "admin")
            or data.is_active is False
        )
    )
    if removing_admin_access:
        active_admins = db.query(User).filter(
            User.role == "admin", User.is_active.is_(True)
        ).count()
        if active_admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The final active administrator cannot be disabled or demoted.",
            )

    if data.full_name is not None:
        user.full_name = data.full_name
    if data.role is not None:
        user.role = data.role.value
    if data.is_active is not None:
        user.is_active = data.is_active
    record_audit_event(
        db,
        "admin.user_updated",
        actor_user_id=current_user.id,
        target_user_id=user.id,
        target=f"user:{user.id}",
        metadata=data.model_dump(exclude_none=True),
    )
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

    record_audit_event(
        db,
        "admin.user_deleted",
        actor_user_id=current_user.id,
        target_user_id=user.id,
        target=f"user:{user.id}",
        metadata={"email": user.email},
    )
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

    import psutil
    cpu_percent = psutil.cpu_percent(interval=0.1)
    mem_percent = psutil.virtual_memory().percent

    model = product_forecast_service.warmup()

    return SystemHealth(
        status="operational" if db_status == "healthy" and model["available"] and model["warmed"] else "degraded",
        total_users=db.query(User).count(),
        total_forecasts=db.query(Forecast).filter(Forecast.model_name.in_(PRODUCT_MODEL_NAMES)).count(),
        database_status=db_status,
        forecast_status="ready" if model["available"] and model["warmed"] else "not_ready",
        forecast_error=model["error"],
        model_name=model["display_name"],
        model_version=model["version"],
        artifact_fingerprint=model["artifact_fingerprint"],
        uptime_seconds=time.time() - _start_time,
        cpu_usage=cpu_percent,
        memory_usage=mem_percent,
    )


@router.get("/stats")
def get_stats(
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Get platform statistics (admin only)."""
    total_users = db.query(User).count()
    total_forecasts = db.query(Forecast).count()
    total_alerts = db.query(Alert).count()

    return {
        "total_users": total_users,
        "total_forecasts": total_forecasts,
        "total_alerts": total_alerts,
        "users_by_role": {
            "admin": db.query(User).filter(User.role == "admin").count(),
            "user": db.query(User).filter(User.role == "user").count(),
        },
    }


@router.get("/model-readiness")
def model_readiness(
    current_user: User = Depends(require_role(["admin"])),
):
    """Return fixed packaged-artifact status without mutation controls."""
    return product_forecast_service.warmup()


@router.get("/model-readiness/all")
def all_model_readiness(
    current_user: User = Depends(require_role(["admin"])),
):
    """Return independent readiness for every fixed forecast artifact."""
    del current_user
    return {
        "artifacts": [
            product_forecast_service.warmup(),
            product_forecast_service.warmup(168),
        ]
    }
