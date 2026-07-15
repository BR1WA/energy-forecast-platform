from typing import Dict, Type
import torch.nn as nn

from app.ml.architectures import (
    PatchTST,
    SOTAForecastingModel,
    CNN_BiLSTM,
    iTransformer,
    AdvancedPatchTST
)

try:
    from training.models.hybrid_v2 import Hybrid_v2
except ImportError:
    Hybrid_v2 = None

MODEL_REGISTRY: Dict[str, Type[nn.Module]] = {
    "PatchTST": PatchTST,
    "SOTAForecastingModel": SOTAForecastingModel,
    "CNN-BiLSTM": CNN_BiLSTM,
    "CNN_BiLSTM": CNN_BiLSTM,
    "iTransformer": iTransformer,
    "AdvancedPatchTST": AdvancedPatchTST,
}

if Hybrid_v2 is not None:
    MODEL_REGISTRY["Hybrid_v2"] = Hybrid_v2
    MODEL_REGISTRY["HybridV2"] = Hybrid_v2

def get_model_class(arch_name: str) -> Type[nn.Module]:
    """Retrieve the PyTorch module class for a given architecture name."""
    if arch_name not in MODEL_REGISTRY:
        raise ValueError(f"Architecture '{arch_name}' is not registered in MODEL_REGISTRY.")
    return MODEL_REGISTRY[arch_name]
