from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db

from app.models.models import ModelRegistry

router = APIRouter(prefix="/api/v1/models", tags=["Models Registry"])

@router.get("/")
def get_models(db: Session = Depends(get_db)):
    models = db.query(ModelRegistry).all()
    return [
        {
            "id": str(m.id),
            "horizon": m.horizon,
            "model_name": m.model_name,
            "version": m.version,
            "metrics": m.metrics,
            "status": m.status,
            "created_at": m.created_at.isoformat() if m.created_at else None
        }
        for m in models
    ]
