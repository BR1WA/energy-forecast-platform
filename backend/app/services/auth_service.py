"""
Authentication service — JWT token management and password hashing.
Uses bcrypt directly (passlib has compatibility issues with bcrypt 5.x).
"""
from datetime import datetime, timedelta, timezone
import logging
from typing import Optional
from jose import jwt, JWTError
import bcrypt
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.config import get_settings
from app.database import get_db
from app.models import User, RefreshToken

settings = get_settings()

logger = logging.getLogger(__name__)

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    """Verify a password against its hash."""
    if not hashed_password:
        return False
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token."""
    import uuid
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh", "jti": str(uuid.uuid4())})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency: extract and validate current user from JWT."""
    payload = decode_token(token)

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id: int = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    try:
        uid = int(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload format",
        )

    user = db.query(User).filter(User.id == uid).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    # Update last_activity if it's more than 30 seconds ago (throttled to save database writes)
    now = datetime.now(timezone.utc)
    last_act = user.last_activity
    should_update = False
    if not last_act:
        should_update = True
    else:
        if last_act.tzinfo is None:
            last_act_utc = last_act.replace(tzinfo=timezone.utc)
        else:
            last_act_utc = last_act.astimezone(timezone.utc)
        if (now - last_act_utc).total_seconds() > 10:
            should_update = True

    if should_update:
        user.last_activity = now
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update last_activity: {e}")

    return user


def require_role(allowed_roles: list[str]):
    """FastAPI dependency factory: require specific user roles."""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {', '.join(allowed_roles)}",
            )
        return current_user
    return role_checker


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Authenticate a user by email and password."""
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user:
        return None
    if not user.password_hash or not verify_password(password, user.password_hash):
        return None
    return user


def store_refresh_token(db: Session, token: str, user_id: int, *, commit: bool = True):
    """Store a refresh-token hash; callers may keep it in their transaction."""
    import hashlib
    token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
    
    # Extract expiration from JWT payload
    payload = decode_token(token)
    exp_ts = payload.get("exp")
    expires_at = datetime.fromtimestamp(exp_ts, tz=timezone.utc)
    
    # Store the new token
    db_token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        is_revoked=False
    )
    db.add(db_token)
    
    # Clean up expired tokens for this user
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.expires_at < datetime.now(timezone.utc)
    ).delete()
    
    if commit:
        db.commit()
    else:
        db.flush()


def verify_refresh_token(db: Session, token: str) -> bool:
    """Verify if a refresh token is valid and exists in the database."""
    import hashlib
    token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
    
    db_token = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
        RefreshToken.is_revoked == False,
        RefreshToken.expires_at > datetime.now(timezone.utc)
    ).first()
    
    return db_token is not None


def consume_refresh_token(db: Session, token: str) -> bool:
    """Atomically revoke one live refresh token to prevent concurrent replay."""
    import hashlib
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    changed = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
        RefreshToken.is_revoked.is_(False),
        RefreshToken.expires_at > datetime.now(timezone.utc),
    ).update({"is_revoked": True}, synchronize_session=False)
    return changed == 1


def revoke_user_sessions(db: Session, user_id: int) -> int:
    return db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.is_revoked.is_(False),
    ).update({"is_revoked": True}, synchronize_session=False)
