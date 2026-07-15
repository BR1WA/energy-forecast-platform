"""training/baselines/linear.py — Linear Regression baseline.

LinearRegression natively supports multi-output (a single least-squares solve
over all outputs). No MultiOutputRegressor wrapper needed — much faster.
"""
import numpy as np
from sklearn.linear_model import LinearRegression
from .base import ForecastModel


class LinearModel(ForecastModel):
    """Linear Regression over flattened windows (native multi-output)."""

    name = "linear"
    model_type = "classical"
    supports_feature_importance = True   # via coef_
    supports_gpu = False

    def __init__(self):
        self._lr = LinearRegression(n_jobs=-1)
        self.horizon = None
        self.n_targets = None

    def _flatten(self, X: np.ndarray) -> np.ndarray:
        return X.reshape(X.shape[0], -1)

    def fit(self, X: np.ndarray, Y: np.ndarray) -> None:
        self.horizon = Y.shape[1]
        self.n_targets = Y.shape[2]
        self._lr.fit(self._flatten(X), Y.reshape(len(Y), -1))

    def predict(self, X: np.ndarray) -> np.ndarray:
        Y_flat = self._lr.predict(self._flatten(X))
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
        if not hasattr(self._lr, "coef_"):
            return None
        return np.abs(self._lr.coef_).mean(axis=0)
