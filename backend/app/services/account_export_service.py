"""Owner-scoped, machine-readable account archive generation."""
from __future__ import annotations

from datetime import date, datetime, timezone
import io
import json
from tempfile import SpooledTemporaryFile
from typing import Callable, Iterable
import zipfile

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import (
    Alert,
    AlertConfig,
    AuditEvent,
    EnergyBudget,
    Forecast,
    Meter,
    Recommendation,
    SimulationSession,
    Site,
    SiteSettings,
    SmartMeterReading,
    User,
)


EXPORT_VERSION = "1.0"
EXPORT_SPOOL_LIMIT_BYTES = 8 * 1024 * 1024


def _json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"Unsupported export value: {type(value).__name__}")


def _write_json(archive: zipfile.ZipFile, name: str, value) -> None:
    archive.writestr(name, json.dumps(value, default=_json_default, ensure_ascii=False, indent=2) + "\n")


def _write_ndjson(
    archive: zipfile.ZipFile,
    name: str,
    rows: Iterable,
    serializer: Callable,
) -> int:
    count = 0
    with archive.open(name, "w") as raw:
        with io.TextIOWrapper(raw, encoding="utf-8", write_through=True) as text:
            for row in rows:
                text.write(json.dumps(serializer(row), default=_json_default, ensure_ascii=False, separators=(",", ":")))
                text.write("\n")
                count += 1
    return count


def _audit_record(row: AuditEvent, user_id: int, site_ids: list[int]) -> dict:
    references_other_user = row.target_user_id is not None and row.target_user_id != user_id
    return {
        "id": row.id,
        "event_type": row.event_type,
        "actor_scope": "self" if row.actor_user_id == user_id else "system_or_operator",
        "target_scope": "self" if row.target_user_id == user_id else None,
        "site_id": row.site_id if row.site_id in site_ids else None,
        "target": None if references_other_user else row.target,
        "metadata": {} if references_other_user else row.metadata_json,
        "created_at": row.created_at,
    }


def build_account_archive(db: Session, user: User) -> SpooledTemporaryFile:
    """Build a complete archive without loading large reading sets into memory."""
    site_ids = [row[0] for row in db.query(Site.id).filter(Site.user_id == user.id).all()]
    meter_ids = [
        row[0]
        for row in db.query(Meter.id).filter(Meter.site_id.in_(site_ids)).all()
    ] if site_ids else []
    spool = SpooledTemporaryFile(max_size=EXPORT_SPOOL_LIMIT_BYTES, mode="w+b")
    counts: dict[str, int] = {}
    try:
        with zipfile.ZipFile(spool, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            account = {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "is_active": user.is_active,
                "is_setup_complete": user.is_setup_complete,
                "preferences": user.preferences or {},
                "data_mode": user.data_mode,
                "email_verified_at": user.email_verified_at,
                "created_at": user.created_at,
                "last_login": user.last_login,
                "avatar_url": user.avatar_url,
            }
            _write_json(archive, "account.json", account)

            sites = db.query(Site).filter(Site.user_id == user.id).order_by(Site.id).all()
            _write_json(archive, "sites.json", [{
                "id": row.id,
                "name": row.name,
                "address": row.address,
                "region": row.region,
                "timezone": row.timezone,
                "provider": row.provider,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            } for row in sites])
            counts["sites"] = len(sites)

            meters = db.query(Meter).filter(Meter.site_id.in_(site_ids)).order_by(Meter.id).all() if site_ids else []
            _write_json(archive, "meters.json", [{
                "id": row.id,
                "site_id": row.site_id,
                "external_id": row.external_id,
                "name": row.name,
                "meter_type": row.meter_type,
                "status": row.status,
                "source_type": row.source_type,
                "is_primary": row.is_primary,
                "expected_interval_seconds": row.expected_interval_seconds,
                "last_seen_at": row.last_seen_at,
                "created_at": row.created_at,
            } for row in meters])
            counts["meters"] = len(meters)

            site_settings = db.query(SiteSettings).filter(SiteSettings.site_id.in_(site_ids)).order_by(SiteSettings.id).all() if site_ids else []
            _write_json(archive, "site-settings.json", [{
                "site_id": row.site_id,
                "country": row.country,
                "region": row.region,
                "electricity_provider": row.electricity_provider,
                "currency": row.currency,
                "peak_rate": row.peak_rate,
                "off_peak_rate": row.off_peak_rate,
                "peak_start_hour": row.peak_start_hour,
                "peak_end_hour": row.peak_end_hour,
                "sensor_type": row.sensor_type,
                "updated_at": row.updated_at,
            } for row in site_settings])
            counts["site_settings"] = len(site_settings)

            counts["readings"] = _write_ndjson(
                archive,
                "readings.ndjson",
                db.query(SmartMeterReading)
                .filter(SmartMeterReading.meter_id.in_(meter_ids))
                .order_by(SmartMeterReading.meter_id, SmartMeterReading.timestamp)
                .yield_per(1000) if meter_ids else [],
                lambda row: {
                    "id": row.id,
                    "meter_id": row.meter_id,
                    "timestamp": row.timestamp,
                    "active_power_kw": row.gap,
                    "reactive_power_kvar": row.grp,
                    "voltage_v": row.voltage,
                    "current_a": row.intensity,
                    "sub_metering_1_wh": row.sub_metering_1,
                    "sub_metering_2_wh": row.sub_metering_2,
                    "sub_metering_3_wh": row.sub_metering_3,
                    "energy_kwh": row.energy_kwh,
                    "source": row.source,
                    "quality": row.quality,
                },
            )

            counts["forecasts"] = _write_ndjson(
                archive,
                "forecasts.ndjson",
                db.query(Forecast).filter(Forecast.user_id == user.id).order_by(Forecast.created_at, Forecast.id).yield_per(200),
                lambda row: {
                    "id": row.id,
                    "site_id": row.site_id,
                    "model_registry_id": row.model_registry_id,
                    "horizon_hours": row.horizon,
                    "input_source": row.input_source,
                    "input_snapshot": row.input_snapshot,
                    "confidence_method": row.confidence_method,
                    "model_name": row.model_name,
                    "input_start": row.input_start,
                    "input_end": row.input_end,
                    "predictions": row.predictions,
                    "metrics": row.metrics,
                    "created_at": row.created_at,
                },
            )
            counts["alerts"] = _write_ndjson(
                archive,
                "alerts.ndjson",
                db.query(Alert).filter(Alert.user_id == user.id).order_by(Alert.created_at, Alert.id).yield_per(500),
                lambda row: {
                    "id": row.id,
                    "site_id": row.site_id,
                    "forecast_id": row.forecast_id,
                    "alert_type": row.alert_type,
                    "rule_key": row.rule_key,
                    "severity": row.severity,
                    "message": row.message,
                    "peak_kw": row.peak_kw,
                    "evidence": row.evidence_json,
                    "is_acknowledged": row.is_acknowledged,
                    "acknowledged_at": row.acknowledged_at,
                    "resolved_at": row.resolved_at,
                    "created_at": row.created_at,
                },
            )
            counts["recommendations"] = _write_ndjson(
                archive,
                "recommendations.ndjson",
                db.query(Recommendation).filter(Recommendation.user_id == user.id).order_by(Recommendation.created_at, Recommendation.id).yield_per(500),
                lambda row: {
                    "id": row.id,
                    "site_id": row.site_id,
                    "alert_id": row.alert_id,
                    "category": row.category,
                    "title": row.title,
                    "message": row.message,
                    "status": row.status,
                    "estimated_excess_cost_per_hour_mad": row.estimated_excess_cost_per_hour_mad,
                    "evidence": row.evidence_json,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                },
            )

            alert_configs = db.query(AlertConfig).filter(AlertConfig.user_id == user.id).order_by(AlertConfig.id).all()
            _write_json(archive, "alert-configurations.json", [{
                "id": row.id,
                "site_id": row.site_id,
                "threshold_kw": row.threshold_kw,
                "cooldown_minutes": row.cooldown_minutes,
                "missing_data_minutes": row.missing_data_minutes,
                "email_enabled": row.email_enabled,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            } for row in alert_configs])
            counts["alert_configurations"] = len(alert_configs)

            budget = db.query(EnergyBudget).filter(EnergyBudget.user_id == user.id).one_or_none()
            _write_json(archive, "budget.json", None if budget is None else {
                "monthly_budget_mad": budget.monthly_budget_mad,
                "monthly_budget_kwh": budget.monthly_budget_kwh,
                "created_at": budget.created_at,
                "updated_at": budget.updated_at,
            })
            counts["budgets"] = 0 if budget is None else 1

            simulations = db.query(SimulationSession).filter(SimulationSession.site_id.in_(site_ids)).order_by(SimulationSession.id).all() if site_ids else []
            _write_json(archive, "simulation-sessions.json", [{
                "site_id": row.site_id,
                "is_running": row.is_running,
                "configuration": row.configuration,
                "started_at": row.started_at,
                "last_error": row.last_error,
                "updated_at": row.updated_at,
            } for row in simulations])
            counts["simulation_sessions"] = len(simulations)

            audit_filter = or_(AuditEvent.actor_user_id == user.id, AuditEvent.target_user_id == user.id)
            if site_ids:
                audit_filter = or_(audit_filter, AuditEvent.site_id.in_(site_ids))
            counts["audit_events"] = _write_ndjson(
                archive,
                "audit-events.ndjson",
                db.query(AuditEvent).filter(audit_filter).order_by(AuditEvent.created_at, AuditEvent.id).yield_per(500),
                lambda row: _audit_record(row, user.id, site_ids),
            )

            _write_json(archive, "manifest.json", {
                "schema": "energyforecast.account-export",
                "version": EXPORT_VERSION,
                "generated_at": datetime.now(timezone.utc),
                "account_id": user.id,
                "counts": counts,
                "excluded_secret_classes": [
                    "password hashes",
                    "refresh and action token hashes",
                    "OAuth subjects and credentials",
                    "meter ingestion key hashes",
                    "email provider credentials and outbox payloads",
                ],
            })
            archive.writestr(
                "README.txt",
                "EnergyForecast account export\n"
                "JSON files contain bounded account/configuration records. NDJSON files contain one record per line for large collections.\n"
                "See manifest.json for schema version, counts, and deliberately excluded secret classes.\n",
            )
        spool.seek(0)
        return spool
    except Exception:
        spool.close()
        raise
