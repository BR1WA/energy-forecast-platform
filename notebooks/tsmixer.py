import torch
import torch.nn as nn

class RevIN(nn.Module):
    """Reversible Instance Normalization (stateless across forward passes for multi-GPU safety)"""
    def __init__(self, num_features: int, eps=1e-5, affine=True):
        super().__init__()
        self.num_features = num_features
        self.eps = eps
        self.affine = affine
        if self.affine:
            self.affine_weight = nn.Parameter(torch.ones(self.num_features))
            self.affine_bias = nn.Parameter(torch.zeros(self.num_features))

    def forward(self, x, mode: str, mean=None, stdev=None):
        if mode == 'norm':
            mean = torch.mean(x, dim=1, keepdim=True).detach()
            stdev = torch.sqrt(torch.var(x, dim=1, keepdim=True, unbiased=False) + self.eps).detach()
            x = (x - mean) / stdev
            if self.affine:
                x = x * self.affine_weight + self.affine_bias
            return x, mean, stdev
        elif mode == 'denorm':
            if self.affine:
                x = (x - self.affine_bias) / (self.affine_weight + self.eps)
            x = x * stdev + mean
            return x

class TSMixerBlock(nn.Module):
    """TSMixer Block implementing Time mixing and Feature mixing"""
    def __init__(self, c_in, lookback, d_ff, dropout=0.1):
        super().__init__()
        # Time mixing (along lookback dimension)
        self.norm1 = nn.LayerNorm([lookback, c_in])
        self.time_mlp = nn.Sequential(
            nn.Linear(lookback, lookback),
            nn.GELU(),
            nn.Dropout(dropout)
        )
        # Feature mixing (along channel dimension)
        self.norm2 = nn.LayerNorm([lookback, c_in])
        self.feature_mlp = nn.Sequential(
            nn.Linear(c_in, d_ff),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_ff, c_in),
            nn.Dropout(dropout)
        )
        
    def forward(self, x):
        # Time Mixing
        res = x
        x = self.norm1(x)
        x = x.transpose(1, 2)
        x = self.time_mlp(x)
        x = x.transpose(1, 2)
        x = x + res
        
        # Feature Mixing
        res = x
        x = self.norm2(x)
        x = self.feature_mlp(x)
        x = x + res
        return x

class TSMixer(nn.Module):
    """Google's TSMixer: An All-MLP Architecture for Time Series Forecasting with Exogenous Features"""
    def __init__(self, c_out=7, c_weather=3, lookback=336, forecast_horizon=168, 
                 d_ff=64, num_blocks=3, dropout=0.1, revin=True):
        super().__init__()
        self.c_out = c_out
        self.c_weather = c_weather
        self.c_in = c_out + c_weather
        self.lookback = lookback
        self.forecast_horizon = forecast_horizon
        
        self.revin = revin
        if self.revin:
            self.revin_layer = RevIN(c_out)
            
        self.blocks = nn.ModuleList([
            TSMixerBlock(self.c_in, lookback, d_ff, dropout)
            for _ in range(num_blocks)
        ])
        
        # Prediction head: maps (B, L, C_in) -> (B, H, C_out)
        self.head = nn.Linear(lookback * self.c_in, forecast_horizon * c_out)
        
    def forward(self, x_targets, x_weather, temporal=None):
        # x_targets: (B, L, C_out)
        # x_weather: (B, L, C_weather)
        
        # 1. Normalize targets using RevIN
        if self.revin:
            x_targets, mean, stdev = self.revin_layer(x_targets, 'norm')
            
        # Concatenate targets and exogenous features
        x = torch.cat([x_targets, x_weather], dim=-1) # (B, L, C_in)
        
        # 2. Sequential mixing blocks
        for block in self.blocks:
            x = block(x)
            
        # 3. Projection Head
        batch_size = x.size(0)
        x_flat = x.reshape(batch_size, -1) # Flatten (B, L * C_in)
        out = self.head(x_flat) # Project to (B, H * C_out)
        out = out.reshape(batch_size, self.forecast_horizon, self.c_out)
        
        # 4. Denormalize targets using RevIN
        if self.revin:
            out = self.revin_layer(out, 'denorm', mean=mean, stdev=stdev)
        return out
