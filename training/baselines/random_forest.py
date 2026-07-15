"""training/baselines/random_forest.py — Random Forest baseline.

RandomForestRegressor natively supports multi-output regression by building
trees that predict all outputs simultaneously (one split per node covers all
outputs). This is orders of magnitude faster than MultiOutputRegressor, which
fits one complete forest per output dimension.
"""
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from .base import ForecastModel


class RandomForestModel(ForecastModel):
    """
    Random Forest over flattened windows (native multi-output).

    Defaults are set for benchmarking quality (unconstrained depth, 200 trees).
    Hyperparameter tuning comes in Phase 3.3.
    """

    name = "random_forest"
    model_type = "tree"
    supports_feature_importance = True
    supports_gpu = False

    def __init__(
        self,
        n_estimators: int = 200,
        max_depth=None,            # Uncapped — let the forest learn
        min_samples_leaf: int = 2,
        random_state: int = 42,
        n_jobs: int = -1,
        **kwargs
    ):
        self._rf = RandomForestRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_leaf=min_samples_leaf,
            random_state=random_state,
            n_jobs=n_jobs,
            **kwargs
        )
        self.horizon = None
        self.n_targets = None

    def _flatten(self, X: np.ndarray) -> np.ndarray:
        return X.reshape(X.shape[0], -1)

    def fit(self, X_train: np.ndarray, Y_train: np.ndarray, X_val: np.ndarray = None, Y_val: np.ndarray = None) -> None:
        """
        X_train : (n_samples, lookback, n_features)
        Y_train : (n_samples, horizon, n_targets)
        """
        self.horizon = Y_train.shape[1]
        self.n_targets = Y_train.shape[2]
        self._rf.fit(self._flatten(X_train), Y_train.reshape(len(Y_train), -1))

    def predict(self, X: np.ndarray) -> np.ndarray:
        Y_flat = self._rf.predict(self._flatten(X))
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

    def get_feature_importance(self, feature_names=None) -> np.ndarray:
        """Return mean feature importances from the native RF estimator."""
        if not hasattr(self._rf, "feature_importances_"):
            return None
        return self._rf.feature_importances_
