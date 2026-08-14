from __future__ import annotations

import numpy as np

from training.month_foundation import (
    calibrate_intervals,
    quantiles_from_center,
    reconcile,
)
from training.month_serious import (
    HORIZON_DAYS,
    LOOKBACK_DAYS,
    _window_components,
    causal_interpolate,
    maximum_missing_run,
)


def _calendar(days: int) -> np.ndarray:
    index = np.arange(days)
    weekday = index % 7
    year_day = index % 365
    return np.column_stack(
        [
            np.sin(2 * np.pi * weekday / 7),
            np.cos(2 * np.pi * weekday / 7),
            np.sin(2 * np.pi * year_day / 365),
            np.cos(2 * np.pi * year_day / 365),
            (weekday < 5).astype(float),
            np.zeros(days),
            np.zeros(days),
            np.zeros(days),
        ]
    ).astype(np.float32)


def test_missing_run_and_causal_interpolation() -> None:
    history = np.asarray([1.0, np.nan, np.nan, 4.0, np.nan], dtype=np.float32)
    assert maximum_missing_run(history) == 2
    np.testing.assert_allclose(causal_interpolate(history), [1, 2, 3, 4, 4])


def test_features_never_use_realized_future_weather() -> None:
    total_days = LOOKBACK_DAYS + HORIZON_DAYS + 5
    origin = LOOKBACK_DAYS
    rng = np.random.default_rng(7)
    row = (12.0 + rng.normal(0, 1, total_days)).astype(np.float32)
    dates = np.arange(
        np.datetime64("2012-01-01"),
        np.datetime64("2012-01-01") + total_days,
    )
    actual = rng.normal(size=(total_days, 8)).astype(np.float32)
    climate = rng.normal(size=(total_days, 8)).astype(np.float32)
    calendar = _calendar(total_days)

    first = _window_components(row, dates, actual, climate, calendar, origin)
    changed = actual.copy()
    changed[origin:] += 1_000_000.0
    second = _window_components(row, dates, changed, climate, calendar, origin)

    np.testing.assert_array_equal(first["point_features"], second["point_features"])
    np.testing.assert_array_equal(first["total_features"], second["total_features"])
    for name in first["baselines"]:
        np.testing.assert_array_equal(
            first["baselines"][name], second["baselines"][name]
        )


def test_features_use_future_climatology_not_future_actual_weather() -> None:
    total_days = LOOKBACK_DAYS + HORIZON_DAYS + 5
    origin = LOOKBACK_DAYS
    rng = np.random.default_rng(9)
    row = (10.0 + rng.normal(0, 1, total_days)).astype(np.float32)
    dates = np.arange(
        np.datetime64("2012-01-01"),
        np.datetime64("2012-01-01") + total_days,
    )
    actual = rng.normal(size=(total_days, 8)).astype(np.float32)
    climate = rng.normal(size=(total_days, 8)).astype(np.float32)
    calendar = _calendar(total_days)

    first = _window_components(row, dates, actual, climate, calendar, origin)
    changed = climate.copy()
    changed[origin : origin + HORIZON_DAYS, 0] += 10.0
    second = _window_components(row, dates, actual, changed, calendar, origin)

    assert not np.array_equal(first["point_features"], second["point_features"])
    assert not np.array_equal(first["total_features"], second["total_features"])


def test_reconciliation_preserves_selected_total() -> None:
    daily = np.arange(1, 1 + 2 * HORIZON_DAYS, dtype=np.float32).reshape(
        2, HORIZON_DAYS
    )
    independent_total = daily.sum(axis=1) + np.asarray([30.0, -60.0])
    reconciled, total = reconcile(daily, independent_total, 0.75)
    np.testing.assert_allclose(reconciled.sum(axis=1), total, rtol=0, atol=1e-3)


def test_conformal_interval_expansion_hits_validation_target() -> None:
    rng = np.random.default_rng(12)
    center = np.full((200, HORIZON_DAYS), 5.0, dtype=np.float32)
    target = (center + rng.normal(size=center.shape)).astype(np.float32)
    raw = np.stack([center - 0.25, center, center + 0.25], axis=2)
    expansion = calibrate_intervals(target, center, raw)
    calibrated = quantiles_from_center(center, raw, expansion)
    coverage = np.mean(
        (target >= calibrated[:, :, 0]) & (target <= calibrated[:, :, 2])
    )
    assert 0.79 <= coverage <= 0.83
