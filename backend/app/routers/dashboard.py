from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.services.auth_service import get_current_user
from app.services.consumption_service import consumption_service
from app.services.weather_service import weather_service
from app.services.alert_service import alert_service
from app.services.dashboard_service import dashboard_service
import concurrent.futures

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])

@router.get("/summary")
def get_summary(
    lat: float = None,
    lon: float = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Unified dashboard summary aggregating energy score, estimated bill,
    recommendations, forecasts, and live simulation states.
    """
    return dashboard_service.get_summary(db, user_id=current_user.id, lat=lat, lon=lon)

@router.get("/overview")
def get_overview(
    lat: float = None,
    lon: float = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
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
            return consumption_service.get_current_consumption(db, user_id=current_user.id)
        except Exception as e:
            print(f"Consumption Service Error: {e}")
            return None

    def get_weather():
        try:
            actual_lat = lat if lat is not None else 33.5731
            actual_lon = lon if lon is not None else -7.5898
            return weather_service.get_weather(actual_lat, actual_lon, mode="current")
        except Exception as e:
            print(f"Weather Service Error: {e}")
            return None

    def get_alerts():
        try:
            return alert_service.get_recent_alerts(db, user_id=current_user.id, limit=5)
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
