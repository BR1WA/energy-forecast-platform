from __future__ import annotations

import numpy as np
import pytest

from training.month_strong import (
    HORIZON_DAYS,
    LOOKBACK_DAYS,
    _window_components,
    align_quantiles_to_center,
    promotion_decision,
    reconcile_daily_to_total,
    rolling_origins,
)


def test_rolling_origins_stay_inside_target_segment() -> None:
    origins = rolling_origins(255, 292, requested=24)

    assert origins.tolist() == list(range(255, 263))
    assert origins.min() >= 255
    assert origins.max() + HORIZON_DAYS <= 292


def test_features_do_not_read_future_target_values() -> None:
    origin = LOOKBACK_DAYS
    length = origin + HORIZON_DAYS
    history = np.linspace(3.0, 9.0, LOOKBACK_DAYS, dtype=np.float32)
    first = np.concatenate(
        [history, np.linspace(4.0, 7.0, HORIZON_DAYS, dtype=np.float32)]
    )
    second = first.copy()
    second[origin:] += 100.0
    calendar = np.zeros((length, 9), dtype=np.float32)

    first_components = _window_components(first, calendar, origin)
    second_components = _window_components(second, calendar, origin)

    np.testing.assert_array_equal(
        first_components["point_features"],
        second_components["point_features"],
    )
    np.testing.assert_array_equal(
        first_components["total_features"],
        second_components["total_features"],
    )
    np.testing.assert_array_equal(
        first_components["damped_trend"],
        second_components["damped_trend"],
    )
    assert not np.array_equal(first_components["target"], second_components["target"])


def test_center_alignment_preserves_quantile_widths() -> None:
    quantiles = np.asarray([[1.0, 2.0, 5.0], [3.0, 4.0, 6.0]], dtype=np.float32)
    center = np.asarray([4.0, 8.0], dtype=np.float32)

    aligned = align_quantiles_to_center(quantiles, center, weight=0.5)

    np.testing.assert_allclose(aligned[:, 1], [3.0, 6.0])
    np.testing.assert_allclose(aligned[:, 1] - aligned[:, 0], [1.0, 1.0])
    np.testing.assert_allclose(aligned[:, 2] - aligned[:, 1], [3.0, 2.0])
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        align_quantiles_to_center(quantiles, center, weight=1.1)


def test_reconciliation_makes_daily_medians_sum_to_total() -> None:
    class Matrix:
        n_windows = 2

    daily = np.tile(
        np.asarray([[1.0, 2.0, 3.0]], dtype=np.float32),
        (2 * HORIZON_DAYS, 1),
    )
    totals = np.asarray([[80.0, 90.0, 100.0], [50.0, 60.0, 70.0]])

    reconciled, reconciled_totals = reconcile_daily_to_total(
        Matrix(), daily, totals, 1.0
    )

    daily_median_totals = reconciled[:, 1].reshape(2, HORIZON_DAYS).sum(axis=1)
    np.testing.assert_allclose(daily_median_totals, reconciled_totals[:, 1])
    np.testing.assert_allclose(daily_median_totals, [90.0, 60.0])


def test_promotion_requires_every_predeclared_gate() -> None:
    candidate = {
        "daily_macro_mae_kwh": 9.0,
        "month_total_mae_kwh": 90.0,
        "daily_macro_r2": 0.1,
        "daily_macro_bias_kwh": 0.1,
        "central_80_coverage_percent": 80.0,
    }
    baseline = {
        "seasonal": {
            "daily_macro_mae_kwh": 10.0,
            "month_total_mae_kwh": 100.0,
        }
    }

    accepted = promotion_decision(candidate, baseline)
    assert accepted["promoted"] is True

    candidate["daily_macro_r2"] = -0.01
    rejected = promotion_decision(candidate, baseline)
    assert rejected["promoted"] is False
    assert rejected["checks"]["positive_daily_macro_r2"] is False
