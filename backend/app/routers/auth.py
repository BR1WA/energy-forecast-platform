"""
Authentication router — login, register, token refresh.
"""
from datetime import datetime, timezone
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
from sqlalchemy.orm import Session
import os
import time

logger = logging.getLogger(__name__)

from app.database import get_db
from app.models import User, RefreshToken
from app.schemas import (
    UserRegister, UserLogin, UserResponse, TokenResponse,
    RefreshRequest, TokenData, UserUpdateMe, PasswordUpdate,
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

settings = get_settings()

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(request: Request, data: UserRegister, db: Session = Depends(get_db)):
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

    db.commit()
    db.refresh(user)
    ensure_default_site(db, user.id)
    record_audit_event(db, "auth.registered", actor_user_id=user.id, target_user_id=user.id, target=f"user:{user.id}")
    db.commit()

    # Generate tokens
    token_data = {"sub": str(user.id), "role": user.role}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # Store refresh token in DB
    store_refresh_token(db, refresh_token, user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT)
def login(request: Request, data: UserLogin, db: Session = Depends(get_db)):
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

    # Generate tokens
    token_data = {"sub": str(user.id), "role": user.role}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # Store refresh token in DB
    store_refresh_token(db, refresh_token, user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=TokenData)
def refresh_token(data: RefreshRequest, db: Session = Depends(get_db)):
    """Refresh an access token using a valid refresh token and rotate it."""
    payload = decode_token(data.refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Verify refresh token exists in DB and is active
    if not verify_refresh_token(db, data.refresh_token):
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
    old_hash = hashlib.sha256(data.refresh_token.encode('utf-8')).hexdigest()
    db.query(RefreshToken).filter(RefreshToken.token_hash == old_hash).update({"is_revoked": True})

    # Issue new access token and new rotated refresh token
    token_data = {"sub": str(user.id), "role": user.role}
    new_access = create_access_token(token_data)
    new_refresh = create_refresh_token(token_data)

    # Store new refresh token
    store_refresh_token(db, new_refresh, user.id)

    return TokenData(access_token=new_access, refresh_token=new_refresh)


@router.post("/logout")
def logout(
    data: Optional[RefreshRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Log out a user by invalidating their refresh token(s)."""
    import hashlib
    if data and data.refresh_token:
        # Invalidate the specific token
        token_hash = hashlib.sha256(data.refresh_token.encode('utf-8')).hexdigest()
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
    return {"message": "Logged out successfully"}


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
        os.makedirs("static/avatars", exist_ok=True)
        
        # 4. Generate unique filename
        timestamp = int(time.time())
        new_filename = f"user_{current_user.id}_{timestamp}{ext}"
        file_path = os.path.join("static", "avatars", new_filename)
        
        # 5. Write contents to file
        with open(file_path, "wb") as f:
            f.write(contents)
            
        # 6. Delete old avatar file if it exists
        if current_user.avatar_url and current_user.avatar_url.startswith("/static/avatars/"):
            old_path = current_user.avatar_url.lstrip("/")
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
            old_path = current_user.avatar_url.lstrip("/")
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except Exception as ex:
                    logger.error(f"Failed to remove avatar file: {ex}")
        
        current_user.avatar_url = None
        db.commit()
        db.refresh(current_user)
        
    return UserResponse.model_validate(current_user)
