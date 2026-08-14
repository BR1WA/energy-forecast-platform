from __future__ import annotations

import numpy as np

from training.hourly_foundation_challenger import (
    apply_conformal,
    baseline_candidates,
    conformal_offsets,
    fixed_origins,
    point_metrics,
)


def test_hourly_baselines_are_causal_and_have_requested_horizon():
    context = np.arange(672, dtype=np.float32)
    baselines = baseline_candidates(context, 168)
    assert set(baselines) == {
        "last_week_repeat",
        "last_day_repeat",
        "same_hour_four_week_median",
    }
    assert all(values.shape == (168,) for values in baselines.values())
    assert np.array_equal(baselines["last_week_repeat"], context[-168:])


def test_fixed_origins_never_cross_the_declared_split_end():
    origins = fixed_origins(6132, 7008, 168, 6)
    assert origins[0] == 6132
    assert origins[-1] + 168 == 7008


def test_conformal_calibration_preserves_order_and_metrics_are_finite():
    contexts = np.tile(np.linspace(1, 10, 672, dtype=np.float32), (2, 1))
    targets = np.tile(np.linspace(10, 12, 24, dtype=np.float32), (2, 1))
    prediction = np.stack([targets - 0.5, targets, targets + 0.5], axis=2).astype(
        np.float32
    )
    offsets = conformal_offsets(targets, prediction, contexts)
    calibrated = apply_conformal(prediction, offsets, contexts)
    assert np.all(calibrated[:, :, 0] <= calibrated[:, :, 1])
    assert np.all(calibrated[:, :, 1] <= calibrated[:, :, 2])
    result = point_metrics(targets, calibrated, np.asarray([1, 2]))
    assert result["macro_mae_kwh"] == 0
    assert np.isfinite(result["central_80_coverage_percent"])
