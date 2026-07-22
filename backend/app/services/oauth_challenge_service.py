"""Single-use OAuth state and nonce challenges stored only as hashes."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import uuid

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import OAuthChallenge


@dataclass(frozen=True)
class IssuedOAuthChallenge:
    state: str
    nonce: str
    expires_in_seconds: int


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def issue_oauth_challenge(db: Session, *, action: str, user_id: int | None = None) -> IssuedOAuthChallenge:
    if action not in {"login", "link"}:
        raise ValueError("Unsupported OAuth challenge action")
    settings = get_settings()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    expires_in = settings.GOOGLE_CHALLENGE_EXPIRE_MINUTES * 60
    db.add(OAuthChallenge(
        id=str(uuid.uuid4()),
        user_id=user_id,
        action=action,
        state_hash=_hash(state),
        nonce_hash=_hash(nonce),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
    ))
    db.flush()
    return IssuedOAuthChallenge(state=state, nonce=nonce, expires_in_seconds=expires_in)


def consume_oauth_challenge(
    db: Session,
    *,
    state: str,
    nonce: str,
    action: str,
    user_id: int | None = None,
) -> bool:
    now = datetime.now(timezone.utc)
    row = db.query(OAuthChallenge).filter(
        OAuthChallenge.state_hash == _hash(state),
        OAuthChallenge.action == action,
        OAuthChallenge.user_id == user_id,
    ).first()
    if row is None or row.nonce_hash != _hash(nonce):
        return False
    changed = db.query(OAuthChallenge).filter(
        OAuthChallenge.id == row.id,
        OAuthChallenge.used_at.is_(None),
        OAuthChallenge.expires_at > now,
    ).update({"used_at": now}, synchronize_session=False)
    return changed == 1
