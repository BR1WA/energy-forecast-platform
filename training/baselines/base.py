"""
training/baselines/base.py

Abstract base class for all forecast models — baselines and deep learning alike.
Every model in this project implements this interface so train.py stays generic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
import numpy as np


class ForecastModel(ABC):
    """
    Unified interface for all forecasting models.

    Class Attributes
    ----------------
    name            : str  — unique identifier used in CLI and directory paths.
    model_type      : str  — one of 'classical', 'tree', 'deep_learning'.
    supports_feature_importance : bool
    supports_gpu    : bool
    """

    name: str = "base"
    model_type: str = "classical"
    supports_feature_importance: bool = False
    supports_gpu: bool = False

    @abstractmethod
    def fit(self, X_train: np.ndarray, Y_train: np.ndarray, X_val: np.ndarray = None, Y_val: np.ndarray = None) -> None:
        """
        Train the model.
        X_train: (n_samples, lookback, n_features)
        Y_train: (n_samples, horizon, n_targets)
        X_val, Y_val: optional validation sets for deep learning early stopping.
        """
        ...

    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Generate predictions.

        Parameters
        ----------
        X : np.ndarray  shape (n_samples, lookback, n_features)

        Returns
        -------
        np.ndarray  shape (n_samples, horizon, n_targets)
        """
        ...

    def save(self, path: Path) -> None:
        """Serialize the model to disk. Override for custom logic."""
        import pickle
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, path: Path) -> "ForecastModel":
        """Deserialize from disk."""
        import pickle
        with open(path, "rb") as f:
            return pickle.load(f)

    def get_feature_importance(
        self, feature_names: Optional[list] = None
    ) -> Optional[np.ndarray]:
        """
        Return feature importances if supported.

        Returns
        -------
        np.ndarray of shape (n_features,) or None
        """
        return None
