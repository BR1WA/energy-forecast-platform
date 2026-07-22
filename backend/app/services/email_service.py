"""Transactional email outbox and SMTP delivery provider."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import logging
import smtplib
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import EmailOutbox

logger = logging.getLogger(__name__)


def enqueue_email(db: Session, *, recipient: str, template: str, payload: dict, dedup_key: str, user_id: int | None = None) -> bool:
    """Persist mail intent in the caller's transaction; duplicate keys are idempotent."""
    row = EmailOutbox(id=str(uuid.uuid4()), user_id=user_id, recipient=recipient, template=template, payload=payload, dedup_key=dedup_key)
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
        return True
    except IntegrityError:
        return False


def render_message(template: str, payload: dict) -> tuple[str, str]:
    app = "EnergyForecast"
    if template == "verify_email":
        subject = f"Verify your {app} email"
        text = f"Verify your email: {payload['url']}\nThis link expires in one hour."
    elif template == "password_reset":
        subject = f"Reset your {app} password"
        text = f"Reset your password: {payload['url']}\nThis link expires in one hour."
    elif template == "critical_alert":
        subject = f"Critical energy alert: {payload['title']}"
        text = f"{payload['message']}\nView alerts: {payload['url']}"
    else:
        raise ValueError(f"Unknown email template: {template}")
    return subject, text


def deliver_outbox_row(row: EmailOutbox) -> None:
    settings = get_settings()
    if not settings.EMAIL_DELIVERY_ENABLED:
        raise RuntimeError("Email delivery is disabled")
    subject, text = render_message(row.template, row.payload)
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.EMAIL_FROM_ADDRESS
    message["To"] = row.recipient
    if settings.EMAIL_REPLY_TO:
        message["Reply-To"] = settings.EMAIL_REPLY_TO
    message.set_content(text)
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as client:
        if settings.SMTP_USE_TLS:
            client.starttls()
        if settings.SMTP_USERNAME:
            client.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        client.send_message(message)


def process_due_email(db: Session) -> int:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    rows = db.query(EmailOutbox).filter(EmailOutbox.status == "pending", EmailOutbox.next_attempt_at <= now).order_by(EmailOutbox.created_at).limit(20).all()
    processed = 0
    for row in rows:
        try:
            deliver_outbox_row(row)
            row.status, row.sent_at, row.last_error = "sent", now, None
        except Exception as exc:
            row.attempts += 1
            row.last_error = str(exc)[:500]
            if row.attempts >= settings.EMAIL_MAX_ATTEMPTS:
                row.status = "failed"
            else:
                row.next_attempt_at = now + timedelta(minutes=2 ** min(row.attempts, 6))
            logger.warning("Email delivery attempt failed for %s: %s", row.id, exc)
        processed += 1
    return processed
