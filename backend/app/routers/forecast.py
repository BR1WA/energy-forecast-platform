"""
Forecast router — model inference, history, samples.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import numpy as np

from app.database import get_db
from app.models import User, Forecast, Alert, AlertConfig
from app.schemas import (
    ForecastRequest, ForecastResponse, ForecastHistoryItem,
    ModelInfo, SampleDataset
)
from app.services.auth_service import get_current_user, require_role
from app.services.forecast_service import get_forecast_service, TARGET_COLS

router = APIRouter(prefix="/api/v1/forecast", tags=["Forecasting"])


@router.get("/models", response_model=List[ModelInfo])
def list_models(current_user: User = Depends(get_current_user)):
    """List available forecasting models with metrics."""
    service = get_forecast_service()
    return service.get_available_models()


@router.get("/samples", response_model=List[SampleDataset])
def list_samples(current_user: User = Depends(get_current_user)):
    """List available sample datasets for quick demo."""
    service = get_forecast_service()
    return service.get_sample_datasets()


@router.post("/predict", response_model=ForecastResponse)
def predict(
    request: ForecastRequest,
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: Session = Depends(get_db),
):
    service = get_forecast_service()

    if not request.model_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="model_name is required for predictions",
        )

    # Get input data
    if request.sample_name:
        if request.sample_name not in service.samples:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sample '{request.sample_name}' not found. Available: {list(service.samples.keys())}",
            )
        sample = service.samples[request.sample_name]
        targets = sample['targets']
        calendar = sample['calendar']
    elif request.data:
        targets = np.array(request.data, dtype=np.float32)
        calendar = np.array(request.calendar, dtype=np.float32) if request.calendar else None
        if targets.shape != (96, 7):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Input data must be shape [96, 7], got {targets.shape}",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either 'sample_name' or 'data'",
        )

    # Get user's custom alert threshold from config
    alert_config = db.query(AlertConfig).filter(
        AlertConfig.user_id == current_user.id
    ).first()
    threshold = alert_config.threshold_kw if alert_config else 3.0

    # Run inference
    try:
        predictions, alerts_data = service.predict(
            request.model_name, targets, calendar, threshold_kw=threshold
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Model inference failed: {str(e)}",
        )

    # Save forecast to database
    forecast = Forecast(
        user_id=current_user.id,
        model_name=request.model_name,
        predictions=predictions.tolist(),
    )
    db.add(forecast)
    db.flush()

    # Save alerts and dispatch email notifications if enabled
    email_enabled = alert_config.email_enabled if alert_config else True

    for alert_data in alerts_data:
        alert = Alert(
            user_id=current_user.id,
            forecast_id=forecast.id,
            alert_type=alert_data['alert_type'],
            severity=alert_data['severity'],
            message=alert_data['message'],
            peak_kw=alert_data.get('peak_kw'),
        )
        db.add(alert)

        if email_enabled and current_user.email:
            try:
                from app.services.alert_service import send_alert_email
                send_alert_email(
                    email_to=current_user.email,
                    alert_type=alert_data['alert_type'],
                    severity=alert_data['severity'],
                    message=alert_data['message'],
                )
            except Exception as email_err:
                print(f"Failed to dispatch alert email in route: {email_err}")

    db.commit()
    db.refresh(forecast)

    return ForecastResponse(
        id=forecast.id,
        model_name=forecast.model_name,
        predictions=predictions.tolist(),
        prediction_labels=TARGET_COLS,
        created_at=forecast.created_at,
        alerts=alerts_data,
    )


@router.post("/compare")
def compare_models(
    request: ForecastRequest,
    current_user: User = Depends(require_role(["admin", "analyst"])),
):
    """Run all models on the same input for comparison."""
    service = get_forecast_service()

    if request.sample_name:
        if request.sample_name not in service.samples:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sample '{request.sample_name}' not found",
            )
        sample = service.samples[request.sample_name]
        targets = sample['targets']
        calendar = sample['calendar']
    elif request.data:
        targets = np.array(request.data, dtype=np.float32)
        calendar = np.array(request.calendar, dtype=np.float32) if request.calendar else None
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either 'sample_name' or 'data'",
        )

    results = service.predict_comparison(targets, calendar)

    return {
        'models': {
            name: preds.tolist() for name, preds in results.items()
        },
        'labels': TARGET_COLS,
        'input_data': targets[:, 0].tolist(),  # GAP lookback for chart
    }


@router.get("/history", response_model=List[ForecastHistoryItem])
def get_history(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get forecast history for current user."""
    forecasts = (
        db.query(Forecast)
        .filter(Forecast.user_id == current_user.id)
        .order_by(Forecast.created_at.desc())
        .limit(limit)
        .all()
    )

    result = []
    for f in forecasts:
        peak_power = None
        if f.predictions and len(f.predictions) > 0:
            gap_preds = [row[0] for row in f.predictions if len(row) > 0]
            peak_power = max(gap_preds) if gap_preds else None

        result.append(ForecastHistoryItem(
            id=f.id,
            model_name=f.model_name,
            created_at=f.created_at,
            peak_power=peak_power,
        ))

    return result
