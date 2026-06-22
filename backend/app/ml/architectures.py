"""
ML Model Architectures — must EXACTLY match training notebook definitions.
"""
import torch
import torch.nn as nn
import math


class RevIN(nn.Module):
    """Reversible Instance Normalization (Kim et al., 2022)."""
    def __init__(self, num_features, eps=1e-5, affine=True):
        super().__init__()
        self.eps = eps
        self.affine = affine
        if self.affine:
            self.affine_weight = nn.Parameter(torch.ones(num_features))
            self.affine_bias = nn.Parameter(torch.zeros(num_features))

    def forward(self, x, mode='norm', mean=None, stdev=None):
        if mode == 'norm':
            self.mean = torch.mean(x, dim=1, keepdim=True).detach()
            self.stdev = torch.sqrt(
                torch.var(x, dim=1, keepdim=True, unbiased=False) + self.eps
            ).detach()
            x = (x - self.mean) / self.stdev
            if self.affine:
                x = x * self.affine_weight + self.affine_bias
            return x, self.mean, self.stdev
        elif mode == 'denorm':
            if self.affine:
                x = (x - self.affine_bias) / (self.affine_weight + self.eps)
            x = x * stdev + mean
            return x


class PatchTST(nn.Module):
    """
    PatchTST: A Time Series is Worth 64 Words (Nie et al., ICLR 2023).
    Pure Transformer with channel-independent patching.
    """
    def __init__(self, num_targets=7, patch_len=16, stride=8, lookback=96,
                 d_model=128, n_heads=8, n_layers=3, d_ff=256,
                 dropout=0.2, forecast_horizon=24):
        super().__init__()
        self.num_targets = num_targets
        self.patch_len = patch_len
        self.stride = stride
        self.lookback = lookback
        self.d_model = d_model
        self.forecast_horizon = forecast_horizon

        self.num_patches = (lookback - patch_len) // stride + 1

        self.revin = RevIN(num_features=num_targets)
        self.patch_embedding = nn.Linear(patch_len, d_model)
        self.pos_encoding = nn.Parameter(
            torch.randn(1, self.num_patches, d_model) * 0.02
        )
        self.input_norm = nn.LayerNorm(d_model)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=n_heads, dim_feedforward=d_ff,
            dropout=dropout, batch_first=True, activation='gelu'
        )
        self.transformer_encoder = nn.TransformerEncoder(
            encoder_layer, num_layers=n_layers, norm=nn.LayerNorm(d_model)
        )

        self.flatten_dim = self.num_patches * d_model
        self.prediction_head = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(self.flatten_dim, forecast_horizon)
        )

    def forward(self, x_targets, x_calendar=None):
        batch_size = x_targets.shape[0]

        x_norm, mean, stdev = self.revin(x_targets, mode='norm')
        x_ci = x_norm.transpose(1, 2).reshape(batch_size * self.num_targets, self.lookback, 1)

        patches = x_ci.unfold(dimension=1, size=self.patch_len, step=self.stride).squeeze(2)
        patch_embed = self.patch_embedding(patches)
        patch_embed = patch_embed + self.pos_encoding
        patch_embed = self.input_norm(patch_embed)

        transformer_out = self.transformer_encoder(patch_embed)
        flat = transformer_out.reshape(batch_size * self.num_targets, -1)
        preds_ci = self.prediction_head(flat)

        preds = preds_ci.reshape(batch_size, self.num_targets, self.forecast_horizon)
        preds = preds.transpose(1, 2)

        pred_final = self.revin(preds, mode='denorm', mean=mean, stdev=stdev)
        return pred_final


class SOTAForecastingModel(nn.Module):
    """
    SOTA Hybrid: RevIN + Multi-Scale Patching + BiGRU + Transformer + Cross-Variable Attention.
    """
    def __init__(self, num_targets=7, patch_len_1=8, patch_len_2=24, stride=8,
                 lookback=96, d_model=64, d_channel=256, forecast_horizon=24):
        super().__init__()
        self.num_targets = num_targets
        self.patch_len_1 = patch_len_1
        self.patch_len_2 = patch_len_2
        self.stride = stride
        self.lookback = lookback
        self.d_model = d_model
        self.d_channel = d_channel
        self.forecast_horizon = forecast_horizon

        self.num_patches = (lookback - patch_len_1) // stride + 1
        self.revin = RevIN(num_features=num_targets)

        self.embed_1 = nn.Linear(patch_len_1, d_model)
        self.embed_2 = nn.Linear(patch_len_2, d_model)
        self.calendar_embed = nn.Linear(6, 2 * d_model)

        self.gru = nn.GRU(d_model * 2, d_model, batch_first=True, bidirectional=True)
        self.transformer = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(
                d_model * 2, nhead=4, dim_feedforward=d_model * 4,
                batch_first=True, dropout=0.2
            ),
            num_layers=2
        )

        self.flat_dim = self.num_patches * (d_model * 2)
        self.channel_proj = nn.Linear(self.flat_dim, d_channel)
        self.cross_var_attn = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(
                d_model=d_channel, nhead=8, dim_feedforward=d_channel * 2,
                batch_first=True, dropout=0.2
            ),
            num_layers=1
        )
        self.predict_head = nn.Linear(d_channel, forecast_horizon)

    def forward(self, x_targets, x_calendar):
        batch_size = x_targets.shape[0]
        x_norm, mean, stdev = self.revin(x_targets, mode='norm')
        x_ci = x_norm.transpose(1, 2).reshape(batch_size * self.num_targets, -1, 1)

        patches_1 = x_ci.unfold(dimension=1, size=self.patch_len_1, step=self.stride).squeeze(2)
        pad_len = self.patch_len_2 - self.patch_len_1
        x_ci_padded = torch.cat([x_ci[:, :1, :].repeat(1, pad_len, 1), x_ci], dim=1)
        patches_2 = x_ci_padded.unfold(dimension=1, size=self.patch_len_2, step=self.stride).squeeze(2)

        embed_1 = self.embed_1(patches_1)
        embed_2 = self.embed_2(patches_2)
        feat_in = torch.cat([embed_1, embed_2], dim=-1)

        patch_indices = [i * self.stride + self.patch_len_1 - 1 for i in range(self.num_patches)]
        cal_patched = x_calendar[:, patch_indices, :]
        cal_feat = self.calendar_embed(cal_patched)
        cal_feat = cal_feat.repeat_interleave(self.num_targets, dim=0)
        feat_in = feat_in + cal_feat

        gru_out, _ = self.gru(feat_in)
        tf_out = self.transformer(gru_out)

        tf_flat = tf_out.reshape(batch_size * self.num_targets, -1)
        channel_feats = tf_flat.reshape(batch_size, self.num_targets, -1)
        channel_feats = self.channel_proj(channel_feats)
        cross_out = self.cross_var_attn(channel_feats)

        preds = self.predict_head(cross_out)
        preds = preds.transpose(1, 2)
        pred_final = self.revin(preds, mode='denorm', mean=mean, stdev=stdev)
        return pred_final


class CNN_BiLSTM(nn.Module):
    """Baseline CNN-BiLSTM for multi-step forecasting."""
    def __init__(self, num_targets=7, forecast_horizon=24, cnn_filters=64, lstm_hidden=64):
        super(CNN_BiLSTM, self).__init__()
        self.num_targets = num_targets
        self.forecast_horizon = forecast_horizon

        self.cnn = nn.Sequential(
            nn.Conv1d(in_channels=num_targets, out_channels=cnn_filters, kernel_size=2, padding=1),
            nn.ReLU(),
            nn.MaxPool1d(kernel_size=2),
            nn.Conv1d(in_channels=cnn_filters, out_channels=cnn_filters, kernel_size=2, padding=1),
            nn.ReLU(),
            nn.MaxPool1d(kernel_size=2)
        )

        self.lstm = nn.LSTM(
            input_size=cnn_filters, hidden_size=lstm_hidden,
            num_layers=2, batch_first=True, bidirectional=True
        )

        self.fc = nn.Sequential(
            nn.Linear(lstm_hidden * 2, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, forecast_horizon * num_targets)
        )

    def forward(self, x_targets, x_calendar=None):
        x = x_targets.permute(0, 2, 1)
        x = self.cnn(x)
        x = x.permute(0, 2, 1)
        out, _ = self.lstm(x)
        last_out = out[:, -1, :]
        pred = self.fc(last_out)
        return pred.view(-1, self.forecast_horizon, self.num_targets)


class PositionalEncoding(nn.Module):
    """Sinusoidal Positional Encoding"""
    def __init__(self, d_model, max_len=5000):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe', pe.unsqueeze(0))

    def forward(self, x):
        return x + self.pe[:, :x.size(1), :]


class TemporalEmbedding(nn.Module):
    """Embeds Temporal Calendar Features (Hour, DayOfWeek, Month)"""
    def __init__(self, d_model):
        super().__init__()
        self.hour_embed = nn.Embedding(24, d_model)
        self.weekday_embed = nn.Embedding(7, d_model)
        self.month_embed = nn.Embedding(12, d_model)
        
    def forward(self, temporal_patches):
        # temporal_patches: (B, Num_Patches, 3) where 3 is [Hour, DayOfWeek, Month]
        hour_x = self.hour_embed(temporal_patches[:, :, 0])
        weekday_x = self.weekday_embed(temporal_patches[:, :, 1])
        month_x = self.month_embed(temporal_patches[:, :, 2])
        return hour_x + weekday_x + month_x


class Flatten_Head(nn.Module):
    """Flatten Head for PatchTST mapping channel tokens to the forecast horizon"""
    def __init__(self, individual: bool, n_vars: int, head_nf: int, target_window: int, head_dropout=0.0):
        super().__init__()
        self.individual = individual
        self.n_vars = n_vars
        
        if self.individual:
            self.linears = nn.ModuleList()
            self.dropouts = nn.ModuleList()
            for _ in range(self.n_vars):
                self.dropouts.append(nn.Dropout(head_dropout))
                self.linears.append(nn.Linear(head_nf, target_window))
        else:
            self.dropout = nn.Dropout(head_dropout)
            self.linear = nn.Linear(head_nf, target_window)

    def forward(self, x):
        # x shape: (B, C, Num_Patches, d_model)
        x = x.reshape(x.size(0), x.size(1), -1) # (B, C, Num_Patches * d_model)
        if self.individual:
            x_out = []
            for i in range(self.n_vars):
                z = self.dropouts[i](x[:, i, :])
                x_out.append(self.linears[i](z))
            x = torch.stack(x_out, dim=1) # (B, C, Target_Window)
        else:
            x = self.dropout(x)
            x = self.linear(x) # (B, C, Target_Window)
        return x


class AdvancedPatchTST(nn.Module):
    """Upgraded PatchTST with Temporal Features and stateless RevIN"""
    def __init__(self, c_in=7, context_window=336, target_window=168, 
                 patch_len=16, stride=8, d_model=128, n_heads=8, 
                 n_layers=3, d_ff=256, dropout=0.2, head_dropout=0.2, 
                 individual=False, revin=True, affine=True):
        super().__init__()
        self.c_in = c_in
        self.context_window = context_window
        self.target_window = target_window
        self.patch_len = patch_len
        self.stride = stride
        
        self.revin = revin
        if self.revin: 
            self.revin_layer = RevIN(c_in, affine=affine)
            
        # Patching mechanics
        self.patch_num = int((context_window - patch_len)/stride + 1)
        self.padding_patch_layer = nn.ReplicationPad1d((0, stride)) 
        self.patch_num += 1 # Account for padding
        
        self.value_embedding = nn.Linear(patch_len, d_model, bias=False)
        self.position_encoding = PositionalEncoding(d_model, max_len=1024)
        self.temporal_embedding = TemporalEmbedding(d_model)
        self.dropout = nn.Dropout(dropout)
        
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=n_heads, dim_feedforward=d_ff, 
            dropout=dropout, activation='gelu', batch_first=True, norm_first=True
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)
        self.head = Flatten_Head(individual, c_in, d_model * self.patch_num, target_window, head_dropout=head_dropout)

    def forward(self, x, temporal):
        # x shape: (B, S, C)
        # temporal shape: (B, S, 3) [Hour, DayOfWeek, Month]
        
        # 1. Normalize
        if self.revin: 
            x, mean, stdev = self.revin_layer(x, 'norm')
            
        # Channel Independence: (B, S, C) -> (B, C, S)
        x = x.permute(0, 2, 1) 
        
        # 2. Patching Sequence
        x = self.padding_patch_layer(x)
        x = x.unfold(dimension=-1, size=self.patch_len, step=self.stride) # (B, C, Num_Patches, Patch_Len)
        
        # Merge Batch and Channels
        batch_size = x.size(0)
        x = x.reshape(batch_size * self.c_in, self.patch_num, self.patch_len)
        
        # 2.5 Patching Temporal Features
        temporal_pad = self.padding_patch_layer(temporal.permute(0, 2, 1).float())
        temporal_unfold = temporal_pad.unfold(dimension=-1, size=self.patch_len, step=self.stride)
        temporal_patches = temporal_unfold[:, :, :, -1] # Get last element of each patch (B, 3, Num_Patches)
        temporal_patches = temporal_patches.permute(0, 2, 1).long() # (B, Num_Patches, 3)
        
        # Compute and add temporal calendar embedding
        temp_emb = self.temporal_embedding(temporal_patches) # (B, Num_Patches, d_model)
        temp_emb = temp_emb.unsqueeze(1).repeat(1, self.c_in, 1, 1) # (B, C, Num_Patches, d_model)
        temp_emb = temp_emb.reshape(batch_size * self.c_in, self.patch_num, -1)
        
        # 3. Embeddings
        x = self.value_embedding(x) + temp_emb
        x = self.position_encoding(x)
        x = self.dropout(x)
        
        # 4. Transformer Encoder
        x = self.encoder(x)
        
        # 5. Head
        x = x.reshape(batch_size, self.c_in, self.patch_num, -1)
        x = self.head(x) # (B, C, Target_Window)
        
        # 6. Denorm
        x = x.permute(0, 2, 1) # (B, Target_Window, C)
        if self.revin:
            x = self.revin_layer(x, 'denorm', mean=mean, stdev=stdev)
            
        return x


class iTransformer(nn.Module):
    """iTransformer with Calendar Embeddings as Channels/Tokens"""
    def __init__(self, c_in=7, lookback=336, forecast_horizon=168, 
                 d_model=128, n_heads=8, n_layers=3, d_ff=256, 
                 dropout=0.1, revin=True, affine=True):
        super().__init__()
        self.c_in = c_in
        self.lookback = lookback
        self.forecast_horizon = forecast_horizon
        
        self.revin = revin
        if self.revin:
            self.revin_layer = RevIN(c_in, affine=affine)
            
        # Feature Projection (transposed: maps lookback window length to d_model)
        self.token_embedding = nn.Linear(lookback, d_model)
        
        # Embeddings for Calendar Features
        self.hour_embed = nn.Embedding(24, d_model)
        self.weekday_embed = nn.Embedding(7, d_model)
        self.month_embed = nn.Embedding(12, d_model)
        
        # Pool temporal dimensions across sequence to form a single token
        self.temporal_pool = nn.Linear(lookback, 1)
        
        # Learnable channel embeddings (order invariance requires some variable identity)
        self.channel_embed = nn.Parameter(torch.zeros(1, c_in, d_model))
        
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=n_heads, dim_feedforward=d_ff,
            dropout=dropout, activation='gelu', batch_first=True, norm_first=True
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)
        
        # Linear head for each variable independently
        self.head = nn.Linear(d_model, forecast_horizon)
        
    def forward(self, x, temporal):
        # x shape: (B, Lookback, C)
        # temporal shape: (B, Lookback, 3)
        
        # 1. RevIN normalization
        if self.revin:
            x, mean, stdev = self.revin_layer(x, 'norm')
            
        # 2. Feature projection
        # Transpose sequence and channel dims: (B, L, C) -> (B, C, L)
        x_trans = x.permute(0, 2, 1)
        enc_in = self.token_embedding(x_trans) # (B, C, d_model)
        
        # 3. Calendar embedding & pooling
        hour_emb = self.hour_embed(temporal[:, :, 0]) # (B, L, d_model)
        weekday_emb = self.weekday_embed(temporal[:, :, 1]) # (B, L, d_model)
        month_emb = self.month_embed(temporal[:, :, 2]) # (B, L, d_model)
        
        temp_emb = hour_emb + weekday_emb + month_emb # (B, L, d_model)
        temp_emb_pooled = self.temporal_pool(temp_emb.permute(0, 2, 1)).squeeze(-1) # (B, d_model)
        
        # Add calendar embeddings to all target tokens
        enc_in = enc_in + temp_emb_pooled.unsqueeze(1) # (B, C, d_model)
        enc_in = enc_in + self.channel_embed
        
        # 4. Multi-head attention across channels
        enc_out = self.encoder(enc_in) # (B, C, d_model)
        
        # 5. Predict & Transpose back
        dec_out = self.head(enc_out) # (B, C, Horizon)
        dec_out = dec_out.permute(0, 2, 1) # (B, Horizon, C)
        
        # 6. RevIN denormalization
        if self.revin:
            dec_out = self.revin_layer(dec_out, 'denorm', mean=mean, stdev=stdev)
            
        return dec_out
