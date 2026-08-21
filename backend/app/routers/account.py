"""Portable account export and securely reauthenticated self-service deletion."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.limiter import limiter
from app.models import AuthIdentity, User
from app.routers import auth as auth_router
from app.schemas import AccountDeletionCapabilities, AccountDeletionRequest, GoogleChallengeResponse
from app.services.account_export_service import build_account_archive
from app.services.account_deletion_service import delete_account_data
from app.services.audit_service import record_audit_event
from app.services.auth_service import get_current_user, verify_password
from app.services.avatar_storage import (
    avatar_object_key,
    get_avatar_storage,
    process_avatar_cleanup,
    schedule_avatar_cleanup,
)
from app.services.oauth_challenge_service import consume_oauth_challenge, issue_oauth_challenge


router = APIRouter(prefix="/api/v1/account", tags=["Account"])
settings = get_settings()


def _archive_chunks(archive, chunk_size: int = 64 * 1024) -> Iterator[bytes]:
    try:
        while chunk := archive.read(chunk_size):
            yield chunk
    finally:
        archive.close()


def _deletion_method(db: Session, user: User) -> tuple[str, bool]:
    if user.password_hash:
        return "password", False
    linked = db.query(AuthIdentity.id).filter(
        AuthIdentity.user_id == user.id,
        AuthIdentity.provider == "google",
    ).first() is not None
    return "google", bool(linked and auth_router.settings.GOOGLE_AUTH_ENABLED)


@router.get("/export")
@limiter.limit(settings.EXPENSIVE_RATE_LIMIT)
def export_account(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return a documented owner-scoped ZIP while excluding every credential class."""
    record_audit_event(
        db,
        "account.exported",
        actor_user_id=current_user.id,
        target_user_id=current_user.id,
        target=f"user:{current_user.id}",
    )
    db.commit()
    archive = build_account_archive(db, current_user)
    filename = f"energyforecast-account-{current_user.id}-{datetime.now(timezone.utc).date().isoformat()}.zip"
    return StreamingResponse(
        _archive_chunks(archive),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/deletion/capabilities", response_model=AccountDeletionCapabilities)
def deletion_capabilities(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    method, google_available = _deletion_method(db, current_user)
    return AccountDeletionCapabilities(
        method=method,
        google_reauthentication_available=google_available,
    )


@router.post("/deletion/challenge", response_model=GoogleChallengeResponse)
def deletion_challenge(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_router._require_trusted_origin(request)
    method, google_available = _deletion_method(db, current_user)
    if method != "google" or not google_available:
        raise auth_router._error(
            "google_reauthentication_unavailable",
            "Google reauthentication is not available for this account.",
            status.HTTP_409_CONFLICT,
        )
    challenge = issue_oauth_challenge(db, action="delete_account", user_id=current_user.id)
    db.commit()
    return GoogleChallengeResponse(**challenge.__dict__)


@router.delete("")
def delete_account(
    request: Request,
    response: Response,
    data: AccountDeletionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_router._require_trusted_origin(request)
    method, google_available = _deletion_method(db, current_user)
    if method == "password":
        if not data.current_password or not verify_password(data.current_password, current_user.password_hash):
            raise auth_router._error(
                "recent_auth_required",
                "Current password confirmation is required.",
                status.HTTP_403_FORBIDDEN,
            )
    else:
        if not google_available or not data.google_credential or not data.google_state:
            raise auth_router._error(
                "google_reauthentication_required",
                "Recent Google reauthentication is required.",
                status.HTTP_403_FORBIDDEN,
            )
        nonce = auth_router._unverified_google_nonce(data.google_credential)
        claims = auth_router._verified_google_identity(data.google_credential, expected_nonce=nonce)
        if not consume_oauth_challenge(
            db,
            state=data.google_state,
            nonce=nonce,
            action="delete_account",
            user_id=current_user.id,
        ):
            db.rollback()
            raise auth_router._error(
                "google_state_invalid",
                "Google reauthentication state is invalid, expired, or already used.",
                status.HTTP_401_UNAUTHORIZED,
            )
        identity = db.query(AuthIdentity.id).filter(
            AuthIdentity.user_id == current_user.id,
            AuthIdentity.provider == "google",
            AuthIdentity.subject == claims["sub"],
        ).first()
        if identity is None:
            db.rollback()
            raise auth_router._error(
                "google_identity_mismatch",
                "The reauthenticated Google identity does not own this account.",
                status.HTTP_403_FORBIDDEN,
            )

    user_id = current_user.id
    old_object_key = avatar_object_key(current_user.avatar_url)
    if old_object_key:
        schedule_avatar_cleanup(db, old_object_key, "account_deleted")

    delete_account_data(db, user_id)
    record_audit_event(
        db,
        "account.deleted",
        target="deleted-account",
        metadata={"authentication_method": method, "retained": "anonymized_security_event"},
    )
    db.commit()
    auth_router._clear_refresh_cookie(response)
    if old_object_key:
        process_avatar_cleanup(
            db,
            storage=get_avatar_storage(auth_router.settings),
            settings=auth_router.settings,
        )
    return {"message": "Account and owned product data were permanently deleted."}
