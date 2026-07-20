"""Persisted, site-owned simulator state."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import SimulationSession
from app.services.site_service import ensure_user_site, get_primary_meter

DEFAULT_CONFIGURATION = {
    "day_part": "evening",
    "occupants": 2,
    "temperature": 25.0,
    "ac_level": "medium",
    "washing_machine": False,
    "solar": "off",
}


class SimulationService:
    def _session(self, db: Session, user_id: int) -> SimulationSession:
        site = ensure_user_site(db, user_id)
        session = (
            db.query(SimulationSession)
            .filter(SimulationSession.site_id == site.id)
            .first()
        )
        if session is None:
            session = SimulationSession(
                site_id=site.id,
                user_id=user_id,
                configuration=dict(DEFAULT_CONFIGURATION),
            )
            db.add(session)
            db.flush()
        return session

    def get_state(self, db: Session, user_id: int) -> dict:
        session = self._session(db, user_id)
        config = {**DEFAULT_CONFIGURATION, **(session.configuration or {})}
        uptime = 0.0
        if session.is_running and session.started_at:
            started_at = session.started_at
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            uptime = max(0.0, (datetime.now(timezone.utc) - started_at).total_seconds())
        return {
            "is_running": session.is_running,
            "uptime": uptime,
            "site_id": session.site_id,
            **config,
        }

    def configure_simulation(self, db: Session, user_id: int, config: dict) -> dict:
        session = self._session(db, user_id)
        session.configuration = {
            **DEFAULT_CONFIGURATION,
            **(session.configuration or {}),
            **{key: value for key, value in config.items() if key in DEFAULT_CONFIGURATION},
        }
        db.commit()
        return {"status": "configured", **self.get_state(db, user_id)}

    def start_simulation(self, db: Session, user_id: int) -> dict:
        session = self._session(db, user_id)
        meter = get_primary_meter(db, user_id)
        if meter is not None:
            meter.source_type = "simulation"
            meter.expected_interval_seconds = 5
        session.is_running = True
        session.started_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "started", **self.get_state(db, user_id)}

    def stop_simulation(self, db: Session, user_id: int) -> dict:
        session = self._session(db, user_id)
        session.is_running = False
        db.commit()
        return {"status": "stopped", **self.get_state(db, user_id)}

    def reset_simulation(self, db: Session, user_id: int) -> dict:
        session = self._session(db, user_id)
        session.is_running = False
        session.started_at = None
        session.configuration = dict(DEFAULT_CONFIGURATION)
        db.commit()
        return {"status": "reset", **self.get_state(db, user_id)}

    @staticmethod
    def reading_for_configuration(config: dict) -> dict:
        """Generate one labeled simulator sample from an explicit session config."""
        import random

        base_map = {"morning": 0.8, "afternoon": 0.4, "evening": 1.8, "night": 0.2}
        gap = base_map.get(config.get("day_part"), 0.5)
        gap += float(config.get("occupants", 2)) * 0.15

        ac_map = {"off": 0.0, "low": 0.4, "medium": 0.9, "high": 1.8}
        ac_base = ac_map.get(config.get("ac_level"), 0.0)
        if float(config.get("temperature", 25.0)) > 30.0:
            ac_base *= 1.25
        gap += ac_base
        if config.get("washing_machine"):
            gap += 0.8
        if config.get("day_part") in ("morning", "afternoon"):
            gap += {"off": 0.0, "low": -0.4, "high": -1.2}.get(config.get("solar"), 0.0)

        gap = max(0.02, gap + random.uniform(-0.08, 0.08))
        voltage = 230.0 + random.uniform(-1.0, 1.0)
        return {
            "active_power_kw": round(gap, 3),
            "reactive_power_kvar": round(gap * 0.08 + random.uniform(-0.01, 0.01), 3),
            "voltage_v": round(voltage, 1),
            "current_a": round((gap * 1000.0) / voltage, 2),
            "sub_metering_1_wh": round(max(0.0, (800.0 if config.get("washing_machine") else 50.0) + random.uniform(-10.0, 10.0)), 2),
            "sub_metering_2_wh": round(max(0.0, gap * 150.0 + random.uniform(-15.0, 15.0)), 2),
            "sub_metering_3_wh": round(max(0.0, ac_base * 1000.0 + random.uniform(-20.0, 20.0)), 2),
            "timestamp": datetime.now(timezone.utc),
        }



simulation_service = SimulationService()
