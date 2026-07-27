"""Explicit, non-destructive synthetic history preparation for demos and tests."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import SmartMeterReading
from app.schemas import MeterSample
from app.services.ingestion_service import ingestion_service
from app.services.product_forecast_service import LOOKBACK_HOURS, product_forecast_service
from app.services.site_service import ensure_user_site, get_primary_meter


DEMO_SOURCE = "forecast_demo"


def _hourly_load(timestamp: datetime, index: int) -> float:
    hour = timestamp.hour
    morning = math.exp(-((hour - 8) / 2.2) ** 2) * 0.55
    evening = math.exp(-((hour - 20) / 2.8) ** 2) * 0.9
    weekly_variation = math.sin((index / 24) * math.pi * 2 / 7) * 0.08
    return max(0.25, 0.48 + morning + evening + weekly_variation)


class ForecastDemoService:
    def prepare_history(self, db: Session, user_id: int) -> dict:
        """Fill the current 336-hour window without removing user readings."""
        ensure_user_site(db, user_id)
        meter = get_primary_meter(db, user_id)
        if meter is None:  # Defensive: ensure_user_site creates a primary meter.
            raise RuntimeError("A primary meter could not be prepared.")

        now = datetime.now(timezone.utc)
        anchor = now.replace(minute=0, second=0, microsecond=0)
        start = anchor - timedelta(hours=LOOKBACK_HOURS)
        samples = []
        for index in range(LOOKBACK_HOURS + 1):
            timestamp = start + timedelta(hours=index)
            active_power = _hourly_load(timestamp, index)
            voltage = 230.0 + math.sin(index / 9) * 2.4
            samples.append(
                MeterSample(
                    timestamp=timestamp,
                    active_power_kw=round(active_power, 3),
                    reactive_power_kvar=round(active_power * 0.08, 3),
                    voltage_v=round(voltage, 1),
                    current_a=round(active_power * 1000 / voltage, 2),
                )
            )

        previous_interval = meter.expected_interval_seconds
        had_readings = (
            db.query(SmartMeterReading.id)
            .filter(SmartMeterReading.meter_id == meter.id)
            .first()
            is not None
        )
        ingestion = ingestion_service.ingest(
            db,
            meter,
            samples,
            source=DEMO_SOURCE,
            idempotency_key=f"forecast-demo-{anchor:%Y%m%d%H}",
        )
        if had_readings and previous_interval is not None:
            # Preparing test history must not change an established live meter cadence.
            meter.expected_interval_seconds = previous_interval

        prepared = product_forecast_service.prepare_input(db, user_id)
        return {
            "status": "ready" if prepared.ready else "insufficient_data",
            "meter_id": meter.id,
            "synthetic_source": DEMO_SOURCE,
            "required_hours": LOOKBACK_HOURS,
            "accepted_rows": ingestion["accepted_rows"],
            "duplicate_rows": ingestion["duplicate_rows"],
            "coverage_percent": round(prepared.coverage_percent, 2),
            "observed_hours": prepared.observed_hours,
            "maximum_gap_hours": prepared.maximum_gap_hours,
            "forecast_origin": prepared.origin,
            "message": (
                "Forecast demo history is ready. Existing meter readings were preserved."
                if prepared.ready
                else "Synthetic history was added, but the active forecast window still needs attention."
            ),
        }


forecast_demo_service = ForecastDemoService()
