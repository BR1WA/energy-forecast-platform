"""
SQLAlchemy ORM models for the Energy Forecast platform.
"""
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text,
    ForeignKey, JSON, func
)
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    role = Column(String(20), default="viewer", nullable=False)  # admin, analyst, viewer
    subscription_tier = Column(String(50), default="free", nullable=False)  # free, pro, enterprise
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    last_activity = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    forecasts = relationship("Forecast", back_populates="user", cascade="all, delete-orphan")
    alert_configs = relationship("AlertConfig", back_populates="user", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="user", cascade="all, delete-orphan")


class Forecast(Base):
    __tablename__ = "forecasts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    model_name = Column(String(50), nullable=False)
    input_start = Column(DateTime(timezone=True), nullable=True)
    input_end = Column(DateTime(timezone=True), nullable=True)
    predictions = Column(JSON, nullable=False)  # 24-step forecast array
    metrics = Column(JSON, nullable=True)  # {mae, rmse, mape} if actuals available
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="forecasts")
    alerts = relationship("Alert", back_populates="forecast", cascade="all, delete-orphan")


class AlertConfig(Base):
    __tablename__ = "alert_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    threshold_kw = Column(Float, nullable=False, default=3.0)
    email_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="alert_configs")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    forecast_id = Column(Integer, ForeignKey("forecasts.id"), nullable=True)
    alert_type = Column(String(30), nullable=False)  # peak_demand, cost_threshold
    severity = Column(String(10), default="medium")  # low, medium, high
    message = Column(Text, nullable=True)
    peak_kw = Column(Float, nullable=True)
    is_acknowledged = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="alerts")
    forecast = relationship("Forecast", back_populates="alerts")


class SmartMeterReading(Base):
    __tablename__ = "smart_meter_readings"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=func.now())
    gap = Column(Float, nullable=False)       # Global Active Power (kW)
    grp = Column(Float, nullable=False)       # Global Reactive Power (kW)
    voltage = Column(Float, nullable=False)
    intensity = Column(Float, nullable=False)
    sub_metering_1 = Column(Float, nullable=False)
    sub_metering_2 = Column(Float, nullable=False)
    sub_metering_3 = Column(Float, nullable=False)


