"""Analytics summaries and reports backed only by persisted user data."""
from __future__ import annotations

import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Alert, Forecast, User
from app.schemas import AnalyticsSummary, ForecastHistoryItem
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])


def _forecast_values(forecast: Forecast) -> list[float]:
    return [float(row[0]) for row in (forecast.predictions or []) if row]


@router.get("/summary", response_model=AnalyticsSummary)
def get_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return user-owned forecast and alert facts.

    Historical accuracy and consumption chart series are intentionally empty
    until forecasts are linked to their matching meter observations.
    """
    forecasts = (
        db.query(Forecast)
        .filter(Forecast.user_id == current_user.id)
        .order_by(Forecast.created_at.desc())
        .all()
    )
    model_counts = (
        db.query(Forecast.model_name, func.count(Forecast.id))
        .filter(Forecast.user_id == current_user.id)
        .group_by(Forecast.model_name)
        .all()
    )
    peaks = [max(values) for forecast in forecasts if (values := _forecast_values(forecast))]
    recent_forecasts = [
        ForecastHistoryItem(
            id=forecast.id,
            model_name=forecast.model_name,
            created_at=forecast.created_at,
            peak_power=max(values) if (values := _forecast_values(forecast)) else None,
        )
        for forecast in forecasts[:10]
    ]
    total_alerts = db.query(Alert).filter(Alert.user_id == current_user.id).count()
    unacknowledged_alerts = (
        db.query(Alert)
        .filter(Alert.user_id == current_user.id, Alert.is_acknowledged.is_(False))
        .count()
    )
    return AnalyticsSummary(
        total_forecasts=len(forecasts),
        total_alerts=total_alerts,
        unacknowledged_alerts=unacknowledged_alerts,
        models_used={name: count for name, count in model_counts},
        avg_peak_power=sum(peaks) / len(peaks) if peaks else None,
        recent_forecasts=recent_forecasts,
        consumption_trend=[],
        weekly_consumption=[],
        consumption_by_hour=[],
        monthly_accuracy=[],
        model_performance=[],
        heatmap_data=[],
    )


@router.get("/report/pdf")
def export_pdf_report(
    forecast_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export a short report of the user's persisted forecast data."""
    query = db.query(Forecast).filter(Forecast.user_id == current_user.id)
    if forecast_id is not None:
        forecast = query.filter(Forecast.id == forecast_id).first()
        if forecast is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forecast not found")
    else:
        forecast = query.order_by(Forecast.created_at.desc()).first()

    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from reportlab.lib import colors

    buffer = io.BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=48, leftMargin=48, topMargin=48, bottomMargin=48)
    styles = getSampleStyleSheet()
    story = [Paragraph("Energy Forecast Report", styles["Title"]), Spacer(1, 12)]
    story.append(Paragraph(f"Account: {current_user.email}", styles["BodyText"]))
    if forecast is None:
        story.append(Spacer(1, 12))
        story.append(Paragraph("No persisted forecast is available for this account.", styles["BodyText"]))
    else:
        values = _forecast_values(forecast)
        story.extend([
            Spacer(1, 12),
            Paragraph(f"Model: {forecast.model_name}", styles["BodyText"]),
            Paragraph(f"Created: {forecast.created_at.isoformat() if forecast.created_at else 'Unknown'}", styles["BodyText"]),
            Paragraph(f"Forecast horizon: {len(values)} steps", styles["BodyText"]),
            Paragraph(f"Peak predicted demand: {max(values):.3f} kW" if values else "No prediction values were stored.", styles["BodyText"]),
            Spacer(1, 12),
        ])
        rows = [["Step", "Predicted demand (kW)"]] + [[str(index + 1), f"{value:.3f}"] for index, value in enumerate(values)]
        table = Table(rows, colWidths=[100, 180])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(table)

    document.build(story)
    buffer.seek(0)
    filename = f"energy_report_{forecast.id if forecast else 'summary'}.pdf"
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={filename}"})
