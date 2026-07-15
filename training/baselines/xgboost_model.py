"""training/baselines/xgboost_model.py — XGBoost baseline.

XGBoost >= 2.0 supports native multi-output regression via multi_strategy.
This avoids MultiOutputRegressor (which fits one model per output) and is
orders of magnitude faster for horizon*n_targets outputs.
"""
from __future__ import annotations
import numpy as np
from .base import ForecastModel


class XGBoostModel(ForecastModel):
    """
    XGBoost over flattened windows (native multi-output via multi_strategy).

    Conservative stable defaults that work well without tuning.
    Hyperparameter tuning (Phase 3.3) will refine these via Optuna.
    """

    name = "xgboost"
    model_type = "tree"
    supports_feature_importance = True
    supports_gpu = False

    def __init__(
        self,
        n_estimators: int = 300,
        max_depth: int = 6,
        learning_rate: float = 0.05,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        random_state: int = 42,
        n_jobs: int = -1,
        **kwargs,
    ):
        try:
            from xgboost import XGBRegressor
        except ImportError:
            raise ImportError(
            "xgboost is required. Install: pip install xgboost"
        )
        self._fit_kwargs = kwargs.pop("fit_kwargs", {})
        
        # multi_strategy='multi_output_tree' is available in XGBoost >= 2.0
        # It builds one tree that predicts all outputs simultaneously.
        self._xgb = XGBRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            subsample=subsample,
            colsample_bytree=colsample_bytree,
            random_state=random_state,
            n_jobs=n_jobs,
            verbosity=0,
            tree_method="hist",          # fastest CPU method
            multi_strategy="multi_output_tree",  # native multi-output
            **kwargs,
        )
        self.horizon = None
        self.n_targets = None

    def _flatten(self, X: np.ndarray) -> np.ndarray:
        return X.reshape(X.shape[0], -1)

    def fit(self, X_train: np.ndarray, Y_train: np.ndarray, X_val: np.ndarray = None, Y_val: np.ndarray = None) -> None:
        self.horizon = Y_train.shape[1]
        self.n_targets = Y_train.shape[2]
        
        eval_set = None
        if X_val is not None and Y_val is not None:
            eval_set = [(self._flatten(X_val), Y_val.reshape(len(Y_val), -1))]
            
        self._xgb.fit(
            self._flatten(X_train), 
            Y_train.reshape(len(Y_train), -1),
            eval_set=eval_set,
            verbose=False,
            **self._fit_kwargs
        )

    def predict(self, X: np.ndarray) -> np.ndarray:
        Y_flat = self._xgb.predict(self._flatten(X))
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
        if not hasattr(self._xgb, "feature_importances_"):
            return None
        return self._xgb.feature_importances_
