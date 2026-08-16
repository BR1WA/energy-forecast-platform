import torch
import torch.nn as nn
from abc import ABC, abstractmethod

class ForecastModel(nn.Module, ABC):
    """
    Abstract base class for all forecasting models to ensure a unified interface
    across Hybrid_v2, iTransformer, etc.
    """
    
    @abstractmethod
    def forward(self, x, temporal):
        """
        Forward pass for PyTorch model.
        """
        pass

    def train_model(self, *args, **kwargs):
        """
        Specific training logic or loops if necessary.
        By default, we handle training in train.py, but this allows custom logic.
        """
        pass

    def predict(self, x, temporal=None):
        """
        Inference method. Defaults to calling forward.
        """
        self.eval()
        with torch.no_grad():
            return self.forward(x, temporal)

    def save(self, filepath: str):
        """
        Save model weights and configuration.
        """
        torch.save(self.state_dict(), filepath)

    def load(self, filepath: str, device: torch.device):
        """
        Load model weights.
        """
        self.load_state_dict(
            torch.load(filepath, map_location=device, weights_only=True)
        )
