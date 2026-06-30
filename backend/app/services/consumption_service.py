from sqlalchemy.orm import Session
from app.models.models import SmartMeterReading

class ConsumptionService:
    def get_current_consumption(self, db: Session, user_id: int):
        reading = db.query(SmartMeterReading).order_by(SmartMeterReading.timestamp.desc()).first()
        if not reading:
            return {"kw": 0, "status": "empty"}
        return {
            "kw": reading.gap,
            "status": "normal" if reading.gap < 4.0 else "high",
            "voltage": reading.voltage,
            "intensity": reading.intensity,
            "timestamp": reading.timestamp.isoformat() if reading.timestamp else None
        }

    def get_history(self, db: Session, user_id: int, hours: int = 24):
        # We'd normally filter by timestamp > now - hours
        readings = db.query(SmartMeterReading).order_by(SmartMeterReading.timestamp.desc()).limit(hours * 60).all()
        return [{"kw": r.gap, "timestamp": r.timestamp.isoformat()} for r in readings]

    def get_statistics(self, db: Session, user_id: int):
        return {"average_daily": 12.5, "peak": 5.2}

consumption_service = ConsumptionService()
