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

from app.config import get_settings
from app.models import Meter, Site, SiteSettings, SmartMeterReading

logger = logging.getLogger("app.forecast")

LOOKBACK_HOURS = 336
HORIZON_HOURS = 24  # Compatibility alias for the stable PFE contract.
MONTH_HORIZON_HOURS = 30 * 24
MONTH_TARGET_DAYS = 30
MONTH_TARGET_INTERVAL_HOURS = 24
MONTH_CONTEXT_DAYS = 365
MONTH_LOOKBACK_HOURS = MONTH_CONTEXT_DAYS * 24
MONTH_MINIMUM_OBSERVED_DAYS = 270
MONTH_MAXIMUM_GAP_DAYS = 3
MINIMUM_COVERAGE_PERCENT = 95.0
MAXIMUM_GAP_HOURS = 3
MODEL_NAME = "global_tft_24h"
MODEL_VERSION = "1.0.0"
FALLBACK_NAME = "seasonal_naive_168h"
WEEK_MODEL_NAME = "global_tft_168h"
WEEK_FALLBACK_NAME = "seasonal_naive_week_168h"
MONTH_MODEL_NAME = "month_production_v3"
MONTH_FALLBACK_NAME = "seasonal_naive_daily_last28"
SUPPORTED_HORIZONS = (24, 168, MONTH_HORIZON_HOURS)
ARTIFACT_ROOT = Path(__file__).resolve().parents[2] / "model_artifacts"
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_MONTH_RELEASE_DIR = (
    REPOSITORY_ROOT
    / "models"
    / "lcl_global_forecasting"
    / "month_production_v3"
    / "release"
)
ARTIFACT_DIR = ARTIFACT_ROOT / MODEL_NAME  # Compatibility alias used by tests/docs.
MANIFEST_PATH = ARTIFACT_DIR / "manifest.json"


@dataclass(frozen=True)
class ForecastArtifactSpec:
    horizon_hours: int
    model_name: str
    fallback_name: str
    display_name: str
    target_count: int
    target_interval_hours: int
    resolution: str
    feature_flag: str | None = None
    release_dir: Path | None = None

    @property
    def artifact_dir(self) -> Path:
        return self.release_dir or (ARTIFACT_ROOT / self.model_name)


ARTIFACT_SPECS = {
    24: ForecastArtifactSpec(
        horizon_hours=24,
        model_name=MODEL_NAME,
        fallback_name=FALLBACK_NAME,
        display_name="Global TFT 24-hour",
        target_count=24,
        target_interval_hours=1,
        resolution="hourly",
    ),
    168: ForecastArtifactSpec(
        horizon_hours=168,
        model_name=WEEK_MODEL_NAME,
        fallback_name=WEEK_FALLBACK_NAME,
        display_name="Global TFT 168-hour",
        target_count=168,
        target_interval_hours=1,
        resolution="hourly",
        feature_flag="FORECAST_168H_ENABLED",
    ),
    MONTH_HORIZON_HOURS: ForecastArtifactSpec(
        horizon_hours=MONTH_HORIZON_HOURS,
        model_name=MONTH_MODEL_NAME,
        fallback_name=MONTH_FALLBACK_NAME,
        display_name="Chronos-2 LoRA 30-day daily",
        target_count=MONTH_TARGET_DAYS,
        target_interval_hours=MONTH_TARGET_INTERVAL_HOURS,
        resolution="daily",
        feature_flag="FORECAST_30D_ENABLED",
        release_dir=(
            CANONICAL_MONTH_RELEASE_DIR
            if CANONICAL_MONTH_RELEASE_DIR.is_dir()
            else ARTIFACT_ROOT / MONTH_MODEL_NAME
        ),
    ),
}
PRODUCT_MODEL_NAMES = tuple(
    name
    for spec in ARTIFACT_SPECS.values()
    for name in (spec.model_name, spec.fallback_name)
)


class ForecastInputError(ValueError):
    """Raised when persisted meter history cannot support an honest forecast."""


class ForecastCapabilityError(ValueError):
    """Raised when a requested fixed forecast capability is not advertised."""

    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


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


@dataclass
class PreparedMonthForecastInput:
    site: Site | None = None
    meter: Meter | None = None
    origin: datetime | None = None
    values: np.ndarray | None = None
    coverage_percent: float = 0.0
    observed_hours: int = 0
    observed_days: int = 0
    maximum_gap_hours: int = MONTH_LOOKBACK_HOURS
    maximum_gap_days: int = MONTH_CONTEXT_DAYS
    latest_reading_at: datetime | None = None
    sources: list[str] = field(default_factory=list)
    imputed_days: list[int] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return not self.reasons and self.values is not None and self.origin is not None


class ProductForecastService:
    def __init__(
        self,
        *,
        forecast_168h_enabled: bool | None = None,
        forecast_30d_enabled: bool | None = None,
    ) -> None:
        self._models: dict[int, object] = {}
        self._manifests: dict[int, dict] = {}
        self._artifact_errors: dict[int, str] = {}
        self._forecast_168h_enabled = forecast_168h_enabled
        self._forecast_30d_enabled = forecast_30d_enabled

    def is_enabled(self, horizon_hours: int) -> bool:
        if horizon_hours == 24:
            return True
        if horizon_hours == 168:
            if self._forecast_168h_enabled is not None:
                return self._forecast_168h_enabled
            return get_settings().FORECAST_168H_ENABLED
        if horizon_hours == MONTH_HORIZON_HOURS:
            if self._forecast_30d_enabled is not None:
                return self._forecast_30d_enabled
            return get_settings().FORECAST_30D_ENABLED
        return False

    @staticmethod
    def artifact_spec(horizon_hours: int) -> ForecastArtifactSpec:
        spec = ARTIFACT_SPECS.get(horizon_hours)
        if spec is None:
            raise ForecastCapabilityError(
                "FORECAST_HORIZON_UNSUPPORTED",
                "Only 24-hour, 168-hour, and 30-day daily forecasts are supported.",
                422,
            )
        return spec

    def require_enabled(self, horizon_hours: int) -> ForecastArtifactSpec:
        spec = self.artifact_spec(horizon_hours)
        if not self.is_enabled(horizon_hours):
            raise ForecastCapabilityError(
                "FORECAST_CAPABILITY_DISABLED",
                (
                    "The 7-day / 168-hour forecast is disabled in this runtime. "
                    "Enable FORECAST_168H_ENABLED only when the packaged weekly artifact is available."
                    if horizon_hours == 168
                    else (
                        "The 30-day daily forecast is disabled in this runtime. "
                        "Enable FORECAST_30D_ENABLED only when its adapter and pinned base model are packaged."
                        if horizon_hours == MONTH_HORIZON_HOURS
                        else "The requested forecast capability is not enabled."
                    )
                ),
                404,
            )
        return spec

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
            prepared.reasons.append(
                "Configure a primary electricity meter before forecasting."
            )
            return prepared
        prepared.meter = meter

        latest = (
            db.query(SmartMeterReading)
            .filter(SmartMeterReading.meter_id == meter.id)
            .order_by(SmartMeterReading.timestamp.desc())
            .first()
        )
        if latest is None:
            prepared.reasons.append(
                "Import or ingest meter readings before forecasting."
            )
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
                SmartMeterReading.timestamp
                >= start - timedelta(hours=MAXIMUM_GAP_HOURS),
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
                    start_power = (
                        previous.gap + (current.gap - previous.gap) * start_ratio
                    )
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
            prepared.reasons.append(
                "The 336-hour input window still contains missing or invalid values."
            )
        if not prepared.reasons:
            prepared.values = hourly_values.astype(np.float32)
        return prepared

    def prepare_month_input(
        self, db: Session, user_id: int
    ) -> PreparedMonthForecastInput:
        """Build 365 causal rolling 24-hour totals from persisted meter intervals."""
        prepared = PreparedMonthForecastInput()
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
            prepared.reasons.append(
                "Configure a primary electricity meter before forecasting."
            )
            return prepared
        prepared.meter = meter

        latest = (
            db.query(SmartMeterReading)
            .filter(SmartMeterReading.meter_id == meter.id)
            .order_by(SmartMeterReading.timestamp.desc())
            .first()
        )
        if latest is None:
            prepared.reasons.append(
                "Import or ingest meter readings before forecasting."
            )
            return prepared

        latest_timestamp = _as_utc(latest.timestamp)
        origin = _ceil_hour(latest_timestamp)
        start = origin - timedelta(hours=MONTH_LOOKBACK_HOURS)
        prepared.origin = origin
        prepared.latest_reading_at = latest_timestamp

        readings = (
            db.query(SmartMeterReading)
            .filter(
                SmartMeterReading.meter_id == meter.id,
                SmartMeterReading.timestamp
                >= start - timedelta(hours=MAXIMUM_GAP_HOURS),
                SmartMeterReading.timestamp <= origin,
            )
            .order_by(SmartMeterReading.timestamp.asc())
            .all()
        )
        energy = np.zeros(MONTH_LOOKBACK_HOURS, dtype=np.float64)
        covered_seconds = np.zeros(MONTH_LOOKBACK_HOURS, dtype=np.float64)
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
                if bucket_index < 0 or bucket_index >= MONTH_LOOKBACK_HOURS:
                    break
                bucket_end = min(start + timedelta(hours=bucket_index + 1), clipped_end)
                overlap = (bucket_end - cursor).total_seconds()
                if direct_energy is not None:
                    interval_energy = direct_energy * overlap / elapsed
                else:
                    start_ratio = (cursor - interval_start).total_seconds() / elapsed
                    end_ratio = (bucket_end - interval_start).total_seconds() / elapsed
                    start_power = (
                        previous.gap + (current.gap - previous.gap) * start_ratio
                    )
                    end_power = previous.gap + (current.gap - previous.gap) * end_ratio
                    interval_energy = (start_power + end_power) / 2 * overlap / 3600
                energy[bucket_index] += max(0.0, interval_energy)
                covered_seconds[bucket_index] += overlap
                cursor = bucket_end
            source_names.update([previous.source, current.source])

        covered_seconds = np.minimum(covered_seconds, 3600.0)
        hourly_coverage = covered_seconds / 3600.0
        valid_hours = hourly_coverage >= (MINIMUM_COVERAGE_PERCENT / 100)
        prepared.coverage_percent = float(hourly_coverage.mean() * 100)
        prepared.observed_hours = int(valid_hours.sum())
        prepared.maximum_gap_hours = _longest_false_run(valid_hours)
        prepared.sources = sorted(source_names)

        day_coverage = covered_seconds.reshape(MONTH_CONTEXT_DAYS, 24).sum(axis=1) / (
            24 * 3600
        )
        valid_days = day_coverage >= (MINIMUM_COVERAGE_PERCENT / 100)
        prepared.observed_days = int(valid_days.sum())
        if valid_days.any():
            first = int(np.flatnonzero(valid_days)[0])
            last = int(np.flatnonzero(valid_days)[-1])
            prepared.maximum_gap_days = _longest_false_run(valid_days[first : last + 1])
        prepared.imputed_days = [int(index) for index in np.flatnonzero(~valid_days)]

        daily_values = np.full(MONTH_CONTEXT_DAYS, np.nan, dtype=np.float64)
        daily_energy = energy.reshape(MONTH_CONTEXT_DAYS, 24).sum(axis=1)
        daily_values[valid_days] = daily_energy[valid_days] / day_coverage[valid_days]
        valid_indices = np.flatnonzero(np.isfinite(daily_values))
        if valid_indices.size:
            missing_indices = np.flatnonzero(~np.isfinite(daily_values))
            daily_values[missing_indices] = np.interp(
                missing_indices, valid_indices, daily_values[valid_indices]
            )

        if prepared.observed_days < MONTH_MINIMUM_OBSERVED_DAYS:
            prepared.reasons.append(
                f"Only {prepared.observed_days} complete daily blocks are available; "
                f"at least {MONTH_MINIMUM_OBSERVED_DAYS} are required."
            )
        if prepared.maximum_gap_days > MONTH_MAXIMUM_GAP_DAYS:
            prepared.reasons.append(
                f"The longest internal daily gap is {prepared.maximum_gap_days} days; "
                f"the maximum is {MONTH_MAXIMUM_GAP_DAYS} days."
            )
        if not valid_days[-1]:
            prepared.reasons.append(
                "The latest rolling 24-hour block has less than 95% coverage."
            )
        if not np.isfinite(daily_values).all():
            prepared.reasons.append(
                "The daily context still contains missing or invalid values."
            )
        if not prepared.reasons:
            prepared.values = daily_values.astype(np.float32)
        return prepared

    def _load_manifest(self, horizon_hours: int) -> tuple[dict | None, str | None]:
        spec = self.artifact_spec(horizon_hours)
        if horizon_hours in self._manifests or horizon_hours in self._artifact_errors:
            return self._manifests.get(horizon_hours), self._artifact_errors.get(
                horizon_hours
            )
        try:
            manifest_path = spec.artifact_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_name = manifest.get("name", manifest.get("model_name"))
            if manifest_name != spec.model_name:
                raise RuntimeError(
                    "The packaged model name does not match its fixed capability."
                )
            if horizon_hours == MONTH_HORIZON_HOURS:
                contract = manifest["contract"]
                if manifest.get("status") != "production_eligible":
                    raise RuntimeError(
                        "The monthly release did not pass its production gate."
                    )
                if int(contract["context_days"]) != MONTH_CONTEXT_DAYS:
                    raise RuntimeError(
                        "The monthly context does not match the product contract."
                    )
                if int(contract["horizon_days"]) != MONTH_TARGET_DAYS:
                    raise RuntimeError(
                        "The monthly horizon does not match the product contract."
                    )
                if contract["target_frequency"] != "daily":
                    raise RuntimeError(
                        "The monthly release must produce daily targets."
                    )
                if contract["quantiles"] != [0.1, 0.5, 0.9]:
                    raise RuntimeError("The monthly quantile contract is unsupported.")
                checkpoint = spec.artifact_dir / manifest["adapter"]["filename"]
                checkpoint_size = int(manifest["adapter"]["bytes"])
                checkpoint_sha = manifest["adapter"]["sha256"]
            else:
                if int(manifest["lookback_hours"]) != LOOKBACK_HOURS:
                    raise RuntimeError(
                        "The packaged model lookback does not match the product contract."
                    )
                if int(manifest["horizon_hours"]) != horizon_hours:
                    raise RuntimeError(
                        "The packaged model horizon does not match its fixed capability."
                    )
                if manifest["quantiles"] != [0.1, 0.5, 0.9]:
                    raise RuntimeError(
                        "The packaged model quantile contract is unsupported."
                    )
                checkpoint = spec.artifact_dir / manifest["checkpoint_file"]
                checkpoint_size = int(manifest["checkpoint_size_bytes"])
                checkpoint_sha = manifest["checkpoint_sha256"]
            if not checkpoint.is_file():
                raise RuntimeError("The packaged model checkpoint is missing.")
            if checkpoint.stat().st_size != checkpoint_size:
                raise RuntimeError("The packaged model checkpoint size is invalid.")
            digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
            if digest != checkpoint_sha:
                raise RuntimeError(
                    "The packaged model checkpoint failed its SHA-256 integrity check."
                )
            self._manifests[horizon_hours] = manifest
        except (OSError, KeyError, TypeError, ValueError, RuntimeError) as exc:
            self._artifact_errors[horizon_hours] = str(exc)
        return self._manifests.get(horizon_hours), self._artifact_errors.get(
            horizon_hours
        )

    def model_status(self, horizon_hours: int = 24) -> dict:
        spec = self.artifact_spec(horizon_hours)
        enabled = self.is_enabled(horizon_hours)
        if not enabled:
            return {
                "available": False,
                "enabled": False,
                "horizon_hours": horizon_hours,
                "name": spec.model_name,
                "display_name": spec.display_name,
                "version": MODEL_VERSION,
                "artifact_fingerprint": None,
                "error": "The capability is disabled by configuration.",
            }
        manifest, artifact_error = self._load_manifest(horizon_hours)
        torch_available = importlib.util.find_spec("torch") is not None
        error = artifact_error
        if error is None and not torch_available:
            error = "PyTorch is not installed in this runtime."
        if error is None and horizon_hours == MONTH_HORIZON_HOURS:
            missing = [
                dependency
                for dependency in ("chronos", "peft", "huggingface_hub")
                if importlib.util.find_spec(dependency) is None
            ]
            if missing:
                error = (
                    f"Monthly inference dependencies are missing: {', '.join(missing)}."
                )
        fingerprint = None
        if manifest:
            fingerprint = (
                manifest["adapter"]["sha256"]
                if horizon_hours == MONTH_HORIZON_HOURS
                else manifest.get("checkpoint_sha256")
            )
        return {
            "available": error is None,
            "enabled": True,
            "horizon_hours": horizon_hours,
            "name": spec.model_name,
            "display_name": (
                manifest.get("display_name", spec.display_name)
                if manifest
                else spec.display_name
            ),
            "version": (
                manifest.get("version", MODEL_VERSION) if manifest else MODEL_VERSION
            ),
            "artifact_fingerprint": fingerprint,
            "error": error,
        }

    def warmup(self, horizon_hours: int = 24) -> dict:
        """Validate and load one fixed production artifact without client data."""
        status = (
            self.model_status()
            if horizon_hours == 24
            else self.model_status(horizon_hours)
        )
        if not status["available"]:
            return {**status, "warmed": False}
        try:
            self._load_model(horizon_hours)
            return {**status, "warmed": True}
        except Exception as exc:
            logger.exception("Forecast model %sh warm-up failed", horizon_hours)
            return {**status, "available": False, "warmed": False, "error": str(exc)}

    def capabilities(self) -> dict:
        """Advertise only fixed capabilities that satisfy their visibility gate."""
        day = self.warmup()
        advertised = [
            {
                "horizon_hours": 24,
                "label": "Next 24 hours",
                "description": "Next 24 hourly energy values",
                "model": day,
            }
        ]
        optional = (
            (168, "Next 7 days", "Next 168 hourly energy values"),
            (
                MONTH_HORIZON_HOURS,
                "Next 30 days",
                "Next 30 daily energy values from the production Chronos-2 adapter",
            ),
        )
        for horizon_hours, label, description in optional:
            if not self.is_enabled(horizon_hours):
                continue
            model = self.warmup(horizon_hours)
            if model["available"] and model.get("warmed"):
                spec = self.artifact_spec(horizon_hours)
                advertised.append(
                    {
                        "horizon_hours": horizon_hours,
                        "target_count": spec.target_count,
                        "target_interval_hours": spec.target_interval_hours,
                        "resolution": spec.resolution,
                        "label": label,
                        "description": description,
                        "model": model,
                    }
                )
        advertised[0].update(
            {"target_count": 24, "target_interval_hours": 1, "resolution": "hourly"}
        )
        return {"default_horizon_hours": 24, "capabilities": advertised}

    def _require_advertised(self, horizon_hours: int) -> ForecastArtifactSpec:
        spec = self.require_enabled(horizon_hours)
        if horizon_hours in (168, MONTH_HORIZON_HOURS):
            status = self.warmup(horizon_hours)
            if not status["available"] or not status.get("warmed"):
                label = "7-day / 168-hour" if horizon_hours == 168 else "30-day daily"
                raise ForecastCapabilityError(
                    "FORECAST_ARTIFACT_NOT_READY",
                    (
                        f"The {label} model artifact is unavailable or could not be loaded. "
                        f"{status.get('error') or 'Check the packaged model and restart the backend.'}"
                    ),
                    503,
                )
        return spec

    def readiness(self, db: Session, user_id: int, horizon_hours: int = 24) -> dict:
        self._require_advertised(horizon_hours)
        spec = self.artifact_spec(horizon_hours)
        prepared = (
            self.prepare_month_input(db, user_id)
            if horizon_hours == MONTH_HORIZON_HOURS
            else self.prepare_input(db, user_id)
        )
        model = self.warmup(horizon_hours)
        if not prepared.ready:
            status = "insufficient_data"
        elif model["available"] and model.get("warmed"):
            status = "ready"
        else:
            status = "fallback_ready"
        ready_for_model = (
            prepared.ready and model["available"] and bool(model.get("warmed"))
        )
        required_hours = (
            MONTH_MINIMUM_OBSERVED_DAYS * 24
            if horizon_hours == MONTH_HORIZON_HOURS
            else LOOKBACK_HOURS
        )
        observed_days = getattr(prepared, "observed_days", 0)
        return {
            "horizon_hours": horizon_hours,
            "target_count": spec.target_count,
            "target_interval_hours": spec.target_interval_hours,
            "status": status,
            "ready_for_model": ready_for_model,
            "ready_for_tft": ready_for_model and horizon_hours != MONTH_HORIZON_HOURS,
            "fallback_available": prepared.ready,
            "required_hours": required_hours,
            "required_days": (
                MONTH_MINIMUM_OBSERVED_DAYS
                if horizon_hours == MONTH_HORIZON_HOURS
                else None
            ),
            "minimum_coverage_percent": MINIMUM_COVERAGE_PERCENT,
            "maximum_allowed_gap_hours": (
                MONTH_MAXIMUM_GAP_DAYS * 24
                if horizon_hours == MONTH_HORIZON_HOURS
                else MAXIMUM_GAP_HOURS
            ),
            "coverage_percent": round(prepared.coverage_percent, 2),
            "observed_hours": prepared.observed_hours,
            "missing_hours": max(0, required_hours - prepared.observed_hours),
            "imputed_hours": (
                0
                if horizon_hours == MONTH_HORIZON_HOURS
                else len(prepared.imputed_timestamps) if prepared.ready else 0
            ),
            "maximum_gap_hours": prepared.maximum_gap_hours,
            "observed_days": observed_days,
            "missing_days": (
                max(0, MONTH_MINIMUM_OBSERVED_DAYS - observed_days)
                if horizon_hours == MONTH_HORIZON_HOURS
                else 0
            ),
            "imputed_days": (
                len(prepared.imputed_days)
                if prepared.ready and horizon_hours == MONTH_HORIZON_HOURS
                else 0
            ),
            "maximum_gap_days": getattr(prepared, "maximum_gap_days", 0),
            "unit": "kWh",
            "resolution": spec.resolution,
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

    def _calendar(
        self, timestamps: list[datetime], site: Site, country: str | None
    ) -> np.ndarray:
        zone = self._site_zone(site)
        local_timestamps = [timestamp.astimezone(zone) for timestamp in timestamps]
        years = sorted({timestamp.year for timestamp in local_timestamps})
        try:
            country_holidays = holidays.country_holidays(
                self._country_code(country), years=years
            )
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

    def _load_model(self, horizon_hours: int):
        if horizon_hours in self._models:
            return self._models[horizon_hours]
        manifest, error = self._load_manifest(horizon_hours)
        if error or manifest is None:
            raise RuntimeError(error or "Model manifest is unavailable.")
        spec = self.artifact_spec(horizon_hours)
        if horizon_hours == MONTH_HORIZON_HOURS:
            try:
                import torch

                from app.ml.month_production import MonthProductionForecaster
            except ImportError as exc:
                raise RuntimeError(
                    "Monthly Chronos-2 inference dependencies are not installed."
                ) from exc
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model = MonthProductionForecaster(spec.artifact_dir, device=device)
            self._models[horizon_hours] = model
            return model
        try:
            import torch

            from app.ml.global_tft import GlobalTFT
        except ImportError as exc:
            raise RuntimeError("PyTorch is not installed in this runtime.") from exc

        checkpoint_path = spec.artifact_dir / manifest["checkpoint_file"]
        try:
            checkpoint = torch.load(
                checkpoint_path, map_location="cpu", weights_only=True
            )
        except TypeError:
            checkpoint = torch.load(checkpoint_path, map_location="cpu")
        architecture = manifest.get("architecture", {})
        model = GlobalTFT(
            hidden_size=int(architecture.get("hidden_size", 128)),
            n_heads=int(architecture.get("attention_heads", 4)),
            dropout=float(architecture.get("dropout", 0.1)),
        )
        model.load_state_dict(checkpoint["model_state_dict"], strict=True)
        model.eval()
        self._models[horizon_hours] = model
        return model

    def _predict_month(
        self, prepared: PreparedMonthForecastInput
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        assert prepared.values is not None
        prediction = self._load_model(MONTH_HORIZON_HOURS).predict(prepared.values)
        lower = np.asarray(prediction["p10"], dtype=np.float64)
        median = np.asarray(prediction["p50"], dtype=np.float64)
        upper = np.asarray(prediction["p90"], dtype=np.float64)
        if any(
            values.shape != (MONTH_TARGET_DAYS,) for values in (lower, median, upper)
        ):
            raise RuntimeError("The monthly model returned an invalid forecast tensor.")
        combined = np.stack([lower, median, upper], axis=1)
        if not np.isfinite(combined).all() or np.min(combined) < 0:
            raise RuntimeError("The monthly model returned invalid energy values.")
        combined.sort(axis=1)
        return combined[:, 0], combined[:, 1], combined[:, 2]

    def _generate_month(self, db: Session, user_id: int) -> dict:
        spec = self._require_advertised(MONTH_HORIZON_HOURS)
        prepared = self.prepare_month_input(db, user_id)
        if not prepared.ready:
            raise ForecastInputError(" ".join(prepared.reasons))
        assert prepared.values is not None
        assert prepared.origin is not None
        assert prepared.site is not None

        model_status = self.warmup(MONTH_HORIZON_HOURS)
        method = "chronos2_lora"
        model_name = spec.model_name
        fallback_reason = None
        inference_started = time.perf_counter()
        try:
            lower, median, upper = self._predict_month(prepared)
            confidence_method = (
                "Chronos-2 10th/50th/90th quantiles with validation-only asymmetric "
                "scale-normalized conformal calibration."
            )
        except Exception as exc:
            logger.exception(
                "Chronos-2 monthly inference failed; using the declared last-28-day fallback"
            )
            method = "seasonal_naive"
            model_name = spec.fallback_name
            fallback_reason = str(exc)
            median = np.resize(prepared.values[-28:], MONTH_TARGET_DAYS).astype(
                np.float64
            )
            lower = upper = np.full(MONTH_TARGET_DAYS, np.nan)
            confidence_method = "Last-28-day seasonal point forecast; no uncertainty interval is available."
        inference_seconds = time.perf_counter() - inference_started

        points = []
        prediction_rows = []
        for index in range(MONTH_TARGET_DAYS):
            timestamp = prepared.origin + timedelta(
                hours=index * MONTH_TARGET_INTERVAL_HOURS
            )
            p50 = round(float(median[index]), 5)
            p10 = round(float(lower[index]), 5) if math.isfinite(lower[index]) else None
            p90 = round(float(upper[index]), 5) if math.isfinite(upper[index]) else None
            points.append(
                {
                    "timestamp": timestamp,
                    "p10_kwh": p10,
                    "p50_kwh": p50,
                    "p90_kwh": p90,
                }
            )
            prediction_rows.append([p50, p10, p90])

        return {
            "horizon_hours": MONTH_HORIZON_HOURS,
            "target_count": MONTH_TARGET_DAYS,
            "target_interval_hours": MONTH_TARGET_INTERVAL_HOURS,
            "resolution": "daily",
            "model_name": model_name,
            "model_version": (
                model_status["version"]
                if method == "chronos2_lora"
                else "deterministic-v1"
            ),
            "method": method,
            "fallback_reason": fallback_reason,
            "confidence_method": confidence_method,
            "prediction_rows": prediction_rows,
            "points": points,
            "site": prepared.site,
            "meter": prepared.meter,
            "origin": prepared.origin,
            "input_start": prepared.origin - timedelta(days=MONTH_CONTEXT_DAYS),
            "forecast_end": prepared.origin + timedelta(days=MONTH_TARGET_DAYS),
            "coverage_percent": round(prepared.coverage_percent, 2),
            "observed_hours": prepared.observed_hours,
            "observed_days": prepared.observed_days,
            "maximum_gap_hours": prepared.maximum_gap_hours,
            "maximum_gap_days": prepared.maximum_gap_days,
            "sources": prepared.sources,
            "preprocessing": {
                "aggregation": "interval-integrated rolling 24-hour energy",
                "context_days": MONTH_CONTEXT_DAYS,
                "minimum_observed_days": MONTH_MINIMUM_OBSERVED_DAYS,
                "daily_coverage_threshold_percent": MINIMUM_COVERAGE_PERCENT,
                "short_context": "left-pad with earliest observed daily value",
                "imputation": "linear interpolation within observed daily history",
                "imputed_day_indices": prepared.imputed_days,
            },
            "inference_seconds": round(inference_seconds, 4),
            "artifact_fingerprint": (
                model_status["artifact_fingerprint"]
                if method == "chronos2_lora"
                else None
            ),
        }

    def _predict_tft(
        self,
        prepared: PreparedForecastInput,
        country: str | None,
        mean: float,
        standard_deviation: float,
        horizon_hours: int,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        import torch

        assert (
            prepared.values is not None
            and prepared.origin is not None
            and prepared.site is not None
        )
        normalized = (prepared.values - mean) / standard_deviation
        past_timestamps = [
            prepared.origin - timedelta(hours=LOOKBACK_HOURS - index)
            for index in range(LOOKBACK_HOURS)
        ]
        future_timestamps = [
            prepared.origin + timedelta(hours=index) for index in range(horizon_hours)
        ]
        batch = {
            "x": torch.from_numpy(normalized[None, :, None].astype(np.float32)),
            "x_calendar": torch.from_numpy(
                self._calendar(past_timestamps, prepared.site, country)[None]
            ),
            "y_calendar": torch.from_numpy(
                self._calendar(future_timestamps, prepared.site, country)[None]
            ),
        }
        model = self._load_model(horizon_hours)
        with torch.inference_mode():
            output = model(batch)["quantiles"].cpu().numpy()[0]
        if output.shape != (horizon_hours, 3) or not np.isfinite(output).all():
            raise RuntimeError("The model returned an invalid forecast tensor.")
        output = np.maximum(0.0, output * standard_deviation + mean)
        output.sort(axis=1)
        return output[:, 0], output[:, 1], output[:, 2]

    def generate(self, db: Session, user_id: int, horizon_hours: int = 24) -> dict:
        if horizon_hours == MONTH_HORIZON_HOURS:
            return self._generate_month(db, user_id)
        spec = self._require_advertised(horizon_hours)
        prepared = self.prepare_input(db, user_id)
        if not prepared.ready:
            raise ForecastInputError(" ".join(prepared.reasons))
        assert (
            prepared.values is not None
            and prepared.origin is not None
            and prepared.site is not None
        )

        site_settings = (
            db.query(SiteSettings)
            .filter(SiteSettings.site_id == prepared.site.id)
            .one_or_none()
        )
        model_status = (
            self.warmup() if horizon_hours == 24 else self.warmup(horizon_hours)
        )
        mean = float(prepared.values.mean())
        standard_deviation = max(float(prepared.values.std()), 1e-6)
        preprocessing = {
            "aggregation": "interval-integrated hourly energy",
            "normalization": "rolling_window_zscore",
            "scaler_mean_kwh": mean,
            "scaler_std_kwh": standard_deviation,
            "imputation": "linear interpolation across gaps up to 3 hours",
            "imputed_timestamps": [
                value.isoformat() for value in prepared.imputed_timestamps
            ],
        }
        method = "global_tft"
        model_name = spec.model_name
        fallback_reason = None
        inference_started = time.perf_counter()
        try:
            if not model_status["available"] or not model_status.get("warmed"):
                raise RuntimeError(
                    model_status["error"] or "The TFT model is unavailable."
                )
            lower, median, upper = self._predict_tft(
                prepared,
                site_settings.country if site_settings else None,
                mean,
                standard_deviation,
                horizon_hours,
            )
            confidence_method = "Native Global TFT 10th/50th/90th quantile outputs; not recalibrated for this site."
        except Exception as exc:
            logger.exception(
                "Global TFT %sh inference failed; using the declared seasonal fallback",
                horizon_hours,
            )
            method = "seasonal_naive"
            model_name = spec.fallback_name
            fallback_reason = str(exc)
            fallback_start = LOOKBACK_HOURS - 168
            median = prepared.values[
                fallback_start : fallback_start + horizon_hours
            ].astype(np.float64)
            lower = upper = np.full(horizon_hours, np.nan)
            confidence_method = (
                "Seasonal-naive point forecast; no uncertainty interval is available."
            )
        inference_seconds = time.perf_counter() - inference_started

        points = []
        prediction_rows = []
        for index in range(horizon_hours):
            timestamp = prepared.origin + timedelta(hours=index)
            p50 = round(float(median[index]), 5)
            p10 = round(float(lower[index]), 5) if math.isfinite(lower[index]) else None
            p90 = round(float(upper[index]), 5) if math.isfinite(upper[index]) else None
            points.append(
                {"timestamp": timestamp, "p10_kwh": p10, "p50_kwh": p50, "p90_kwh": p90}
            )
            prediction_rows.append([p50, p10, p90])

        return {
            "horizon_hours": horizon_hours,
            "target_count": horizon_hours,
            "target_interval_hours": 1,
            "resolution": "hourly",
            "model_name": model_name,
            "model_version": (
                model_status["version"]
                if method == "global_tft"
                else "deterministic-v1"
            ),
            "method": method,
            "fallback_reason": fallback_reason,
            "confidence_method": confidence_method,
            "prediction_rows": prediction_rows,
            "points": points,
            "site": prepared.site,
            "meter": prepared.meter,
            "origin": prepared.origin,
            "input_start": prepared.origin - timedelta(hours=LOOKBACK_HOURS),
            "forecast_end": prepared.origin + timedelta(hours=horizon_hours),
            "coverage_percent": round(prepared.coverage_percent, 2),
            "observed_hours": prepared.observed_hours,
            "maximum_gap_hours": prepared.maximum_gap_hours,
            "sources": prepared.sources,
            "preprocessing": preprocessing,
            "inference_seconds": round(inference_seconds, 4),
            "artifact_fingerprint": (
                model_status["artifact_fingerprint"] if method == "global_tft" else None
            ),
        }


product_forecast_service = ProductForecastService()
