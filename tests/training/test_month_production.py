import json
from pathlib import Path

import numpy as np
import pytest

from training.month_production import (
    HORIZON,
    Window,
    apply_conformal,
    model_context,
    seasonal_baselines,
)
from training.month_production_inference import MonthProductionForecaster

REPOSITORY = Path(__file__).resolve().parents[2]
RELEASE = (
    REPOSITORY / "models" / "lcl_global_forecasting" / "month_production_v3" / "release"
)


def test_short_context_is_causally_left_padded() -> None:
    history = np.arange(300, dtype=np.float32)
    context = model_context(history)
    assert context.shape == (365,)
    assert np.all(context[:65] == 0)
    assert np.array_equal(context[-300:], history)


def test_too_short_context_is_rejected() -> None:
    with pytest.raises(ValueError, match="At least 270"):
        model_context(np.arange(269, dtype=np.float32))


def test_baselines_are_nonnegative_and_month_length() -> None:
    candidates = seasonal_baselines(np.arange(365, dtype=np.float32))
    assert candidates
    assert all(value.shape == (HORIZON,) for value in candidates.values())
    assert all(np.min(value) >= 0 for value in candidates.values())


def test_scaled_conformal_keeps_ordered_nonnegative_quantiles() -> None:
    context = np.linspace(10, 100, 365, dtype=np.float32)
    window = Window("test", np.datetime64("2026-01-01"), context, np.ones(30))
    prediction = np.tile(np.array([[[5.0, 10.0, 15.0]]]), (1, 30, 1))
    calibrated = apply_conformal(prediction, (-0.2, 0.9), [window])
    assert np.min(calibrated) >= 0
    assert np.all(calibrated[:, :, 0] <= calibrated[:, :, 1])
    assert np.all(calibrated[:, :, 1] <= calibrated[:, :, 2])


def test_release_manifest_and_adapter_are_consistent() -> None:
    manifest = json.loads((RELEASE / "manifest.json").read_text(encoding="utf-8"))
    adapter = RELEASE / manifest["adapter"]["filename"]
    assert manifest["status"] == "production_eligible"
    assert manifest["contract"]["horizon_days"] == 30
    assert len(manifest["base_model"]["revision"]) == 40
    assert len(manifest["base_model"]["model_sha256"]) == 64
    assert adapter.stat().st_size == manifest["adapter"]["bytes"]
    assert MonthProductionForecaster._sha256(adapter) == manifest["adapter"]["sha256"]
    assert (
        MonthProductionForecaster._sha256(
            RELEASE / manifest["reproducibility"]["selection_file"]
        )
        == manifest["reproducibility"]["selection_sha256"]
    )
    assert (
        MonthProductionForecaster._sha256(
            RELEASE / manifest["reproducibility"]["audit_file"]
        )
        == manifest["reproducibility"]["audit_sha256"]
    )
