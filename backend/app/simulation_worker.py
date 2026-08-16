"""Single-purpose worker that advances explicitly started simulator sessions."""
from __future__ import annotations

import logging
import time

from app.config import get_settings
from app.database import SessionLocal
from app.models import SimulationSession
from app.services.simulation_service import simulation_service


logger = logging.getLogger(__name__)


def run_once() -> int:
    db = SessionLocal()
    try:
        sessions = (
            db.query(SimulationSession)
            .filter(SimulationSession.is_running.is_(True))
            .all()
        )
        for session in sessions:
            simulation_service.advance_session(db, session)
        if sessions:
            db.commit()
        return len(sessions)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    interval = get_settings().SIMULATION_WORKER_INTERVAL_SECONDS
    logger.info("Simulation worker started with a %ss interval", interval)
    while True:
        try:
            advanced = run_once()
            if advanced:
                logger.debug("Advanced %s simulator session(s)", advanced)
        except Exception:
            logger.exception("Simulation worker iteration failed")
        time.sleep(interval)


if __name__ == "__main__":
    main()
