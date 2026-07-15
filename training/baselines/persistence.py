"""training/baselines/persistence.py — Naive persistence (last-value-repeated) baseline."""
from __future__ import annotations
import numpy as np
from .base import ForecastModel


class PersistenceModel(ForecastModel):
    """
    Persistence baseline: repeats the last observed value across the entire horizon.

    For each test window, prediction[t+k] = X[-1] for all k in [1, horizon].
    """

    name = "persistence"
    model_type = "classical"
    supports_feature_importance = False
    supports_gpu = False

    def __init__(self, target_col_idx: list[int] = None, **kwargs):
        """
        target_col_idx: List of feature indices that correspond to the targets.
        If None, assumes the first N features are the targets (where N = n_targets).
        """
        self.target_col_idx = target_col_idx

    def fit(self, X_train: np.ndarray, Y_train: np.ndarray, X_val: np.ndarray = None, Y_val: np.ndarray = None) -> None:
        self.horizon = Y_train.shape[1]
        self.n_targets = Y_train.shape[2]

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Returns the last observed step repeated for the full horizon.

        Parameters
        ----------
        X : (n_samples, lookback, n_features)

        Returns
        -------
        (n_samples, horizon, n_targets)
        """
        # Take the last time step for target columns only
        last_step = X[:, -1, :self.n_targets]        # (n_samples, n_targets)
        return np.stack([last_step] * self.horizon, axis=1)   # (n_samples, horizon, n_targets)
