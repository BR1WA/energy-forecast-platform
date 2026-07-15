"""training/baselines/__init__.py — Model registry for the training CLI."""
from .base import ForecastModel
from .persistence import PersistenceModel
from .seasonal_naive import SeasonalNaiveModel
from .linear import LinearModel
from .ridge import RidgeModel
from .random_forest import RandomForestModel
from training.models.patchtst import PatchTSTModel

_REGISTRY = {
    "persistence":    PersistenceModel,
    "seasonal_naive": SeasonalNaiveModel,
    "linear":         LinearModel,
    "ridge":          RidgeModel,
    "random_forest":  RandomForestModel,
    "patchtst":       PatchTSTModel,
}

# XGBoost is optional — only register if the package is installed
try:
    from .xgboost_model import XGBoostModel
    _REGISTRY["xgboost"] = XGBoostModel
except ImportError:
    pass


def get_model(name: str, **kwargs) -> ForecastModel:
    """Instantiate a model by name. Kwargs are forwarded to the constructor."""
    name = name.lower()
    if name not in _REGISTRY:
        available = sorted(_REGISTRY.keys())
        raise ValueError(
            f"Unknown model '{name}'. Available: {available}"
        )
    return _REGISTRY[name](**kwargs)


def list_models() -> list:
    return sorted(_REGISTRY.keys())
