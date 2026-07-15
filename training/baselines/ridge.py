"""training/baselines/ridge.py — Ridge Regression baseline.

Ridge natively supports multi-output regression (unlike XGBoost/RF which need
MultiOutputRegressor). Using it directly is orders of magnitude faster since
sklearn solves all outputs in a single Cholesky factorization.
"""
import numpy as np
from sklearn.linear_model import Ridge
from .base import ForecastModel


class RidgeModel(ForecastModel):
    """
    Ridge Regression (L2-regularised) over flattened windows.

    Uses Ridge directly (not wrapped in MultiOutputRegressor) so all output
    dimensions are solved simultaneously — ~100x faster for 168 outputs.
    """

    name = "ridge"
    model_type = "classical"
    supports_feature_importance = True   # via coef_
    supports_gpu = False

    def __init__(self, alpha: float = 1.0):
        self._ridge = Ridge(alpha=alpha)
        self.horizon = None
        self.n_targets = None

    def _flatten(self, X: np.ndarray) -> np.ndarray:
        return X.reshape(X.shape[0], -1)

    def fit(self, X: np.ndarray, Y: np.ndarray) -> None:
        """
        X : (n_samples, lookback, n_features)
        Y : (n_samples, horizon, n_targets)
        """
        self.horizon = Y.shape[1]
        self.n_targets = Y.shape[2]
        X_flat = self._flatten(X)
        Y_flat = Y.reshape(len(Y), -1)     # (n_samples, horizon * n_targets)
        self._ridge.fit(X_flat, Y_flat)

    def predict(self, X: np.ndarray) -> np.ndarray:
        X_flat = self._flatten(X)
        Y_flat = self._ridge.predict(X_flat)
        return Y_flat.reshape(len(X), self.horizon, self.n_targets)

    def save(self, path) -> None:
        import pickle
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, path):
        import pickle
        with open(path, "rb") as f:
            return pickle.load(f)

    def get_feature_importance(self, feature_names=None):
        """Mean absolute coefficient across all output dimensions."""
        if not hasattr(self._ridge, "coef_"):
            return None
        coef = self._ridge.coef_    # (horizon * n_targets, n_flat_features)
        return np.abs(coef).mean(axis=0)
