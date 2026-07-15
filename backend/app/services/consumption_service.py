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
        from sqlalchemy import func
        # 1. Peak Demand (max Global Active Power)
        max_gap = db.query(func.max(SmartMeterReading.gap)).scalar() or 0.0
        
        # 2. Average Daily Power (average hourly active power multiplied by 24h)
        avg_gap = db.query(func.avg(SmartMeterReading.gap)).scalar() or 0.0
        
        # 3. Cumulative Energy Consumption (sum of Global Active Power scaled by 1-minute time blocks to kWh)
        total_minutes = db.query(func.count(SmartMeterReading.id)).scalar() or 1
        total_kwh = (db.query(func.sum(SmartMeterReading.gap)).scalar() or 0.0) / 60.0
        
        return {
            "average_daily": round(avg_gap * 24.0, 2), # Daily kWh estimation
            "peak": round(max_gap, 2), # Peak kW
            "total_kwh": round(total_kwh, 2) # Total kWh
        }

consumption_service = ConsumptionService()

