from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.services.auth_service import get_current_user
from app.services.consumption_service import consumption_service

router = APIRouter(prefix="/api/v1/consumption", tags=["Consumption"])

@router.get("/current")
def get_current(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return consumption_service.get_current_consumption(db, user_id=current_user.id)

@router.get("/history")
def get_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return consumption_service.get_history(db, user_id=current_user.id)

@router.get("/statistics")
def get_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return consumption_service.get_statistics(db, user_id=current_user.id)

@router.get("/export")
def export_consumption(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return {"url": "/static/dummy_export.csv"}

