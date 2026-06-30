import torch
import torch.nn as nn
from .base import ForecastModel
from training.features.scaling import RevIN

class iTransformer(ForecastModel):
    """
    iTransformer: Inverted Transformers are Effective for Time Series Forecasting (ICLR 2024).
    Treats each variable (time series channel) as an independent token.
    Upgraded to accept cyclical calendar and Open-Meteo weather features.
    """
    def __init__(self, config):
        super().__init__()
        self.c_in = config['num_targets']
        self.lookback = config['lookback']
        self.forecast_horizon = config['forecast_horizon']
        self.d_model = config.get('d_model', 512)
        
        self.revin = RevIN(self.c_in)
        
        # 1. Feature Projection
        # Maps the entire lookback sequence of a single channel into d_model
        self.token_embedding = nn.Linear(self.lookback, self.d_model)
        
        # 2. Exogenous/Temporal Feature Embedding
        d_temporal = config.get('d_temporal', 8)
        self.temporal_embed = nn.Linear(d_temporal, self.d_model)
        # Pool temporal dimensions across the sequence to form a single summary token
        self.temporal_pool = nn.Linear(self.lookback, 1)
        
        # 3. Channel Identity Embedding (Helps the model distinguish which variable is which)
        self.channel_embed = nn.Parameter(torch.zeros(1, self.c_in, self.d_model))
        
        # 4. Transformer Encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=self.d_model, 
            nhead=config.get('n_heads', 8), 
            dim_feedforward=config.get('d_ff', 2048),
            dropout=config.get('dropout', 0.1), 
            activation='gelu', 
            batch_first=True, 
            norm_first=True
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=config.get('e_layers', 3))
        
        # 5. Prediction Head
        # Projects d_model back to the forecast horizon
        self.head = nn.Linear(self.d_model, self.forecast_horizon)
        
    def forward(self, x_targets, x_temporal=None):
        # x_targets: (B, Lookback, C)
        # x_temporal: (B, Lookback, d_temporal)
        
        # Normalize
        x_norm, mean, stdev = self.revin(x_targets, mode='norm')
        
        # Invert dimensions: tokens are now channels, token length is Lookback
        # (B, Lookback, C) -> (B, C, Lookback)
        x_trans = x_norm.permute(0, 2, 1)
        
        # Project each channel's history into d_model
        enc_in = self.token_embedding(x_trans) # (B, C, d_model)
        
        # Temporal/Weather Processing
        if x_temporal is not None:
            temp_emb = self.temporal_embed(x_temporal.float()) # (B, Lookback, d_model)
            # Pool to get a single token summarizing the period
            temp_emb_pooled = self.temporal_pool(temp_emb.permute(0, 2, 1)).squeeze(-1) # (B, d_model)
            
            # Broadcast temporal summary to all channel tokens
            enc_in = enc_in + temp_emb_pooled.unsqueeze(1) # (B, C, d_model)
            
        # Add channel identity
        enc_in = enc_in + self.channel_embed
        
        # Attention across variables (tokens)
        enc_out = self.encoder(enc_in) # (B, C, d_model)
        
        # Predict
        dec_out = self.head(enc_out) # (B, C, Horizon)
        dec_out = dec_out.permute(0, 2, 1) # (B, Horizon, C)
        
        # Denormalize
        pred_final = self.revin(dec_out, mode='denorm', mean=mean, stdev=stdev)
        return pred_final
