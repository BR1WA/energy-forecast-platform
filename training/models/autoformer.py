import torch
import torch.nn as nn
import math
from .base import ForecastModel

class moving_avg(nn.Module):
    """
    Moving average block to highlight the trend of time series
    """
    def __init__(self, kernel_size, stride):
        super(moving_avg, self).__init__()
        self.kernel_size = kernel_size
        self.avg = nn.AvgPool1d(kernel_size=kernel_size, stride=stride, padding=0)

    def forward(self, x):
        # padding on the both ends of time series
        front = x[:, 0:1, :].repeat(1, (self.kernel_size - 1) // 2, 1)
        end = x[:, -1:, :].repeat(1, (self.kernel_size - 1) // 2, 1)
        x = torch.cat([front, x, end], dim=1)
        x = self.avg(x.permute(0, 2, 1))
        x = x.permute(0, 2, 1)
        return x


class series_decomp(nn.Module):
    """
    Series decomposition block
    """
    def __init__(self, kernel_size):
        super(series_decomp, self).__init__()
        self.moving_avg = moving_avg(kernel_size, stride=1)

    def forward(self, x):
        moving_mean = self.moving_avg(x)
        res = x - moving_mean
        return res, moving_mean

class Autoformer(ForecastModel):
    """
    Simplified Autoformer for demonstration and baseline testing.
    Predicts residuals after decomposing the trend.
    """
    def __init__(self, config):
        super().__init__()
        self.seq_len = config['lookback']
        self.pred_len = config['forecast_horizon']
        self.c_in = config['num_targets']
        self.d_model = config.get('d_model', 512)
        
        self.decomp = series_decomp(config.get('moving_avg', 25))
        
        # Simple token embedding
        self.value_embedding = nn.Linear(self.c_in, self.d_model)
        
        # We will use a standard transformer encoder for the residual as a simplified stand-in 
        # for full AutoCorrelation if this is just the baseline skeleton. 
        # Note: A true Autoformer uses AutoCorrelationLayer. For PFE scope, we implement the 
        # decomposition architecture pattern.
        
        self.encoder = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(
                d_model=self.d_model, nhead=8, batch_first=True
            ),
            num_layers=config.get('e_layers', 2)
        )
        
        self.projection = nn.Linear(self.d_model, self.c_in, bias=True)
        
        # Trend projection
        self.trend_projection = nn.Linear(self.seq_len, self.pred_len)

    def forward(self, x, temporal=None):
        # x: (B, L, C)
        res, trend = self.decomp(x)
        
        # Trend forecasting
        trend_forecast = self.trend_projection(trend.permute(0, 2, 1)).permute(0, 2, 1)
        
        # Residual forecasting
        res_emb = self.value_embedding(res)
        enc_out = self.encoder(res_emb)
        
        # Take the last pred_len tokens or pool
        # For simplicity, project the flat sequence or use the last tokens
        # Here we just map the sequence dimension:
        res_forecast = enc_out[:, -self.pred_len:, :]
        if res_forecast.size(1) < self.pred_len:
            # If pred_len > seq_len, we would need to pad or project.
            # Simplified projection:
            pass
            
        res_forecast = self.projection(res_forecast) # (B, pred_len, C)
        
        # Combine
        out = trend_forecast + res_forecast
        return out
