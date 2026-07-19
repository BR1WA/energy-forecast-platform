"""
Pydantic schemas for request/response validation.
"""
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import math


# ======================== AUTH ========================

class UserRole(str, Enum):
    admin = "admin"
    user = "user"


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=100)
    full_name: str = Field(min_length=1, max_length=100)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


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
    new_password: str = Field(min_length=6, max_length=100)


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
