"""Transactional outbox claiming, retry, and provider delivery orchestration."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import random
import time
import uuid

from sqlalchemy import and_, or_
from sqlalchemy import insert
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import EmailOutbox
from app.services.email_providers import MailProvider, SMTPMailProvider
from app.services.email_templates import render_email

logger = logging.getLogger(__name__)
ELIGIBLE_STATUSES = ("pending", "retry")


def enqueue_email(
    db: Session,
    *,
    recipient: str,
    template: str,
    payload: dict,
    dedup_key: str,
    user_id: int | None = None,
    template_version: str = "v1",
) -> EmailOutbox | None:
    """Add one logical email to the caller's transaction."""
    row_id = str(uuid.uuid4())
    values = {
        "id": row_id,
        "user_id": user_id,
        "recipient": recipient.strip().lower(),
        "template": template,
        "template_version": template_version,
        "payload": payload,
        "dedup_key": dedup_key,
        "status": "pending",
    }
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        statement = postgresql_insert(EmailOutbox).values(**values).on_conflict_do_nothing(index_elements=["dedup_key"])
    elif dialect == "sqlite":
        statement = sqlite_insert(EmailOutbox).values(**values).on_conflict_do_nothing(index_elements=["dedup_key"])
    else:
        # The supported production/test databases have native conflict handling.
        # A plain insert preserves transaction ownership for other dialects.
        statement = insert(EmailOutbox).values(**values)
    result = db.execute(statement.returning(EmailOutbox.id)).scalar_one_or_none()
    if result is None:
        return None
    return db.get(EmailOutbox, row_id)


def claim_due_emails(
    db: Session,
    *,
    worker_id: str,
    now: datetime | None = None,
    limit: int = 20,
    settings: Settings | None = None,
) -> list[str]:
    """Atomically lease due rows; PostgreSQL workers skip each other's locks."""
    settings = settings or get_settings()
    now = now or datetime.now(timezone.utc)
    eligible = or_(
        and_(EmailOutbox.status.in_(ELIGIBLE_STATUSES), EmailOutbox.next_attempt_at <= now),
        and_(EmailOutbox.status == "processing", EmailOutbox.lease_expires_at <= now),
    )
    query = db.query(EmailOutbox).filter(eligible).order_by(EmailOutbox.next_attempt_at, EmailOutbox.created_at)
    if db.get_bind().dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)
    rows = query.limit(limit).all()
    lease_until = now + timedelta(seconds=settings.EMAIL_LEASE_SECONDS)
    for row in rows:
        row.status = "processing"
        row.lease_owner = worker_id
        row.lease_expires_at = lease_until
        row.attempts += 1
        row.last_error = None
    db.flush()
    return [row.id for row in rows]


def _safe_error(exc: Exception) -> str:
    """Persist only the exception type; provider bodies and addresses are secrets."""
    return f"{type(exc).__module__}.{type(exc).__name__}"[:200]


def _record_failure(
    db: Session,
    *,
    row_id: str,
    worker_id: str,
    exc: Exception,
    now: datetime,
    settings: Settings,
    random_value: float,
) -> str:
    row = db.query(EmailOutbox).filter(
        EmailOutbox.id == row_id,
        EmailOutbox.status == "processing",
        EmailOutbox.lease_owner == worker_id,
    ).first()
    if row is None:
        return "lease_lost"
    row.last_error = _safe_error(exc)
    row.lease_owner = None
    row.lease_expires_at = None
    if row.attempts >= settings.EMAIL_MAX_ATTEMPTS:
        row.status = "dead"
    else:
        backoff = settings.EMAIL_RETRY_BASE_SECONDS * (2 ** max(row.attempts - 1, 0))
        jitter = int(backoff * 0.25 * max(0.0, min(random_value, 1.0)))
        row.status = "retry"
        row.next_attempt_at = now + timedelta(seconds=backoff + jitter)
    db.commit()
    return row.status


def process_due_email(
    db: Session,
    *,
    provider: MailProvider | None = None,
    worker_id: str | None = None,
    now: datetime | None = None,
    settings: Settings | None = None,
    random_source: random.Random | None = None,
) -> int:
    """Claim, commit the lease, then deliver without holding database locks."""
    settings = settings or get_settings()
    if provider is None:
        if not settings.EMAIL_DELIVERY_ENABLED:
            return 0
        provider = SMTPMailProvider(settings)
    worker_id = worker_id or str(uuid.uuid4())
    now = now or datetime.now(timezone.utc)
    random_source = random_source or random.SystemRandom()
    claimed_ids = claim_due_emails(db, worker_id=worker_id, now=now, settings=settings)
    db.commit()

    processed = 0
    for row_id in claimed_ids:
        started = time.monotonic()
        row = db.query(EmailOutbox).filter(
            EmailOutbox.id == row_id,
            EmailOutbox.status == "processing",
            EmailOutbox.lease_owner == worker_id,
        ).first()
        if row is None:
            continue
        message_type = row.template
        attempt = row.attempts
        try:
            rendered = render_email(row, settings)
            provider_id = provider.send(rendered)
            sent_at = datetime.now(timezone.utc)
            updated = db.query(EmailOutbox).filter(
                EmailOutbox.id == row_id,
                EmailOutbox.status == "processing",
                EmailOutbox.lease_owner == worker_id,
            ).update({
                "status": "sent",
                "sent_at": sent_at,
                "provider_message_id": (provider_id or "")[:255] or None,
                "lease_owner": None,
                "lease_expires_at": None,
                "last_error": None,
            })
            db.commit()
            outcome = "sent" if updated == 1 else "lease_lost"
        except Exception as exc:
            db.rollback()
            outcome = _record_failure(
                db,
                row_id=row_id,
                worker_id=worker_id,
                exc=exc,
                now=datetime.now(timezone.utc),
                settings=settings,
                random_value=random_source.random(),
            )
        latency_ms = int((time.monotonic() - started) * 1000)
        logger.info(
            "email_outbox id=%s type=%s status=%s attempt=%s latency_ms=%s",
            row_id,
            message_type,
            outcome,
            attempt,
            latency_ms,
        )
        processed += 1
    return processed


def retry_dead_email(db: Session, row: EmailOutbox, *, now: datetime | None = None) -> None:
    if row.status != "dead":
        raise ValueError("Only dead email can be retried")
    row.status = "retry"
    row.attempts = 0
    row.next_attempt_at = now or datetime.now(timezone.utc)
    row.lease_owner = None
    row.lease_expires_at = None
    row.last_error = None
    row.provider_message_id = None
