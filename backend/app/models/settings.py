from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, func
from app.database import Base

class SystemSettings(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    is_setup_complete = Column(Boolean, default=False)
    
    # Localization
    country = Column(String(100), default="Morocco")
    region = Column(String(100), default="Casablanca-Settat")
    electricity_provider = Column(String(100), default="Lydec")
    currency = Column(String(10), default="MAD")
    
    # Tariffs
    peak_rate = Column(Float, default=1.5)      # Example MAD rate
    off_peak_rate = Column(Float, default=1.0)  # Example MAD rate
    peak_start_hour = Column(Integer, default=6)
    peak_end_hour = Column(Integer, default=22)
    
    # Sensor Config
    sensor_type = Column(String(50), default="simulator") # 'simulator' or 'real_api'
    sensor_api_url = Column(String(500), nullable=True)
    
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
