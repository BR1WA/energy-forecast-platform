"""training/baselines/_sklearn_base.py — Mixin for all sklearn-based flat-window models."""
from __future__ import annotations

import numpy as np
from typing import Optional
from .base import ForecastModel


class SklearnForecastModel(ForecastModel):
    """
    Mixin that handles flattening (lookback, n_features) -> (lookback * n_features,)
    and reshaping predictions back to (n_samples, horizon, n_targets).

    Concrete subclasses only need to set `self._model` and define `name`.
    """

    model_type = "classical"
    supports_feature_importance = False
    supports_gpu = False

    def _flatten(self, X: np.ndarray) -> np.ndarray:
        """(n_samples, lookback, n_features) -> (n_samples, lookback * n_features)"""
        n_samples = X.shape[0]
        return X.reshape(n_samples, -1)

    def fit(self, X_train: np.ndarray, Y_train: np.ndarray, X_val: np.ndarray = None, Y_val: np.ndarray = None) -> None:
        """
        X : (n_samples, lookback, n_features)
        Y : (n_samples, horizon, n_targets)
        """
        self.horizon = Y_train.shape[1]
        self.n_targets = Y_train.shape[2]
        # Ignore X_val and Y_val for classical models
        self._model.fit(self._flatten(X_train), Y_train.reshape(len(Y_train), -1))

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        X : (n_samples, lookback, n_features)
        Returns (n_samples, horizon, n_targets)
        """
        X_flat = self._flatten(X)
        Y_flat = self._model.predict(X_flat)
        return Y_flat.reshape(len(X), self.horizon, self.n_targets)

    def get_feature_importance(
        self, feature_names: Optional[list] = None
    ) -> Optional[np.ndarray]:
        """
        Delegate to the underlying estimator if it exposes feature_importances_
        (tree models) or coef_ (linear models).
        For MultiOutputRegressor, averages across all sub-estimators.
        """
        estimator = self._model
        # MultiOutputRegressor wraps individual estimators
        if hasattr(estimator, "estimators_"):
            sub = estimator.estimators_[0]
            if hasattr(sub, "feature_importances_"):
                return np.mean(
                    [e.feature_importances_ for e in estimator.estimators_], axis=0
                )
            if hasattr(sub, "coef_"):
                # Linear models: mean absolute coefficient across all output estimators
                return np.abs(
                    np.mean([e.coef_ for e in estimator.estimators_], axis=0)
                )
        # Direct multi-output model (e.g. Ridge without MultiOutputRegressor)
        if hasattr(estimator, "feature_importances_"):
            return estimator.feature_importances_
        if hasattr(estimator, "coef_"):
            coef = estimator.coef_
            if coef.ndim > 1:
                return np.abs(coef).mean(axis=0)
            return np.abs(coef)
        return None
