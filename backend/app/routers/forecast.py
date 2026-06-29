"""
Forecast router — model inference, history, samples.
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List, Optional
import numpy as np
import io

from app.database import get_db
from app.models import User, Forecast, Alert, AlertConfig
from app.schemas import (
    ForecastRequest, ForecastResponse, ForecastHistoryItem,
    ModelInfo, SampleDataset
)
from app.services.auth_service import get_current_user, require_role
from app.services.forecast_service import get_forecast_service, TARGET_COLS
from app.limiter import limiter
from app.config import get_settings

settings = get_settings()

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
@limiter.limit(settings.RATE_LIMIT)
def predict(
    request: Request,
    payload: ForecastRequest,
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: Session = Depends(get_db),
):
    service = get_forecast_service()

    if not payload.model_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="model_name is required for predictions",
        )

    # Determine lookback based on horizon
    lookback = 96
    if payload.horizon == 168:
        lookback = 512
    elif payload.horizon == 720:
        lookback = 1440

    # Get input data
    start_hour = None
    input_start = None
    input_end = None
    timestamps = None

    if payload.sample_name:
        if payload.sample_name not in service.samples:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sample '{payload.sample_name}' not found. Available: {list(service.samples.keys())}",
            )
        sample = service.samples[payload.sample_name]
        targets = sample['targets'][-lookback:]
        calendar = sample['calendar'][-lookback:] if sample.get('calendar') is not None else None
        start_hour = sample.get('start_hour')
        input_start = sample.get('input_start')
        input_end = sample.get('input_end')
        timestamps = sample.get('timestamps')
        if timestamps is not None:
            timestamps = timestamps[-lookback:]
    elif payload.data:
        targets = np.array(payload.data, dtype=np.float32)
        calendar = np.array(payload.calendar, dtype=np.float32) if payload.calendar else None
        if targets.shape != (lookback, 7):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Input data must be shape [{lookback}, 7] for horizon {payload.horizon}h, got {targets.shape}",
            )
        import datetime
        input_end = datetime.datetime.now(datetime.timezone.utc)
        input_start = input_end - datetime.timedelta(hours=lookback-1)
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
            payload.model_name, targets, calendar, threshold_kw=threshold, 
            start_hour=start_hour, horizon=payload.horizon, timestamps=timestamps
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Model inference failed: {str(e)}",
        )

    # Save forecast to database, using the model name with horizon suffix for clarity
    model_db_name = payload.model_name
    if payload.horizon != 24 and not payload.model_name.endswith(f"_{payload.horizon}"):
        model_db_name = f"{payload.model_name}_{payload.horizon}"

    forecast = Forecast(
        user_id=current_user.id,
        model_name=model_db_name,
        predictions=predictions.tolist(),
        input_start=input_start,
        input_end=input_end,
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

    # Return the full lookback window of actual GAP values as input_data for charting
    input_gap = targets[:, 0].tolist()  # All 96 hours of Global Active Power

    return ForecastResponse(
        id=forecast.id,
        model_name=forecast.model_name,
        predictions=predictions.tolist(),
        prediction_labels=TARGET_COLS,
        created_at=forecast.created_at,
        alerts=alerts_data,
        input_data=input_gap,
    )


@router.post("/compare")
def compare_models(
    request: ForecastRequest,
    current_user: User = Depends(require_role(["admin", "analyst"])),
):
    """Run all models on the same input for comparison."""
    service = get_forecast_service()

    # Determine lookback based on horizon
    lookback = 96
    if request.horizon == 168:
        lookback = 512
    elif request.horizon == 720:
        lookback = 1440

    timestamps = None

    if request.sample_name:
        if request.sample_name not in service.samples:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sample '{request.sample_name}' not found",
            )
        sample = service.samples[request.sample_name]
        targets = sample['targets'][-lookback:]
        calendar = sample['calendar'][-lookback:] if sample.get('calendar') is not None else None
        timestamps = sample.get('timestamps')
        if timestamps is not None:
            timestamps = timestamps[-lookback:]
    elif request.data:
        targets = np.array(request.data, dtype=np.float32)
        calendar = np.array(request.calendar, dtype=np.float32) if request.calendar else None
        if targets.shape != (lookback, 7):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Input data must be shape [{lookback}, 7] for horizon {request.horizon}h, got {targets.shape}",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either 'sample_name' or 'data'",
        )

    results = service.predict_comparison(targets, calendar, horizon=request.horizon, timestamps=timestamps)

    return {
        'models': {
            name: preds.tolist() for name, preds in results.items()
        },
        'labels': TARGET_COLS,
        'input_data': targets[:, 0].tolist(),  # GAP lookback for chart
    }


@router.post("/predict/upload", response_model=ForecastResponse)
@limiter.limit(settings.RATE_LIMIT)
def predict_upload(
    request: Request,
    file: UploadFile = File(...),
    model_name: str = Form(...),
    horizon: int = Form(24),
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: Session = Depends(get_db),
):
    """Run forecast from an uploaded CSV file."""
    import pandas as pd

    if not file.filename or not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are accepted.",
        )

    try:
        contents = file.file.read()
        df = pd.read_csv(io.BytesIO(contents), index_col=0, parse_dates=True)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse CSV: {str(e)}",
        )

    # Determine lookback based on horizon
    lookback = 96
    if horizon == 168:
        lookback = 512
    elif horizon == 720:
        lookback = 1440

    service = get_forecast_service()

    # Validate rows count before slicing
    if len(df) < lookback:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV must have at least {lookback} rows for horizon {horizon}h, got {len(df)}.",
        )
    df = df.tail(lookback)

    # Validate columns
    missing = [c for c in TARGET_COLS if c not in df.columns]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV missing required columns: {missing}. Expected: {TARGET_COLS}",
        )

    targets = df[TARGET_COLS].values.astype(np.float32)

    # Generate cyclical calendar features from the datetime index
    hours = df.index.hour.values
    days = df.index.dayofweek.values
    months = df.index.month.values
    from app.services.forecast_service import generate_calendar_features
    calendar = generate_calendar_features(hours, days, months)

    # Get user's custom alert threshold
    alert_config = db.query(AlertConfig).filter(
        AlertConfig.user_id == current_user.id
    ).first()
    threshold = alert_config.threshold_kw if alert_config else 3.0

    # Run inference
    start_hour = int((df.index[-1].hour + 1) % 24)
    try:
        predictions, alerts_data = service.predict(
            model_name, targets, calendar, threshold_kw=threshold, 
            start_hour=start_hour, horizon=horizon, timestamps=df.index
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Model inference failed: {str(e)}",
        )

    import datetime
    input_start = df.index[0].to_pydatetime()
    input_end = df.index[-1].to_pydatetime()
    if input_start.tzinfo is None:
        input_start = input_start.replace(tzinfo=datetime.timezone.utc)
        input_end = input_end.replace(tzinfo=datetime.timezone.utc)

    # Save forecast
    forecast = Forecast(
        user_id=current_user.id,
        model_name=model_name,
        predictions=predictions.tolist(),
        input_start=input_start,
        input_end=input_end,
    )
    db.add(forecast)
    db.flush()

    # Save alerts
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
            except Exception:
                pass

    db.commit()
    db.refresh(forecast)

    input_gap = targets[:, 0].tolist()

    return ForecastResponse(
        id=forecast.id,
        model_name=forecast.model_name,
        predictions=predictions.tolist(),
        prediction_labels=TARGET_COLS,
        created_at=forecast.created_at,
        alerts=alerts_data,
        input_data=input_gap,
    )


@router.post("/compare/upload")
def compare_upload(
    file: UploadFile = File(...),
    horizon: int = Form(24),
    current_user: User = Depends(require_role(["admin", "analyst"])),
):
    """Run comparison from an uploaded CSV file."""
    import pandas as pd

    if not file.filename or not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are accepted.",
        )

    try:
        contents = file.file.read()
        df = pd.read_csv(io.BytesIO(contents), index_col=0, parse_dates=True)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse CSV: {str(e)}",
        )

    # Determine lookback based on horizon
    lookback = 96
    if horizon == 168:
        lookback = 512
    elif horizon == 720:
        lookback = 1440

    service = get_forecast_service()
    if len(df) < lookback:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV must have at least {lookback} rows for horizon {horizon}h, got {len(df)}.",
        )
    df = df.tail(lookback)

    missing = [c for c in TARGET_COLS if c not in df.columns]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV missing required columns: {missing}.",
        )

    targets = df[TARGET_COLS].values.astype(np.float32)
    hours = df.index.hour.values
    days = df.index.dayofweek.values
    months = df.index.month.values
    from app.services.forecast_service import generate_calendar_features
    calendar = generate_calendar_features(hours, days, months)

    results = service.predict_comparison(targets, calendar, horizon=horizon, timestamps=df.index)

    return {
        'models': {name: preds.tolist() for name, preds in results.items()},
        'labels': TARGET_COLS,
        'input_data': targets[:, 0].tolist(),
    }


@router.post("/smart-meter/sync", response_model=ForecastResponse)
def sync_smart_meter_forecast(
    payload: ForecastRequest,
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: Session = Depends(get_db),
):
    """
    Sync live readings from the simulated Enedis Linky smart meter,
    run the selected forecast model, and save the forecast to the database.
    """
    import datetime
    from datetime import timezone
    import pandas as pd
    from app.services.smart_meter_service import get_smart_meter_service
    from app.services.forecast_service import get_forecast_service
    
    model_name = payload.model_name or 'sota'
    horizon = payload.horizon or 24
    
    # Determine lookback based on horizon
    lookback = 96
    if horizon == 168:
        lookback = 512
    elif horizon == 720:
        lookback = 1440

    service = get_forecast_service()
    
    # Map model name based on horizon if not ended with it
    full_model_key = model_name
    if horizon != 24 and not model_name.endswith(f"_{horizon}"):
        full_model_key = f"{model_name}_{horizon}"
        
    if full_model_key not in service.models:
        if model_name in service.models:
            full_model_key = model_name
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Model '{model_name}' for horizon {horizon}h is not loaded. Available: {list(service.models.keys())}"
            )

    # Fetch live readings with dynamic lookback
    meter_service = get_smart_meter_service()
    targets = meter_service.fetch_live_readings(db=db, limit=lookback) # Shape (lookback, 7)
    
    # Generate cyclical calendar features for lookback hours
    now = datetime.datetime.now(timezone.utc)
    hours = []
    days = []
    months = []
    for h in range(lookback):
        step_time = now - datetime.timedelta(hours=(lookback - 1 - h))
        hours.append(step_time.hour)
        days.append(step_time.weekday())
        months.append(step_time.month)
        
    hours = np.array(hours)
    days = np.array(days)
    months = np.array(months)
    
    from app.services.forecast_service import generate_calendar_features
    calendar = generate_calendar_features(hours, days, months)
    timestamps = pd.date_range(end=now, periods=lookback, freq='h')

    # Get user alert threshold config
    alert_config = db.query(AlertConfig).filter(AlertConfig.user_id == current_user.id).first()
    threshold = alert_config.threshold_kw if alert_config else 3.0

    start_hour = (now + datetime.timedelta(hours=1)).hour # Start of forecast horizon
    
    try:
        predictions, alerts_data = service.predict(
            model_name, targets, calendar, threshold_kw=threshold, 
            start_hour=start_hour, horizon=horizon, timestamps=timestamps
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Smart meter forecast execution failed: {str(e)}",
        )

    # Save to DB
    input_end = now
    input_start = now - datetime.timedelta(hours=lookback - 1)
    forecast = Forecast(
        user_id=current_user.id,
        model_name=full_model_key,
        predictions=predictions.tolist(),
        input_start=input_start,
        input_end=input_end,
    )
    db.add(forecast)
    db.flush()

    # Save alerts
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
                print(f"[Smart Meter Sync] Failed to dispatch alert email: {email_err}")

    db.commit()
    db.refresh(forecast)

    return ForecastResponse(
        id=forecast.id,
        model_name=model_name,
        predictions=predictions.tolist(),
        prediction_labels=TARGET_COLS,
        created_at=forecast.created_at,
        alerts=[
            {
                "alert_type": a['alert_type'],
                "severity": a['severity'],
                "message": a['message'],
                "peak_kw": a.get('peak_kw')
            } for a in alerts_data
        ],
        input_data=targets[:, 0].tolist(),
    )


@router.post("/smart-meter/compare")
def compare_smart_meter_forecasts(
    payload: ForecastRequest,
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: Session = Depends(get_db),
):
    """
    Sync live readings from the simulated Enedis Linky smart meter,
    run all forecast models for the chosen horizon, and return comparison results.
    """
    import datetime
    from datetime import timezone
    import pandas as pd
    from app.services.smart_meter_service import get_smart_meter_service
    
    horizon = payload.horizon or 24
    
    # Determine lookback based on horizon
    lookback = 96
    if horizon == 168:
        lookback = 512
    elif horizon == 720:
        lookback = 1440

    # Fetch live readings with dynamic lookback
    meter_service = get_smart_meter_service()
    targets = meter_service.fetch_live_readings(db=db, limit=lookback) # Shape (lookback, 7)
    
    # Generate cyclical calendar features for lookback hours
    now = datetime.datetime.now(timezone.utc)
    hours = []
    days = []
    months = []
    for h in range(lookback):
        step_time = now - datetime.timedelta(hours=(lookback - 1 - h))
        hours.append(step_time.hour)
        days.append(step_time.weekday())
        months.append(step_time.month)
        
    hours = np.array(hours)
    days = np.array(days)
    months = np.array(months)
    
    from app.services.forecast_service import generate_calendar_features
    calendar = generate_calendar_features(hours, days, months)
    timestamps = pd.date_range(end=now, periods=lookback, freq='h')

    service = get_forecast_service()
    results = service.predict_comparison(targets, calendar, horizon=horizon, timestamps=timestamps)

    return {
        'models': {name: preds.tolist() for name, preds in results.items()},
        'labels': TARGET_COLS,
        'input_data': targets[:, 0].tolist(),
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


@router.websocket("/smart-meter/live-ws")
async def live_smart_meter_websocket(websocket: WebSocket, token: str = None, db: Session = Depends(get_db)):
    import asyncio
    from app.services.smart_meter_service import get_smart_meter_service
    from app.services.forecast_service import get_forecast_service
    from app.database import SessionLocal
    from app.models import SmartMeterReading, User
    from app.services.auth_service import decode_token
    from datetime import datetime, timezone

    if not token:
        await websocket.accept()
        await websocket.close(code=1008, reason="Token is missing")
        return
        
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await websocket.accept()
            await websocket.close(code=1008, reason="Invalid token type")
            return
            
        user_id = payload.get("sub")
        if not user_id:
            await websocket.accept()
            await websocket.close(code=1008, reason="Invalid token payload")
            return
            
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user or not user.is_active:
            await websocket.accept()
            await websocket.close(code=1008, reason="User unauthorized or inactive")
            return
    except Exception as e:
        await websocket.accept()
        await websocket.close(code=1008, reason=f"Authentication failed: {str(e)}")
        return

    await websocket.accept()
    print("[WS-LIVE] Client connected to live smart meter telemetry.")
    
    meter_service = get_smart_meter_service()
    forecast_service = get_forecast_service()
    
    try:
        while True:
            # 1. Fetch live reading
            reading = meter_service.fetch_single_live_reading()
            
            # 2. Save reading to database
            db_session = SessionLocal()
            try:
                db_reading = SmartMeterReading(
                    gap=reading["gap"],
                    grp=reading["grp"],
                    voltage=reading["voltage"],
                    intensity=reading["intensity"],
                    sub_metering_1=reading["sub_metering_1"],
                    sub_metering_2=reading["sub_metering_2"],
                    sub_metering_3=reading["sub_metering_3"],
                    timestamp=datetime.now(timezone.utc)
                )
                db_session.add(db_reading)
                db_session.commit()
            except Exception as db_err:
                print(f"[WS-LIVE] Error saving reading to database: {db_err}")
            finally:
                db_session.close()
            
            # 3. Generate 96h lookback and run model prediction
            try:
                targets = meter_service.fetch_live_readings() # returns [96, 7]
                preds, _ = forecast_service.predict(model_name='sota', targets=targets)
                gap_predictions = [round(float(p), 3) for p in preds[:, 0]]
            except Exception as pred_err:
                print(f"[WS-LIVE] Forecast prediction error: {pred_err}")
                gap_predictions = []
                
            # 4. Attach predictions to payload and send
            reading["predictions"] = gap_predictions
            await websocket.send_json(reading)
            
            await asyncio.sleep(2.0)
    except Exception as e:
        print(f"[WS-LIVE] Telemetry stream ended: {e}")

