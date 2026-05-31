"""
ML Model Architectures — must EXACTLY match training notebook definitions.
"""
import torch
import torch.nn as nn


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
