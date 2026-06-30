from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db

router = APIRouter(prefix="/api/v1/data-mode", tags=["Data Mode"])

@router.get("/")
def get_data_mode(db: Session = Depends(get_db)):
    # In a real app, extract user_id from auth token
    return {"mode": "SIMULATION", "readonly": False}

@router.put("/")
def update_data_mode(mode: str, db: Session = Depends(get_db)):
    return {"status": "success", "mode": mode}
