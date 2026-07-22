"""Persisted, evidence-backed alert evaluation for owned meter data."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import Alert, AlertConfig, Meter, Site, SmartMeterReading, User
from app.services.email_service import enqueue_email
from app.config import get_settings
from app.services.recommendation_service import recommendation_service

logger = logging.getLogger(__name__)


def critical_email_delivery_status(user: User) -> tuple[bool, str | None]:
    """Return whether this account may opt in to critical-alert delivery."""
    if not get_settings().EMAIL_DELIVERY_ENABLED:
        return False, "mail_disabled"
    if user.email_verified_at is None:
        return False, "email_unverified"
    return True, None


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class AlertService:
    def get_recent_alerts(self, db: Session, user_id: int, limit: int = 5):
        alerts = db.query(Alert).filter(Alert.user_id == user_id).order_by(Alert.created_at.desc()).limit(limit).all()
        return [
            {
                "id": alert.id,
                "type": alert.alert_type,
                "severity": alert.severity,
                "message": alert.message,
                "timestamp": alert.created_at.isoformat() if alert.created_at else None,
            }
            for alert in alerts
        ]

    def config_for_site(self, db: Session, site: Site) -> AlertConfig:
        config = (
            db.query(AlertConfig)
            .filter(AlertConfig.user_id == site.user_id, AlertConfig.site_id == site.id)
            .first()
        )
        if config is not None:
            return config

        legacy_config = (
            db.query(AlertConfig)
            .filter(AlertConfig.user_id == site.user_id, AlertConfig.site_id.is_(None))
            .first()
        )
        if legacy_config is not None:
            legacy_config.site_id = site.id
            return legacy_config

        config = AlertConfig(user_id=site.user_id, site_id=site.id)
        db.add(config)
        db.flush()
        return config

    def _create_if_due(
        self,
        db: Session,
        *,
        site: Site,
        config: AlertConfig,
        rule_key: str,
        alert_type: str,
        severity: str,
        message: str,
        peak_kw: float | None,
        evidence: dict,
        now: datetime,
    ) -> Alert | None:
        unresolved = (
            db.query(Alert.id)
            .filter(
                Alert.user_id == site.user_id,
                Alert.site_id == site.id,
                Alert.rule_key == rule_key,
                Alert.resolved_at.is_(None),
            )
            .first()
        )
        if unresolved is not None:
            return None

        cutoff = now - timedelta(minutes=config.cooldown_minutes)
        recent = (
            db.query(Alert.id)
            .filter(
                Alert.user_id == site.user_id,
                Alert.site_id == site.id,
                Alert.rule_key == rule_key,
                Alert.created_at >= cutoff,
            )
            .first()
        )
        if recent is not None:
            return None

        alert = Alert(
            user_id=site.user_id,
            site_id=site.id,
            alert_type=alert_type,
            rule_key=rule_key,
            severity=severity,
            message=message,
            peak_kw=peak_kw,
            evidence_json=evidence,
        )
        db.add(alert)
        db.flush()
        recommendation_service.create_for_alert(db, alert)
        if severity == "critical" and config.email_enabled:
            user = db.query(User).filter(User.id == site.user_id).first()
            if user and critical_email_delivery_status(user)[0]:
                public_url = get_settings().PUBLIC_FRONTEND_URL.rstrip("/")
                enqueue_email(
                    db,
                    user_id=user.id,
                    recipient=user.email,
                    template="critical_alert",
                    dedup_key=f"critical-alert:{alert.id}:{user.id}",
                    payload={
                        "alert_id": alert.id,
                        "title": alert.alert_type.replace("_", " ").title(),
                        "message": message,
                        "evidence": dict(alert.evidence_json or {}),
                        "timezone": site.timezone,
                        "url": f"{public_url}/alerts#alert-{alert.id}",
                    },
                )
        return alert

    @staticmethod
    def _resolve_rule(db: Session, site: Site, rule_key: str, now: datetime) -> int:
        alerts = (
            db.query(Alert)
            .filter(
                Alert.user_id == site.user_id,
                Alert.site_id == site.id,
                Alert.rule_key == rule_key,
                Alert.resolved_at.is_(None),
            )
            .all()
        )
        for alert in alerts:
            alert.resolved_at = now
        return len(alerts)

    def evaluate_reading(self, db: Session, meter: Meter, reading: SmartMeterReading) -> Alert | None:
        site = db.query(Site).filter(Site.id == meter.site_id).first()
        if site is None or reading.gap < 0:
            return None

        config = self.config_for_site(db, site)
        observed_at = _as_utc(reading.timestamp)
        if reading.source == "push":
            self._resolve_rule(db, site, f"missing_data:{meter.id}", observed_at)
        if reading.gap < config.threshold_kw:
            self._resolve_rule(db, site, f"high_load:{meter.id}", observed_at)
            return None

        severity = "critical" if reading.gap >= config.threshold_kw * 1.25 else "high"
        return self._create_if_due(
            db,
            site=site,
            config=config,
            rule_key=f"high_load:{meter.id}",
            alert_type="high_consumption",
            severity=severity,
            message=(
                f"Meter '{meter.name}' recorded {reading.gap:.3f} kW, above the "
                f"configured {config.threshold_kw:.3f} kW threshold."
            ),
            peak_kw=reading.gap,
            evidence={
                "meter_id": meter.id,
                "meter_name": meter.name,
                "observed_at": observed_at.isoformat(),
                "observed_kw": reading.gap,
                "threshold_kw": config.threshold_kw,
                "source": reading.source,
            },
            now=observed_at,
        )

    def evaluate_missing_push_data(self, db: Session, now: datetime | None = None) -> list[Alert]:
        now = now or datetime.now(timezone.utc)
        created: list[Alert] = []
        meters = (
            db.query(Meter)
            .filter(Meter.source_type == "push", Meter.status == "active")
            .order_by(Meter.id)
            .all()
        )
        for meter in meters:
            if meter.last_seen_at is None:
                continue
            site = db.query(Site).filter(Site.id == meter.site_id).first()
            if site is None:
                continue
            config = self.config_for_site(db, site)
            last_seen = _as_utc(meter.last_seen_at)
            age_minutes = (now - last_seen).total_seconds() / 60
            if age_minutes < config.missing_data_minutes:
                continue
            alert = self._create_if_due(
                db,
                site=site,
                config=config,
                rule_key=f"missing_data:{meter.id}",
                alert_type="missing_data",
                severity="high",
                message=(
                    f"Meter '{meter.name}' has not sent push data for "
                    f"{int(age_minutes)} minutes."
                ),
                peak_kw=None,
                evidence={
                    "meter_id": meter.id,
                    "meter_name": meter.name,
                    "last_seen_at": last_seen.isoformat(),
                    "age_minutes": round(age_minutes, 1),
                    "missing_data_minutes": config.missing_data_minutes,
                },
                now=now,
            )
            if alert is not None:
                created.append(alert)
        return created


alert_service = AlertService()
