"""Standalone transactional email worker."""
from __future__ import annotations
import logging
import time
from app.config import get_settings
from app.database import SessionLocal
from app.services.email_service import process_due_email

logger = logging.getLogger(__name__)


def run_once() -> int:
    db = SessionLocal()
    try:
        result = process_due_email(db)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    interval = get_settings().EMAIL_WORKER_POLL_SECONDS
    while True:
        try:
            run_once()
        except Exception:
            logger.exception("Email worker iteration failed")
        time.sleep(interval)
