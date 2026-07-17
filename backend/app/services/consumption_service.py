from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.models import Meter, Site, SmartMeterReading

class ConsumptionService:
    @staticmethod
    def _query_for_user(db: Session, user_id: int):
        return (
            db.query(SmartMeterReading)
            .join(Meter, SmartMeterReading.meter_id == Meter.id)
            .join(Site, Meter.site_id == Site.id)
            .filter(Site.user_id == user_id)
        )

    def get_current_consumption(self, db: Session, user_id: int):
        reading = self._query_for_user(db, user_id).order_by(SmartMeterReading.timestamp.desc()).first()
        if not reading:
            return {"kw": 0, "status": "empty", "source": None, "age_seconds": None}
        timestamp = reading.timestamp
        if timestamp and timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        age_seconds = int(max(0, (datetime.now(timezone.utc) - timestamp).total_seconds())) if timestamp else None
        return {
            "kw": reading.gap,
            "status": "normal" if reading.gap < 4.0 else "high",
            "voltage": reading.voltage,
            "intensity": reading.intensity,
            "timestamp": reading.timestamp.isoformat() if reading.timestamp else None,
            "source": reading.source,
            "age_seconds": age_seconds,
        }

    def get_history(self, db: Session, user_id: int, hours: int = 24):
        readings = (
            self._query_for_user(db, user_id)
            .order_by(SmartMeterReading.timestamp.desc())
            .limit(hours * 60)
            .all()
        )
        return [{"kw": r.gap, "timestamp": r.timestamp.isoformat()} for r in readings]

    def get_statistics(self, db: Session, user_id: int):
        from sqlalchemy import func
        # 1. Peak Demand (max Global Active Power)
        readings = self._query_for_user(db, user_id)
        max_gap = readings.with_entities(func.max(SmartMeterReading.gap)).scalar() or 0.0
        
        # 2. Average Daily Power (average hourly active power multiplied by 24h)
        avg_gap = readings.with_entities(func.avg(SmartMeterReading.gap)).scalar() or 0.0
        
        # 3. Cumulative Energy Consumption (sum of Global Active Power scaled by 1-minute time blocks to kWh)
        total_kwh = (readings.with_entities(func.sum(SmartMeterReading.gap)).scalar() or 0.0) / 60.0
        
        return {
            "average_daily": round(avg_gap * 24.0, 2), # Daily kWh estimation
            "peak": round(max_gap, 2), # Peak kW
            "total_kwh": round(total_kwh, 2) # Total kWh
        }

consumption_service = ConsumptionService()
