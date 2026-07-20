"""Truthful one-site forecasting from persisted primary-meter readings."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import holidays
import numpy as np
from sqlalchemy.orm import Session

from app.models import Meter, Site, SiteSettings, SmartMeterReading


logger = logging.getLogger("app.forecast")

LOOKBACK_HOURS = 336
HORIZON_HOURS = 24
MINIMUM_COVERAGE_PERCENT = 95.0
MAXIMUM_GAP_HOURS = 3
MODEL_NAME = "global_tft_24h"
MODEL_VERSION = "1.0.0"
FALLBACK_NAME = "seasonal_naive_168h"
ARTIFACT_DIR = Path(__file__).resolve().parents[2] / "model_artifacts" / MODEL_NAME
MANIFEST_PATH = ARTIFACT_DIR / "manifest.json"


class ForecastInputError(ValueError):
    """Raised when persisted meter history cannot support an honest forecast."""


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _ceil_hour(value: datetime) -> datetime:
    value = _as_utc(value)
    floor = value.replace(minute=0, second=0, microsecond=0)
    return floor if value == floor else floor + timedelta(hours=1)


def _longest_false_run(values: np.ndarray) -> int:
    longest = current = 0
    for value in values:
        if value:
            current = 0
        else:
            current += 1
            longest = max(longest, current)
    return longest


@dataclass
class PreparedForecastInput:
    site: Site | None = None
    meter: Meter | None = None
    origin: datetime | None = None
    values: np.ndarray | None = None
    coverage_percent: float = 0.0
    observed_hours: int = 0
    maximum_gap_hours: int = LOOKBACK_HOURS
    latest_reading_at: datetime | None = None
    sources: list[str] = field(default_factory=list)
    imputed_timestamps: list[datetime] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return not self.reasons and self.values is not None and self.origin is not None


class ProductForecastService:
    def __init__(self) -> None:
        self._model = None
        self._manifest: dict | None = None
        self._artifact_error: str | None = None

    @staticmethod
    def _site_zone(site: Site) -> ZoneInfo:
        try:
            return ZoneInfo(site.timezone)
        except (KeyError, ValueError):
            return ZoneInfo("UTC")

    def prepare_input(self, db: Session, user_id: int) -> PreparedForecastInput:
        prepared = PreparedForecastInput()
        site = db.query(Site).filter(Site.user_id == user_id).one_or_none()
        if site is None:
            prepared.reasons.append("Configure your site before forecasting.")
            return prepared
        prepared.site = site

        meter = (
            db.query(Meter)
            .filter(Meter.site_id == site.id, Meter.is_primary.is_(True))
            .one_or_none()
        )
        if meter is None:
            prepared.reasons.append("Configure a primary electricity meter before forecasting.")
            return prepared
        prepared.meter = meter

        latest = (
            db.query(SmartMeterReading)
            .filter(SmartMeterReading.meter_id == meter.id)
            .order_by(SmartMeterReading.timestamp.desc())
            .first()
        )
        if latest is None:
            prepared.reasons.append("Import or ingest meter readings before forecasting.")
            return prepared

        latest_timestamp = _as_utc(latest.timestamp)
        origin = _ceil_hour(latest_timestamp)
        start = origin - timedelta(hours=LOOKBACK_HOURS)
        prepared.origin = origin
        prepared.latest_reading_at = latest_timestamp

        readings = (
            db.query(SmartMeterReading)
            .filter(
                SmartMeterReading.meter_id == meter.id,
                SmartMeterReading.timestamp >= start - timedelta(hours=MAXIMUM_GAP_HOURS),
                SmartMeterReading.timestamp <= origin,
            )
            .order_by(SmartMeterReading.timestamp.asc())
            .all()
        )
        energy = np.zeros(LOOKBACK_HOURS, dtype=np.float64)
        covered_seconds = np.zeros(LOOKBACK_HOURS, dtype=np.float64)
        source_names: set[str] = set()

        for previous, current in zip(readings, readings[1:]):
            interval_start = _as_utc(previous.timestamp)
            interval_end = _as_utc(current.timestamp)
            elapsed = (interval_end - interval_start).total_seconds()
            if elapsed <= 0 or elapsed > MAXIMUM_GAP_HOURS * 3600:
                continue
            if not math.isfinite(previous.gap) or not math.isfinite(current.gap):
                continue

            clipped_start = max(interval_start, start)
            clipped_end = min(interval_end, origin)
            if clipped_end <= clipped_start:
                continue

            direct_energy = None
            if previous.energy_kwh is not None and current.energy_kwh is not None:
                difference = current.energy_kwh - previous.energy_kwh
                if math.isfinite(difference) and difference >= 0:
                    direct_energy = float(difference)

            cursor = clipped_start
            while cursor < clipped_end:
                bucket_index = int((cursor - start).total_seconds() // 3600)
                if bucket_index < 0 or bucket_index >= LOOKBACK_HOURS:
                    break
                bucket_end = min(start + timedelta(hours=bucket_index + 1), clipped_end)
                overlap = (bucket_end - cursor).total_seconds()
                if direct_energy is not None:
                    interval_energy = direct_energy * overlap / elapsed
                else:
                    start_ratio = (cursor - interval_start).total_seconds() / elapsed
                    end_ratio = (bucket_end - interval_start).total_seconds() / elapsed
                    start_power = previous.gap + (current.gap - previous.gap) * start_ratio
                    end_power = previous.gap + (current.gap - previous.gap) * end_ratio
                    interval_energy = (start_power + end_power) / 2 * overlap / 3600
                energy[bucket_index] += max(0.0, interval_energy)
                covered_seconds[bucket_index] += overlap
                cursor = bucket_end
            source_names.update([previous.source, current.source])

        covered_seconds = np.minimum(covered_seconds, 3600.0)
        coverage_ratios = covered_seconds / 3600.0
        valid_hours = coverage_ratios >= (MINIMUM_COVERAGE_PERCENT / 100)
        prepared.coverage_percent = float(coverage_ratios.mean() * 100)
        prepared.observed_hours = int(valid_hours.sum())
        prepared.maximum_gap_hours = _longest_false_run(valid_hours)
        prepared.sources = sorted(source_names)
        prepared.imputed_timestamps = [
            start + timedelta(hours=int(index))
            for index in np.flatnonzero(~valid_hours)
        ]

        hourly_values = np.full(LOOKBACK_HOURS, np.nan, dtype=np.float64)
        hourly_values[valid_hours] = energy[valid_hours] / coverage_ratios[valid_hours]
        valid_indices = np.flatnonzero(np.isfinite(hourly_values))
        if valid_indices.size:
            missing_indices = np.flatnonzero(~np.isfinite(hourly_values))
            hourly_values[missing_indices] = np.interp(
                missing_indices, valid_indices, hourly_values[valid_indices]
            )

        if prepared.coverage_percent < MINIMUM_COVERAGE_PERCENT:
            prepared.reasons.append(
                f"History coverage is {prepared.coverage_percent:.1f}%; at least 95% of 336 hours is required."
            )
        if prepared.maximum_gap_hours > MAXIMUM_GAP_HOURS:
            prepared.reasons.append(
                f"The longest data gap is {prepared.maximum_gap_hours} hours; the maximum is 3 hours."
            )
        if not np.isfinite(hourly_values).all():
            prepared.reasons.append("The 336-hour input window still contains missing or invalid values.")
        if not prepared.reasons:
            prepared.values = hourly_values.astype(np.float32)
        return prepared

    def _load_manifest(self) -> tuple[dict | None, str | None]:
        if self._manifest is not None or self._artifact_error is not None:
            return self._manifest, self._artifact_error
        try:
            manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            checkpoint = ARTIFACT_DIR / manifest["checkpoint_file"]
            if not checkpoint.is_file():
                raise RuntimeError("The packaged model checkpoint is missing.")
            digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
            if digest != manifest["checkpoint_sha256"]:
                raise RuntimeError("The packaged model checkpoint failed its SHA-256 integrity check.")
            self._manifest = manifest
        except (OSError, KeyError, ValueError, RuntimeError) as exc:
            self._artifact_error = str(exc)
        return self._manifest, self._artifact_error

    def model_status(self) -> dict:
        manifest, artifact_error = self._load_manifest()
        torch_available = importlib.util.find_spec("torch") is not None
        error = artifact_error
        if error is None and not torch_available:
            error = "PyTorch is not installed in this runtime."
        return {
            "available": error is None,
            "name": MODEL_NAME,
            "display_name": manifest.get("display_name", "Global TFT 24-hour") if manifest else "Global TFT 24-hour",
            "version": manifest.get("version", MODEL_VERSION) if manifest else MODEL_VERSION,
            "artifact_fingerprint": manifest.get("checkpoint_sha256") if manifest else None,
            "error": error,
        }

    def readiness(self, db: Session, user_id: int) -> dict:
        prepared = self.prepare_input(db, user_id)
        model = self.model_status()
        if not prepared.ready:
            status = "insufficient_data"
        elif model["available"]:
            status = "ready"
        else:
            status = "fallback_ready"
        return {
            "status": status,
            "ready_for_tft": prepared.ready and model["available"],
            "fallback_available": prepared.ready,
            "required_hours": LOOKBACK_HOURS,
            "minimum_coverage_percent": MINIMUM_COVERAGE_PERCENT,
            "maximum_allowed_gap_hours": MAXIMUM_GAP_HOURS,
            "coverage_percent": round(prepared.coverage_percent, 2),
            "observed_hours": prepared.observed_hours,
            "missing_hours": LOOKBACK_HOURS - prepared.observed_hours,
            "imputed_hours": len(prepared.imputed_timestamps) if prepared.ready else 0,
            "maximum_gap_hours": prepared.maximum_gap_hours,
            "unit": "kWh",
            "resolution": "hourly",
            "latest_reading_at": prepared.latest_reading_at,
            "forecast_origin": prepared.origin,
            "reasons": prepared.reasons,
            "model": model,
        }

    @staticmethod
    def _country_code(country: str | None) -> str:
        aliases = {
            "morocco": "MA",
            "united kingdom": "GB",
            "uk": "GB",
            "france": "FR",
            "spain": "ES",
            "germany": "DE",
            "united states": "US",
            "usa": "US",
        }
        normalized = (country or "Morocco").strip().lower()
        return aliases.get(normalized, country or "MA")

    def _calendar(self, timestamps: list[datetime], site: Site, country: str | None) -> np.ndarray:
        zone = self._site_zone(site)
        local_timestamps = [timestamp.astimezone(zone) for timestamp in timestamps]
        years = sorted({timestamp.year for timestamp in local_timestamps})
        try:
            country_holidays = holidays.country_holidays(self._country_code(country), years=years)
        except (KeyError, NotImplementedError):
            country_holidays = {}

        rows = []
        for timestamp in local_timestamps:
            next_day = timestamp + timedelta(days=1)
            is_holiday = timestamp.date() in country_holidays
            next_is_holiday = next_day.date() in country_holidays
            hour = 2 * math.pi * timestamp.hour / 24
            weekday = 2 * math.pi * timestamp.weekday() / 7
            month = 2 * math.pi * (timestamp.month - 1) / 12
            rows.append(
                [
                    math.sin(hour),
                    math.cos(hour),
                    math.sin(weekday),
                    math.cos(weekday),
                    math.sin(month),
                    math.cos(month),
                    float(timestamp.weekday() < 5 and not is_holiday),
                    float(is_holiday),
                    float(next_day.weekday() < 5 and not next_is_holiday),
                ]
            )
        return np.asarray(rows, dtype=np.float32)

    def _load_model(self):
        if self._model is not None:
            return self._model
        manifest, error = self._load_manifest()
        if error or manifest is None:
            raise RuntimeError(error or "Model manifest is unavailable.")
        try:
            import torch

            from app.ml.global_tft import GlobalTFT
        except ImportError as exc:
            raise RuntimeError("PyTorch is not installed in this runtime.") from exc

        checkpoint_path = ARTIFACT_DIR / manifest["checkpoint_file"]
        try:
            checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
        except TypeError:
            checkpoint = torch.load(checkpoint_path, map_location="cpu")
        model = GlobalTFT()
        model.load_state_dict(checkpoint["model_state_dict"], strict=True)
        model.eval()
        self._model = model
        return model

    def _predict_tft(
        self,
        prepared: PreparedForecastInput,
        country: str | None,
        mean: float,
        standard_deviation: float,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        import torch

        assert prepared.values is not None and prepared.origin is not None and prepared.site is not None
        normalized = (prepared.values - mean) / standard_deviation
        past_timestamps = [
            prepared.origin - timedelta(hours=LOOKBACK_HOURS - index)
            for index in range(LOOKBACK_HOURS)
        ]
        future_timestamps = [prepared.origin + timedelta(hours=index) for index in range(HORIZON_HOURS)]
        batch = {
            "x": torch.from_numpy(normalized[None, :, None].astype(np.float32)),
            "x_calendar": torch.from_numpy(self._calendar(past_timestamps, prepared.site, country)[None]),
            "y_calendar": torch.from_numpy(self._calendar(future_timestamps, prepared.site, country)[None]),
        }
        model = self._load_model()
        with torch.inference_mode():
            output = model(batch)["quantiles"].cpu().numpy()[0]
        if output.shape != (HORIZON_HOURS, 3) or not np.isfinite(output).all():
            raise RuntimeError("The model returned an invalid forecast tensor.")
        output = np.maximum(0.0, output * standard_deviation + mean)
        output.sort(axis=1)
        return output[:, 0], output[:, 1], output[:, 2]

    def generate(self, db: Session, user_id: int) -> dict:
        prepared = self.prepare_input(db, user_id)
        if not prepared.ready:
            raise ForecastInputError(" ".join(prepared.reasons))
        assert prepared.values is not None and prepared.origin is not None and prepared.site is not None

        settings = (
            db.query(SiteSettings).filter(SiteSettings.site_id == prepared.site.id).one_or_none()
        )
        model_status = self.model_status()
        mean = float(prepared.values.mean())
        standard_deviation = max(float(prepared.values.std()), 1e-6)
        preprocessing = {
            "aggregation": "interval-integrated hourly energy",
            "normalization": "rolling_window_zscore",
            "scaler_mean_kwh": mean,
            "scaler_std_kwh": standard_deviation,
            "imputation": "linear interpolation across gaps up to 3 hours",
            "imputed_timestamps": [value.isoformat() for value in prepared.imputed_timestamps],
        }
        method = "global_tft"
        model_name = MODEL_NAME
        fallback_reason = None
        inference_started = time.perf_counter()
        try:
            if not model_status["available"]:
                raise RuntimeError(model_status["error"] or "The TFT model is unavailable.")
            lower, median, upper = self._predict_tft(
                prepared,
                settings.country if settings else None,
                mean,
                standard_deviation,
            )
            confidence_method = (
                "Native Global TFT 10th/50th/90th quantile outputs; not recalibrated for this site."
            )
        except Exception as exc:
            logger.exception("Global TFT inference failed; using the declared seasonal fallback")
            method = "seasonal_naive"
            model_name = FALLBACK_NAME
            fallback_reason = str(exc)
            median = prepared.values[168:192].astype(np.float64)
            lower = upper = np.full(HORIZON_HOURS, np.nan)
            confidence_method = "Seasonal-naive point forecast; no uncertainty interval is available."
        inference_seconds = time.perf_counter() - inference_started

        points = []
        prediction_rows = []
        for index in range(HORIZON_HOURS):
            timestamp = prepared.origin + timedelta(hours=index)
            p50 = round(float(median[index]), 5)
            p10 = round(float(lower[index]), 5) if math.isfinite(lower[index]) else None
            p90 = round(float(upper[index]), 5) if math.isfinite(upper[index]) else None
            points.append({"timestamp": timestamp, "p10_kwh": p10, "p50_kwh": p50, "p90_kwh": p90})
            prediction_rows.append([p50, p10, p90])

        return {
            "model_name": model_name,
            "model_version": MODEL_VERSION if method == "global_tft" else "deterministic-v1",
            "method": method,
            "fallback_reason": fallback_reason,
            "confidence_method": confidence_method,
            "prediction_rows": prediction_rows,
            "points": points,
            "site": prepared.site,
            "meter": prepared.meter,
            "origin": prepared.origin,
            "coverage_percent": round(prepared.coverage_percent, 2),
            "observed_hours": prepared.observed_hours,
            "maximum_gap_hours": prepared.maximum_gap_hours,
            "sources": prepared.sources,
            "preprocessing": preprocessing,
            "inference_seconds": round(inference_seconds, 4),
            "artifact_fingerprint": model_status["artifact_fingerprint"] if method == "global_tft" else None,
        }


product_forecast_service = ProductForecastService()
