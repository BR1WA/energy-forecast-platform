"""Product API for fixed hourly and daily forecast capabilities."""

from __future__ import annotations

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import get_settings
from app.limiter import limiter
from app.models import Forecast, User
from app.schemas import (
    ForecastCapabilitiesResponse,
    ForecastDemoHistoryResponse,
    ForecastReadiness,
    ForecastRunRequest,
    ProductForecastHistoryItem,
    ProductForecastResponse,
)
from app.services.auth_service import get_current_user
from app.services.audit_service import record_audit_event
from app.services.forecast_demo_service import forecast_demo_service
from app.services.product_forecast_service import (
    LOOKBACK_HOURS,
    PRODUCT_MODEL_NAMES,
    ForecastCapabilityError,
    ForecastInputError,
    product_forecast_service,
)

router = APIRouter(prefix="/api/v1/forecast", tags=["Forecast"])
PRODUCT_MODELS = PRODUCT_MODEL_NAMES
settings = get_settings()


def _capability_error(exc: ForecastCapabilityError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": str(exc)},
    )


def _serialize(forecast: Forecast) -> dict:
    snapshot = forecast.input_snapshot or {}
    origin = snapshot.get("forecast_origin")
    rows = forecast.predictions or []
    target_interval_hours = int(snapshot.get("target_interval_hours", 1))
    resolution = snapshot.get("resolution", "hourly")
    points = []
    if origin:
        parsed_origin = datetime.fromisoformat(origin)
        for index, row in enumerate(rows):
            points.append(
                {
                    "timestamp": parsed_origin
                    + timedelta(hours=index * target_interval_hours),
                    "p50_kwh": float(row[0]),
                    "p10_kwh": (
                        float(row[1]) if len(row) > 1 and row[1] is not None else None
                    ),
                    "p90_kwh": (
                        float(row[2]) if len(row) > 2 and row[2] is not None else None
                    ),
                }
            )
    return {
        "id": forecast.id,
        "model_name": forecast.model_name,
        "model_version": snapshot.get("model_version", "unknown"),
        "method": snapshot.get("method", "unknown"),
        "fallback_reason": snapshot.get("fallback_reason"),
        "unit": "kWh",
        "timezone": snapshot.get("timezone", "UTC"),
        "horizon_hours": forecast.horizon or 24,
        "target_count": int(snapshot.get("target_count", len(rows))),
        "target_interval_hours": target_interval_hours,
        "resolution": resolution,
        "input_start": forecast.input_start,
        "input_end": forecast.input_end,
        "forecast_start": origin,
        "forecast_end": snapshot.get("forecast_end"),
        "coverage_percent": snapshot.get("coverage_percent", 0),
        "observed_hours": snapshot.get("observed_hours", 0),
        "maximum_gap_hours": snapshot.get("maximum_gap_hours", 0),
        "sources": snapshot.get("sources", []),
        "confidence_method": forecast.confidence_method,
        "artifact_fingerprint": snapshot.get("artifact_fingerprint"),
        "points": points,
        "created_at": forecast.created_at,
    }


@router.get("/capabilities", response_model=ForecastCapabilitiesResponse)
def get_capabilities(current_user: User = Depends(get_current_user)):
    del current_user
    return product_forecast_service.capabilities()


@router.get("/readiness", response_model=ForecastReadiness)
def get_readiness(
    horizon_hours: int = Query(24),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return product_forecast_service.readiness(db, current_user.id, horizon_hours)
    except ForecastCapabilityError as exc:
        raise _capability_error(exc) from exc


@router.post("/prepare-demo-history", response_model=ForecastDemoHistoryResponse)
@limiter.limit(settings.EXPENSIVE_RATE_LIMIT)
def prepare_demo_history(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = forecast_demo_service.prepare_history(db, current_user.id)
    record_audit_event(
        db,
        "forecast.demo_history_prepared",
        actor_user_id=current_user.id,
        target=f"meter:{result['meter_id']}",
        metadata={
            "accepted_rows": result["accepted_rows"],
            "duplicate_rows": result["duplicate_rows"],
            "coverage_percent": result["coverage_percent"],
        },
    )
    db.commit()
    return result


@router.post(
    "/run", response_model=ProductForecastResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit(settings.EXPENSIVE_RATE_LIMIT)
def run_forecast(
    request: Request,
    data: ForecastRunRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    horizon_hours = data.horizon_hours if data is not None else 24
    try:
        result = product_forecast_service.generate(db, current_user.id, horizon_hours)
    except ForecastCapabilityError as exc:
        raise _capability_error(exc) from exc
    except ForecastInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "FORECAST_INPUT_NOT_READY", "message": str(exc)},
        ) from exc

    origin = result["origin"]
    forecast = Forecast(
        user_id=current_user.id,
        site_id=result["site"].id,
        model_name=result["model_name"],
        horizon=horizon_hours,
        input_source="meter",
        input_start=result.get("input_start", origin - timedelta(hours=LOOKBACK_HOURS)),
        input_end=origin,
        predictions=result["prediction_rows"],
        confidence_method=result["confidence_method"],
        input_snapshot={
            "product_contract": (
                "one_site_primary_meter_30_daily_v1"
                if result["resolution"] == "daily"
                else f"one_site_primary_meter_{horizon_hours}h_v1"
            ),
            "model_version": result["model_version"],
            "method": result["method"],
            "fallback_reason": result["fallback_reason"],
            "timezone": result["site"].timezone,
            "meter_id": result["meter"].id,
            "forecast_origin": origin.isoformat(),
            "forecast_end": result["forecast_end"].isoformat(),
            "target_count": result["target_count"],
            "target_interval_hours": result["target_interval_hours"],
            "resolution": result["resolution"],
            "coverage_percent": result["coverage_percent"],
            "observed_hours": result["observed_hours"],
            "observed_days": result.get("observed_days", 0),
            "maximum_gap_hours": result["maximum_gap_hours"],
            "maximum_gap_days": result.get("maximum_gap_days", 0),
            "sources": result["sources"],
            "preprocessing": result["preprocessing"],
            "inference_seconds": result["inference_seconds"],
            "artifact_fingerprint": result["artifact_fingerprint"],
        },
    )
    db.add(forecast)
    db.commit()
    db.refresh(forecast)
    return _serialize(forecast)


def _apply_horizon_filter(query, horizon_hours: int | None):
    if horizon_hours is not None:
        query = query.filter(Forecast.horizon == horizon_hours)
    return query


@router.get("/latest", response_model=ProductForecastResponse | None)
def get_latest_forecast(
    horizon_hours: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if horizon_hours is not None:
        try:
            product_forecast_service.require_enabled(horizon_hours)
        except ForecastCapabilityError as exc:
            raise _capability_error(exc) from exc
    query = db.query(Forecast).filter(
        Forecast.user_id == current_user.id,
        Forecast.model_name.in_(PRODUCT_MODELS),
    )
    forecast = (
        _apply_horizon_filter(query, horizon_hours)
        .order_by(Forecast.created_at.desc(), Forecast.id.desc())
        .first()
    )
    return _serialize(forecast) if forecast else None


@router.get("/history", response_model=list[ProductForecastHistoryItem])
def get_forecast_history(
    horizon_hours: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if horizon_hours is not None:
        try:
            product_forecast_service.require_enabled(horizon_hours)
        except ForecastCapabilityError as exc:
            raise _capability_error(exc) from exc
    query = db.query(Forecast).filter(
        Forecast.user_id == current_user.id,
        Forecast.model_name.in_(PRODUCT_MODELS),
    )
    forecasts = (
        _apply_horizon_filter(query, horizon_hours)
        .order_by(Forecast.created_at.desc(), Forecast.id.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "id": forecast.id,
            "model_name": forecast.model_name,
            "method": (forecast.input_snapshot or {}).get("method", "unknown"),
            "horizon_hours": forecast.horizon or 24,
            "target_count": int(
                (forecast.input_snapshot or {}).get(
                    "target_count", len(forecast.predictions or [])
                )
            ),
            "target_interval_hours": int(
                (forecast.input_snapshot or {}).get("target_interval_hours", 1)
            ),
            "resolution": (forecast.input_snapshot or {}).get("resolution", "hourly"),
            "forecast_start": (forecast.input_snapshot or {}).get("forecast_origin"),
            "created_at": forecast.created_at,
        }
        for forecast in forecasts
    ]
