from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.database import Base
from app.models import EmailOutbox
from app.services.account_action_service import seal_action_token
from app.services.email_providers import CapturingMailProvider, RenderedEmail, SMTPMailProvider
from app.services.email_service import claim_due_emails, enqueue_email, process_due_email, retry_dead_email


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _settings(**overrides):
    values = {
        "DEBUG": True,
        "JWT_SECRET_KEY": "email-test-jwt-secret-with-more-than-32-characters",
        "ADMIN_PASSWORD": "email-test-admin-password",
        "EMAIL_MAX_ATTEMPTS": 2,
        "EMAIL_LEASE_SECONDS": 60,
        "EMAIL_RETRY_BASE_SECONDS": 10,
        "EMAIL_FROM_ADDRESS": "sender@example.test",
        "SMTP_HOST": "smtp.example.test",
        "SMTP_USERNAME": "user",
        "SMTP_PASSWORD": "password",
    }
    values.update(overrides)
    return Settings(**values)


def _enqueue(db, key="event:1"):
    return enqueue_email(
        db,
        recipient="person@example.test",
        template="critical_alert",
        template_version="v1",
        payload={
            "alert_id": 1,
            "title": "Threshold",
            "message": "Measured threshold exceeded",
            "evidence": {
                "meter_name": "Primary meter",
                "observed_at": "2026-07-22T10:00:00+00:00",
                "observed_kw": 4.0,
                "threshold_kw": 3.0,
                "source": "push",
            },
            "timezone": "Africa/Casablanca",
            "url": "https://app.example.test/alerts#alert-1",
        },
        dedup_key=key,
    )


def test_outbox_participates_in_caller_transaction_and_deduplicates():
    db = _session()
    _enqueue(db)
    db.rollback()
    assert db.query(EmailOutbox).count() == 0

    first = _enqueue(db)
    duplicate = _enqueue(db)
    db.commit()
    assert first is not None
    assert duplicate is None
    assert db.query(EmailOutbox).count() == 1


def test_provider_outage_retries_then_moves_to_dead_and_can_be_requeued(caplog):
    db = _session()
    _enqueue(db)
    db.commit()
    provider = CapturingMailProvider(failure=RuntimeError("provider response containing person@example.test"))
    settings = _settings()
    now = datetime.now(timezone.utc)

    with caplog.at_level(logging.INFO):
        assert process_due_email(db, provider=provider, worker_id="worker-a", now=now, settings=settings) == 1
    row = db.query(EmailOutbox).one()
    assert row.status == "retry"
    assert row.last_error == "builtins.RuntimeError"
    assert "person@example.test" not in caplog.text

    row.next_attempt_at = now - timedelta(seconds=1)
    db.commit()
    assert process_due_email(db, provider=provider, worker_id="worker-a", now=now, settings=settings) == 1
    db.refresh(row)
    assert row.status == "dead"
    assert row.attempts == 2

    retry_dead_email(db, row, now=now)
    db.commit()
    assert row.status == "retry"
    assert row.attempts == 0


def test_expired_lease_is_reclaimed_but_active_lease_is_not():
    db = _session()
    now = datetime.now(timezone.utc)
    expired = _enqueue(db, "event:expired")
    active = _enqueue(db, "event:active")
    db.flush()
    for row, expiry in ((expired, now - timedelta(seconds=1)), (active, now + timedelta(seconds=30))):
        row.status = "processing"
        row.lease_owner = "old-worker"
        row.lease_expires_at = expiry
    db.commit()

    claimed = claim_due_emails(db, worker_id="new-worker", now=now, settings=_settings())
    db.commit()
    assert claimed == [expired.id]
    assert db.query(EmailOutbox).filter(EmailOutbox.id == active.id).one().lease_owner == "old-worker"


def test_smtp_provider_builds_plain_text_and_html_multipart():
    settings = _settings(EMAIL_FROM_NAME="Energy Test", EMAIL_REPLY_TO="help@example.test")
    rendered = RenderedEmail("person@example.test", "Subject", "Plain body", "<p>HTML body</p>")

    with patch("app.services.email_providers.smtplib.SMTP") as smtp:
        provider_id = SMTPMailProvider(settings).send(rendered)
    message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
    assert message.is_multipart()
    assert message.get_body(preferencelist=("plain",)).get_content().strip() == "Plain body"
    assert "HTML body" in message.get_body(preferencelist=("html",)).get_content()
    assert message["Reply-To"] == "help@example.test"
    assert provider_id == message["Message-ID"]


def test_action_token_envelope_and_raw_token_never_reach_logs(caplog):
    db = _session()
    raw_token = "raw-action-token-that-must-never-be-logged"
    sealed_token = seal_action_token(raw_token)
    enqueue_email(
        db,
        recipient="person@example.test",
        template="verify_email",
        payload={"action_token_id": 9, "sealed_token": sealed_token},
        dedup_key="verify:9",
    )
    db.commit()
    provider = CapturingMailProvider(failure=RuntimeError(f"provider echoed {raw_token} {sealed_token}"))
    with caplog.at_level(logging.INFO):
        assert process_due_email(db, provider=provider, worker_id="worker-secret-test", settings=_settings()) == 1
    assert raw_token not in caplog.text
    assert sealed_token not in caplog.text
    assert db.query(EmailOutbox).one().last_error == "builtins.RuntimeError"
