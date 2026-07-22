"""
Authentication router — login, register, token refresh.
"""
from datetime import datetime, timezone
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request, Response
from sqlalchemy.orm import Session
import os
import time

logger = logging.getLogger(__name__)

from app.database import get_db
from app.models import User, RefreshToken, AuthIdentity
from app.schemas import (
    UserRegister, UserLogin, UserResponse, TokenResponse,
    TokenData, UserUpdateMe, PasswordUpdate, VerifyTokenRequest, PasswordResetRequest, PasswordResetConfirm, GoogleCredentialRequest,
)
from app.services.auth_service import (
    hash_password, verify_password, authenticate_user, create_access_token,
    create_refresh_token, decode_token, get_current_user, store_refresh_token,
    verify_refresh_token
)
from app.services.site_service import ensure_default_site
from app.services.audit_service import record_audit_event
from app.limiter import limiter
from app.config import get_settings
from app.services.account_action_service import issue_action_token, consume_action_token
from app.services.email_service import enqueue_email

settings = get_settings()

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/api/v1/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie("refresh_token", path="/api/v1/auth", httponly=True, secure=not settings.DEBUG, samesite="lax")


def _verified_google_identity(credential: str) -> dict:
    if not settings.GOOGLE_AUTH_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Google sign-in is not enabled")
    try:
        from google.auth.transport.requests import Request as GoogleRequest
        from google.oauth2 import id_token
        claims = id_token.verify_oauth2_token(credential, GoogleRequest(), settings.GOOGLE_CLIENT_ID)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google credential could not be verified")
    if not claims.get("email_verified") or not claims.get("sub") or not claims.get("email"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google account has no verified email")
    return claims


def _login_response(response: Response, db: Session, user: User) -> TokenResponse:
    token_data = {"sub": str(user.id), "role": user.role}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    store_refresh_token(db, refresh_token, user.id)
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token, user=UserResponse.model_validate(user))


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(request: Request, response: Response, data: UserRegister, db: Session = Depends(get_db)):
    """Register a new user account."""
    # Check if email already exists
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    # Create user
    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        role="user",
        is_active=True,
        is_setup_complete=False,
    )
    db.add(user)

    db.flush()
    ensure_default_site(db, user.id)
    record_audit_event(db, "auth.registered", actor_user_id=user.id, target_user_id=user.id, target=f"user:{user.id}")
    db.commit()
    db.refresh(user)

    return _login_response(response, db, user)


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT)
def login(request: Request, response: Response, data: UserLogin, db: Session = Depends(get_db)):
    """Authenticate and receive JWT tokens."""
    user = authenticate_user(db, data.email, data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Update last login
    user.last_login = datetime.now(timezone.utc)
    record_audit_event(db, "auth.login", actor_user_id=user.id, target_user_id=user.id, target=f"user:{user.id}")
    db.commit()

    return _login_response(response, db, user)


@router.post("/google", response_model=TokenResponse)
def google_login(data: GoogleCredentialRequest, response: Response, db: Session = Depends(get_db)):
    """Sign in with a Google ID token after server-side audience verification."""
    claims = _verified_google_identity(data.credential)
    identity = db.query(AuthIdentity).filter(AuthIdentity.provider == "google", AuthIdentity.subject == claims["sub"]).first()
    if identity:
        user = db.query(User).filter(User.id == identity.user_id, User.is_active.is_(True)).first()
        if user:
            return _login_response(response, db, user)
    existing = db.query(User).filter(User.email == claims["email"].lower()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Sign in with your existing method, then link Google from account security")
    user = User(email=claims["email"].lower(), full_name=claims.get("name"), role="user", is_active=True, email_verified_at=datetime.now(timezone.utc))
    db.add(user)
    db.flush()
    ensure_default_site(db, user.id)
    db.add(AuthIdentity(user_id=user.id, provider="google", subject=claims["sub"], email=user.email))
    record_audit_event(db, "auth.google_registered", actor_user_id=user.id, target_user_id=user.id, target=f"user:{user.id}")
    db.commit()
    db.refresh(user)
    return _login_response(response, db, user)


@router.post("/google/link")
def link_google_identity(data: GoogleCredentialRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Link only a verified Google account for the currently authenticated email."""
    claims = _verified_google_identity(data.credential)
    if claims["email"].lower() != current_user.email.lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google email must match the signed-in account")
    conflicting = db.query(AuthIdentity).filter(AuthIdentity.provider == "google", AuthIdentity.subject == claims["sub"]).first()
    if conflicting and conflicting.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Google account is already linked")
    if not conflicting:
        db.add(AuthIdentity(user_id=current_user.id, provider="google", subject=claims["sub"], email=current_user.email))
        record_audit_event(db, "auth.google_linked", actor_user_id=current_user.id, target_user_id=current_user.id, target=f"user:{current_user.id}")
        db.commit()
    return {"message": "Google account linked"}


@router.post("/refresh", response_model=TokenData)
def refresh_token(request: Request, response: Response, db: Session = Depends(get_db)):
    """Refresh an access token using a valid refresh token and rotate it."""
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh session is missing")
    payload = decode_token(token)

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Verify refresh token exists in DB and is active
    if not verify_refresh_token(db, token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid, expired, or revoked",
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )

    # Invalidate old refresh token (rotation)
    import hashlib
    old_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
    db.query(RefreshToken).filter(RefreshToken.token_hash == old_hash).update({"is_revoked": True})

    # Issue new access token and new rotated refresh token
    token_data = {"sub": str(user.id), "role": user.role}
    new_access = create_access_token(token_data)
    new_refresh = create_refresh_token(token_data)

    # Store new refresh token
    store_refresh_token(db, new_refresh, user.id)
    _set_refresh_cookie(response, new_refresh)

    return TokenData(access_token=new_access)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Log out a user by invalidating their refresh token(s)."""
    import hashlib
    token = request.cookies.get("refresh_token")
    if token:
        # Invalidate the specific token
        token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
        db_token = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
        if db_token:
            db_token.is_revoked = True
            db.commit()
    else:
        # Invalidate all active tokens for this user
        db.query(RefreshToken).filter(
            RefreshToken.user_id == current_user.id,
            RefreshToken.is_revoked == False
        ).update({"is_revoked": True})
        db.commit()
    _clear_refresh_cookie(response)
    return {"message": "Logged out successfully"}


@router.post("/verification/resend", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
def resend_verification(request: Request, data: PasswordResetRequest, db: Session = Depends(get_db)):
    """Queue a verification email without exposing whether the address exists."""
    user = db.query(User).filter(User.email == data.email).first()
    if user and not user.email_verified_at and settings.EMAIL_DELIVERY_ENABLED:
        token = issue_action_token(db, user.id, "verify_email")
        enqueue_email(
            db, user_id=user.id, recipient=user.email, template="verify_email",
            dedup_key=f"verify:{user.id}:{token[:12]}",
            payload={"url": f"{settings.PUBLIC_FRONTEND_URL.rstrip('/')}/verify-email?token={token}"},
        )
        db.commit()
    return {"message": "If an account needs verification, an email will be sent shortly."}


@router.post("/verification/confirm")
def confirm_verification(data: VerifyTokenRequest, db: Session = Depends(get_db)):
    action = consume_action_token(db, data.token, "verify_email")
    if action is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification link is invalid or expired")
    user = db.query(User).filter(User.id == action.user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification link is invalid or expired")
    user.email_verified_at = datetime.now(timezone.utc)
    record_audit_event(db, "auth.email_verified", actor_user_id=user.id, target_user_id=user.id, target=f"user:{user.id}")
    db.commit()
    return {"message": "Email verified"}


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
def request_password_reset(request: Request, data: PasswordResetRequest, db: Session = Depends(get_db)):
    """Non-enumerating password reset request."""
    user = db.query(User).filter(User.email == data.email, User.is_active.is_(True)).first()
    if user and user.password_hash and settings.EMAIL_DELIVERY_ENABLED:
        token = issue_action_token(db, user.id, "password_reset")
        enqueue_email(
            db, user_id=user.id, recipient=user.email, template="password_reset",
            dedup_key=f"reset:{user.id}:{token[:12]}",
            payload={"url": f"{settings.PUBLIC_FRONTEND_URL.rstrip('/')}/reset-password?token={token}"},
        )
        db.commit()
    return {"message": "If an account matches this email, reset instructions will be sent shortly."}


@router.post("/password-reset/confirm")
def confirm_password_reset(data: PasswordResetConfirm, db: Session = Depends(get_db)):
    action = consume_action_token(db, data.token, "password_reset")
    if action is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset link is invalid or expired")
    user = db.query(User).filter(User.id == action.user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset link is invalid or expired")
    user.password_hash = hash_password(data.new_password)
    db.query(RefreshToken).filter(RefreshToken.user_id == user.id, RefreshToken.is_revoked.is_(False)).update({"is_revoked": True})
    record_audit_event(db, "auth.password_reset", actor_user_id=user.id, target_user_id=user.id, target=f"user:{user.id}")
    db.commit()
    return {"message": "Password reset. Please sign in."}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user profile."""
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
def update_me(
    data: UserUpdateMe,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update current user's profile."""
    if data.full_name is not None:
        current_user.full_name = data.full_name
    db.commit()
    db.refresh(current_user)
    return UserResponse.model_validate(current_user)


@router.put("/password")
def update_password(
    data: PasswordUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change current user's password."""
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    current_user.password_hash = hash_password(data.new_password)
    db.query(RefreshToken).filter(
        RefreshToken.user_id == current_user.id,
        RefreshToken.is_revoked.is_(False),
    ).update({"is_revoked": True})
    record_audit_event(
        db,
        "auth.password_changed",
        actor_user_id=current_user.id,
        target_user_id=current_user.id,
        target=f"user:{current_user.id}",
    )
    db.commit()
    return {"message": "Password updated. Sign in again on your other devices."}


@router.post("/me/avatar", response_model=UserResponse)
def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a new profile picture/avatar (Admin/User)."""
    # 1. Validate file extension and MIME type
    allowed_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    allowed_mime_types = {"image/jpeg", "image/png", "image/gif", "image/webp"}

    filename = file.filename or "avatar"
    _, ext = os.path.splitext(filename.lower())
    
    if ext not in allowed_extensions or file.content_type not in allowed_mime_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPG, JPEG, PNG, GIF, and WebP images are allowed.",
        )

    # 2. Validate file size (limit: 2MB)
    max_size = 2 * 1024 * 1024 # 2MB
    
    try:
        contents = file.file.read()
        file_size = len(contents)
        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image file size must not exceed 2MB.",
            )
        
        # 3. Create static/avatars/ directory if needed
        os.makedirs(settings.AVATAR_STORAGE_DIR, exist_ok=True)
        
        # 4. Generate unique filename
        timestamp = int(time.time())
        new_filename = f"user_{current_user.id}_{timestamp}{ext}"
        file_path = os.path.join(settings.AVATAR_STORAGE_DIR, new_filename)
        
        # 5. Write contents to file
        with open(file_path, "wb") as f:
            f.write(contents)
            
        # 6. Delete old avatar file if it exists
        if current_user.avatar_url and current_user.avatar_url.startswith("/static/avatars/"):
            old_path = os.path.join(settings.AVATAR_STORAGE_DIR, os.path.basename(current_user.avatar_url))
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except Exception as ex:
                    logger.error(f"Failed to remove old avatar: {ex}")
                    
        # 7. Update user's avatar_url
        current_user.avatar_url = f"/static/avatars/{new_filename}"
        db.commit()
        db.refresh(current_user)
        
        return UserResponse.model_validate(current_user)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process image upload: {str(e)}",
        )


@router.delete("/me/avatar", response_model=UserResponse)
def delete_avatar(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete current user's profile picture/avatar."""
    if current_user.avatar_url:
        if current_user.avatar_url.startswith("/static/avatars/"):
            old_path = os.path.join(settings.AVATAR_STORAGE_DIR, os.path.basename(current_user.avatar_url))
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except Exception as ex:
                    logger.error(f"Failed to remove avatar file: {ex}")
        
        current_user.avatar_url = None
        db.commit()
        db.refresh(current_user)
        
    return UserResponse.model_validate(current_user)
