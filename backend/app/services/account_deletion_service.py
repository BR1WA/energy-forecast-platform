"""Bounded, set-based removal of all data owned by one account."""
from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import (
    AccountActionToken,
    Alert,
    AlertConfig,
    AuditEvent,
    AuthIdentity,
    EmailOutbox,
    EnergyBudget,
    Forecast,
    IngestionBatch,
    Meter,
    OAuthChallenge,
    Recommendation,
    RefreshToken,
    SimulationSession,
    Site,
    SiteSettings,
    SmartMeterReading,
    User,
)


def delete_account_data(db: Session, user_id: int) -> dict[str, int]:
    """Delete one user's complete ownership graph without loading every reading."""
    site_ids = [row[0] for row in db.query(Site.id).filter(Site.user_id == user_id).all()]
    meter_ids = (
        [row[0] for row in db.query(Meter.id).filter(Meter.site_id.in_(site_ids)).all()]
        if site_ids
        else []
    )

    counts: dict[str, int] = {}
    audit_filter = or_(AuditEvent.actor_user_id == user_id, AuditEvent.target_user_id == user_id)
    if site_ids:
        audit_filter = or_(audit_filter, AuditEvent.site_id.in_(site_ids))
    counts["audit_events"] = db.query(AuditEvent).filter(audit_filter).delete(synchronize_session=False)

    counts["email_outbox"] = (
        db.query(EmailOutbox).filter(EmailOutbox.user_id == user_id).delete(synchronize_session=False)
    )
    counts["oauth_challenges"] = (
        db.query(OAuthChallenge).filter(OAuthChallenge.user_id == user_id).delete(synchronize_session=False)
    )
    counts["recommendations"] = (
        db.query(Recommendation).filter(Recommendation.user_id == user_id).delete(synchronize_session=False)
    )
    counts["alerts"] = db.query(Alert).filter(Alert.user_id == user_id).delete(synchronize_session=False)
    counts["alert_configs"] = (
        db.query(AlertConfig).filter(AlertConfig.user_id == user_id).delete(synchronize_session=False)
    )
    counts["forecasts"] = db.query(Forecast).filter(Forecast.user_id == user_id).delete(synchronize_session=False)
    counts["energy_budgets"] = (
        db.query(EnergyBudget).filter(EnergyBudget.user_id == user_id).delete(synchronize_session=False)
    )

    if meter_ids:
        counts["readings"] = (
            db.query(SmartMeterReading)
            .filter(SmartMeterReading.meter_id.in_(meter_ids))
            .delete(synchronize_session=False)
        )
        counts["ingestion_batches"] = (
            db.query(IngestionBatch)
            .filter(IngestionBatch.meter_id.in_(meter_ids))
            .delete(synchronize_session=False)
        )
        counts["meters"] = db.query(Meter).filter(Meter.id.in_(meter_ids)).delete(synchronize_session=False)
    else:
        counts.update({"readings": 0, "ingestion_batches": 0, "meters": 0})

    if site_ids:
        counts["simulation_sessions"] = (
            db.query(SimulationSession)
            .filter(SimulationSession.site_id.in_(site_ids))
            .delete(synchronize_session=False)
        )
        counts["site_settings"] = (
            db.query(SiteSettings)
            .filter(SiteSettings.site_id.in_(site_ids))
            .delete(synchronize_session=False)
        )
        counts["sites"] = db.query(Site).filter(Site.id.in_(site_ids)).delete(synchronize_session=False)
    else:
        counts.update({"simulation_sessions": 0, "site_settings": 0, "sites": 0})

    counts["refresh_tokens"] = (
        db.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete(synchronize_session=False)
    )
    counts["action_tokens"] = (
        db.query(AccountActionToken)
        .filter(AccountActionToken.user_id == user_id)
        .delete(synchronize_session=False)
    )
    counts["auth_identities"] = (
        db.query(AuthIdentity).filter(AuthIdentity.user_id == user_id).delete(synchronize_session=False)
    )
    counts["users"] = db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
    return counts
