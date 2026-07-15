from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/api/v1/data-mode", tags=["Data Mode"])

@router.get("/")
def get_data_mode(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return {"mode": current_user.data_mode, "readonly": False}

@router.put("/")
def update_data_mode(
    mode: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    current_user.data_mode = mode
    db.commit()
    return {"status": "success", "mode": mode}

