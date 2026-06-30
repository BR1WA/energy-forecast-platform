from fastapi import APIRouter, Depends
import time
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db

router = APIRouter(prefix="/api/v1/system", tags=["System"])

START_TIME = time.time()

@router.get("/health")
def get_health(db: Session = Depends(get_db)):
    """
    Returns system health and uptime.
    """
    uptime = int(time.time() - START_TIME)
    
    # Check DB connection
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"
    
    return {
        "backend": "healthy",
        "database": db_status,
        "forecast": "placeholder",
        "weather": "healthy",
        "uptime": uptime
    }

@router.get("/version")
def get_version():
    """
    Returns system version.
    """
    return {
        "version": "1.0.0"
    }
