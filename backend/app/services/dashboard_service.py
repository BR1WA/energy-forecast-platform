"""Evidence-only dashboard aggregates for the authenticated user's energy data."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Alert, Forecast, Meter, Site, SmartMeterReading
from app.services.consumption_service import consumption_service
from app.services.simulation_service import simulation_service
from app.services.weather_service import weather_service
from app.services.recommendation_service import recommendation_service


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class DashboardService:
    def _readings(self, db: Session, user_id: int, limit: int = 1440) -> list[SmartMeterReading]:
        return (
            db.query(SmartMeterReading)
            .join(Meter, SmartMeterReading.meter_id == Meter.id)
            .join(Site, Meter.site_id == Site.id)
            .filter(Site.user_id == user_id)
            .order_by(SmartMeterReading.timestamp.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def _greeting() -> str:
        hour = datetime.now().hour
        if hour < 12:
            return "Good Morning"
        if hour < 17:
            return "Good Afternoon"
        return "Good Evening"

    def _latest_forecast(self, db: Session, user_id: int) -> Forecast | None:
        return (
            db.query(Forecast)
            .filter(Forecast.user_id == user_id)
            .order_by(Forecast.created_at.desc())
            .first()
        )

    def _forecast_payload(
        self,
        db: Session,
        user_id: int,
        forecast: Forecast | None,
    ) -> dict:
        if not forecast or not forecast.predictions:
            return {
                "points": [],
                "peak_hour": None,
                "expected_consumption": None,
                "estimated_cost": None,
                "forecast_reliability": "Not available",
                "explainability": "Run a forecast after importing or ingesting enough meter readings.",
                "validation": {"available": False, "message": "No persisted forecast is available."},
                "model_version": None,
                "confidence_method": None,
            }

        values = [float(row[0]) for row in forecast.predictions if row]
        points = [{"time": f"H+{index + 1}", "predicted": round(value, 3)} for index, value in enumerate(values)]
        peak_index = values.index(max(values)) if values else None
        validation = {
            "available": False,
            "message": "Outcome validation is unavailable until exact forecast target timestamps are matched.",
        }

        return {
            "points": points,
            "peak_hour": f"H+{peak_index + 1}" if peak_index is not None else None,
            "expected_consumption": round(sum(values), 3) if values else None,
            "estimated_cost": None,
            "forecast_reliability": "Point forecast (not calibrated)",
            "explainability": f"Persisted forecast from {forecast.model_name}.",
            "validation": validation,
            "model_version": forecast.model_name,
            "confidence_method": forecast.confidence_method,
        }

    def get_summary(self, db: Session, user_id: int, lat: float | None = None, lon: float | None = None):
        readings = self._readings(db, user_id)
        latest = readings[0] if readings else None
        monthly = consumption_service.get_monthly_summary(db, user_id)
        forecast = self._latest_forecast(db, user_id)
        forecast_payload = self._forecast_payload(db, user_id, forecast)
        simulation = simulation_service.get_state(db, user_id)
        alerts = (
            db.query(Alert)
            .filter(Alert.user_id == user_id)
            .order_by(Alert.created_at.desc())
            .limit(10)
            .all()
        )
        recommendations = recommendation_service.list_for_user(db, user_id)
        excess_cost_per_hour = round(
            sum(item.estimated_excess_cost_per_hour_mad or 0 for item in recommendations), 4
        )

        weather_data = None
        try:
            weather_data = weather_service.get_weather(lat or 33.5731, lon or -7.5898, mode="current")
        except Exception:
            weather_data = None

        active_power = latest.gap if latest else 0.0
        source = latest.source if latest else None
        budget = monthly["budget"]
        progress_pct = budget["progress_pct"] or 0.0
        if progress_pct > 90:
            mission_status = "Over Budget"
        elif progress_pct > 70:
            mission_status = "At Risk"
        else:
            mission_status = "On Track"

        today_story = [
            {"icon": "check", "text": f"Latest reading source: {source or 'no meter reading yet'}."},
            {"icon": "check", "text": "Billing uses the configured site peak and off-peak rates."},
        ]
        if budget["target_mad"] is not None:
            today_story.append({"icon": "alert" if progress_pct >= 75 else "check", "text": f"Budget progress: {progress_pct}% of the monthly target."})

        timeline = [
            {
                "time": _as_utc(alert.created_at).strftime("%H:%M") if alert.created_at else "",
                "event": alert.message or alert.alert_type,
                "severity": "warning" if alert.severity == "high" else "info",
            }
            for alert in alerts
        ]
        if simulation["is_running"]:
            timeline.insert(0, {"time": "", "event": "Simulator session is running.", "severity": "info"})

        appliances = []
        if simulation["is_running"]:
            appliances = [
                {"name": "Simulator", "status": "Running", "level": "SIMULATED"},
                {"name": "Configured occupants", "status": "Simulation", "level": str(simulation["occupants"])},
            ]

        forecast_available = bool(forecast_payload["points"])
        confidence_basis = "Calibrated confidence is not available."
        if forecast_available:
            confidence_basis = forecast_payload["confidence_method"] or "Point forecast; calibrated interval not available."

        return {
            "executive": {
                "greeting": self._greeting(),
                "household_name": "Your site",
                "energy_score": 0,
                "estimated_bill": monthly["total_cost"],
                "actionable_recommendations": len(recommendations),
                "forecast_reliability": forecast_payload["forecast_reliability"],
                "current_tariff_tier": "Site peak/off-peak tariff",
                "summary_sentence": "Import meter data or run the labelled simulator to populate your dashboard.",
                "today_story": today_story,
                "bill_delta": None,
                "score_delta": None,
                "proactive_sentence": (
                    f"{len(recommendations)} evidence-backed action(s) are ready for review."
                    if recommendations
                    else "Recommendations appear only when supported by measured data."
                ),
            },
            "assistant": {
                "headline": "Evidence-based status",
                "body": (
                    recommendations[0].message
                    if recommendations
                    else "No appliance-level recommendations are generated without device or sub-meter evidence."
                ),
                "warning": None,
                "recommended_action": recommendations[0].title if recommendations else "Review your meter data quality and configured tariff.",
                "response": "Review the evidence and complete or dismiss each action." if recommendations else "Recommendations are unavailable until enough measured data is available.",
                "quick_actions": ["View Forecast", "Run Simulation", "View Budget", "Export Report"],
            },
            "live_status": {
                "appliances": appliances,
                "load": {
                    "active_power": round(active_power, 2),
                    "voltage": round(latest.voltage, 1) if latest else None,
                    "current": round(latest.intensity, 2) if latest else None,
                    "frequency": None,
                    "source": source,
                },
            },
            "live_consumption": {
                "current_power": round(active_power, 2),
                "today_energy": monthly["total_kwh"],
                "today_peak": monthly["peak_kw"],
                "average_load": round(sum(reading.gap for reading in readings) / len(readings), 2) if readings else None,
            },
            "energy_flow": {
                "solar_generation": 0.0,
                "grid_import": round(active_power, 2),
                "house_consumption": round(active_power, 2),
                "solar_offset_pct": 0,
                "current_tariff_rate": monthly["tariff"].get("peak_rate"),
            },
            "forecast": forecast_payload,
            "recommendations": {
                "priority_list": [
                    {
                        "id": item.id,
                        "title": item.title,
                        "message": item.message,
                        "category": item.category,
                        "estimated_excess_cost_per_hour_mad": item.estimated_excess_cost_per_hour_mad,
                    }
                    for item in recommendations[:3]
                ],
                "excess_cost_per_hour_mad": excess_cost_per_hour if recommendations else None,
            },
            "budget": {
                "target": budget["target_mad"],
                "current_cost": monthly["total_cost"],
                "progress_pct": progress_pct,
                "projected_cost": budget["projected_mad"],
                "tariff_tier": "Site peak/off-peak tariff",
                "remaining": budget["remaining_mad"],
                "projected_without_recs": budget["projected_mad"],
                "projected_with_recs": budget["projected_mad"],
                "savings_if_applied": 0,
                "mission_status": mission_status,
            },
            "timeline": timeline,
            "weather": weather_data,
            "intelligence_radar": {
                "dimensions": [
                    {"label": "Budget Health", "value": round(max(0, 100 - progress_pct), 1), "unit": "%", "status": "green" if progress_pct < 70 else "amber"},
                    {"label": "Forecast", "value": "Available" if forecast_available else "Not run", "unit": "", "status": "blue"},
                ],
                "condition": "Measured data only",
                "message": "The dashboard does not infer appliance state or savings without evidence.",
                "confidence": {"pct": None, "basis": confidence_basis, "trend": "Not calibrated"},
            },
            "today_vs_yesterday": {"metrics": []},
            "ai_decisions": [
                {"text": "Persisted forecast available" if forecast_available else "No persisted forecast available", "done": forecast_available},
                {"text": "Simulator is running" if simulation["is_running"] else "Simulator is stopped", "done": simulation["is_running"]},
            ],
        }


dashboard_service = DashboardService()
