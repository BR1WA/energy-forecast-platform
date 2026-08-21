"""Standalone retry worker for durable avatar-object cleanup."""
from __future__ import annotations

import logging
import time

from app.config import get_settings
from app.database import SessionLocal
from app.services.avatar_storage import process_avatar_cleanup
from app.services.worker_health_service import record_worker_success


logger = logging.getLogger(__name__)


def run_once() -> int:
    db = SessionLocal()
    try:
        processed = process_avatar_cleanup(db)
        record_worker_success(db, "avatar_cleanup")
        db.commit()
        return processed
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    interval = get_settings().AVATAR_CLEANUP_POLL_SECONDS
    while True:
        try:
            run_once()
        except Exception:
            logger.exception("Avatar cleanup worker iteration failed")
        time.sleep(interval)
