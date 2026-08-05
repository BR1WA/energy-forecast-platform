"""Owned report summaries and forecast PDF export."""
from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Alert, Forecast, Recommendation, Site, SiteSettings, User
from app.schemas import AnalyticsSummary, ReportForecastItem
from app.services.auth_service import get_current_user
from app.services.product_forecast_service import PRODUCT_MODEL_NAMES


router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])
PRODUCT_MODELS = PRODUCT_MODEL_NAMES
FORECAST_PEAK_SAMPLE_LIMIT = 500


def _forecast_values(forecast: Forecast) -> list[float]:
    return [float(row[0]) for row in (forecast.predictions or []) if row and row[0] is not None]


def _report_item(forecast: Forecast) -> ReportForecastItem:
    values = _forecast_values(forecast)
    snapshot = forecast.input_snapshot or {}
    return ReportForecastItem(
        id=forecast.id,
        model_name=forecast.model_name,
        method=snapshot.get("method", "unknown"),
        horizon_hours=forecast.horizon or 24,
        created_at=forecast.created_at,
        forecast_start=snapshot.get("forecast_origin"),
        peak_hourly_kwh=max(values) if values else None,
        total_kwh=sum(values) if values else None,
    )


@router.get("/summary", response_model=AnalyticsSummary)
def get_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    total_forecasts = (
        db.query(Forecast.id)
        .filter(Forecast.user_id == current_user.id, Forecast.model_name.in_(PRODUCT_MODELS))
        .count()
    )
    # Prediction arrays can contain 168 points. Keep the report summary's memory
    # use bounded even for long-lived accounts while retaining a representative
    # recent peak sample and the exact all-time count.
    forecasts = (
        db.query(Forecast)
        .filter(Forecast.user_id == current_user.id, Forecast.model_name.in_(PRODUCT_MODELS))
        .order_by(Forecast.created_at.desc(), Forecast.id.desc())
        .limit(FORECAST_PEAK_SAMPLE_LIMIT)
        .all()
    )
    peaks = [max(values) for forecast in forecasts if (values := _forecast_values(forecast))]
    total_alerts = db.query(Alert).filter(Alert.user_id == current_user.id).count()
    open_alerts = (
        db.query(Alert)
        .filter(Alert.user_id == current_user.id, Alert.resolved_at.is_(None))
        .count()
    )
    resolved_alerts = total_alerts - open_alerts
    open_recommendations = (
        db.query(Recommendation)
        .filter(Recommendation.user_id == current_user.id, Recommendation.status == "open")
        .count()
    )
    return AnalyticsSummary(
        total_forecasts=total_forecasts,
        total_alerts=total_alerts,
        open_alerts=open_alerts,
        resolved_alerts=resolved_alerts,
        open_recommendations=open_recommendations,
        avg_forecast_peak_kwh=sum(peaks) / len(peaks) if peaks else None,
        recent_forecasts=[_report_item(forecast) for forecast in forecasts[:10]],
    )


@router.get("/report/pdf")
def export_pdf_report(
    forecast_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Forecast).filter(
        Forecast.user_id == current_user.id,
        Forecast.model_name.in_(PRODUCT_MODELS),
    )
    if forecast_id is not None:
        forecast = query.filter(Forecast.id == forecast_id).first()
        if forecast is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forecast not found")
    else:
        forecast = query.order_by(Forecast.created_at.desc(), Forecast.id.desc()).first()

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=42,
        leftMargin=42,
        topMargin=42,
        bottomMargin=42,
        title="Energy Forecast Report",
    )
    styles = getSampleStyleSheet()
    report_title = "Energy Forecast Report"
    if forecast is not None:
        report_horizon = forecast.horizon or len(forecast.predictions or []) or 24
        report_title = (
            "7-Day / 168-Hour Energy Forecast Report"
            if report_horizon == 168
            else "Next 24 Hours Energy Forecast Report"
        )
    story = [Paragraph(report_title, styles["Title"]), Spacer(1, 10)]
    story.append(Paragraph(f"Account: {current_user.email}", styles["BodyText"]))
    story.append(Paragraph(f"Generated: {datetime.now(timezone.utc).isoformat()}", styles["BodyText"]))

    if forecast is None:
        story.extend([Spacer(1, 12), Paragraph("No persisted product forecast is available for this account.", styles["BodyText"])])
    else:
        snapshot = forecast.input_snapshot or {}
        site = (
            db.query(Site)
            .filter(Site.id == forecast.site_id, Site.user_id == current_user.id)
            .first()
        )
        site_settings = db.query(SiteSettings).filter(SiteSettings.site_id == site.id).first() if site else None
        values = _forecast_values(forecast)
        horizon_hours = forecast.horizon or len(forecast.predictions or []) or 24
        origin_text = snapshot.get("forecast_origin")
        origin = datetime.fromisoformat(origin_text) if origin_text else None
        sources = ", ".join(snapshot.get("sources", [])) or "Not recorded"
        story.extend(
            [
                Spacer(1, 12),
                Paragraph(f"Site: {site.name if site else 'Not recorded'}", styles["BodyText"]),
                Paragraph(f"Timezone: {snapshot.get('timezone') or (site.timezone if site else 'Not recorded')}", styles["BodyText"]),
                Paragraph(f"Input period: {forecast.input_start.isoformat() if forecast.input_start else 'Not recorded'} to {forecast.input_end.isoformat() if forecast.input_end else 'Not recorded'}", styles["BodyText"]),
                Paragraph(f"Data source(s): {sources}", styles["BodyText"]),
                Paragraph(f"Input coverage: {snapshot.get('coverage_percent', 'Not recorded')}%", styles["BodyText"]),
                Paragraph(f"Forecast method: {snapshot.get('method', 'unknown')}", styles["BodyText"]),
                Paragraph(f"Model: {forecast.model_name} version {snapshot.get('model_version', 'unknown')}", styles["BodyText"]),
                Paragraph(f"Output: {horizon_hours} hourly energy values in kWh", styles["BodyText"]),
                Paragraph(f"Total median energy: {sum(values):.3f} kWh" if values else "No prediction values were stored.", styles["BodyText"]),
                Paragraph(f"Peak hourly energy: {max(values):.3f} kWh" if values else "Peak hourly energy is unavailable.", styles["BodyText"]),
                Paragraph(
                    f"Tariff context: {site_settings.currency}; peak {site_settings.peak_rate:.3f}, off-peak {site_settings.off_peak_rate:.3f} per kWh"
                    if site_settings
                    else "Tariff context was not recorded.",
                    styles["BodyText"],
                ),
                Paragraph(f"Uncertainty: {forecast.confidence_method or 'No uncertainty interval is available.'}", styles["BodyText"]),
            ]
        )
        if snapshot.get("fallback_reason"):
            story.append(Paragraph(f"Fallback reason: {snapshot['fallback_reason']}", styles["BodyText"]))
        story.extend([Spacer(1, 10), Paragraph("Client-site forecast accuracy has not yet been established.", styles["Italic"]), Spacer(1, 12)])

        rows = [["Target time", "P10 kWh", "Median kWh", "P90 kWh"]]
        for index, row in enumerate(forecast.predictions or []):
            timestamp = origin + timedelta(hours=index) if origin else None
            rows.append(
                [
                    timestamp.isoformat() if timestamp else f"H+{index + 1}",
                    f"{float(row[1]):.3f}" if len(row) > 1 and row[1] is not None else "-",
                    f"{float(row[0]):.3f}",
                    f"{float(row[2]):.3f}" if len(row) > 2 and row[2] is not None else "-",
                ]
            )
        table = Table(rows, repeatRows=1, colWidths=[210, 70, 80, 70])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ]
            )
        )
        story.append(table)

    document.build(story)
    buffer.seek(0)
    filename = (
        f"energy_forecast_{forecast.horizon or 24}h_{forecast.id}.pdf"
        if forecast
        else "energy_forecast_empty.pdf"
    )
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
