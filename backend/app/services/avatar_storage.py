"""Durable local avatar storage with decoded-image validation and retryable cleanup."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import BytesIO
import logging
import os
from pathlib import Path
import re
import tempfile
import uuid
from typing import Protocol

from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import AvatarCleanupJob


logger = logging.getLogger(__name__)
register_heif_opener(thumbnails=False)
AVATAR_URL_PREFIX = "/static/avatars/"
OBJECT_KEY_PATTERN = re.compile(r"^[0-9a-f]{32}\.webp$")
LEGACY_OBJECT_KEY_PATTERN = re.compile(r"^user_[0-9]+_[0-9]+\.(?:jpe?g|png|gif|webp)$")
SUPPORTED_CONTENT_TYPES = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
    "image/heic": "HEIF",
    "image/heif": "HEIF",
}


class AvatarStorage(Protocol):
    def store(self, content: bytes) -> str: ...
    def delete(self, object_key: str) -> None: ...
    def exists(self, object_key: str) -> bool: ...
    def public_url(self, object_key: str) -> str: ...


class AvatarValidationError(ValueError):
    pass


@dataclass(frozen=True)
class PreparedAvatar:
    content: bytes
    width: int
    height: int


def avatar_object_key(avatar_url: str | None) -> str | None:
    if not avatar_url or not avatar_url.startswith(AVATAR_URL_PREFIX):
        return None
    key = avatar_url.removeprefix(AVATAR_URL_PREFIX)
    return key if OBJECT_KEY_PATTERN.fullmatch(key) or LEGACY_OBJECT_KEY_PATTERN.fullmatch(key) else None


def prepare_avatar(raw: bytes, content_type: str | None, settings: Settings | None = None) -> PreparedAvatar:
    settings = settings or get_settings()
    if not raw:
        raise AvatarValidationError("Avatar image is empty.")
    if len(raw) > settings.AVATAR_MAX_BYTES:
        raise AvatarValidationError(f"Avatar image must not exceed {settings.AVATAR_MAX_BYTES // (1024 * 1024)} MB.")
    expected_format = SUPPORTED_CONTENT_TYPES.get((content_type or "").lower())
    if expected_format is None:
        raise AvatarValidationError("Avatar must be a JPEG, PNG, WebP, HEIC, or HEIF image.")

    try:
        with Image.open(BytesIO(raw)) as probe:
            decoded_format = probe.format
            width, height = probe.size
            probe.verify()
        if decoded_format != expected_format:
            raise AvatarValidationError("Avatar content does not match its declared image type.")
        if width < 1 or height < 1 or max(width, height) > settings.AVATAR_MAX_DIMENSION:
            raise AvatarValidationError(
                f"Avatar dimensions must be between 1 and {settings.AVATAR_MAX_DIMENSION} pixels."
            )
        with Image.open(BytesIO(raw)) as decoded:
            decoded.load()
            sanitized = ImageOps.exif_transpose(decoded)
            sanitized = sanitized.convert("RGBA" if "A" in sanitized.getbands() else "RGB")
            output = BytesIO()
            sanitized.save(output, format="WEBP", quality=90, method=6)
    except AvatarValidationError:
        raise
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as exc:
        raise AvatarValidationError("Avatar image could not be decoded safely.") from exc
    return PreparedAvatar(content=output.getvalue(), width=width, height=height)


class LocalAvatarStorage:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, object_key: str) -> Path:
        if not OBJECT_KEY_PATTERN.fullmatch(object_key) and not LEGACY_OBJECT_KEY_PATTERN.fullmatch(object_key):
            raise ValueError("Invalid avatar object key")
        path = (self.root / object_key).resolve()
        if path.parent != self.root:
            raise ValueError("Invalid avatar object path")
        return path

    def store(self, content: bytes) -> str:
        object_key = f"{uuid.uuid4().hex}.webp"
        destination = self._path(object_key)
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.root, prefix=".upload-", suffix=".tmp", delete=False) as handle:
                temporary_path = handle.name
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, destination)
        finally:
            if temporary_path and os.path.exists(temporary_path):
                os.remove(temporary_path)
        return object_key

    def delete(self, object_key: str) -> None:
        self._path(object_key).unlink(missing_ok=True)

    def exists(self, object_key: str) -> bool:
        return self._path(object_key).is_file()

    def public_url(self, object_key: str) -> str:
        self._path(object_key)
        return f"{AVATAR_URL_PREFIX}{object_key}"


def get_avatar_storage(settings: Settings | None = None) -> LocalAvatarStorage:
    settings = settings or get_settings()
    return LocalAvatarStorage(settings.AVATAR_STORAGE_DIR)


def schedule_avatar_cleanup(db: Session, object_key: str, reason: str) -> AvatarCleanupJob:
    existing = db.query(AvatarCleanupJob).filter(AvatarCleanupJob.object_key == object_key).first()
    if existing is not None:
        return existing
    job = AvatarCleanupJob(id=str(uuid.uuid4()), object_key=object_key, reason=reason)
    db.add(job)
    db.flush()
    return job


def process_avatar_cleanup(
    db: Session,
    *,
    storage: AvatarStorage | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
    limit: int = 20,
) -> int:
    settings = settings or get_settings()
    storage = storage or get_avatar_storage(settings)
    now = now or datetime.now(timezone.utc)
    query = (
        db.query(AvatarCleanupJob)
        .filter(
            AvatarCleanupJob.status.in_(("pending", "retry")),
            AvatarCleanupJob.next_attempt_at <= now,
        )
        .order_by(AvatarCleanupJob.next_attempt_at, AvatarCleanupJob.created_at)
    )
    if db.get_bind().dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)
    jobs = query.limit(limit).all()
    for job in jobs:
        job.attempts += 1
        try:
            storage.delete(job.object_key)
            db.delete(job)
        except Exception as exc:
            job.last_error = f"{type(exc).__module__}.{type(exc).__name__}"[:200]
            if job.attempts >= settings.AVATAR_CLEANUP_MAX_ATTEMPTS:
                job.status = "dead"
            else:
                job.status = "retry"
                job.next_attempt_at = now + timedelta(
                    seconds=settings.AVATAR_CLEANUP_RETRY_SECONDS * (2 ** max(job.attempts - 1, 0))
                )
            logger.warning("avatar_cleanup id=%s status=%s", job.id, job.status)
    db.commit()
    return len(jobs)
