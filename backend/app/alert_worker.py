"""Standalone worker for periodic alert rules that do not run during ingestion."""
from __future__ import annotations

import logging
import time

from app.config import get_settings
from app.database import SessionLocal
from app.services.alert_service import alert_service


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
logger = logging.getLogger(__name__)


def run_once() -> int:
    db = SessionLocal()
    try:
        alerts = alert_service.evaluate_missing_push_data(db)
        db.commit()
        return len(alerts)
    except Exception:
        db.rollback()
        logger.exception("Alert worker run failed")
        raise
    finally:
        db.close()


def main() -> None:
    settings = get_settings()
    interval = settings.ALERT_WORKER_INTERVAL_SECONDS
    logger.info("Alert worker started with a %ss interval", interval)
    while True:
        created = run_once()
        if created:
            logger.info("Created %s missing-data alert(s)", created)
        time.sleep(interval)


if __name__ == "__main__":
    main()
