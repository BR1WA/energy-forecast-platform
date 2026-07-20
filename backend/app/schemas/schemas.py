"""
Pydantic schemas for request/response validation.
"""
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum
import math


# ======================== AUTH ========================

class UserRole(str, Enum):
    admin = "admin"
    user = "user"


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)
    full_name: str = Field(min_length=1, max_length=100)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class UserLogin(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class ConsumptionPeriod(str, Enum):
    live = "live"
    today = "today"
    seven_days = "7d"
    month = "month"
    year = "year"
    all = "all"
    custom = "custom"


class ConsumptionPoint(BaseModel):
    timestamp: datetime
    average_kw: float
    min_kw: float | None
    max_kw: float | None
    energy_kwh: float
    sample_count: int


class ConsumptionSourceCount(BaseModel):
    source: str
    count: int


class ConsumptionFreshness(BaseModel):
    status: str
    age_seconds: int | None
    expected_interval_seconds: int | None
    last_seen_at: datetime | None
    source: str | None
    quality: str | None


class ConsumptionPeriodSummary(BaseModel):
    timeframe: str
    period_start: datetime
    period_end: datetime
    timezone: str
    granularity: str
    total_kwh: float
    estimated_cost: float
    currency: str
    average_kw: float
    peak_kw: float
    coverage_pct: float
    sample_count: int
    sources: List[ConsumptionSourceCount]
    freshness: ConsumptionFreshness
    points: List[ConsumptionPoint]


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    avatar_url: Optional[str] = None
    last_activity: Optional[datetime] = None
    is_setup_complete: bool = False
    preferences: Optional[Dict[str, Any]] = None

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenData(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"


# ======================== INGESTION ========================

class MeterSample(BaseModel):
    """Canonical electricity measurement accepted from every ingestion source."""
    model_config = ConfigDict(populate_by_name=True)

    timestamp: datetime
    active_power_kw: float = Field(ge=0, le=100)
    reactive_power_kvar: float = Field(default=0, ge=0, le=100)
    voltage_v: float = Field(default=230, gt=0, le=1000)
    current_a: Optional[float] = Field(default=None, ge=0, le=1000)
    sub_metering_1_wh: float = Field(default=0, ge=0, le=100_000)
    sub_metering_2_wh: float = Field(default=0, ge=0, le=100_000)
    sub_metering_3_wh: float = Field(default=0, ge=0, le=100_000)
    energy_kwh: Optional[float] = Field(default=None, ge=0, le=10_000_000)

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_have_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone offset")
        return value

    @field_validator(
        "active_power_kw", "reactive_power_kvar", "voltage_v", "current_a",
        "sub_metering_1_wh", "sub_metering_2_wh", "sub_metering_3_wh", "energy_kwh",
    )
    @classmethod
    def values_must_be_finite(cls, value: Optional[float]) -> Optional[float]:
        if value is not None and not math.isfinite(value):
            raise ValueError("measurement values must be finite")
        return value


class MeterSampleBatch(BaseModel):
    samples: List[MeterSample] = Field(min_length=1, max_length=1000)
    idempotency_key: Optional[str] = Field(default=None, min_length=8, max_length=100)


class IngestionKeyResponse(BaseModel):
    meter_id: int
    api_key: str


class MeterConfiguration(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    expected_interval_seconds: int = Field(ge=5, le=86_400)


class SimulationConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_part: Literal["morning", "afternoon", "evening", "night"] = "evening"
    occupants: int = Field(default=2, ge=1, le=12)
    temperature: float = Field(default=25.0, ge=5, le=50)
    ac_level: Literal["off", "low", "medium", "high"] = "medium"
    washing_machine: bool = False
    solar: Literal["off", "low", "high"] = "off"


class IngestionResult(BaseModel):
    batch_id: str
    total_rows: int
    accepted_rows: int
    duplicate_rows: int
    rejected_rows: int
    errors: List[Dict[str, Any]]


# ======================== USERS (Admin) ========================

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

class UserUpdateMe(BaseModel):
    full_name: Optional[str] = None

class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=100)


# ======================== FORECAST ========================

class ForecastRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_name: Optional[str] = Field(None, description="Model to use: 'patchtst', 'sota', 'cnn_bilstm', 'itransformer'")
    sample_name: Optional[str] = Field(None, description="Name of pre-loaded sample dataset")
    data: Optional[List[List[float]]] = Field(None, description="Raw input data [lookback timesteps x 7 features]")
    calendar: Optional[List[List[float]]] = Field(None, description="Calendar features [lookback x 6]")
    horizon: int = Field(24, description="Forecast horizon in hours (24, 168, or 720)")


class ForecastResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    model_name: str
    predictions: List[List[float]]  # [24 x 7]
    prediction_labels: List[str]  # column names
    created_at: datetime
    alerts: List[Dict[str, Any]] = []
    input_data: Optional[List[float]] = None  # GAP lookback values for chart
    model_id: Optional[int] = None
    model_version: Optional[str] = None
    horizon: Optional[int] = None
    input_source: Optional[str] = None
    confidence_method: str = "model output without calibrated interval"

class ForecastHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    model_name: str
    created_at: datetime
    peak_power: Optional[float] = None


class ForecastModelStatus(BaseModel):
    available: bool
    name: str
    display_name: str
    version: str
    artifact_fingerprint: Optional[str] = None
    error: Optional[str] = None


class ForecastReadiness(BaseModel):
    status: Literal["ready", "fallback_ready", "insufficient_data"]
    ready_for_tft: bool
    fallback_available: bool
    required_hours: int
    minimum_coverage_percent: float
    maximum_allowed_gap_hours: int
    coverage_percent: float
    observed_hours: int
    missing_hours: int
    imputed_hours: int
    maximum_gap_hours: int
    unit: Literal["kWh"]
    resolution: Literal["hourly"]
    latest_reading_at: Optional[datetime] = None
    forecast_origin: Optional[datetime] = None
    reasons: List[str] = Field(default_factory=list)
    model: ForecastModelStatus


class ProductForecastPoint(BaseModel):
    timestamp: datetime
    p10_kwh: Optional[float] = None
    p50_kwh: float
    p90_kwh: Optional[float] = None


class ProductForecastResponse(BaseModel):
    id: int
    model_name: str
    model_version: str
    method: Literal["global_tft", "seasonal_naive", "unknown"]
    fallback_reason: Optional[str] = None
    unit: Literal["kWh"] = "kWh"
    timezone: str
    horizon_hours: int
    input_start: Optional[datetime] = None
    input_end: Optional[datetime] = None
    forecast_start: datetime
    forecast_end: Optional[datetime] = None
    coverage_percent: float
    observed_hours: int
    maximum_gap_hours: int
    sources: List[str]
    confidence_method: str
    artifact_fingerprint: Optional[str] = None
    points: List[ProductForecastPoint]
    created_at: datetime


class ProductForecastHistoryItem(BaseModel):
    id: int
    model_name: str
    method: str
    forecast_start: Optional[datetime] = None
    created_at: datetime

class ModelInfo(BaseModel):
    id: str
    name: str
    display_name: str
    architecture_type: str
    description: Optional[str] = None
    training_metrics: Optional[Dict[str, float]] = None
    is_active: bool
    version: str
    accuracy: float
    last_trained: Optional[str] = None
    parameters: Dict[str, Any] = {}
    status: str


class SampleDataset(BaseModel):
    name: str
    description: str
    season: str
    date_range: str


# ======================== ALERTS ========================

class AlertConfigCreate(BaseModel):
    threshold_kw: float = Field(ge=0.1, le=20.0, default=3.0)
    cooldown_minutes: int = Field(ge=5, le=1440, default=60)
    missing_data_minutes: int = Field(ge=5, le=10080, default=60)
    email_enabled: bool = True


class AlertConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    threshold_kw: float
    cooldown_minutes: int
    missing_data_minutes: int
    email_enabled: bool
    created_at: datetime

class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_type: str
    severity: str
    message: Optional[str] = None
    peak_kw: Optional[float] = None
    evidence_json: Optional[Dict[str, Any]] = None
    is_acknowledged: bool
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime

class AlertAcknowledge(BaseModel):
    alert_id: int


class RecommendationStatusUpdate(BaseModel):
    status: str = Field(pattern="^(open|completed|dismissed)$")


class RecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    title: str
    message: str
    status: str
    estimated_excess_cost_per_hour_mad: Optional[float] = None
    evidence_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: Optional[datetime] = None


class ConsumptionTrendPoint(BaseModel):
    date: str
    consumption: float
    predicted: Optional[float] = None

class WeeklyConsumptionPoint(BaseModel):
    week: str
    actual: float
    predicted: float
    savings: float

class HourlyPatternPoint(BaseModel):
    hour: str
    weekday: float
    weekend: float

class MonthlyAccuracyPoint(BaseModel):
    month: str
    cnn_bilstm: float
    sota_hybrid: float
    patchtst: float

class ModelPerformancePoint(BaseModel):
    metric: str
    cnn_bilstm: float
    sota_hybrid: float
    patchtst: float

class HeatmapPoint(BaseModel):
    day: str
    hour: int
    value: float

class AnalyticsSummary(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    total_forecasts: int
    total_alerts: int
    unacknowledged_alerts: int
    models_used: Dict[str, int]  # {model_name: count}
    avg_peak_power: Optional[float] = None
    recent_forecasts: List[ForecastHistoryItem]
    consumption_trend: List[ConsumptionTrendPoint] = []
    weekly_consumption: List[WeeklyConsumptionPoint] = []
    consumption_by_hour: List[HourlyPatternPoint] = []
    monthly_accuracy: List[MonthlyAccuracyPoint] = []
    model_performance: List[ModelPerformancePoint] = []
    heatmap_data: List[HeatmapPoint] = []


# ======================== ADMIN ========================

class SystemHealth(BaseModel):
    status: str
    active_models: int
    total_users: int
    total_forecasts: int
    database_status: str
    uptime_seconds: float
    cpu_usage: float
    memory_usage: float
