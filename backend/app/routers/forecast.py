"""Product forecast API: one site, one primary meter, one 24-hour contract."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Forecast, User
from app.schemas import ForecastReadiness, ProductForecastHistoryItem, ProductForecastResponse
from app.services.auth_service import get_current_user
from app.services.product_forecast_service import (
    FALLBACK_NAME,
    MODEL_NAME,
    ForecastInputError,
    product_forecast_service,
)


router = APIRouter(prefix="/api/v1/forecast", tags=["Forecast"])
PRODUCT_MODELS = (MODEL_NAME, FALLBACK_NAME)


def _serialize(forecast: Forecast) -> dict:
    snapshot = forecast.input_snapshot or {}
    origin = snapshot.get("forecast_origin")
    rows = forecast.predictions or []
    points = []
    if origin:
        from datetime import datetime

        parsed_origin = datetime.fromisoformat(origin)
        for index, row in enumerate(rows):
            points.append(
                {
                    "timestamp": parsed_origin + timedelta(hours=index),
                    "p50_kwh": float(row[0]),
                    "p10_kwh": float(row[1]) if len(row) > 1 and row[1] is not None else None,
                    "p90_kwh": float(row[2]) if len(row) > 2 and row[2] is not None else None,
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


@router.get("/readiness", response_model=ForecastReadiness)
def get_readiness(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return product_forecast_service.readiness(db, current_user.id)


@router.post("/run", response_model=ProductForecastResponse, status_code=status.HTTP_201_CREATED)
def run_forecast(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = product_forecast_service.generate(db, current_user.id)
    except ForecastInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    origin = result["origin"]
    forecast = Forecast(
        user_id=current_user.id,
        site_id=result["site"].id,
        model_name=result["model_name"],
        horizon=24,
        input_source="meter",
        input_start=origin - timedelta(hours=336),
        input_end=origin,
        predictions=result["prediction_rows"],
        confidence_method=result["confidence_method"],
        input_snapshot={
            "product_contract": "one_site_primary_meter_24h_v1",
            "model_version": result["model_version"],
            "method": result["method"],
            "fallback_reason": result["fallback_reason"],
            "timezone": result["site"].timezone,
            "meter_id": result["meter"].id,
            "forecast_origin": origin.isoformat(),
            "forecast_end": (origin + timedelta(hours=24)).isoformat(),
            "coverage_percent": result["coverage_percent"],
            "observed_hours": result["observed_hours"],
            "maximum_gap_hours": result["maximum_gap_hours"],
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


@router.get("/latest", response_model=ProductForecastResponse | None)
def get_latest_forecast(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    forecast = (
        db.query(Forecast)
        .filter(Forecast.user_id == current_user.id, Forecast.model_name.in_(PRODUCT_MODELS))
        .order_by(Forecast.created_at.desc(), Forecast.id.desc())
        .first()
    )
    return _serialize(forecast) if forecast else None


@router.get("/history", response_model=list[ProductForecastHistoryItem])
def get_forecast_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    forecasts = (
        db.query(Forecast)
        .filter(Forecast.user_id == current_user.id, Forecast.model_name.in_(PRODUCT_MODELS))
        .order_by(Forecast.created_at.desc(), Forecast.id.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "id": forecast.id,
            "model_name": forecast.model_name,
            "method": (forecast.input_snapshot or {}).get("method", "unknown"),
            "forecast_start": (forecast.input_snapshot or {}).get("forecast_origin"),
            "created_at": forecast.created_at,
        }
        for forecast in forecasts
    ]
