import torch
import torch.nn as nn
import math

class CyclicalEncoding(nn.Module):
    """
    Encodes cyclical features (hour, weekday, month, day_of_year) using sin and cos transformations.
    Instead of learning independent embeddings, it projects the cyclical nature directly,
    ensuring that hour 23 is close to hour 0.
    """
    def __init__(self, d_model):
        super().__init__()
        # We will map each cyclical feature to a fraction of the d_model dimension.
        # 4 features * 2 (sin, cos) = 8 dimensions per token. 
        # We project these 8 dimensions up to d_model.
        self.projection = nn.Linear(8, d_model)
        
    def forward(self, temporal):
        # temporal shape: (B, Lookback, 4) -> [hour, weekday, month, day_of_year]
        hour = temporal[:, :, 0:1]
        weekday = temporal[:, :, 1:2]
        month = temporal[:, :, 2:3]
        day_of_year = temporal[:, :, 3:4]
        
        # Normalize and apply sin/cos
        h_sin = torch.sin(2 * math.pi * hour / 24.0)
        h_cos = torch.cos(2 * math.pi * hour / 24.0)
        
        w_sin = torch.sin(2 * math.pi * weekday / 7.0)
        w_cos = torch.cos(2 * math.pi * weekday / 7.0)
        
        m_sin = torch.sin(2 * math.pi * (month - 1) / 12.0)
        m_cos = torch.cos(2 * math.pi * (month - 1) / 12.0)
        
        d_sin = torch.sin(2 * math.pi * (day_of_year - 1) / 366.0)
        d_cos = torch.cos(2 * math.pi * (day_of_year - 1) / 366.0)
        
        # Concatenate all cyclical features
        # Shape: (B, Lookback, 8)
        cyclical_feat = torch.cat([h_sin, h_cos, w_sin, w_cos, m_sin, m_cos, d_sin, d_cos], dim=-1)
        
        # Project to d_model
        # Shape: (B, Lookback, d_model)
        out = self.projection(cyclical_feat.float())
        return out
