import math
import torch
import torch.nn as nn
from tsmixer import RevIN

class WeatheriTransformer(nn.Module):
    """Weather-Aware iTransformer incorporating Weather Covariates as Transposed Tokens"""
    def __init__(self, c_out=7, c_weather=3, lookback=336, forecast_horizon=168, 
                 d_model=128, n_heads=8, n_layers=3, d_ff=256, 
                 dropout=0.1, revin=True, affine=True):
        super().__init__()
        self.c_out = c_out
        self.c_weather = c_weather
        self.c_in = c_out + c_weather
        self.lookback = lookback
        self.forecast_horizon = forecast_horizon
        
        self.revin = revin
        if self.revin:
            self.revin_layer = RevIN(c_out, affine=affine)
            
        # Target token projection (L -> d_model)
        self.token_embedding = nn.Linear(lookback, d_model)
        # Weather token projection (L -> d_model)
        self.weather_embedding = nn.Linear(lookback, d_model)
        
        # Calendar embeddings
        self.hour_embed = nn.Embedding(24, d_model)
        self.weekday_embed = nn.Embedding(7, d_model)
        self.month_embed = nn.Embedding(12, d_model)
        self.temporal_pool = nn.Linear(lookback, 1)
        
        # Learnable channel embeddings for target + weather tokens
        self.channel_embed = nn.Parameter(torch.zeros(1, self.c_in, d_model))
        
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=n_heads, dim_feedforward=d_ff,
            dropout=dropout, activation='gelu', batch_first=True, norm_first=True
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)
        
        # Mapping from target token to forecast horizon
        self.head = nn.Linear(d_model, forecast_horizon)
        
    def forward(self, x_targets, x_weather, temporal):
        # x_targets: (B, L, C_out)
        # x_weather: (B, L, C_weather)
        # temporal: (B, L, 3)
        
        # 1. Target RevIN normalization
        if self.revin:
            x_targets, mean, stdev = self.revin_layer(x_targets, 'norm')
            
        # 2. Variable transposition
        targets_trans = x_targets.permute(0, 2, 1) # (B, C_out, L)
        weather_trans = x_weather.permute(0, 2, 1) # (B, C_weather, L)
        
        # 3. Independent token embeddings
        enc_targets = self.token_embedding(targets_trans) # (B, C_out, d_model)
        enc_weather = self.weather_embedding(weather_trans) # (B, C_weather, d_model)
        
        # Combine target and weather tokens
        enc_in = torch.cat([enc_targets, enc_weather], dim=1) # (B, C_in, d_model)
        
        # 4. Integrate Calendar embeddings
        hour_emb = self.hour_embed(temporal[:, :, 0])
        weekday_emb = self.weekday_embed(temporal[:, :, 1])
        month_emb = self.month_embed(temporal[:, :, 2])
        temp_emb = hour_emb + weekday_emb + month_emb # (B, L, d_model)
        temp_emb_pooled = self.temporal_pool(temp_emb.permute(0, 2, 1)).squeeze(-1) # (B, d_model)
        
        # Add temporal features to all variable tokens
        enc_in = enc_in + temp_emb_pooled.unsqueeze(1)
        enc_in = enc_in + self.channel_embed
        
        # 5. Transformer Encoder: Self-Attention across targets and weather variables
        enc_out = self.encoder(enc_in) # (B, C_in, d_model)
        
        # 6. Discard weather tokens, project target tokens to the forecast horizon
        enc_out_targets = enc_out[:, :self.c_out, :] # (B, C_out, d_model)
        dec_out = self.head(enc_out_targets) # (B, C_out, Horizon)
        dec_out = dec_out.permute(0, 2, 1) # (B, Horizon, C_out)
        
        # 7. Target RevIN denormalization
        if self.revin:
            dec_out = self.revin_layer(dec_out, 'denorm', mean=mean, stdev=stdev)
        return dec_out
