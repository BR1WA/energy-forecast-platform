"""training/baselines/seasonal_naive.py — Seasonal Naive baseline."""
from __future__ import annotations
import numpy as np
from .base import ForecastModel


class SeasonalNaiveModel(ForecastModel):
    """
    Seasonal Naive baseline: predicts the corresponding values from exactly
    one season (period) ago in the lookback window.

    For hourly energy data, season = 168 (one week).
    If the lookback is shorter than the season, falls back to persistence.
    """

    name = "seasonal_naive"
    model_type = "classical"
    supports_feature_importance = False
    supports_gpu = False

    def __init__(self, season: int = 168, target_col_idx: list[int] = None, **kwargs):
        """
        season: The seasonality period (e.g., 168 for weekly with hourly data).
        target_col_idx: Which feature columns correspond to the targets.
        """
        self.season = season
        self.target_col_idx = target_col_idx

    def fit(self, X_train: np.ndarray, Y_train: np.ndarray, X_val: np.ndarray = None, Y_val: np.ndarray = None) -> None:
        self.horizon = Y_train.shape[1]
        self.n_targets = Y_train.shape[2]
        self.horizon = Y_train.shape[1]
        self.lookback = X_train.shape[1]

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict using the seasonal lag.

        Parameters
        ----------
        X : (n_samples, lookback, n_features)

        Returns
        -------
        (n_samples, horizon, n_targets)
        """
        n_samples, lookback, n_features = X.shape
        preds = np.zeros((n_samples, self.horizon, self.n_targets), dtype=np.float32)

        for h in range(self.horizon):
            # Look back by one season relative to the current forecast step
            lag_idx = lookback - self.season + h
            if lag_idx < 0:
                # Fallback: use the last available step
                lag_idx = lookback - 1
            # Clamp to valid range
            lag_idx = min(max(lag_idx, 0), lookback - 1)
            preds[:, h, :] = X[:, lag_idx, :self.n_targets]

        return preds
