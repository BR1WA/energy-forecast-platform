"""
SQLAlchemy ORM models for the Energy Forecast platform.
"""
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text,
    ForeignKey, JSON, func, UniqueConstraint, Index, CheckConstraint, text
)
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=True)
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
    email_verified_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    forecasts = relationship("Forecast", back_populates="user", cascade="all, delete-orphan")
    alert_configs = relationship("AlertConfig", back_populates="user", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="user", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    action_tokens = relationship("AccountActionToken", back_populates="user", cascade="all, delete-orphan")
    identities = relationship("AuthIdentity", back_populates="user", cascade="all, delete-orphan")
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


class AccountActionToken(Base):
    __tablename__ = "account_action_tokens"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('verify_email', 'reset_password')",
            name="ck_account_action_tokens_purpose",
        ),
        UniqueConstraint("token_hash"),
        Index("ix_account_action_tokens_token_hash", "token_hash"),
        Index("ix_action_tokens_user_purpose", "user_id", "purpose"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    purpose = Column(String(40), nullable=False)
    token_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    user = relationship("User", back_populates="action_tokens")


class AuthIdentity(Base):
    __tablename__ = "auth_identities"
    __table_args__ = (
        UniqueConstraint("provider", "subject", name="uq_auth_identity_provider_subject"),
        UniqueConstraint("user_id", "provider", name="uq_auth_identity_user_provider"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    provider = Column(String(40), nullable=False)
    subject = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    user = relationship("User", back_populates="identities")


class OAuthChallenge(Base):
    __tablename__ = "oauth_challenges"
    __table_args__ = (
        CheckConstraint(
            "action IN ('login', 'link', 'delete_account')",
            name="ck_oauth_challenges_action",
        ),
        UniqueConstraint("state_hash"),
        Index("ix_oauth_challenges_state_hash", "state_hash", unique=True),
        Index("ix_oauth_challenges_expiry", "expires_at", "used_at"),
    )

    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(20), nullable=False)
    state_hash = Column(String(64), nullable=False)
    nonce_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EmailOutbox(Base):
    __tablename__ = "email_outbox"
    __table_args__ = (
        UniqueConstraint("dedup_key", name="uq_email_outbox_dedup_key"),
        CheckConstraint(
            "status IN ('pending', 'processing', 'sent', 'retry', 'dead')",
            name="ck_email_outbox_status",
        ),
        Index("ix_email_outbox_due", "status", "next_attempt_at", "lease_expires_at"),
    )

    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    recipient = Column(String(255), nullable=False)
    template = Column(String(80), nullable=False)
    template_version = Column(String(20), nullable=False, default="v1")
    payload = Column(JSON, nullable=False, default=dict)
    dedup_key = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    lease_owner = Column(String(64), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    provider_message_id = Column(String(255), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class AvatarCleanupJob(Base):
    __tablename__ = "avatar_cleanup_jobs"
    __table_args__ = (
        UniqueConstraint("object_key", name="uq_avatar_cleanup_jobs_object_key"),
        CheckConstraint(
            "status IN ('pending', 'retry', 'dead')",
            name="ck_avatar_cleanup_jobs_status",
        ),
        Index("ix_avatar_cleanup_jobs_due", "status", "next_attempt_at"),
    )

    id = Column(String(36), primary_key=True)
    object_key = Column(String(255), nullable=False)
    reason = Column(String(40), nullable=False)
    status = Column(String(20), nullable=False, default="pending", server_default="pending")
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    next_attempt_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_error = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Site(Base):
    __tablename__ = "sites"
    __table_args__ = (UniqueConstraint("user_id", name="uq_sites_user_id"),)

    id = Column(Integer, primary_key=True)
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
    __table_args__ = (
        Index(
            "uq_meters_primary_site",
            "site_id",
            unique=True,
            postgresql_where=text("is_primary IS TRUE"),
            sqlite_where=text("is_primary = 1"),
        ),
    )

    id = Column(Integer, primary_key=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False, index=True)
    external_id = Column(String(100), nullable=True, index=True)
    name = Column(String(120), nullable=False)
    meter_type = Column(String(50), nullable=False, default="electricity")
    status = Column(String(20), nullable=False, default="active")
    source_type = Column(String(20), nullable=False, default="simulation")
    is_primary = Column(Boolean, nullable=False, default=False)
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

    id = Column(Integer, primary_key=True)
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

    id = Column(Integer, primary_key=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    is_running = Column(Boolean, nullable=False, default=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    configuration = Column(JSON, nullable=False, default=dict)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    site = relationship("Site", back_populates="simulation_sessions")


class WorkerHeartbeat(Base):
    """Last successful loop completed by each durable worker."""

    __tablename__ = "worker_heartbeats"

    worker_name = Column(String(64), primary_key=True)
    last_success_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True)
    actor_user_id = Column(Integer, nullable=True, index=True)
    target_user_id = Column(Integer, nullable=True, index=True)
    site_id = Column(Integer, nullable=True, index=True)
    event_type = Column(String(80), nullable=False, index=True)
    target = Column(String(160), nullable=True)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Forecast(Base):
    __tablename__ = "forecasts"
    __table_args__ = (
        Index("ix_forecasts_user_created", "user_id", "created_at", "id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=True, index=True)
    model_registry_id = Column(Integer, ForeignKey("model_registry.id"), nullable=True, index=True)
    horizon = Column(Integer, nullable=True)
    input_source = Column(String(20), nullable=True)
    input_snapshot = Column(JSON, nullable=True)
    confidence_method = Column(String(120), nullable=True)
    model_name = Column(String(50), nullable=False)
    input_start = Column(DateTime(timezone=True), nullable=True)
    input_end = Column(DateTime(timezone=True), nullable=True)
    predictions = Column(JSON, nullable=False)  # Fixed-cadence forecast array.
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
    cooldown_minutes = Column(Integer, nullable=False, default=60)
    missing_data_minutes = Column(Integer, nullable=False, default=60)
    email_enabled = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="alert_configs")


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_user_created", "user_id", "created_at", "id"),
        Index("ix_alerts_site_rule_created", "site_id", "rule_key", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=True, index=True)
    forecast_id = Column(Integer, ForeignKey("forecasts.id"), nullable=True)
    alert_type = Column(String(30), nullable=False)  # peak_demand, cost_threshold
    rule_key = Column(String(160), nullable=True)
    severity = Column(String(10), default="medium")  # low, medium, high
    message = Column(Text, nullable=True)
    peak_kw = Column(Float, nullable=True)
    evidence_json = Column(JSON, nullable=True)
    is_acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="alerts")
    forecast = relationship("Forecast", back_populates="alerts")
    recommendations = relationship("Recommendation", back_populates="alert", cascade="all, delete-orphan")


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (UniqueConstraint("alert_id", name="uq_recommendations_alert_id"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=True, index=True)
    category = Column(String(40), nullable=False)
    title = Column(String(160), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="open", index=True)
    estimated_excess_cost_per_hour_mad = Column(Float, nullable=True)
    evidence_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="recommendations")
    alert = relationship("Alert", back_populates="recommendations")


class SmartMeterReading(Base):
    __tablename__ = "smart_meter_readings"
    __table_args__ = (
        UniqueConstraint(
            "meter_id",
            "timestamp",
            name="uq_smart_meter_readings_meter_timestamp",
        ),
        Index("ix_smart_meter_readings_meter_timestamp", "meter_id", "timestamp"),
    )

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
    __table_args__ = (
        Index(
            "uq_model_registry_active_dataset_horizon",
            "dataset",
            "horizon",
            unique=True,
            postgresql_where=text("active IS TRUE"),
            sqlite_where=text("active = 1"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False) # e.g. patchtst_ihepc_24h
    version = Column(String(20), default="1.0.0", nullable=False)
    experiment_id = Column(String(50), nullable=True) # e.g. exp_20260709_001
    dataset = Column(String(50), nullable=False, default="ihepc")
    horizon = Column(Integer, nullable=False, default=24)
    lookback = Column(Integer, nullable=True)
    experiment_path = Column(String(512), nullable=False)
    model_fingerprint = Column(String(64), nullable=True) # SHA-256 hash
    artifact_contract = Column(JSON, nullable=True)
    contract_validated_at = Column(DateTime(timezone=True), nullable=True)
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
