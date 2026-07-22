"""Product authentication, verified registration, recovery, and identities."""

from datetime import datetime, timedelta, timezone
import hashlib
import logging
import os
import time
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.limiter import limiter
from app.models import AuthIdentity, RefreshToken, User
from app.schemas import (
    AuthCapabilitiesResponse,
    GoogleChallengeResponse,
    GoogleCredentialRequest,
    GoogleLinkRequest,
    GoogleUnlinkRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    PasswordUpdate,
    RegistrationResponse,
    TokenData,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
    UserUpdateMe,
    VerifyTokenRequest,
)
from app.services.account_action_service import (
    ActionPurpose,
    consume_action_token,
    has_recent_action_token,
    issue_action_token,
)
from app.services.audit_service import record_audit_event
from app.services.auth_service import (
    authenticate_user,
    consume_refresh_token,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    revoke_user_sessions,
    store_refresh_token,
    verify_password,
)
from app.services.email_service import enqueue_email
from app.services.oauth_challenge_service import consume_oauth_challenge, issue_oauth_challenge
from app.services.site_service import ensure_default_site

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


def _error(code: str, message: str, status_code: int) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _normalize_origin(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def _allowed_origins() -> set[str]:
    values = {settings.FRONTEND_URL, settings.PUBLIC_FRONTEND_URL}
    if settings.DEBUG:
        values.update({"http://localhost:3000", "http://localhost:3001"})
    return {normalized for value in values if (normalized := _normalize_origin(value))}


def _require_trusted_origin(request: Request) -> None:
    origin = _normalize_origin(request.headers.get("origin", ""))
    if not origin or origin not in _allowed_origins():
        raise _error("csrf_origin_rejected", "The request origin is not allowed.", status.HTTP_403_FORBIDDEN)


def _cookie_kwargs() -> dict:
    return {
        "httponly": True,
        "secure": not settings.DEBUG,
        "samesite": "lax",
        "path": "/api/v1/auth",
        "domain": settings.REFRESH_COOKIE_DOMAIN or None,
    }


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        **_cookie_kwargs(),
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie("refresh_token", **_cookie_kwargs())


def _cookie_error(code: str, message: str, status_code: int) -> JSONResponse:
    response = JSONResponse(status_code=status_code, content={"detail": {"code": code, "message": message}})
    _clear_refresh_cookie(response)
    return response


def _issue_session(response: Response, db: Session, user: User) -> TokenResponse:
    token_data = {"sub": str(user.id), "role": user.role}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    store_refresh_token(db, refresh_token, user.id, commit=False)
    db.commit()
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token, user=UserResponse.model_validate(user))


def _queue_action_email(db: Session, user: User, purpose: ActionPurpose) -> None:
    issued = issue_action_token(db, user.id, purpose)
    template = "verify_email" if purpose == "verify_email" else "password_reset"
    row = enqueue_email(
        db,
        user_id=user.id,
        recipient=user.email,
        template=template,
        template_version="v1",
        dedup_key=f"{purpose}:{user.id}:{issued.record.id}",
        payload={
            "action_token_id": issued.record.id,
            "sealed_token": issued.sealed_token,
        },
    )
    if row is None:
        raise RuntimeError("Could not enqueue the account action email")


def _verify_google_token(credential: str) -> dict:
    from google.auth.transport.requests import Request as GoogleRequest
    from google.oauth2 import id_token

    return id_token.verify_oauth2_token(credential, GoogleRequest(), settings.GOOGLE_CLIENT_ID)


def _verified_google_identity(credential: str, *, expected_nonce: str) -> dict:
    if not settings.GOOGLE_AUTH_ENABLED:
        raise _error("google_auth_disabled", "Google sign-in is not enabled.", status.HTTP_404_NOT_FOUND)
    try:
        claims = _verify_google_token(credential)
    except Exception as exc:
        logger.info("google_identity status=rejected reason=%s", type(exc).__name__)
        raise _error("google_credential_invalid", "Google credential could not be verified.", status.HTTP_401_UNAUTHORIZED)
    if claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
        raise _error("google_issuer_invalid", "Google credential issuer is invalid.", status.HTTP_401_UNAUTHORIZED)
    if claims.get("aud") != settings.GOOGLE_CLIENT_ID:
        raise _error("google_audience_invalid", "Google credential audience is invalid.", status.HTTP_401_UNAUTHORIZED)
    if claims.get("nonce") != expected_nonce:
        raise _error("google_nonce_invalid", "Google credential nonce is invalid.", status.HTTP_401_UNAUTHORIZED)
    if not claims.get("email_verified") or not claims.get("sub") or not claims.get("email"):
        raise _error("google_email_unverified", "Google account has no verified email.", status.HTTP_401_UNAUTHORIZED)
    return claims


def _unverified_google_nonce(credential: str) -> str:
    """Read only the nonce used to locate a challenge; no identity claim is trusted."""
    try:
        from google.auth import jwt as google_jwt

        claims = google_jwt.decode(credential, verify=False)
        return str(claims.get("nonce", ""))
    except Exception:
        raise _error("google_credential_invalid", "Google credential could not be verified.", status.HTTP_401_UNAUTHORIZED)


@router.get("/capabilities", response_model=AuthCapabilitiesResponse)
def auth_capabilities():
    return AuthCapabilitiesResponse(
        email_delivery_enabled=settings.EMAIL_DELIVERY_ENABLED,
        google_auth_enabled=settings.GOOGLE_AUTH_ENABLED,
        google_client_id=settings.GOOGLE_CLIENT_ID if settings.GOOGLE_AUTH_ENABLED else None,
    )


@router.post("/register", response_model=RegistrationResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(request: Request, data: UserRegister, db: Session = Depends(get_db)):
    if not settings.EMAIL_DELIVERY_ENABLED:
        raise _error("email_delivery_unavailable", "Registration is unavailable until email delivery is configured.", status.HTTP_503_SERVICE_UNAVAILABLE)
    if db.query(User.id).filter(User.email == data.email).first():
        raise _error("email_already_registered", "Email already registered.", status.HTTP_409_CONFLICT)

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        role="user",
        is_active=True,
        is_setup_complete=False,
        email_verified_at=None,
    )
    try:
        db.add(user)
        db.flush()
        ensure_default_site(db, user.id)
        _queue_action_email(db, user, "verify_email")
        record_audit_event(db, "auth.registered", target_user_id=user.id, target=f"user:{user.id}")
        db.commit()
    except Exception:
        db.rollback()
        raise
    return RegistrationResponse(message="Check your email to verify your account.")


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT)
def login(request: Request, response: Response, data: UserLogin, db: Session = Depends(get_db)):
    user = authenticate_user(db, data.email, data.password)
    if not user or not user.is_active:
        raise _error("invalid_credentials", "Invalid email or password.", status.HTTP_401_UNAUTHORIZED)
    if user.email_verified_at is None:
        raise _error("email_verification_required", "Verify your email before signing in.", status.HTTP_403_FORBIDDEN)
    user.last_login = datetime.now(timezone.utc)
    record_audit_event(db, "auth.login", actor_user_id=user.id, target_user_id=user.id, target=f"user:{user.id}")
    return _issue_session(response, db, user)


@router.post("/verification/resend", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
def resend_verification(request: Request, data: PasswordResetRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    now = datetime.now(timezone.utc)
    if settings.EMAIL_DELIVERY_ENABLED and user and user.is_active and user.email_verified_at is None:
        cooling_down = has_recent_action_token(
            db,
            user.id,
            "verify_email",
            since=now - timedelta(seconds=60),
        )
        if not cooling_down:
            _queue_action_email(db, user, "verify_email")
            db.commit()
    # Keep the public response neutral for missing, verified, inactive, and cooldown cases.
    hashlib.sha256(data.email.encode("utf-8")).digest()
    return {"message": "If an account needs verification, an email will be sent shortly."}


@router.post("/verification/confirm")
def confirm_verification(data: VerifyTokenRequest, db: Session = Depends(get_db)):
    action = consume_action_token(db, data.token, "verify_email")
    if action is None:
        raise _error("verification_token_invalid", "Verification link is invalid, expired, or already used.", status.HTTP_400_BAD_REQUEST)
    user = db.query(User).filter(User.id == action.user_id, User.is_active.is_(True)).first()
    if user is None:
        db.rollback()
        raise _error("verification_token_invalid", "Verification link is invalid, expired, or already used.", status.HTTP_400_BAD_REQUEST)
    user.email_verified_at = datetime.now(timezone.utc)
    record_audit_event(db, "auth.email_verified", actor_user_id=user.id, target_user_id=user.id, target=f"user:{user.id}")
    db.commit()
    return {"message": "Email verified. You can now sign in."}


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
def request_password_reset(request: Request, data: PasswordResetRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    now = datetime.now(timezone.utc)
    if settings.EMAIL_DELIVERY_ENABLED and user and user.is_active and user.password_hash:
        cooling_down = has_recent_action_token(
            db,
            user.id,
            "reset_password",
            since=now - timedelta(seconds=60),
        )
        if not cooling_down:
            _queue_action_email(db, user, "reset_password")
            db.commit()
    # Perform fixed work for every path without exposing account state.
    hashlib.pbkdf2_hmac("sha256", data.email.encode("utf-8"), b"energyforecast-reset", 20_000)
    return {"message": "If an account matches this email, reset instructions will be sent shortly."}


@router.post("/password-reset/confirm")
def confirm_password_reset(data: PasswordResetConfirm, db: Session = Depends(get_db)):
    action = consume_action_token(db, data.token, "reset_password")
    if action is None:
        raise _error("reset_token_invalid", "Reset link is invalid, expired, or already used.", status.HTTP_400_BAD_REQUEST)
    user = db.query(User).filter(User.id == action.user_id, User.is_active.is_(True)).first()
    if user is None:
        db.rollback()
        raise _error("reset_token_invalid", "Reset link is invalid, expired, or already used.", status.HTTP_400_BAD_REQUEST)
    user.password_hash = hash_password(data.new_password)
    revoke_user_sessions(db, user.id)
    record_audit_event(db, "auth.password_reset", actor_user_id=user.id, target_user_id=user.id, target=f"user:{user.id}")
    db.commit()
    return {"message": "Password reset. Please sign in."}


@router.post("/refresh", response_model=TokenData)
def refresh_token(request: Request, response: Response, db: Session = Depends(get_db)):
    _require_trusted_origin(request)
    token = request.cookies.get("refresh_token")
    if not token:
        return _cookie_error("refresh_session_missing", "Refresh session is missing.", status.HTTP_401_UNAUTHORIZED)
    try:
        payload = decode_token(token)
    except HTTPException:
        return _cookie_error("refresh_token_invalid", "Refresh session is invalid.", status.HTTP_401_UNAUTHORIZED)
    if payload.get("type") != "refresh" or not consume_refresh_token(db, token):
        db.rollback()
        return _cookie_error("refresh_token_replayed", "Refresh session is invalid or already used.", status.HTTP_401_UNAUTHORIZED)
    try:
        user_id = int(payload.get("sub", ""))
    except (TypeError, ValueError):
        db.rollback()
        return _cookie_error("refresh_token_invalid", "Refresh session is invalid.", status.HTTP_401_UNAUTHORIZED)
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user or user.email_verified_at is None:
        db.rollback()
        return _cookie_error("refresh_user_unavailable", "Refresh session is no longer available.", status.HTTP_401_UNAUTHORIZED)
    new_access = create_access_token({"sub": str(user.id), "role": user.role})
    new_refresh = create_refresh_token({"sub": str(user.id), "role": user.role})
    store_refresh_token(db, new_refresh, user.id, commit=False)
    db.commit()
    _set_refresh_cookie(response, new_refresh)
    return TokenData(access_token=new_access)


@router.post("/logout")
def logout(request: Request, response: Response, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_trusted_origin(request)
    token = request.cookies.get("refresh_token")
    if token:
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).update({"is_revoked": True}, synchronize_session=False)
        db.commit()
    _clear_refresh_cookie(response)
    return {"message": "Logged out successfully"}


@router.post("/logout-all")
def logout_all(request: Request, response: Response, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_trusted_origin(request)
    revoke_user_sessions(db, current_user.id)
    record_audit_event(db, "auth.logout_all", actor_user_id=current_user.id, target_user_id=current_user.id, target=f"user:{current_user.id}")
    db.commit()
    _clear_refresh_cookie(response)
    return {"message": "Logged out on all devices"}


@router.post("/google/challenge", response_model=GoogleChallengeResponse)
@limiter.limit("10/minute")
def google_login_challenge(request: Request, db: Session = Depends(get_db)):
    _require_trusted_origin(request)
    if not settings.GOOGLE_AUTH_ENABLED:
        raise _error("google_auth_disabled", "Google sign-in is not enabled.", status.HTTP_404_NOT_FOUND)
    challenge = issue_oauth_challenge(db, action="login")
    db.commit()
    return GoogleChallengeResponse(**challenge.__dict__)


@router.post("/google", response_model=TokenResponse)
def google_login(request: Request, response: Response, data: GoogleCredentialRequest, db: Session = Depends(get_db)):
    _require_trusted_origin(request)
    # Decode only to obtain the nonce; authenticity is checked immediately after.
    nonce = _unverified_google_nonce(data.credential)
    claims = _verified_google_identity(data.credential, expected_nonce=nonce)
    if not consume_oauth_challenge(db, state=data.state, nonce=nonce, action="login"):
        db.rollback()
        raise _error("google_state_invalid", "Google sign-in state is invalid, expired, or already used.", status.HTTP_401_UNAUTHORIZED)
    identity = db.query(AuthIdentity).filter(AuthIdentity.provider == "google", AuthIdentity.subject == claims["sub"]).first()
    if identity:
        user = db.query(User).filter(User.id == identity.user_id, User.is_active.is_(True)).first()
        if not user:
            db.rollback()
            raise _error("account_unavailable", "This account is unavailable.", status.HTTP_403_FORBIDDEN)
        user.last_login = datetime.now(timezone.utc)
        return _issue_session(response, db, user)
    normalized_email = str(claims["email"]).strip().lower()
    if db.query(User.id).filter(User.email == normalized_email).first():
        db.rollback()
        raise _error("google_link_required", "Sign in locally and explicitly link Google from account security.", status.HTTP_409_CONFLICT)
    user = User(
        email=normalized_email,
        full_name=claims.get("name"),
        role="user",
        is_active=True,
        email_verified_at=datetime.now(timezone.utc),
        is_setup_complete=False,
    )
    db.add(user)
    db.flush()
    ensure_default_site(db, user.id)
    db.add(AuthIdentity(user_id=user.id, provider="google", subject=claims["sub"], email=normalized_email))
    record_audit_event(db, "auth.google_registered", actor_user_id=user.id, target_user_id=user.id, target=f"user:{user.id}")
    return _issue_session(response, db, user)


@router.post("/google/link/challenge", response_model=GoogleChallengeResponse)
def google_link_challenge(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_trusted_origin(request)
    if not settings.GOOGLE_AUTH_ENABLED:
        raise _error("google_auth_disabled", "Google sign-in is not enabled.", status.HTTP_404_NOT_FOUND)
    challenge = issue_oauth_challenge(db, action="link", user_id=current_user.id)
    db.commit()
    return GoogleChallengeResponse(**challenge.__dict__)


@router.get("/google/status")
def google_identity_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    linked = db.query(AuthIdentity.id).filter(
        AuthIdentity.user_id == current_user.id,
        AuthIdentity.provider == "google",
    ).first() is not None
    return {"linked": linked, "can_unlink": linked and bool(current_user.password_hash)}


@router.post("/google/link")
def link_google_identity(request: Request, data: GoogleLinkRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_trusted_origin(request)
    if not current_user.password_hash or not verify_password(data.current_password, current_user.password_hash):
        raise _error("recent_auth_required", "Current password confirmation is required.", status.HTTP_403_FORBIDDEN)
    nonce = _unverified_google_nonce(data.credential)
    claims = _verified_google_identity(data.credential, expected_nonce=nonce)
    if not consume_oauth_challenge(db, state=data.state, nonce=nonce, action="link", user_id=current_user.id):
        db.rollback()
        raise _error("google_state_invalid", "Google linking state is invalid, expired, or already used.", status.HTTP_401_UNAUTHORIZED)
    if str(claims["email"]).strip().lower() != current_user.email.lower():
        db.rollback()
        raise _error("google_email_mismatch", "Google email must match the signed-in account.", status.HTTP_400_BAD_REQUEST)
    conflicting = db.query(AuthIdentity).filter(AuthIdentity.provider == "google", AuthIdentity.subject == claims["sub"]).first()
    if conflicting and conflicting.user_id != current_user.id:
        db.rollback()
        raise _error("google_subject_in_use", "Google account is already linked.", status.HTTP_409_CONFLICT)
    existing = db.query(AuthIdentity).filter(AuthIdentity.user_id == current_user.id, AuthIdentity.provider == "google").first()
    if not existing:
        db.add(AuthIdentity(user_id=current_user.id, provider="google", subject=claims["sub"], email=current_user.email))
        record_audit_event(db, "auth.google_linked", actor_user_id=current_user.id, target_user_id=current_user.id, target=f"user:{current_user.id}")
    db.commit()
    return {"message": "Google account linked"}


@router.delete("/google/link")
def unlink_google_identity(request: Request, response: Response, data: GoogleUnlinkRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_trusted_origin(request)
    identity = db.query(AuthIdentity).filter(AuthIdentity.user_id == current_user.id, AuthIdentity.provider == "google").first()
    if identity is None:
        raise _error("google_identity_not_linked", "No Google account is linked.", status.HTTP_404_NOT_FOUND)
    if not current_user.password_hash:
        raise _error("last_login_method", "Set a local password before unlinking your only sign-in method.", status.HTTP_409_CONFLICT)
    if not data.current_password or not verify_password(data.current_password, current_user.password_hash):
        raise _error("recent_auth_required", "Current password confirmation is required.", status.HTTP_403_FORBIDDEN)
    db.delete(identity)
    revoke_user_sessions(db, current_user.id)
    record_audit_event(db, "auth.google_unlinked", actor_user_id=current_user.id, target_user_id=current_user.id, target=f"user:{current_user.id}")
    db.commit()
    _clear_refresh_cookie(response)
    return {"message": "Google account unlinked. Sign in again."}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
def update_me(data: UserUpdateMe, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if data.full_name is not None:
        current_user.full_name = data.full_name
    db.commit()
    db.refresh(current_user)
    return UserResponse.model_validate(current_user)


@router.put("/password")
def update_password(request: Request, data: PasswordUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_trusted_origin(request)
    if not current_user.password_hash or not verify_password(data.current_password, current_user.password_hash):
        raise _error("current_password_invalid", "Current password is incorrect.", status.HTTP_400_BAD_REQUEST)
    current_user.password_hash = hash_password(data.new_password)
    revoke_user_sessions(db, current_user.id)
    record_audit_event(db, "auth.password_changed", actor_user_id=current_user.id, target_user_id=current_user.id, target=f"user:{current_user.id}")
    db.commit()
    return {"message": "Password updated. Sign in again on your other devices."}


@router.post("/me/avatar", response_model=UserResponse)
def upload_avatar(file: UploadFile = File(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    allowed_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    allowed_mime_types = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    filename = file.filename or "avatar"
    _, ext = os.path.splitext(filename.lower())
    if ext not in allowed_extensions or file.content_type not in allowed_mime_types:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only JPG, JPEG, PNG, GIF, and WebP images are allowed.")
    try:
        contents = file.file.read()
        if len(contents) > 2 * 1024 * 1024:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image file size must not exceed 2MB.")
        os.makedirs(settings.AVATAR_STORAGE_DIR, exist_ok=True)
        new_filename = f"user_{current_user.id}_{int(time.time())}{ext}"
        file_path = os.path.join(settings.AVATAR_STORAGE_DIR, new_filename)
        with open(file_path, "wb") as target:
            target.write(contents)
        if current_user.avatar_url and current_user.avatar_url.startswith("/static/avatars/"):
            old_path = os.path.join(settings.AVATAR_STORAGE_DIR, os.path.basename(current_user.avatar_url))
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except Exception as exc:
                    logger.error("Failed to remove old avatar: %s", type(exc).__name__)
        current_user.avatar_url = f"/static/avatars/{new_filename}"
        db.commit()
        db.refresh(current_user)
        return UserResponse.model_validate(current_user)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Avatar processing failed: %s", type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process image upload.")


@router.delete("/me/avatar", response_model=UserResponse)
def delete_avatar(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.avatar_url:
        if current_user.avatar_url.startswith("/static/avatars/"):
            old_path = os.path.join(settings.AVATAR_STORAGE_DIR, os.path.basename(current_user.avatar_url))
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except Exception as exc:
                    logger.error("Failed to remove avatar: %s", type(exc).__name__)
        current_user.avatar_url = None
        db.commit()
        db.refresh(current_user)
    return UserResponse.model_validate(current_user)
