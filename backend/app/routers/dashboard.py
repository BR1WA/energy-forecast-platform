from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db

from app.services.consumption_service import consumption_service
from app.services.weather_service import weather_service
from app.services.alert_service import alert_service
import concurrent.futures

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])

@router.get("/overview")
def get_overview(db: Session = Depends(get_db)):
    """
    Composite endpoint returning data for all dashboard widgets gracefully.
    If one service fails, it returns partial data instead of a 500 error.
    """
    response = {
        "currentConsumption": None,
        "forecast": {"24h": [], "confidence": "high"},
        "alerts": [],
        "weather": None,
        "system": {"status": "ok"},
        "models": {"active": "Hybrid_v2"}
    }
    
    def get_consumption():
        try:
            return consumption_service.get_current_consumption(db, user_id=1)
        except Exception as e:
            print(f"Consumption Service Error: {e}")
            return None

    def get_weather():
        try:
            return weather_service.get_weather(48.8566, 2.3522, mode="current")
        except Exception as e:
            print(f"Weather Service Error: {e}")
            return None

    def get_alerts():
        try:
            return alert_service.get_recent_alerts(db, user_id=1, limit=5)
        except Exception as e:
            print(f"Alert Service Error: {e}")
            return []

    # Execute independent queries concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        f_consumption = executor.submit(get_consumption)
        f_weather = executor.submit(get_weather)
        f_alerts = executor.submit(get_alerts)
        
        response["currentConsumption"] = f_consumption.result()
        response["weather"] = f_weather.result()
        response["alerts"] = f_alerts.result()
    
    return response
