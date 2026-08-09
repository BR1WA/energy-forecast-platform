from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
import mimetypes
from pathlib import Path
from unittest.mock import patch
import uuid
import zipfile

from fastapi.testclient import TestClient
from PIL import Image
from pillow_heif import register_heif_opener
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import (
    Alert,
    AuditEvent,
    AuthIdentity,
    AvatarCleanupJob,
    EmailOutbox,
    Forecast,
    OAuthChallenge,
    RefreshToken,
    SmartMeterReading,
    User,
)
from app.routers import auth as auth_router
from app.services.auth_service import create_access_token, hash_password
from app.services.avatar_storage import (
    AvatarValidationError,
    LocalAvatarStorage,
    prepare_avatar,
    process_avatar_cleanup,
    schedule_avatar_cleanup,
)
from app.services.site_service import ensure_default_site, get_default_meter


ORIGIN = "http://localhost:3000"


@pytest.fixture
def account_context(tmp_path):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    original_storage = auth_router.settings.AVATAR_STORAGE_DIR
    auth_router.settings.AVATAR_STORAGE_DIR = str(tmp_path / "avatars")
    app.dependency_overrides[get_db] = override_get_db
    try:
        yield Session, TestClient(app), Path(auth_router.settings.AVATAR_STORAGE_DIR)
    finally:
        auth_router.settings.AVATAR_STORAGE_DIR = original_storage
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(engine)


def _user(db, email: str, *, password: str | None = "password123") -> User:
    user = User(
        email=email,
        password_hash=hash_password(password) if password else None,
        role="user",
        is_active=True,
        email_verified_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.flush()
    ensure_default_site(db, user.id)
    db.commit()
    return user


def _headers(user: User) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}",
        "Origin": ORIGIN,
    }


def _image_bytes(format_name: str = "PNG", size: tuple[int, int] = (64, 48), color=(20, 120, 220)) -> bytes:
    image = Image.new("RGB", size, color)
    output = BytesIO()
    image.save(output, format=format_name)
    return output.getvalue()


def _heif_bytes(size: tuple[int, int] = (64, 48)) -> bytes:
    register_heif_opener(thumbnails=False)
    output = BytesIO()
    Image.new("RGB", size, color=(20, 120, 220)).save(output, format="HEIF", quality=90)
    return output.getvalue()


def test_avatar_validation_uses_decoded_type_dimensions_and_opaque_paths(tmp_path):
    prepared = prepare_avatar(_image_bytes("PNG"), "image/png", auth_router.settings)
    assert prepared.width == 64 and prepared.height == 48
    with Image.open(BytesIO(prepared.content)) as decoded:
        assert decoded.format == "WEBP"

    with pytest.raises(AvatarValidationError, match="declared image type"):
        prepare_avatar(_image_bytes("PNG"), "image/jpeg", auth_router.settings)
    with pytest.raises(AvatarValidationError, match="dimensions"):
        prepare_avatar(_image_bytes("PNG", (2049, 1)), "image/png", auth_router.settings)

    storage = LocalAvatarStorage(tmp_path)
    key = storage.store(prepared.content)
    assert key.endswith(".webp") and "user" not in key
    assert storage.exists(key)
    with pytest.raises(ValueError, match="Invalid avatar object key"):
        storage.delete("../outside.webp")


def test_heic_avatar_is_decoded_validated_and_normalized_to_webp():
    raw = _heif_bytes()

    prepared = prepare_avatar(raw, "image/heic", auth_router.settings)

    assert (prepared.width, prepared.height) == (64, 48)
    with Image.open(BytesIO(prepared.content)) as normalized:
        assert normalized.format == "WEBP"
        assert normalized.size == (64, 48)

    with pytest.raises(AvatarValidationError, match="declared image type"):
        prepare_avatar(raw, "image/jpeg", auth_router.settings)


def test_avatar_webp_mime_type_is_explicitly_registered():
    assert mimetypes.guess_type("opaque-avatar.webp", strict=True) == ("image/webp", None)


def test_avatar_upload_replace_and_delete_remove_objects_after_commit(account_context):
    Session, client, avatar_root = account_context
    db = Session()
    try:
        user = _user(db, "avatar@example.com")
        first = client.post(
            "/api/v1/auth/me/avatar",
            headers=_headers(user),
            files={"file": ("untrusted.exe", _image_bytes("PNG", color=(10, 20, 30)), "image/png")},
        )
        assert first.status_code == 200
        first_url = first.json()["avatar_url"]
        first_path = avatar_root / first_url.rsplit("/", 1)[-1]
        assert first_path.is_file()
        assert first_path.suffix == ".webp"

        second = client.post(
            "/api/v1/auth/me/avatar",
            headers=_headers(user),
            files={"file": ("avatar.png", _image_bytes("PNG", color=(30, 20, 10)), "image/png")},
        )
        assert second.status_code == 200
        second_url = second.json()["avatar_url"]
        second_path = avatar_root / second_url.rsplit("/", 1)[-1]
        assert second_path.is_file()
        assert not first_path.exists()
        assert db.query(AvatarCleanupJob).count() == 0

        deleted = client.delete("/api/v1/auth/me/avatar", headers=_headers(user))
        assert deleted.status_code == 200
        assert deleted.json()["avatar_url"] is None
        assert not second_path.exists()
        assert db.query(AvatarCleanupJob).count() == 0
    finally:
        db.close()


def test_failed_avatar_cleanup_is_bounded_and_retryable(account_context):
    Session, _, avatar_root = account_context
    db = Session()
    try:
        storage = LocalAvatarStorage(avatar_root)
        key = storage.store(_image_bytes("WEBP"))
        schedule_avatar_cleanup(db, key, "test_failure")
        db.commit()

        class FailingStorage:
            def delete(self, object_key: str) -> None:
                raise OSError("storage unavailable")

        now = datetime.now(timezone.utc)
        assert process_avatar_cleanup(db, storage=FailingStorage(), now=now) == 1
        job = db.query(AvatarCleanupJob).one()
        assert job.status == "retry"
        assert job.last_error == "builtins.OSError"
        job.next_attempt_at = now - timedelta(seconds=1)
        db.commit()

        assert process_avatar_cleanup(db, storage=storage, now=now) == 1
        assert db.query(AvatarCleanupJob).count() == 0
        assert not storage.exists(key)
    finally:
        db.close()


def test_export_archive_is_complete_owner_scoped_and_secret_free(account_context):
    Session, client, _ = account_context
    db = Session()
    try:
        owner = _user(db, "export-owner@example.com")
        other = _user(db, "export-other@example.com")
        meter = get_default_meter(db, owner.id)
        other_meter = get_default_meter(db, other.id)
        meter.ingestion_key_hash = "owner-ingestion-secret-hash"
        other_meter.ingestion_key_hash = "other-ingestion-secret-hash"
        now = datetime.now(timezone.utc)
        db.add_all([
            SmartMeterReading(
                meter_id=meter.id, timestamp=now, gap=1.2, grp=0.1, voltage=230,
                intensity=5, sub_metering_1=1, sub_metering_2=2, sub_metering_3=3,
                source="push", quality="validated",
            ),
            SmartMeterReading(
                meter_id=other_meter.id, timestamp=now, gap=9.9, grp=0.1, voltage=230,
                intensity=5, sub_metering_1=1, sub_metering_2=2, sub_metering_3=3,
                source="push", quality="validated",
            ),
            Forecast(user_id=owner.id, site_id=meter.site_id, model_name="global_tft", horizon=24, predictions=[{"timestamp": now.isoformat(), "q50": 1.1}]),
            Forecast(user_id=other.id, site_id=other_meter.site_id, model_name="other-secret-model", horizon=24, predictions=[]),
            EmailOutbox(
                id=str(uuid.uuid4()), user_id=owner.id, recipient=owner.email,
                template="password_reset", payload={"sealed_token": "sealed-export-secret"},
                dedup_key=f"secret:{uuid.uuid4()}", status="pending",
            ),
            RefreshToken(
                user_id=owner.id, token_hash="refresh-export-secret-hash",
                expires_at=now + timedelta(days=1), is_revoked=False,
            ),
        ])
        db.commit()

        response = client.get("/api/v1/account/export", headers=_headers(owner))
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/zip")
        raw = response.content

        with zipfile.ZipFile(BytesIO(raw)) as archive:
            names = set(archive.namelist())
            text = "\n".join(archive.read(name).decode("utf-8") for name in names)
            for secret in (
                owner.password_hash,
                "owner-ingestion-secret-hash",
                "other-ingestion-secret-hash",
                "refresh-export-secret-hash",
                "sealed-export-secret",
                other.email,
                "other-secret-model",
            ):
                assert secret not in text
            assert {"manifest.json", "account.json", "readings.ndjson", "forecasts.ndjson", "alerts.ndjson", "recommendations.ndjson", "audit-events.ndjson"} <= names
            manifest = json.loads(archive.read("manifest.json"))
            assert manifest["counts"]["readings"] == 1
            assert manifest["counts"]["forecasts"] == 1
            account = json.loads(archive.read("account.json"))
            assert account["email"] == owner.email
            assert "password_hash" not in account
            assert "ingestion_key_hash" not in archive.read("meters.json").decode()
    finally:
        db.close()


def test_local_account_deletion_requires_confirmation_and_removes_owned_data(account_context):
    Session, client, avatar_root = account_context
    db = Session()
    try:
        user = _user(db, "delete-local@example.com")
        other = _user(db, "delete-other@example.com")
        user_id = user.id
        other_id = other.id
        upload = client.post(
            "/api/v1/auth/me/avatar",
            headers=_headers(user),
            files={"file": ("avatar.png", _image_bytes(), "image/png")},
        )
        avatar_path = avatar_root / upload.json()["avatar_url"].rsplit("/", 1)[-1]
        now = datetime.now(timezone.utc)
        db.add(EmailOutbox(
            id=str(uuid.uuid4()), user_id=user.id, recipient=user.email,
            template="critical_alert", payload={}, dedup_key=f"delete:{uuid.uuid4()}", status="pending",
        ))
        db.commit()

        missing_confirmation = client.request(
            "DELETE", "/api/v1/account", headers=_headers(user), json={"current_password": "password123"},
        )
        assert missing_confirmation.status_code == 422
        wrong = client.request(
            "DELETE", "/api/v1/account", headers=_headers(user),
            json={"confirmation": "DELETE", "current_password": "wrong-password"},
        )
        assert wrong.status_code == 403
        assert wrong.json()["detail"]["code"] == "recent_auth_required"

        deleted = client.request(
            "DELETE", "/api/v1/account", headers=_headers(user),
            json={"confirmation": "DELETE", "current_password": "password123"},
        )
        assert deleted.status_code == 200
        db.expire_all()
        assert db.get(User, user_id) is None
        assert db.get(User, other_id) is not None
        assert db.query(EmailOutbox).filter_by(user_id=user_id).count() == 0
        assert not avatar_path.exists()
        retained = db.query(AuditEvent).filter_by(event_type="account.deleted").one()
        assert retained.actor_user_id is None and retained.target_user_id is None and retained.site_id is None
        assert str(user_id) not in json.dumps(retained.metadata_json)
    finally:
        db.close()


def test_google_only_deletion_requires_matching_one_time_reauthentication(account_context):
    Session, client, _ = account_context
    db = Session()
    original_google = auth_router.settings.GOOGLE_AUTH_ENABLED
    original_client = auth_router.settings.GOOGLE_CLIENT_ID
    try:
        auth_router.settings.GOOGLE_AUTH_ENABLED = True
        auth_router.settings.GOOGLE_CLIENT_ID = "browser-client.apps.example.test"
        user = _user(db, "delete-google@example.com", password=None)
        user_id = user.id
        db.add(AuthIdentity(user_id=user.id, provider="google", subject="delete-subject", email=user.email))
        db.commit()

        capability = client.get("/api/v1/account/deletion/capabilities", headers=_headers(user))
        assert capability.json() == {"method": "google", "google_reauthentication_available": True}
        challenge = client.post("/api/v1/account/deletion/challenge", headers=_headers(user))
        assert challenge.status_code == 200

        with patch.object(auth_router, "_unverified_google_nonce", return_value=challenge.json()["nonce"]), patch.object(
            auth_router,
            "_verified_google_identity",
            return_value={"sub": "different-subject", "email": user.email},
        ):
            mismatch = client.request(
                "DELETE", "/api/v1/account", headers=_headers(user),
                json={"confirmation": "DELETE", "google_credential": "controlled-google-credential", "google_state": challenge.json()["state"]},
            )
        assert mismatch.status_code == 403
        assert mismatch.json()["detail"]["code"] == "google_identity_mismatch"
        assert db.get(User, user.id) is not None

        second = client.post("/api/v1/account/deletion/challenge", headers=_headers(user)).json()
        with patch.object(auth_router, "_unverified_google_nonce", return_value=second["nonce"]), patch.object(
            auth_router,
            "_verified_google_identity",
            return_value={"sub": "delete-subject", "email": user.email},
        ):
            deleted = client.request(
                "DELETE", "/api/v1/account", headers=_headers(user),
                json={"confirmation": "DELETE", "google_credential": "controlled-google-credential", "google_state": second["state"]},
            )
        assert deleted.status_code == 200
        db.expire_all()
        assert db.get(User, user_id) is None
        assert db.query(OAuthChallenge).filter_by(user_id=user_id).count() == 0
    finally:
        auth_router.settings.GOOGLE_AUTH_ENABLED = original_google
        auth_router.settings.GOOGLE_CLIENT_ID = original_client
        db.close()
