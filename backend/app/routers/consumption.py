from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db

router = APIRouter(prefix="/api/v1/consumption", tags=["Consumption"])

@router.get("/current")
def get_current(db: Session = Depends(get_db)):
    return {"kw": 2.5}

@router.get("/history")
def get_history(db: Session = Depends(get_db)):
    return []

@router.get("/statistics")
def get_statistics(db: Session = Depends(get_db)):
    return {"average": 12.5}

@router.get("/export")
def export_consumption(db: Session = Depends(get_db)):
    return {"url": "dummy_link.csv"}
