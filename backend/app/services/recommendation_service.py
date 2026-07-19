"""Evidence-backed operational recommendations generated from alert rules."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Alert, Recommendation, SiteSettings


class RecommendationService:
    def create_for_alert(self, db: Session, alert: Alert) -> Recommendation | None:
        """Create one client action per alert without inventing appliance savings."""
        if alert.id is None:
            db.flush()
        existing = db.query(Recommendation).filter(Recommendation.alert_id == alert.id).first()
        if existing:
            return existing

        evidence = dict(alert.evidence_json or {})
        if alert.alert_type == "high_consumption":
            observed_kw = float(evidence.get("observed_kw") or alert.peak_kw or 0)
            threshold_kw = float(evidence.get("threshold_kw") or 0)
            excess_kw = max(0.0, observed_kw - threshold_kw)
            rate = None
            if alert.site_id:
                settings = db.query(SiteSettings).filter(SiteSettings.site_id == alert.site_id).first()
                if settings:
                    rate = max(settings.peak_rate, settings.off_peak_rate)
            excess_cost = round(excess_kw * rate, 4) if rate is not None else None
            evidence.update({"excess_kw": round(excess_kw, 3), "tariff_rate_mad_per_kwh": rate})
            recommendation = Recommendation(
                user_id=alert.user_id,
                site_id=alert.site_id,
                alert_id=alert.id,
                category="peak_load",
                title="Reduce the current load above your configured threshold",
                message=(
                    f"Measured load was {observed_kw:.2f} kW against a {threshold_kw:.2f} kW threshold. "
                    "Check discretionary loads and confirm the meter reading before taking action."
                ),
                estimated_excess_cost_per_hour_mad=excess_cost,
                evidence_json=evidence,
            )
        elif alert.alert_type == "missing_data":
            age_minutes = evidence.get("age_minutes")
            recommendation = Recommendation(
                user_id=alert.user_id,
                site_id=alert.site_id,
                alert_id=alert.id,
                category="data_quality",
                title="Restore push-meter telemetry",
                message=(
                    f"No sample has arrived for {age_minutes} minutes. Check the device, network, and push API key "
                    "before relying on current consumption or forecasts."
                    if age_minutes is not None
                    else "No recent push-meter sample is available. Check the device, network, and push API key."
                ),
                evidence_json=evidence,
            )
        else:
            return None

        db.add(recommendation)
        db.flush()
        return recommendation

    def list_for_user(self, db: Session, user_id: int, include_closed: bool = False) -> list[Recommendation]:
        query = db.query(Recommendation).filter(Recommendation.user_id == user_id)
        if not include_closed:
            query = query.filter(Recommendation.status == "open")
        return query.order_by(Recommendation.created_at.desc()).all()


recommendation_service = RecommendationService()
