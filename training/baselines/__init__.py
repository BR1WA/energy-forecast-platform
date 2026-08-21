"""training/baselines/__init__.py — Model registry for the training CLI."""
from importlib.util import find_spec

from .base import ForecastModel
from .persistence import PersistenceModel
from .seasonal_naive import SeasonalNaiveModel
from .linear import LinearModel
from .ridge import RidgeModel
from .random_forest import RandomForestModel

_REGISTRY = {
    "persistence":    PersistenceModel,
    "seasonal_naive": SeasonalNaiveModel,
    "linear":         LinearModel,
    "ridge":          RidgeModel,
    "random_forest":  RandomForestModel,
}

# PatchTST uses the optional Transformers stack. Keep the general training
# pipeline importable for the CI test profile, which intentionally installs
# only the CPU Torch stack; the model is registered whenever its dependency is
# installed through the foundation profile.
if find_spec("transformers") is not None:
    from training.models.patchtst import PatchTSTModel
    _REGISTRY["patchtst"] = PatchTSTModel

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
