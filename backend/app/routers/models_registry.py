from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import ModelRegistry, User
from app.services.auth_service import get_current_user, require_role
from app.services.forecast_service import get_forecast_service

router = APIRouter(prefix="/api/v1/models", tags=["Models Registry"])

def serialize_model(m: ModelRegistry):
    return {
        "id": m.id,
        "name": m.name,
        "version": m.version,
        "experiment_path": m.experiment_path,
        "model_fingerprint": m.model_fingerprint,
        "active": m.active,
        "mae": m.mae,
        "rmse": m.rmse,
        "created_at": m.created_at.isoformat() if m.created_at else None
    }

@router.get("/")
def get_models(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all registered experiments."""
    models = db.query(ModelRegistry).order_by(ModelRegistry.created_at.desc()).all()
    return [serialize_model(m) for m in models]

@router.get("/active")
def get_active_model(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the current production model."""
    active_model = db.query(ModelRegistry).filter(ModelRegistry.active == True).first()
    if not active_model:
        raise HTTPException(status_code=404, detail="No active model found")
    return serialize_model(active_model)

@router.get("/{model_id}")
def get_model_details(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get specific experiment details."""
    model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return serialize_model(model)

@router.post("/{model_id}/activate")
def activate_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """Activate a specific model for production."""
    target_model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
    if not target_model:
        raise HTTPException(status_code=404, detail="Model not found")
    violations = get_forecast_service().validate_artifact_contract(target_model)
    if violations:
        raise HTTPException(status_code=400, detail=f"Model cannot be activated: {'; '.join(violations)}")
        
    # Deactivate all others
    db.query(ModelRegistry).filter(ModelRegistry.horizon == target_model.horizon).update({"active": False})
    
    # Activate target
    target_model.active = True
    db.commit()
    db.refresh(target_model)
    
    return serialize_model(target_model)
