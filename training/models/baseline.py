import torch
import torch.nn as nn
from .base import ForecastModel

class NaivePersistence(ForecastModel):
    """
    Naïve Persistence Baseline.
    Predicts that the next H steps will simply repeat the last observed value (or sequence).
    """
    def __init__(self, forecast_horizon, num_targets):
        super().__init__()
        self.forecast_horizon = forecast_horizon
        self.num_targets = num_targets

    def forward(self, x, temporal=None):
        # x shape: (B, Lookback, C)
        # Simply take the last observation for each channel and repeat it for the horizon
        last_obs = x[:, -1:, :] # (B, 1, C)
        prediction = last_obs.repeat(1, self.forecast_horizon, 1) # (B, Horizon, C)
        return prediction
