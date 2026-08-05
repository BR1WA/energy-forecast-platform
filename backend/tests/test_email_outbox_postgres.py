from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
import uuid

import pytest

from app.config import Settings
from app.database import SessionLocal
from app.models import AccountActionToken, EmailOutbox, RefreshToken, User
from app.services.account_action_service import consume_action_token, issue_action_token
from app.services.auth_service import consume_refresh_token, create_refresh_token, hash_password, store_refresh_token
from app.services.email_service import claim_due_emails


pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL", "").startswith("postgresql"),
    reason="PostgreSQL locking test requires DATABASE_URL=postgresql://...",
)


def test_postgres_skip_locked_allows_only_one_worker_to_claim_a_message():
    row_id = str(uuid.uuid4())
    dedup = f"postgres-concurrency:{row_id}"
    db = SessionLocal()
    try:
        db.add(EmailOutbox(
            id=row_id,
            recipient="capture@example.test",
            template="critical_alert",
            template_version="v1",
            payload={"title": "Test", "message": "Test", "url": "https://example.test"},
            dedup_key=dedup,
            status="pending",
        ))
        db.commit()
    finally:
        db.close()

    settings = Settings(
        DEBUG=True,
        JWT_SECRET_KEY="postgres-test-jwt-secret-with-more-than-32-characters",
        ADMIN_PASSWORD="postgres-test-admin-password",
        EMAIL_LEASE_SECONDS=60,
    )

    def claim(worker: str):
        session = SessionLocal()
        try:
            claimed = claim_due_emails(session, worker_id=worker, now=datetime.now(timezone.utc), settings=settings)
            session.commit()
            return claimed
        finally:
            session.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim, ("worker-a", "worker-b")))
        assert sum(row_id in result for result in results) == 1
    finally:
        cleanup = SessionLocal()
        try:
            cleanup.query(EmailOutbox).filter(EmailOutbox.id == row_id).delete()
            cleanup.commit()
        finally:
            cleanup.close()


def test_postgres_action_token_race_has_exactly_one_winner():
    marker = uuid.uuid4().hex
    db = SessionLocal()
    try:
        user = User(
            email=f"action-race-{marker}@example.com",
            password_hash=hash_password("racepassword123"),
            role="user",
            is_active=True,
        )
        db.add(user)
        db.flush()
        issued = issue_action_token(db, user.id, "verify_email")
        user_id = user.id
        raw_token = issued.raw_token
        db.commit()
    finally:
        db.close()

    def consume():
        session = SessionLocal()
        try:
            won = consume_action_token(session, raw_token, "verify_email") is not None
            if won:
                session.commit()
            return won
        finally:
            session.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sum(pool.map(lambda _: consume(), range(2))) == 1
    finally:
        cleanup = SessionLocal()
        try:
            cleanup.query(AccountActionToken).filter_by(user_id=user_id).delete()
            cleanup.query(User).filter_by(id=user_id).delete()
            cleanup.commit()
        finally:
            cleanup.close()


def test_postgres_refresh_replay_race_has_exactly_one_winner():
    marker = uuid.uuid4().hex
    db = SessionLocal()
    try:
        user = User(
            email=f"refresh-race-{marker}@example.com",
            password_hash=hash_password("racepassword123"),
            role="user",
            is_active=True,
        )
        db.add(user)
        db.flush()
        user_id = user.id
        token = create_refresh_token({"sub": str(user.id), "role": "user"})
        store_refresh_token(db, token, user.id, commit=False)
        db.commit()
    finally:
        db.close()

    def consume():
        session = SessionLocal()
        try:
            won = consume_refresh_token(session, token)
            session.commit()
            return won
        finally:
            session.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sum(pool.map(lambda _: consume(), range(2))) == 1
    finally:
        cleanup = SessionLocal()
        try:
            cleanup.query(RefreshToken).filter_by(user_id=user_id).delete()
            cleanup.query(User).filter_by(id=user_id).delete()
            cleanup.commit()
        finally:
            cleanup.close()
