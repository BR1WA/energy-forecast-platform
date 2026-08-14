"""Train and audit a strong 30-day household energy forecaster.

The production application currently serves hourly 24 h and 168 h Global TFT
artifacts.  This module is deliberately research-only until its promotion gates
pass.  It trains two pooled, household-agnostic XGBoost quantile models:

* a daily residual model for the next 30 daily kWh totals;
* a reconciled 30-day-total residual model for budget-oriented accuracy.

Both models forecast corrections to causal seasonal profiles.  All scaling is
computed from the 90 days available at each forecast origin, so a cold-start
household never needs a training-period household scaler or identity embedding.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np

LOOKBACK_DAYS = 90
HORIZON_DAYS = 30
WEEKLY_LAGS = 12
QUANTILES = np.asarray([0.1, 0.5, 0.9], dtype=np.float32)
DEFAULT_SEED = 2026
TARGET_INTERVAL_COVERAGE = 0.80

# These thresholds are declared before test evaluation and must not be relaxed
# after viewing the cold-start results.
MIN_DAILY_MAE_IMPROVEMENT_PERCENT = 5.0
MIN_TOTAL_MAE_IMPROVEMENT_PERCENT = 5.0
MIN_MACRO_R2 = 0.0
MAX_ABSOLUTE_DAILY_BIAS_KWH = 0.50
MIN_INTERVAL_COVERAGE_PERCENT = 75.0
MAX_INTERVAL_COVERAGE_PERCENT = 85.0


def set_deterministic_seed(seed: int) -> None:
    """Seed the libraries used here without time-dependent sampling."""

    random.seed(seed)
    np.random.seed(seed)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    temporary.replace(path)


def rolling_origins(
    segment_start: int,
    segment_end: int,
    *,
    requested: int,
    lookback: int = LOOKBACK_DAYS,
    horizon: int = HORIZON_DAYS,
) -> np.ndarray:
    """Return deterministic, unique rolling origins inside one target segment."""

    earliest = max(segment_start, lookback)
    latest = segment_end - horizon
    if latest < earliest:
        raise ValueError(
            f"Segment [{segment_start}, {segment_end}) cannot hold a "
            f"{horizon}-day target after {lookback} days of history."
        )
    return np.unique(
        np.linspace(earliest, latest, num=max(1, requested), dtype=np.int64)
    )


def training_origins(
    train_end: int,
    *,
    stride: int,
    lookback: int = LOOKBACK_DAYS,
    horizon: int = HORIZON_DAYS,
) -> np.ndarray:
    if stride < 1:
        raise ValueError("Training stride must be positive.")
    return np.arange(
        lookback,
        train_end - horizon + 1,
        stride,
        dtype=np.int64,
    )


def valid_windows(
    values: np.ndarray,
    households: Iterable[int],
    origins: Iterable[int],
    *,
    lookback: int = LOOKBACK_DAYS,
    horizon: int = HORIZON_DAYS,
) -> list[tuple[int, int]]:
    """Select windows with complete causal history and complete targets."""

    windows: list[tuple[int, int]] = []
    origins_array = np.asarray(list(origins), dtype=np.int64)
    for raw_household in households:
        household = int(raw_household)
        row = np.asarray(values[household])
        finite = np.isfinite(row).astype(np.int64, copy=False)
        prefix = np.concatenate([np.zeros(1, dtype=np.int64), np.cumsum(finite)])
        required = lookback + horizon
        counts = prefix[origins_array + horizon] - prefix[origins_array - lookback]
        for origin in origins_array[counts == required]:
            windows.append((household, int(origin)))
    if not windows:
        raise RuntimeError("No fully finite monthly forecasting windows were found.")
    return windows


def _linear_weekly_slope(weekly_recent_first: np.ndarray, weeks: int) -> np.ndarray:
    chronological = weekly_recent_first[:weeks][::-1]
    positions = np.arange(weeks, dtype=np.float32)
    centered = positions - positions.mean()
    denominator = float(np.square(centered).sum())
    return (centered[:, None] * (chronological - chronological.mean(axis=0))).sum(
        axis=0
    ) / max(denominator, 1e-6)


def _window_components(
    row: np.ndarray,
    calendar: np.ndarray,
    origin: int,
) -> dict[str, np.ndarray | float]:
    """Build causal features and baselines for one origin.

    The most recent weekly profile always ends at ``origin``.  Future week two
    therefore reuses or adjusts only values observed before the origin; no
    feature indexes into the target interval.
    """

    history = np.asarray(row[origin - LOOKBACK_DAYS : origin], dtype=np.float32)
    target = np.asarray(row[origin : origin + HORIZON_DAYS], dtype=np.float32)
    future_calendar = np.asarray(
        calendar[origin : origin + HORIZON_DAYS], dtype=np.float32
    )
    if (
        history.shape != (LOOKBACK_DAYS,)
        or target.shape != (HORIZON_DAYS,)
        or future_calendar.shape[0] != HORIZON_DAYS
        or not np.isfinite(history).all()
        or not np.isfinite(target).all()
        or not np.isfinite(future_calendar).all()
    ):
        raise ValueError("Window components require complete causal arrays.")

    rolling_mean = float(history.mean(dtype=np.float64))
    rolling_std = float(history.std(dtype=np.float64))
    rolling_std = max(rolling_std, 0.10, abs(rolling_mean) * 0.02)
    history_z = (history - rolling_mean) / rolling_std

    weekly = np.stack(
        [
            row[origin - 7 * (week + 1) : origin - 7 * week]
            for week in range(WEEKLY_LAGS)
        ],
        axis=0,
    ).astype(np.float32)
    if weekly.shape != (WEEKLY_LAGS, 7) or not np.isfinite(weekly).all():
        raise ValueError("Twelve complete weekly profiles are required.")

    steps = np.arange(HORIZON_DAYS, dtype=np.int64)
    slots = steps % 7
    future_weeks = steps // 7
    lag_values = weekly[:, slots].T
    lag_z = (lag_values - rolling_mean) / rolling_std

    mean4_profile = weekly[:4].mean(axis=0)
    median4_profile = np.median(weekly[:4], axis=0)
    mean8_profile = weekly[:8].mean(axis=0)
    median8_profile = np.median(weekly[:8], axis=0)
    std4_profile = weekly[:4].std(axis=0)
    mean4 = mean4_profile[slots]

    slope4_profile = _linear_weekly_slope(weekly, 4)
    slope8_profile = _linear_weekly_slope(weekly, 8)
    slope12_profile = _linear_weekly_slope(weekly, 12)
    # Damping was selected on the known-household validation segment only.
    damped_trend = mean4 + 0.20 * slope4_profile[slots] * (2.5 + future_weeks)
    damped_trend = np.clip(damped_trend, 0.0, None).astype(np.float32)

    recent_statistics: list[float] = []
    for days in (7, 14, 28, 56, 90):
        recent = history[-days:]
        recent_statistics.extend(
            [
                (float(recent.mean()) - rolling_mean) / rolling_std,
                float(recent.std()) / rolling_std,
            ]
        )

    profile_features = np.column_stack(
        [
            (mean4 - rolling_mean) / rolling_std,
            (median4_profile[slots] - rolling_mean) / rolling_std,
            (mean8_profile[slots] - rolling_mean) / rolling_std,
            (median8_profile[slots] - rolling_mean) / rolling_std,
            std4_profile[slots] / rolling_std,
            (lag_values[:, 0] - mean4) / rolling_std,
            (damped_trend - mean4) / rolling_std,
        ]
    ).astype(np.float32)

    slope_features = np.column_stack(
        [
            slope4_profile[slots] / rolling_std,
            slope8_profile[slots] / rolling_std,
            slope12_profile[slots] / rolling_std,
        ]
    ).astype(np.float32)
    horizon_features = np.column_stack(
        [
            steps / max(HORIZON_DAYS - 1, 1),
            future_weeks / 4.0,
            np.sin(2.0 * np.pi * steps / 7.0),
            np.cos(2.0 * np.pi * steps / 7.0),
        ]
    ).astype(np.float32)
    repeated_statistics = np.repeat(
        np.asarray(recent_statistics, dtype=np.float32)[None, :],
        HORIZON_DAYS,
        axis=0,
    )
    magnitude_features = np.repeat(
        np.asarray(
            [math.log1p(max(rolling_mean, 0.0)), math.log1p(rolling_std)],
            dtype=np.float32,
        )[None, :],
        HORIZON_DAYS,
        axis=0,
    )

    point_features = np.concatenate(
        [
            lag_z,
            profile_features,
            repeated_statistics,
            slope_features,
            horizon_features,
            future_calendar,
            magnitude_features,
        ],
        axis=1,
    ).astype(np.float32)

    total_features = np.concatenate(
        [
            history_z,
            ((mean4 - rolling_mean) / rolling_std).astype(np.float32),
            ((damped_trend - rolling_mean) / rolling_std).astype(np.float32),
            future_calendar.reshape(-1),
            np.asarray(recent_statistics, dtype=np.float32),
            np.asarray(
                [
                    slope4_profile.mean() / rolling_std,
                    slope8_profile.mean() / rolling_std,
                    slope12_profile.mean() / rolling_std,
                    math.log1p(max(rolling_mean, 0.0)),
                    math.log1p(rolling_std),
                ],
                dtype=np.float32,
            ),
        ]
    ).astype(np.float32)

    return {
        "point_features": point_features,
        "total_features": total_features,
        "target": target,
        "target_residual_z": ((target - mean4) / rolling_std).astype(np.float32),
        "target_total_residual_z": np.float32(
            (float(target.sum()) - float(mean4.sum())) / (rolling_std * HORIZON_DAYS)
        ),
        "mean4": mean4.astype(np.float32),
        "last_week": lag_values[:, 0].astype(np.float32),
        "recent30": np.repeat(history[-30:].mean(), HORIZON_DAYS).astype(np.float32),
        "damped_trend": damped_trend,
        "scale": np.float32(rolling_std),
    }


@dataclass
class ForecastMatrix:
    point_features: np.ndarray
    total_features: np.ndarray
    target_residual_z: np.ndarray
    target_total_residual_z: np.ndarray
    target: np.ndarray
    mean4: np.ndarray
    baselines: dict[str, np.ndarray]
    scales: np.ndarray
    point_steps: np.ndarray
    point_households: np.ndarray
    window_households: np.ndarray
    window_origins: np.ndarray

    @property
    def n_windows(self) -> int:
        return int(self.window_households.size)


def build_matrix(
    values: np.ndarray,
    calendar: np.ndarray,
    windows: list[tuple[int, int]],
) -> ForecastMatrix:
    """Materialize float32 features for XGBoost and auditable baselines."""

    first_house, first_origin = windows[0]
    first = _window_components(np.asarray(values[first_house]), calendar, first_origin)
    point_width = int(np.asarray(first["point_features"]).shape[1])
    total_width = int(np.asarray(first["total_features"]).shape[0])
    n_windows = len(windows)
    n_points = n_windows * HORIZON_DAYS

    point_features = np.empty((n_points, point_width), dtype=np.float32)
    total_features = np.empty((n_windows, total_width), dtype=np.float32)
    target_residual_z = np.empty(n_points, dtype=np.float32)
    target_total_residual_z = np.empty(n_windows, dtype=np.float32)
    target = np.empty(n_points, dtype=np.float32)
    mean4 = np.empty(n_points, dtype=np.float32)
    scales = np.empty(n_points, dtype=np.float32)
    point_households = np.empty(n_points, dtype=np.int32)
    window_households = np.empty(n_windows, dtype=np.int32)
    window_origins = np.empty(n_windows, dtype=np.int32)
    baselines = {
        name: np.empty(n_points, dtype=np.float32)
        for name in ("last_week", "mean4", "recent30", "damped_trend")
    }

    for window_index, (household, origin) in enumerate(windows):
        components = _window_components(np.asarray(values[household]), calendar, origin)
        start = window_index * HORIZON_DAYS
        end = start + HORIZON_DAYS
        point_features[start:end] = components["point_features"]
        total_features[window_index] = components["total_features"]
        target_residual_z[start:end] = components["target_residual_z"]
        target_total_residual_z[window_index] = components["target_total_residual_z"]
        target[start:end] = components["target"]
        mean4[start:end] = components["mean4"]
        scales[start:end] = float(components["scale"])
        point_households[start:end] = household
        window_households[window_index] = household
        window_origins[window_index] = origin
        for name in baselines:
            baselines[name][start:end] = components[name]

    return ForecastMatrix(
        point_features=point_features,
        total_features=total_features,
        target_residual_z=target_residual_z,
        target_total_residual_z=target_total_residual_z,
        target=target,
        mean4=mean4,
        baselines=baselines,
        scales=scales,
        point_steps=np.tile(np.arange(HORIZON_DAYS, dtype=np.int16), n_windows),
        point_households=point_households,
        window_households=window_households,
        window_origins=window_origins,
    )


def _macro_r2(
    target: np.ndarray,
    prediction: np.ndarray,
    households: np.ndarray,
) -> tuple[float, float]:
    household_r2: list[float] = []
    for household in np.unique(households):
        mask = households == household
        y = target[mask].astype(np.float64)
        p = prediction[mask].astype(np.float64)
        denominator = float(np.square(y - y.mean()).sum())
        if denominator > 1e-12:
            household_r2.append(1.0 - float(np.square(p - y).sum()) / denominator)
    global_denominator = float(
        np.square(target.astype(np.float64) - float(target.mean())).sum()
    )
    global_r2 = 1.0 - float(
        np.square(prediction.astype(np.float64) - target.astype(np.float64)).sum()
    ) / max(global_denominator, 1e-12)
    return float(np.mean(household_r2)), float(global_r2)


def point_metrics(
    matrix: ForecastMatrix,
    prediction: np.ndarray,
    quantile_prediction: np.ndarray | None = None,
) -> dict[str, float | int]:
    target = matrix.target.astype(np.float64)
    prediction = np.asarray(prediction, dtype=np.float64)
    error = prediction - target
    unique_households = np.unique(matrix.point_households)
    house_mae: list[float] = []
    house_rmse: list[float] = []
    house_bias: list[float] = []
    for household in unique_households:
        mask = matrix.point_households == household
        house_error = error[mask]
        house_mae.append(float(np.abs(house_error).mean()))
        house_rmse.append(float(np.sqrt(np.square(house_error).mean())))
        house_bias.append(float(house_error.mean()))
    macro_r2, global_r2 = _macro_r2(target, prediction, matrix.point_households)

    target_windows = target.reshape(matrix.n_windows, HORIZON_DAYS)
    prediction_windows = prediction.reshape(matrix.n_windows, HORIZON_DAYS)
    target_totals = target_windows.sum(axis=1)
    prediction_totals = prediction_windows.sum(axis=1)
    total_error = prediction_totals - target_totals
    total_macro_r2, total_global_r2 = _macro_r2(
        target_totals, prediction_totals, matrix.window_households
    )

    result: dict[str, float | int] = {
        "n_households": int(unique_households.size),
        "n_windows": matrix.n_windows,
        "n_daily_targets": int(target.size),
        "daily_macro_mae_kwh": float(np.mean(house_mae)),
        "daily_macro_rmse_kwh": float(np.mean(house_rmse)),
        "daily_macro_bias_kwh": float(np.mean(house_bias)),
        "daily_macro_r2": macro_r2,
        "daily_global_r2": global_r2,
        "daily_p90_absolute_error_kwh": float(np.percentile(np.abs(error), 90)),
        "month_total_mae_kwh": float(np.abs(total_error).mean()),
        "month_total_median_ape_percent": float(
            np.median(100.0 * np.abs(total_error) / np.maximum(target_totals, 1e-8))
        ),
        "month_total_macro_r2": total_macro_r2,
        "month_total_global_r2": total_global_r2,
    }
    if quantile_prediction is not None:
        quantiles = np.asarray(quantile_prediction, dtype=np.float64)
        lower, median, upper = quantiles.T
        result.update(
            {
                "central_80_coverage_percent": float(
                    100.0 * np.mean((target >= lower) & (target <= upper))
                ),
                "central_80_mean_width_kwh": float(np.mean(upper - lower)),
                "q10_pinball_kwh": float(
                    np.mean(np.maximum(0.1 * (target - lower), -0.9 * (target - lower)))
                ),
                "q50_pinball_kwh": float(0.5 * np.mean(np.abs(target - median))),
                "q90_pinball_kwh": float(
                    np.mean(np.maximum(0.9 * (target - upper), -0.1 * (target - upper)))
                ),
            }
        )
    return result


def calibrate_daily_quantiles(
    validation: ForecastMatrix,
    validation_residual_quantiles: np.ndarray,
) -> dict[str, list[float]]:
    """Fit horizon-specific location and conformal interval corrections."""

    predictions = np.sort(
        np.asarray(validation_residual_quantiles, dtype=np.float64), axis=1
    )
    location: list[float] = []
    expansion: list[float] = []
    for step in range(HORIZON_DAYS):
        mask = validation.point_steps == step
        target = validation.target_residual_z[mask].astype(np.float64)
        step_prediction = predictions[mask]
        offset = float(np.median(target - step_prediction[:, 1]))
        shifted = step_prediction + offset
        conformity = np.maximum(shifted[:, 0] - target, target - shifted[:, 2])
        finite_sample_level = min(
            1.0,
            math.ceil((len(conformity) + 1) * TARGET_INTERVAL_COVERAGE)
            / len(conformity),
        )
        try:
            conformal = float(
                np.quantile(conformity, finite_sample_level, method="higher")
            )
        except TypeError:
            conformal = float(
                np.quantile(conformity, finite_sample_level, interpolation="higher")
            )
        location.append(offset)
        expansion.append(max(0.0, conformal))
    return {"location": location, "interval_expansion": expansion}


def apply_daily_calibration(
    matrix: ForecastMatrix,
    residual_quantiles: np.ndarray,
    calibration: dict[str, list[float]],
) -> np.ndarray:
    residual = np.sort(np.asarray(residual_quantiles, dtype=np.float64), axis=1)
    location = np.asarray(calibration["location"], dtype=np.float64)
    expansion = np.asarray(calibration["interval_expansion"], dtype=np.float64)
    residual += location[matrix.point_steps, None]
    residual[:, 0] -= expansion[matrix.point_steps]
    residual[:, 2] += expansion[matrix.point_steps]
    raw = matrix.mean4[:, None] + residual * matrix.scales[:, None]
    raw = np.maximum(raw, 0.0)
    return np.sort(raw, axis=1).astype(np.float32)


def calibrate_total_quantiles(
    validation: ForecastMatrix,
    residual_quantiles: np.ndarray,
) -> dict[str, float]:
    predictions = np.sort(np.asarray(residual_quantiles, dtype=np.float64), axis=1)
    target = validation.target_total_residual_z.astype(np.float64)
    location = float(np.median(target - predictions[:, 1]))
    shifted = predictions + location
    conformity = np.maximum(shifted[:, 0] - target, target - shifted[:, 2])
    try:
        expansion = float(
            np.quantile(conformity, TARGET_INTERVAL_COVERAGE, method="higher")
        )
    except TypeError:
        expansion = float(
            np.quantile(conformity, TARGET_INTERVAL_COVERAGE, interpolation="higher")
        )
    return {"location": location, "interval_expansion": max(0.0, expansion)}


def apply_total_calibration(
    matrix: ForecastMatrix,
    residual_quantiles: np.ndarray,
    calibration: dict[str, float],
) -> np.ndarray:
    residual = np.sort(np.asarray(residual_quantiles, dtype=np.float64), axis=1)
    residual += calibration["location"]
    residual[:, 0] -= calibration["interval_expansion"]
    residual[:, 2] += calibration["interval_expansion"]
    baseline_total = matrix.mean4.reshape(matrix.n_windows, HORIZON_DAYS).sum(axis=1)
    window_scale = matrix.scales.reshape(matrix.n_windows, HORIZON_DAYS)[:, 0]
    raw = baseline_total[:, None] + (residual * window_scale[:, None] * HORIZON_DAYS)
    return np.sort(np.maximum(raw, 0.0), axis=1).astype(np.float32)


def choose_daily_blend(
    validation: ForecastMatrix,
    model_quantiles: np.ndarray,
) -> float:
    """Choose point-model weight using validation daily MAE only."""

    trend = validation.baselines["damped_trend"].astype(np.float64)
    target = validation.target.astype(np.float64)
    best = (float("inf"), 1.0)
    for weight in np.linspace(0.0, 1.0, 21):
        center = weight * model_quantiles[:, 1] + (1.0 - weight) * trend
        score = float(np.mean(np.abs(center - target)))
        if score < best[0] - 1e-12:
            best = (score, float(weight))
    return best[1]


def blend_daily_quantiles(
    matrix: ForecastMatrix,
    model_quantiles: np.ndarray,
    weight: float,
) -> np.ndarray:
    trend = matrix.baselines["damped_trend"].astype(np.float64)
    model = np.asarray(model_quantiles, dtype=np.float64)
    center = weight * model[:, 1] + (1.0 - weight) * trend
    lower_width = model[:, 1] - model[:, 0]
    upper_width = model[:, 2] - model[:, 1]
    return np.column_stack(
        [
            np.maximum(center - lower_width, 0.0),
            np.maximum(center, 0.0),
            np.maximum(center + upper_width, 0.0),
        ]
    ).astype(np.float32)


def choose_total_blend(
    validation: ForecastMatrix,
    daily_quantiles: np.ndarray,
    total_quantiles: np.ndarray,
) -> float:
    """Choose total-head weight from validation month-total MAE."""

    daily_total = (
        daily_quantiles[:, 1].reshape(validation.n_windows, HORIZON_DAYS).sum(axis=1)
    )
    target_total = validation.target.reshape(validation.n_windows, HORIZON_DAYS).sum(
        axis=1
    )
    best = (float("inf"), 0.0)
    for weight in np.linspace(0.0, 1.0, 21):
        center = weight * total_quantiles[:, 1] + (1.0 - weight) * daily_total
        score = float(np.mean(np.abs(center - target_total)))
        if score < best[0] - 1e-12:
            best = (score, float(weight))
    return best[1]


def reconcile_daily_to_total(
    matrix: ForecastMatrix,
    daily_quantiles: np.ndarray,
    total_quantiles: np.ndarray,
    total_weight: float,
) -> tuple[np.ndarray, np.ndarray]:
    daily = np.asarray(daily_quantiles, dtype=np.float64).reshape(
        matrix.n_windows, HORIZON_DAYS, 3
    )
    daily_sums = daily.sum(axis=1)
    blended_total = (
        total_weight * np.asarray(total_quantiles, dtype=np.float64)
        + (1.0 - total_weight) * daily_sums
    )
    median_delta = blended_total[:, 1] - daily_sums[:, 1]
    daily += median_delta[:, None, None] / HORIZON_DAYS
    daily = np.sort(np.maximum(daily, 0.0), axis=2)
    return daily.reshape(-1, 3).astype(np.float32), np.sort(
        np.maximum(blended_total, 0.0), axis=1
    ).astype(np.float32)


def baseline_metrics(matrix: ForecastMatrix) -> dict[str, dict[str, float | int]]:
    return {
        name: point_metrics(matrix, prediction)
        for name, prediction in matrix.baselines.items()
    }


def best_baseline(
    metrics: dict[str, dict[str, float | int]], key: str
) -> tuple[str, float]:
    name = min(metrics, key=lambda candidate: float(metrics[candidate][key]))
    return name, float(metrics[name][key])


def promotion_decision(
    candidate: dict[str, float | int],
    baselines: dict[str, dict[str, float | int]],
) -> dict[str, Any]:
    daily_name, daily_value = best_baseline(baselines, "daily_macro_mae_kwh")
    total_name, total_value = best_baseline(baselines, "month_total_mae_kwh")
    daily_improvement = (
        100.0 * (daily_value - float(candidate["daily_macro_mae_kwh"])) / daily_value
    )
    total_improvement = (
        100.0 * (total_value - float(candidate["month_total_mae_kwh"])) / total_value
    )
    checks = {
        "daily_mae_improvement": daily_improvement >= MIN_DAILY_MAE_IMPROVEMENT_PERCENT,
        "month_total_mae_improvement": total_improvement
        >= MIN_TOTAL_MAE_IMPROVEMENT_PERCENT,
        "positive_daily_macro_r2": float(candidate["daily_macro_r2"]) >= MIN_MACRO_R2,
        "bounded_daily_bias": abs(float(candidate["daily_macro_bias_kwh"]))
        <= MAX_ABSOLUTE_DAILY_BIAS_KWH,
        "central_80_interval_calibrated": MIN_INTERVAL_COVERAGE_PERCENT
        <= float(candidate["central_80_coverage_percent"])
        <= MAX_INTERVAL_COVERAGE_PERCENT,
    }
    return {
        "promoted": all(checks.values()),
        "checks": checks,
        "daily_comparator": daily_name,
        "daily_comparator_mae_kwh": daily_value,
        "daily_mae_improvement_percent": daily_improvement,
        "month_total_comparator": total_name,
        "month_total_comparator_mae_kwh": total_value,
        "month_total_mae_improvement_percent": total_improvement,
        "thresholds": {
            "minimum_daily_mae_improvement_percent": MIN_DAILY_MAE_IMPROVEMENT_PERCENT,
            "minimum_month_total_mae_improvement_percent": MIN_TOTAL_MAE_IMPROVEMENT_PERCENT,
            "minimum_daily_macro_r2": MIN_MACRO_R2,
            "maximum_absolute_daily_bias_kwh": MAX_ABSOLUTE_DAILY_BIAS_KWH,
            "central_80_coverage_percent_range": [
                MIN_INTERVAL_COVERAGE_PERCENT,
                MAX_INTERVAL_COVERAGE_PERCENT,
            ],
        },
    }


def train_quantile_model(
    train_x: np.ndarray,
    train_y: np.ndarray,
    validation_x: np.ndarray,
    validation_y: np.ndarray,
    *,
    seed: int,
    device: str,
    estimators: int,
    depth: int,
    learning_rate: float,
) -> Any:
    try:
        import xgboost as xgb
    except ImportError as error:
        raise RuntimeError(
            "xgboost>=2.0 is required for the multi-quantile monthly model."
        ) from error

    model = xgb.XGBRegressor(
        objective="reg:quantileerror",
        quantile_alpha=QUANTILES,
        n_estimators=estimators,
        learning_rate=learning_rate,
        max_depth=depth,
        min_child_weight=20,
        subsample=0.85,
        colsample_bytree=0.90,
        reg_alpha=0.02,
        reg_lambda=8.0,
        max_bin=256,
        tree_method="hist",
        device=device,
        eval_metric="quantile",
        early_stopping_rounds=40,
        random_state=seed,
        n_jobs=max(1, min(12, (os_cpu_count() or 4))),
    )
    model.fit(
        train_x,
        train_y,
        eval_set=[(validation_x, validation_y)],
        verbose=25,
    )
    return model


def refit_quantile_model(
    train_x: np.ndarray,
    train_y: np.ndarray,
    *,
    seed: int,
    device: str,
    estimators: int,
    depth: int,
    learning_rate: float,
) -> Any:
    """Refit a frozen design on train+validation without peeking at test."""

    try:
        import xgboost as xgb
    except ImportError as error:
        raise RuntimeError(
            "xgboost>=2.0 is required for the multi-quantile monthly model."
        ) from error

    model = xgb.XGBRegressor(
        objective="reg:quantileerror",
        quantile_alpha=QUANTILES,
        n_estimators=max(1, estimators),
        learning_rate=learning_rate,
        max_depth=depth,
        min_child_weight=20,
        subsample=0.85,
        colsample_bytree=0.90,
        reg_alpha=0.02,
        reg_lambda=8.0,
        max_bin=256,
        tree_method="hist",
        device=device,
        random_state=seed,
        n_jobs=max(1, min(12, (os_cpu_count() or 4))),
    )
    model.fit(train_x, train_y, verbose=False)
    return model


def train_point_model(
    train_x: np.ndarray,
    train_y: np.ndarray,
    validation_x: np.ndarray,
    validation_y: np.ndarray,
    *,
    seed: int,
    device: str,
    estimators: int,
    depth: int,
    learning_rate: float,
) -> Any:
    """Train an MSE center head; quantile loss alone need not maximize R2."""

    try:
        import xgboost as xgb
    except ImportError as error:
        raise RuntimeError("xgboost>=2.0 is required.") from error

    model = xgb.XGBRegressor(
        objective="reg:squarederror",
        n_estimators=estimators,
        learning_rate=learning_rate,
        max_depth=depth,
        min_child_weight=20,
        subsample=0.85,
        colsample_bytree=0.90,
        reg_alpha=0.02,
        reg_lambda=8.0,
        max_bin=256,
        tree_method="hist",
        device=device,
        eval_metric="rmse",
        early_stopping_rounds=40,
        random_state=seed,
        n_jobs=max(1, min(12, (os_cpu_count() or 4))),
    )
    model.fit(
        train_x,
        train_y,
        eval_set=[(validation_x, validation_y)],
        verbose=25,
    )
    return model


def refit_point_model(
    train_x: np.ndarray,
    train_y: np.ndarray,
    *,
    seed: int,
    device: str,
    estimators: int,
    depth: int,
    learning_rate: float,
) -> Any:
    try:
        import xgboost as xgb
    except ImportError as error:
        raise RuntimeError("xgboost>=2.0 is required.") from error

    model = xgb.XGBRegressor(
        objective="reg:squarederror",
        n_estimators=max(1, estimators),
        learning_rate=learning_rate,
        max_depth=depth,
        min_child_weight=20,
        subsample=0.85,
        colsample_bytree=0.90,
        reg_alpha=0.02,
        reg_lambda=8.0,
        max_bin=256,
        tree_method="hist",
        device=device,
        random_state=seed,
        n_jobs=max(1, min(12, (os_cpu_count() or 4))),
    )
    model.fit(train_x, train_y, verbose=False)
    return model


def align_quantiles_to_center(
    residual_quantiles: np.ndarray,
    center: np.ndarray,
    *,
    weight: float = 1.0,
) -> np.ndarray:
    """Preserve learned asymmetric widths while replacing the center head."""

    quantiles = np.sort(np.asarray(residual_quantiles, dtype=np.float32), axis=1)
    center = np.asarray(center, dtype=np.float32).reshape(-1)
    if center.shape[0] != quantiles.shape[0]:
        raise ValueError("Center and quantile predictions must have equal rows.")
    if not 0.0 <= weight <= 1.0:
        raise ValueError("Center weight must be in [0, 1].")
    blended_center = weight * center + (1.0 - weight) * quantiles[:, 1]
    return quantiles + (blended_center - quantiles[:, 1])[:, None]


def os_cpu_count() -> int | None:
    # Kept behind a tiny wrapper to make deterministic tests easy to monkeypatch.
    import os

    return os.cpu_count()


def _predict_quantiles(model: Any, features: np.ndarray) -> np.ndarray:
    prediction = np.asarray(model.predict(features), dtype=np.float32)
    if prediction.ndim == 1:
        prediction = prediction[:, None]
    if prediction.shape != (features.shape[0], len(QUANTILES)):
        raise RuntimeError(
            f"Expected {(features.shape[0], len(QUANTILES))} quantiles, "
            f"received {prediction.shape}."
        )
    return np.sort(prediction, axis=1)


def run_experiment(args: argparse.Namespace) -> dict[str, Any]:
    set_deterministic_seed(args.seed)
    source_root = args.source_root.resolve()
    data_dir = source_root / "data"
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata = json.loads((data_dir / "prepared.json").read_text(encoding="utf-8"))
    values = np.load(data_dir / "daily_raw.npy", mmap_mode="r")
    calendar = np.load(data_dir / "daily_calendar.npy", mmap_mode="r")
    known = np.load(data_dir / "known_households.npy")
    cold = np.load(data_dir / "cold_households.npy")

    if metadata.get("daily_length") != values.shape[1]:
        raise RuntimeError("Prepared metadata and daily array length disagree.")

    train_households = known[: args.max_train_households or len(known)]
    validation_households = known[: args.max_eval_households or len(known)]
    cold_households = cold[: args.max_eval_households or len(cold)]
    train_windows = valid_windows(
        values,
        train_households,
        training_origins(int(metadata["daily_train_end"]), stride=args.train_stride),
    )
    validation_windows = valid_windows(
        values,
        validation_households,
        rolling_origins(
            int(metadata["daily_train_end"]),
            int(metadata["daily_val_end"]),
            requested=args.eval_origins,
        ),
    )
    known_test_windows = valid_windows(
        values,
        validation_households,
        rolling_origins(
            int(metadata["daily_val_end"]),
            int(metadata["daily_length"]),
            requested=args.eval_origins,
        ),
    )
    cold_test_windows = valid_windows(
        values,
        cold_households,
        rolling_origins(
            int(metadata["daily_val_end"]),
            int(metadata["daily_length"]),
            requested=args.eval_origins,
        ),
    )

    print(
        "Windows train/validation/known-test/cold-test:",
        len(train_windows),
        len(validation_windows),
        len(known_test_windows),
        len(cold_test_windows),
        flush=True,
    )
    print("Building causal feature matrices...", flush=True)
    train = build_matrix(values, calendar, train_windows)
    validation = build_matrix(values, calendar, validation_windows)
    known_test = build_matrix(values, calendar, known_test_windows)
    cold_test = build_matrix(values, calendar, cold_test_windows)
    print(
        "Feature shapes:",
        train.point_features.shape,
        train.total_features.shape,
        flush=True,
    )

    started = time.time()
    print("Training daily residual quantile model...", flush=True)
    daily_model = train_quantile_model(
        train.point_features,
        train.target_residual_z,
        validation.point_features,
        validation.target_residual_z,
        seed=args.seed,
        device=args.device,
        estimators=args.daily_estimators,
        depth=args.daily_depth,
        learning_rate=args.learning_rate,
    )
    daily_model_path = output_dir / "daily_quantile_model.ubj"
    daily_model.save_model(daily_model_path)

    print("Training reconciled month-total quantile model...", flush=True)
    total_model = train_quantile_model(
        train.total_features,
        train.target_total_residual_z,
        validation.total_features,
        validation.target_total_residual_z,
        seed=args.seed + 1,
        device=args.device,
        estimators=args.total_estimators,
        depth=args.total_depth,
        learning_rate=args.learning_rate,
    )
    total_model_path = output_dir / "total_quantile_model.ubj"
    total_model.save_model(total_model_path)

    print("Training squared-error daily and month-total center heads...", flush=True)
    daily_center_model = train_point_model(
        train.point_features,
        train.target_residual_z,
        validation.point_features,
        validation.target_residual_z,
        seed=args.seed + 2,
        device=args.device,
        estimators=args.daily_estimators,
        depth=args.daily_depth,
        learning_rate=args.learning_rate,
    )
    total_center_model = train_point_model(
        train.total_features,
        train.target_total_residual_z,
        validation.total_features,
        validation.target_total_residual_z,
        seed=args.seed + 3,
        device=args.device,
        estimators=args.total_estimators,
        depth=args.total_depth,
        learning_rate=args.learning_rate,
    )

    validation_daily_residual = _predict_quantiles(
        daily_model, validation.point_features
    )
    validation_daily_residual = align_quantiles_to_center(
        validation_daily_residual,
        daily_center_model.predict(validation.point_features),
        weight=args.daily_center_weight,
    )
    daily_calibration = calibrate_daily_quantiles(validation, validation_daily_residual)
    validation_daily = apply_daily_calibration(
        validation, validation_daily_residual, daily_calibration
    )
    daily_weight = choose_daily_blend(validation, validation_daily)
    validation_daily = blend_daily_quantiles(validation, validation_daily, daily_weight)

    validation_total_residual = _predict_quantiles(
        total_model, validation.total_features
    )
    validation_total_residual = align_quantiles_to_center(
        validation_total_residual,
        total_center_model.predict(validation.total_features),
        weight=args.total_center_weight,
    )
    total_calibration = calibrate_total_quantiles(validation, validation_total_residual)
    validation_total = apply_total_calibration(
        validation, validation_total_residual, total_calibration
    )
    total_weight = choose_total_blend(validation, validation_daily, validation_total)
    validation_daily, validation_total = reconcile_daily_to_total(
        validation, validation_daily, validation_total, total_weight
    )

    development_models = {
        "daily_best_iteration": int(
            getattr(daily_model, "best_iteration", args.daily_estimators - 1)
        ),
        "total_best_iteration": int(
            getattr(total_model, "best_iteration", args.total_estimators - 1)
        ),
        "daily_center_best_iteration": int(
            getattr(daily_center_model, "best_iteration", args.daily_estimators - 1)
        ),
        "total_center_best_iteration": int(
            getattr(total_center_model, "best_iteration", args.total_estimators - 1)
        ),
    }

    # Once architecture, iteration count, calibration and blend weights are
    # frozen on validation, use all pre-test targets for the final fit.  The
    # chronological test region still remains completely untouched.
    print("Building train+validation refit matrix...", flush=True)
    refit_windows = valid_windows(
        values,
        train_households,
        training_origins(int(metadata["daily_val_end"]), stride=args.train_stride),
    )
    refit = build_matrix(values, calendar, refit_windows)
    print(
        "Refitting frozen daily and month-total designs on",
        len(refit_windows),
        "pre-test windows...",
        flush=True,
    )
    daily_model = refit_quantile_model(
        refit.point_features,
        refit.target_residual_z,
        seed=args.seed,
        device=args.device,
        estimators=development_models["daily_best_iteration"] + 1,
        depth=args.daily_depth,
        learning_rate=args.learning_rate,
    )
    total_model = refit_quantile_model(
        refit.total_features,
        refit.target_total_residual_z,
        seed=args.seed + 1,
        device=args.device,
        estimators=development_models["total_best_iteration"] + 1,
        depth=args.total_depth,
        learning_rate=args.learning_rate,
    )
    daily_center_model = refit_point_model(
        refit.point_features,
        refit.target_residual_z,
        seed=args.seed + 2,
        device=args.device,
        estimators=development_models["daily_center_best_iteration"] + 1,
        depth=args.daily_depth,
        learning_rate=args.learning_rate,
    )
    total_center_model = refit_point_model(
        refit.total_features,
        refit.target_total_residual_z,
        seed=args.seed + 3,
        device=args.device,
        estimators=development_models["total_center_best_iteration"] + 1,
        depth=args.total_depth,
        learning_rate=args.learning_rate,
    )
    daily_model_path = output_dir / "daily_quantile_model.ubj"
    total_model_path = output_dir / "total_quantile_model.ubj"
    daily_center_model_path = output_dir / "daily_center_model.ubj"
    total_center_model_path = output_dir / "total_center_model.ubj"
    daily_model.save_model(daily_model_path)
    total_model.save_model(total_model_path)
    daily_center_model.save_model(daily_center_model_path)
    total_center_model.save_model(total_center_model_path)

    def evaluate_split(matrix: ForecastMatrix) -> dict[str, Any]:
        daily_residual = _predict_quantiles(daily_model, matrix.point_features)
        daily_residual = align_quantiles_to_center(
            daily_residual,
            daily_center_model.predict(matrix.point_features),
            weight=args.daily_center_weight,
        )
        daily = apply_daily_calibration(matrix, daily_residual, daily_calibration)
        daily = blend_daily_quantiles(matrix, daily, daily_weight)
        total_residual = _predict_quantiles(total_model, matrix.total_features)
        total_residual = align_quantiles_to_center(
            total_residual,
            total_center_model.predict(matrix.total_features),
            weight=args.total_center_weight,
        )
        total = apply_total_calibration(matrix, total_residual, total_calibration)
        daily, total = reconcile_daily_to_total(matrix, daily, total, total_weight)
        metrics = point_metrics(matrix, daily[:, 1], daily)
        target_totals = matrix.target.reshape(matrix.n_windows, HORIZON_DAYS).sum(
            axis=1
        )
        metrics.update(
            {
                "month_total_central_80_coverage_percent": float(
                    100.0
                    * np.mean(
                        (target_totals >= total[:, 0]) & (target_totals <= total[:, 2])
                    )
                ),
                "month_total_central_80_mean_width_kwh": float(
                    np.mean(total[:, 2] - total[:, 0])
                ),
            }
        )
        return {
            "candidate": metrics,
            "baselines": baseline_metrics(matrix),
        }

    validation_candidate = point_metrics(
        validation, validation_daily[:, 1], validation_daily
    )
    validation_target_totals = validation.target.reshape(
        validation.n_windows, HORIZON_DAYS
    ).sum(axis=1)
    validation_candidate.update(
        {
            "month_total_central_80_coverage_percent": float(
                100.0
                * np.mean(
                    (validation_target_totals >= validation_total[:, 0])
                    & (validation_target_totals <= validation_total[:, 2])
                )
            ),
            "month_total_central_80_mean_width_kwh": float(
                np.mean(validation_total[:, 2] - validation_total[:, 0])
            ),
        }
    )
    evaluation = {
        "validation_known_development_model": {
            "candidate": validation_candidate,
            "baselines": baseline_metrics(validation),
        },
        "test_known": evaluate_split(known_test),
        "test_cold_start": evaluate_split(cold_test),
    }
    decision = promotion_decision(
        evaluation["test_cold_start"]["candidate"],
        evaluation["test_cold_start"]["baselines"],
    )

    result: dict[str, Any] = {
        "status": "success",
        "experiment": "month_strong_v1",
        "promoted": decision["promoted"],
        "promotion": decision,
        "protocol": {
            "resolution": "daily",
            "lookback_days": LOOKBACK_DAYS,
            "horizon_days": HORIZON_DAYS,
            "quantiles": QUANTILES.tolist(),
            "dataset": "Low Carbon London smart-meter households",
            "dataset_year": metadata.get("year"),
            "known_households_available": int(len(known)),
            "cold_start_households_available": int(len(cold)),
            "train_households": int(len(train_households)),
            "validation_households": int(len(validation_households)),
            "cold_start_test_households": int(len(cold_households)),
            "train_stride_days": args.train_stride,
            "evaluation_origins_requested": args.eval_origins,
            "normalization": "per-window rolling 90-day mean and standard deviation",
            "daily_target": "residual from trailing four-week weekday profile",
            "total_target": "30-day-total residual from trailing four-week weekday profile",
            "test_policy": "chronological rolling origins; cold households excluded from training",
            "daily_mse_center_weight": args.daily_center_weight,
            "month_total_mse_center_weight": args.total_center_weight,
        },
        "models": {
            "daily": {
                "kind": "XGBoost multi-quantile residual model",
                "path": daily_model_path.name,
                "sha256": sha256(daily_model_path),
                "bytes": daily_model_path.stat().st_size,
                "best_iteration": getattr(daily_model, "best_iteration", None),
                "development_best_iteration": development_models[
                    "daily_best_iteration"
                ],
            },
            "month_total": {
                "kind": "XGBoost multi-quantile residual model",
                "path": total_model_path.name,
                "sha256": sha256(total_model_path),
                "bytes": total_model_path.stat().st_size,
                "best_iteration": getattr(total_model, "best_iteration", None),
                "development_best_iteration": development_models[
                    "total_best_iteration"
                ],
            },
            "daily_center": {
                "kind": "XGBoost squared-error residual center model",
                "path": daily_center_model_path.name,
                "sha256": sha256(daily_center_model_path),
                "bytes": daily_center_model_path.stat().st_size,
                "development_best_iteration": development_models[
                    "daily_center_best_iteration"
                ],
            },
            "month_total_center": {
                "kind": "XGBoost squared-error residual center model",
                "path": total_center_model_path.name,
                "sha256": sha256(total_center_model_path),
                "bytes": total_center_model_path.stat().st_size,
                "development_best_iteration": development_models[
                    "total_center_best_iteration"
                ],
            },
        },
        "calibration": {
            "daily": daily_calibration,
            "month_total": total_calibration,
            "daily_model_weight": daily_weight,
            "month_total_model_weight": total_weight,
        },
        "windows": {
            "train": len(train_windows),
            "validation": len(validation_windows),
            "train_plus_validation_refit": len(refit_windows),
            "test_known": len(known_test_windows),
            "test_cold_start": len(cold_test_windows),
        },
        "feature_dimensions": {
            "daily_point": int(train.point_features.shape[1]),
            "month_total": int(train.total_features.shape[1]),
        },
        "evaluation": evaluation,
        "training_seconds": time.time() - started,
        "seed": args.seed,
        "device": args.device,
        "limitations": [
            "The frozen source contains one London calendar year, which limits annual-seasonality evidence.",
            "Cold-start evaluation on London households does not establish Moroccan transfer.",
            "Overlapping rolling windows are not statistically independent.",
            "The candidate remains research-only unless every predeclared promotion gate passes.",
        ],
    }
    atomic_json(output_dir / "metrics.json", result)
    atomic_json(
        output_dir / "calibration.json",
        {
            "daily": daily_calibration,
            "month_total": total_calibration,
            "daily_model_weight": daily_weight,
            "month_total_model_weight": total_weight,
        },
    )
    print(json.dumps(result["promotion"], indent=2), flush=True)
    print(f"Metrics written to {output_dir / 'metrics.json'}", flush=True)
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    repository = Path(__file__).resolve().parents[1]
    default_source = (
        repository / "models" / "lcl_global_forecasting" / "full_selected_v1"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=default_source)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=(
            repository
            / "models"
            / "lcl_global_forecasting"
            / "month_strong_v1"
            / "runs"
            / f"seed_{DEFAULT_SEED}"
        ),
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--train-stride", type=int, default=4)
    parser.add_argument("--eval-origins", type=int, default=24)
    parser.add_argument("--daily-estimators", type=int, default=500)
    parser.add_argument("--total-estimators", type=int, default=500)
    parser.add_argument("--daily-depth", type=int, default=7)
    parser.add_argument("--total-depth", type=int, default=6)
    parser.add_argument("--learning-rate", type=float, default=0.04)
    parser.add_argument(
        "--daily-center-weight",
        type=float,
        default=0.0,
        help="Optional MSE-center weight in [0, 1]; zero preserves the quantile median.",
    )
    parser.add_argument(
        "--total-center-weight",
        type=float,
        default=0.0,
        help="Optional MSE-center weight in [0, 1]; zero preserves the quantile median.",
    )
    parser.add_argument("--max-train-households", type=int, default=None)
    parser.add_argument("--max-eval-households", type=int, default=None)
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run a small end-to-end pipeline validation, not a reportable experiment.",
    )
    args = parser.parse_args(argv)
    for name in ("daily_center_weight", "total_center_weight"):
        if not 0.0 <= getattr(args, name) <= 1.0:
            parser.error(f"--{name.replace('_', '-')} must be in [0, 1]")
    if args.smoke:
        args.train_stride = max(args.train_stride, 20)
        args.eval_origins = min(args.eval_origins, 2)
        args.daily_estimators = min(args.daily_estimators, 8)
        args.total_estimators = min(args.total_estimators, 8)
        args.max_train_households = min(args.max_train_households or 80, 80)
        args.max_eval_households = min(args.max_eval_households or 40, 40)
    return args


if __name__ == "__main__":
    run_experiment(parse_args())
