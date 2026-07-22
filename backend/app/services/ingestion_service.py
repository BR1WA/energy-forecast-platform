"""Validation and persistence shared by CSV, push API, and simulator ingestion."""
from __future__ import annotations

import csv
import hashlib
import io
import secrets
import statistics
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import IngestionBatch, Meter, SmartMeterReading
from app.schemas import MeterSample
from app.services.alert_service import alert_service


CSV_ALIASES = {
    "timestamp": "timestamp",
    "datetime": "timestamp",
    "date_time": "timestamp",
    "active_power_kw": "active_power_kw",
    "gap": "active_power_kw",
    "global_active_power": "active_power_kw",
    "reactive_power_kvar": "reactive_power_kvar",
    "grp": "reactive_power_kvar",
    "global_reactive_power": "reactive_power_kvar",
    "voltage_v": "voltage_v",
    "voltage": "voltage_v",
    "current_a": "current_a",
    "intensity": "current_a",
    "global_intensity": "current_a",
    "sub_metering_1_wh": "sub_metering_1_wh",
    "sub_metering_1": "sub_metering_1_wh",
    "sub_metering_2_wh": "sub_metering_2_wh",
    "sub_metering_2": "sub_metering_2_wh",
    "sub_metering_3_wh": "sub_metering_3_wh",
    "sub_metering_3": "sub_metering_3_wh",
    "energy_kwh": "energy_kwh",
}


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _normalise_column(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("-", "_")


class IngestionService:
    @staticmethod
    def create_api_key(meter: Meter) -> str:
        key = f"eai_{secrets.token_urlsafe(32)}"
        meter.ingestion_key_hash = hashlib.sha256(key.encode()).hexdigest()
        return key

    @staticmethod
    def check_api_key(meter: Meter, presented_key: str | None) -> bool:
        if not meter.ingestion_key_hash or not presented_key:
            return False
        return secrets.compare_digest(
            meter.ingestion_key_hash,
            hashlib.sha256(presented_key.encode()).hexdigest(),
        )

    def parse_csv(self, raw_csv: bytes, max_rows: int = 10_000) -> tuple[list[MeterSample], list[dict[str, Any]], list[str]]:
        try:
            text = raw_csv.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("CSV must be UTF-8 encoded") from exc

        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise ValueError("CSV must include a header row")
        column_map = {
            header: CSV_ALIASES.get(_normalise_column(header))
            for header in reader.fieldnames
        }
        if "timestamp" not in column_map.values() or "active_power_kw" not in column_map.values():
            raise ValueError("CSV needs timestamp and active_power_kw (or GAP) columns")

        samples: list[MeterSample] = []
        errors: list[dict[str, Any]] = []
        for row_number, row in enumerate(reader, start=2):
            if row_number > max_rows + 1:
                raise ValueError(f"CSV exceeds the {max_rows} row limit")
            payload = {
                target: value.strip()
                for header, value in row.items()
                if (target := column_map.get(header)) and value is not None and value.strip() != ""
            }
            try:
                samples.append(MeterSample.model_validate(payload))
            except ValidationError as exc:
                errors.append({"row": row_number, "message": exc.errors()[0]["msg"]})
        return samples, errors, [name for name in column_map.values() if name]

    def preview_csv(self, raw_csv: bytes) -> dict[str, Any]:
        samples, errors, mapped_columns = self.parse_csv(raw_csv, max_rows=10_000)
        return {
            "mapped_columns": sorted(set(mapped_columns)),
            "valid_rows": len(samples),
            "rejected_rows": len(errors),
            "errors": errors[:20],
        }

    def ingest(
        self,
        db: Session,
        meter: Meter,
        samples: Iterable[MeterSample],
        source: str,
        idempotency_key: str | None = None,
        initial_errors: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        sample_list = sorted(list(samples), key=lambda sample: sample.timestamp)
        errors = list(initial_errors or [])
        if idempotency_key:
            previous = (
                db.query(IngestionBatch)
                .filter(
                    IngestionBatch.meter_id == meter.id,
                    IngestionBatch.idempotency_key == idempotency_key,
                )
                .first()
            )
            if previous:
                return self._batch_result(previous)

        batch = IngestionBatch(
            id=str(uuid.uuid4()),
            meter_id=meter.id,
            source=source,
            idempotency_key=idempotency_key,
            total_rows=len(sample_list) + len(errors),
            errors=[],
        )
        db.add(batch)
        db.flush()

        accepted = 0
        duplicates = 0
        accepted_readings: list[SmartMeterReading] = []
        seen_timestamps: set[datetime] = set()
        latest_seen = _as_utc(meter.last_seen_at) if meter.last_seen_at is not None else None
        for row_number, sample in enumerate(sample_list, start=1):
            timestamp = sample.timestamp.astimezone(timezone.utc)
            if timestamp > datetime.now(timezone.utc) + timedelta(minutes=5):
                errors.append({"row": row_number, "message": "timestamp cannot be more than five minutes in the future"})
                continue
            if timestamp in seen_timestamps:
                duplicates += 1
                continue
            seen_timestamps.add(timestamp)
            if source == "push" and latest_seen is not None and timestamp < latest_seen:
                errors.append({"row": row_number, "message": "push samples must not be older than the meter's latest reading"})
                continue
            if (
                db.query(SmartMeterReading.id)
                .filter(SmartMeterReading.meter_id == meter.id, SmartMeterReading.timestamp == timestamp)
                .first()
            ):
                duplicates += 1
                continue

            if sample.energy_kwh is not None:
                previous_energy = (
                    db.query(SmartMeterReading.energy_kwh)
                    .filter(
                        SmartMeterReading.meter_id == meter.id,
                        SmartMeterReading.timestamp < timestamp,
                        SmartMeterReading.energy_kwh.is_not(None),
                    )
                    .order_by(SmartMeterReading.timestamp.desc())
                    .first()
                )
                if previous_energy and sample.energy_kwh < previous_energy[0]:
                    errors.append({"row": row_number, "message": "energy_kwh cannot decrease for a meter"})
                    continue

            current_a = sample.current_a
            if current_a is None:
                current_a = (sample.active_power_kw * 1000) / sample.voltage_v
            reading = SmartMeterReading(
                meter_id=meter.id,
                ingestion_batch_id=batch.id,
                timestamp=timestamp,
                gap=sample.active_power_kw,
                grp=sample.reactive_power_kvar,
                voltage=sample.voltage_v,
                intensity=current_a,
                sub_metering_1=sample.sub_metering_1_wh,
                sub_metering_2=sample.sub_metering_2_wh,
                sub_metering_3=sample.sub_metering_3_wh,
                energy_kwh=sample.energy_kwh,
                source=source,
                quality="validated",
            )
            try:
                with db.begin_nested():
                    db.add(reading)
                    db.flush()
            except IntegrityError:
                duplicates += 1
                continue
            accepted += 1
            accepted_readings.append(reading)
            if latest_seen is None or timestamp > latest_seen:
                latest_seen = timestamp

        meter.last_seen_at = latest_seen
        intervals = [
            (current.timestamp - previous.timestamp).total_seconds()
            for previous, current in zip(sample_list, sample_list[1:])
            if current.timestamp > previous.timestamp
        ]
        if intervals:
            meter.expected_interval_seconds = int(min(86_400, max(5, statistics.median(intervals))))
        batch.accepted_rows = accepted
        batch.duplicate_rows = duplicates
        batch.rejected_rows = len(errors)
        batch.errors = errors[:100]
        # CSV imports are often historical. Alert only current push/simulator
        # readings so an import cannot create a false backlog of live incidents.
        if source in {"push", "simulation"}:
            freshness_cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
            for reading in accepted_readings:
                if _as_utc(reading.timestamp) >= freshness_cutoff:
                    alert_service.evaluate_reading(db, meter, reading)
        db.flush()
        return self._batch_result(batch)

    @staticmethod
    def _batch_result(batch: IngestionBatch) -> dict[str, Any]:
        return {
            "batch_id": batch.id,
            "total_rows": batch.total_rows,
            "accepted_rows": batch.accepted_rows,
            "duplicate_rows": batch.duplicate_rows,
            "rejected_rows": batch.rejected_rows,
            "errors": batch.errors or [],
        }


ingestion_service = IngestionService()
