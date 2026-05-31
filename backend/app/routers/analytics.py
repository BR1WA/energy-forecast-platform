"""
Analytics router — historical forecast data and summary statistics.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import User, Forecast, Alert
from app.schemas import AnalyticsSummary, ForecastHistoryItem
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
def get_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get analytics summary for the current user."""
    # Total forecasts
    total_forecasts = (
        db.query(Forecast)
        .filter(Forecast.user_id == current_user.id)
        .count()
    )

    # Total alerts
    total_alerts = (
        db.query(Alert)
        .filter(Alert.user_id == current_user.id)
        .count()
    )

    # Unacknowledged alerts
    unack_alerts = (
        db.query(Alert)
        .filter(Alert.user_id == current_user.id, Alert.is_acknowledged == False)
        .count()
    )

    # Models used
    model_counts = (
        db.query(Forecast.model_name, func.count(Forecast.id))
        .filter(Forecast.user_id == current_user.id)
        .group_by(Forecast.model_name)
        .all()
    )
    models_used = {name: count for name, count in model_counts}

    # Average peak power
    forecasts = (
        db.query(Forecast)
        .filter(Forecast.user_id == current_user.id)
        .all()
    )

    peak_powers = []
    for f in forecasts:
        if f.predictions and len(f.predictions) > 0:
            gap_preds = [row[0] for row in f.predictions if len(row) > 0]
            if gap_preds:
                peak_powers.append(max(gap_preds))

    avg_peak = sum(peak_powers) / len(peak_powers) if peak_powers else None

    # Recent forecasts
    recent = (
        db.query(Forecast)
        .filter(Forecast.user_id == current_user.id)
        .order_by(Forecast.created_at.desc())
        .limit(10)
        .all()
    )

    recent_items = []
    for f in recent:
        peak = None
        if f.predictions and len(f.predictions) > 0:
            gap_preds = [row[0] for row in f.predictions if len(row) > 0]
            peak = max(gap_preds) if gap_preds else None
        recent_items.append(ForecastHistoryItem(
            id=f.id,
            model_name=f.model_name,
            created_at=f.created_at,
            peak_power=peak,
        ))

    return AnalyticsSummary(
        total_forecasts=total_forecasts,
        total_alerts=total_alerts,
        unacknowledged_alerts=unack_alerts,
        models_used=models_used,
        avg_peak_power=avg_peak,
        recent_forecasts=recent_items,
    )
