"""Atomic, single-use account actions with only SHA-256 token hashes at rest."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Literal

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AccountActionToken

ActionPurpose = Literal["verify_email", "reset_password"]
VALID_PURPOSES = {"verify_email", "reset_password"}


@dataclass(frozen=True)
class IssuedActionToken:
    record: AccountActionToken
    raw_token: str
    sealed_token: str


def hash_action_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _fernet() -> Fernet:
    settings = get_settings()
    derived = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"energyforecast-product-v1-action-token",
        info=b"email-render-only",
    ).derive(settings.JWT_SECRET_KEY.encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(derived))


def seal_action_token(raw_token: str) -> str:
    return _fernet().encrypt(raw_token.encode("utf-8")).decode("ascii")


def unseal_action_token(sealed_token: str) -> str:
    try:
        return _fernet().decrypt(sealed_token.encode("ascii"), ttl=24 * 60 * 60).decode("utf-8")
    except (InvalidToken, UnicodeError, ValueError) as exc:
        raise ValueError("Action token envelope is invalid or expired") from exc


def issue_action_token(
    db: Session,
    user_id: int,
    purpose: ActionPurpose,
    *,
    expires_in_minutes: int = 60,
    now: datetime | None = None,
) -> IssuedActionToken:
    if purpose not in VALID_PURPOSES:
        raise ValueError("Unsupported account action purpose")
    now = now or datetime.now(timezone.utc)
    db.query(AccountActionToken).filter(
        AccountActionToken.user_id == user_id,
        AccountActionToken.purpose == purpose,
        AccountActionToken.used_at.is_(None),
        AccountActionToken.revoked_at.is_(None),
    ).update({"revoked_at": now}, synchronize_session=False)
    raw = secrets.token_urlsafe(32)
    record = AccountActionToken(
        user_id=user_id,
        purpose=purpose,
        token_hash=hash_action_token(raw),
        expires_at=now + timedelta(minutes=expires_in_minutes),
    )
    db.add(record)
    db.flush()
    return IssuedActionToken(record=record, raw_token=raw, sealed_token=seal_action_token(raw))


def consume_action_token(
    db: Session,
    raw_token: str,
    purpose: ActionPurpose,
    *,
    now: datetime | None = None,
) -> AccountActionToken | None:
    if purpose not in VALID_PURPOSES:
        return None
    now = now or datetime.now(timezone.utc)
    token_hash = hash_action_token(raw_token)
    token = db.query(AccountActionToken).filter(
        AccountActionToken.token_hash == token_hash,
        AccountActionToken.purpose == purpose,
    ).first()
    if token is None:
        return None
    claimed = db.query(AccountActionToken).filter(
        AccountActionToken.id == token.id,
        AccountActionToken.used_at.is_(None),
        AccountActionToken.revoked_at.is_(None),
        AccountActionToken.expires_at > now,
    ).update({"used_at": now}, synchronize_session=False)
    if claimed != 1:
        db.rollback()
        return None
    db.flush()
    return db.query(AccountActionToken).filter(AccountActionToken.id == token.id).one()


def has_recent_action_token(
    db: Session,
    user_id: int,
    purpose: ActionPurpose,
    *,
    since: datetime,
) -> bool:
    return db.query(AccountActionToken.id).filter(
        AccountActionToken.user_id == user_id,
        AccountActionToken.purpose == purpose,
        AccountActionToken.created_at >= since,
        AccountActionToken.used_at.is_(None),
        AccountActionToken.revoked_at.is_(None),
    ).first() is not None
