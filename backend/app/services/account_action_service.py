"""Single-use, hashed tokens for verification and password recovery."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import secrets

from sqlalchemy.orm import Session

from app.models import AccountActionToken


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def issue_action_token(db: Session, user_id: int, purpose: str, expires_in_minutes: int = 60) -> str:
    db.query(AccountActionToken).filter(
        AccountActionToken.user_id == user_id,
        AccountActionToken.purpose == purpose,
        AccountActionToken.used_at.is_(None),
    ).update({"used_at": datetime.now(timezone.utc)})
    raw = secrets.token_urlsafe(32)
    db.add(AccountActionToken(
        user_id=user_id,
        purpose=purpose,
        token_hash=_hash(raw),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes),
    ))
    return raw


def consume_action_token(db: Session, raw: str, purpose: str) -> AccountActionToken | None:
    now = datetime.now(timezone.utc)
    token = db.query(AccountActionToken).filter(
        AccountActionToken.token_hash == _hash(raw),
        AccountActionToken.purpose == purpose,
        AccountActionToken.used_at.is_(None),
        AccountActionToken.expires_at > now,
    ).with_for_update().first()
    if token is not None:
        token.used_at = now
    return token
