"""
training/utils/metrics.py

Unified evaluation metrics for all forecasting models.
Every experiment reports this same set so comparisons are apples-to-apples.
"""
from __future__ import annotations

import time
from typing import Dict, Optional
import numpy as np


def calculate_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> Dict[str, float]:
    """
    Calculate standard time-series forecasting metrics.

    Parameters
    ----------
    y_true : (n_samples, horizon, n_targets)  or  (horizon, n_targets)
    y_pred : same shape as y_true

    Returns
    -------
    dict with keys:
        mae, rmse, mape, smape, r2,
        median_ae, max_ae
    """
    if y_true.shape != y_pred.shape:
        raise ValueError(
            f"Shape mismatch: y_true {y_true.shape} vs y_pred {y_pred.shape}"
        )

    eps = 1e-8
    err = y_pred - y_true
    abs_err = np.abs(err)

    mae    = float(np.mean(abs_err))
    rmse   = float(np.sqrt(np.mean(np.square(err))))

    # MAPE: mask near-zero ground truth values to prevent division explosion
    nonzero_mask = np.abs(y_true) > 0.01  # threshold: 10W for energy data
    if nonzero_mask.any():
        mape = float(np.mean(abs_err[nonzero_mask] / np.abs(y_true[nonzero_mask])) * 100)
    else:
        mape = float("nan")

    smape  = float(
        np.mean(
            2.0 * abs_err / (np.abs(y_true) + np.abs(y_pred) + eps)
        ) * 100
    )

    ss_res = np.sum(np.square(err))
    ss_tot = np.sum(np.square(y_true - np.mean(y_true)))
    r2     = float(1.0 - ss_res / (ss_tot + eps))

    median_ae = float(np.median(abs_err))
    max_ae    = float(np.max(abs_err))   # worst-case miss — critical for energy utilities

    return {
        "mae":       mae,
        "rmse":      rmse,
        "mape":      mape,
        "smape":     smape,
        "r2":        r2,
        "median_ae": median_ae,
        "max_ae":    max_ae,
    }


def measure_inference_time(
    model,
    X: np.ndarray,
    n_repeats: int = 5,
) -> float:
    """
    Measure median inference time in milliseconds per sample.

    Parameters
    ----------
    model     : any object with a `.predict(X)` method
    X         : input array (n_samples, ...)
    n_repeats : number of timed repetitions (median used for stability)

    Returns
    -------
    float — ms per sample
    """
    times = []
    for _ in range(n_repeats):
        t0 = time.perf_counter()
        model.predict(X)
        times.append(time.perf_counter() - t0)
    total_seconds = float(np.median(times))
    return (total_seconds / len(X)) * 1000   # ms / sample


def model_size_mb(path) -> Optional[float]:
    """Return the size of a saved model artifact in MB, or None if path missing."""
    import os
    if not os.path.exists(path):
        return None
    return os.path.getsize(path) / (1024 ** 2)
