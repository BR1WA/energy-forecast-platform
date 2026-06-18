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
    is_setup_complete = Column(Boolean, default=False, nullable=False)
    preferences = Column(JSON, nullable=True, default=dict)

    # Relationships
    forecasts = relationship("Forecast", back_populates="user", cascade="all, delete-orphan")
    alert_configs = relationship("AlertConfig", back_populates="user", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="user", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")


class Subscription(Base):
    """Audit trail / provenance for a user's subscription tier.

    `User.subscription_tier` remains a denormalized cache of the currently
    active subscription's tier (kept for fast reads and existing code). The
    canonical history lives here: each row records why and how a tier was
    granted (admin grant, checkout, trial) and its lifecycle status.
    See ENTITLEMENTS_PLAN.md (Phase 4) and audit C1.
    """
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    tier = Column(String(50), nullable=False)          # pro, enterprise (free = absence of active sub)
    status = Column(String(20), nullable=False, default="pending")  # pending, active, cancelled, expired
    source = Column(String(20), nullable=False, default="checkout")  # admin_grant, checkout, trial
    # Opaque reference returned by the (simulated) payment provider at checkout.
    checkout_ref = Column(String(100), nullable=True, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="subscriptions")


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


class ModelRegistry(Base):
    __tablename__ = "model_registry"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    display_name = Column(String(100), nullable=True)
    architecture_type = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    training_metrics = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    version = Column(String(20), default="1.0.0", nullable=False)
    accuracy = Column(Float, nullable=False)
    last_trained = Column(String(50), nullable=True)
    parameters = Column(JSON, nullable=True)
    status = Column(String(20), default="active", nullable=False)



