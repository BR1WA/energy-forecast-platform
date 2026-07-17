"""
SQLAlchemy ORM models for the Energy Forecast platform.
"""
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text,
    ForeignKey, JSON, func, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    role = Column(String(20), default="user", nullable=False)  # admin, user
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    last_activity = Column(DateTime(timezone=True), nullable=True)
    is_setup_complete = Column(Boolean, default=False, nullable=False)
    preferences = Column(JSON, nullable=True, default=dict)
    data_mode = Column(String(20), default="SIMULATION", nullable=False) # LIVE, HISTORICAL, SIMULATION, TRAINING, DEMO

    # Relationships
    forecasts = relationship("Forecast", back_populates="user", cascade="all, delete-orphan")
    alert_configs = relationship("AlertConfig", back_populates="user", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    energy_budget = relationship("EnergyBudget", back_populates="user", uselist=False, cascade="all, delete-orphan")
    sites = relationship("Site", back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(255), unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)

    # Relationships
    user = relationship("User", back_populates="refresh_tokens")


class Site(Base):
    __tablename__ = "sites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    address = Column(String(255), nullable=True)
    region = Column(String(100), nullable=True)
    timezone = Column(String(64), nullable=False, default="Africa/Casablanca")
    provider = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="sites")
    meters = relationship("Meter", back_populates="site", cascade="all, delete-orphan")
    settings = relationship("SiteSettings", back_populates="site", uselist=False, cascade="all, delete-orphan")
    simulation_sessions = relationship("SimulationSession", back_populates="site", cascade="all, delete-orphan")


class Meter(Base):
    __tablename__ = "meters"

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False, index=True)
    external_id = Column(String(100), nullable=True, index=True)
    name = Column(String(120), nullable=False)
    meter_type = Column(String(50), nullable=False, default="electricity")
    status = Column(String(20), nullable=False, default="active")
    source_type = Column(String(20), nullable=False, default="simulation")
    expected_interval_seconds = Column(Integer, nullable=True)
    ingestion_key_hash = Column(String(64), nullable=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    site = relationship("Site", back_populates="meters")
    readings = relationship("SmartMeterReading", back_populates="meter", cascade="all, delete-orphan")
    ingestion_batches = relationship("IngestionBatch", back_populates="meter", cascade="all, delete-orphan")


class IngestionBatch(Base):
    __tablename__ = "ingestion_batches"
    __table_args__ = (UniqueConstraint("meter_id", "idempotency_key", name="uq_ingestion_batches_meter_key"),)

    id = Column(String(36), primary_key=True)
    meter_id = Column(Integer, ForeignKey("meters.id"), nullable=False, index=True)
    source = Column(String(20), nullable=False)
    idempotency_key = Column(String(100), nullable=True)
    total_rows = Column(Integer, nullable=False, default=0)
    accepted_rows = Column(Integer, nullable=False, default=0)
    duplicate_rows = Column(Integer, nullable=False, default=0)
    rejected_rows = Column(Integer, nullable=False, default=0)
    errors = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    meter = relationship("Meter", back_populates="ingestion_batches")
    readings = relationship("SmartMeterReading", back_populates="ingestion_batch")


class SiteSettings(Base):
    __tablename__ = "site_settings"

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False, unique=True, index=True)
    country = Column(String(100), nullable=False, default="Morocco")
    region = Column(String(100), nullable=True)
    electricity_provider = Column(String(100), nullable=True)
    currency = Column(String(10), nullable=False, default="MAD")
    peak_rate = Column(Float, nullable=False, default=1.1)
    off_peak_rate = Column(Float, nullable=False, default=0.8)
    peak_start_hour = Column(Integer, nullable=False, default=6)
    peak_end_hour = Column(Integer, nullable=False, default=22)
    sensor_type = Column(String(50), nullable=False, default="simulator")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    site = relationship("Site", back_populates="settings")


class SimulationSession(Base):
    __tablename__ = "simulation_sessions"
    __table_args__ = (UniqueConstraint("site_id", name="uq_simulation_sessions_site_id"),)

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    is_running = Column(Boolean, nullable=False, default=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    configuration = Column(JSON, nullable=False, default=dict)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    site = relationship("Site", back_populates="simulation_sessions")


class Forecast(Base):
    __tablename__ = "forecasts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=True, index=True)
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
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=True, index=True)
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
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=True, index=True)
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
    meter_id = Column(Integer, ForeignKey("meters.id"), nullable=False, index=True)
    ingestion_batch_id = Column(String(36), ForeignKey("ingestion_batches.id"), nullable=True, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=func.now())
    gap = Column(Float, nullable=False)       # Global Active Power (kW)
    grp = Column(Float, nullable=False)       # Global Reactive Power (kW)
    voltage = Column(Float, nullable=False)
    intensity = Column(Float, nullable=False)
    sub_metering_1 = Column(Float, nullable=False)
    sub_metering_2 = Column(Float, nullable=False)
    sub_metering_3 = Column(Float, nullable=False)
    energy_kwh = Column(Float, nullable=True)
    source = Column(String(20), nullable=False, default="legacy")
    quality = Column(String(20), nullable=False, default="validated")

    meter = relationship("Meter", back_populates="readings")
    ingestion_batch = relationship("IngestionBatch", back_populates="readings")


class ModelRegistry(Base):
    __tablename__ = "model_registry"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False) # e.g. patchtst_ihepc_24h
    version = Column(String(20), default="1.0.0", nullable=False)
    experiment_id = Column(String(50), nullable=True) # e.g. exp_20260709_001
    dataset = Column(String(50), nullable=False, default="ihepc")
    horizon = Column(Integer, nullable=False, default=24)
    lookback = Column(Integer, nullable=True)
    experiment_path = Column(String(255), nullable=False)
    model_fingerprint = Column(String(64), nullable=True) # SHA-256 hash
    active = Column(Boolean, default=False, nullable=False)
    mae = Column(Float, nullable=True)
    rmse = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class EnergyBudget(Base):
    __tablename__ = "energy_budgets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=True, index=True)
    monthly_budget_mad = Column(Float, nullable=False)
    monthly_budget_kwh = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship
    user = relationship("User", back_populates="energy_budget")

