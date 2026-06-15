"""
Pydantic schemas for request/response validation.
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ======================== AUTH ========================

class UserRole(str, Enum):
    admin = "admin"
    analyst = "analyst"
    viewer = "viewer"


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=100)
    full_name: str = Field(min_length=1, max_length=100)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    avatar_url: Optional[str] = None
    last_activity: Optional[datetime] = None
    subscription_tier: Optional[str] = "free"

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenData(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ======================== USERS (Admin) ========================

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    subscription_tier: Optional[str] = None

class UserUpdateMe(BaseModel):
    full_name: Optional[str] = None
    subscription_tier: Optional[str] = None

class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6, max_length=100)


# ======================== FORECAST ========================

class ForecastRequest(BaseModel):
    model_name: Optional[str] = Field(None, description="Model to use: 'patchtst', 'sota', 'cnn_bilstm'")
    sample_name: Optional[str] = Field(None, description="Name of pre-loaded sample dataset")
    data: Optional[List[List[float]]] = Field(None, description="Raw input data [96 timesteps x 7 features]")
    calendar: Optional[List[List[float]]] = Field(None, description="Calendar features [96 x 6]")


class ForecastResponse(BaseModel):
    id: int
    model_name: str
    predictions: List[List[float]]  # [24 x 7]
    prediction_labels: List[str]  # column names
    created_at: datetime
    alerts: List[Dict[str, Any]] = []
    input_data: Optional[List[float]] = None  # GAP lookback values for chart

    class Config:
        from_attributes = True


class ForecastHistoryItem(BaseModel):
    id: int
    model_name: str
    created_at: datetime
    peak_power: Optional[float] = None

    class Config:
        from_attributes = True


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
    email_enabled: bool = True


class AlertConfigResponse(BaseModel):
    id: int
    threshold_kw: float
    email_enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AlertResponse(BaseModel):
    id: int
    alert_type: str
    severity: str
    message: Optional[str] = None
    peak_kw: Optional[float] = None
    is_acknowledged: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AlertAcknowledge(BaseModel):
    alert_id: int


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
