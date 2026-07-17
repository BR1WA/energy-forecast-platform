"""Small append-only audit helper for security-relevant product actions."""
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditEvent


def record_audit_event(
    db: Session,
    event_type: str,
    *,
    actor_user_id: int | None = None,
    target_user_id: int | None = None,
    site_id: int | None = None,
    target: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    db.add(AuditEvent(
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        site_id=site_id,
        event_type=event_type,
        target=target,
        metadata_json=metadata or {},
    ))
