import torch
import torch.nn as nn

class RevIN(nn.Module):
    """Reversible Instance Normalization."""
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

class Hybrid_v2(nn.Module):
    """
    SOTA Hybrid v2: RevIN + Multi-Scale Patching + Transformer Encoder + Cross-Variable Attention.
    (BiGRU has been removed to unblock sequence length limits for long horizons).
    """
    def __init__(self, config):
        super().__init__()
        self.num_targets = config['num_targets']
        self.patch_len_1 = config.get('patch_len_1', 8)
        self.patch_len_2 = config.get('patch_len_2', 24)
        self.stride = config.get('stride', 8)
        self.lookback = config['lookback']
        self.d_model = config.get('d_model', 64)
        self.d_channel = config.get('d_channel', 256)
        self.forecast_horizon = config['forecast_horizon']
        
        # Determine number of patches
        self.num_patches = (self.lookback - self.patch_len_1) // self.stride + 1
        
        self.revin = RevIN(num_features=self.num_targets)

        # Multi-scale patch embeddings
        self.embed_1 = nn.Linear(self.patch_len_1, self.d_model)
        self.embed_2 = nn.Linear(self.patch_len_2, self.d_model)
        
        # We assume calendar/weather features are passed pre-encoded and just project them
        # E.g., cyclical encoding output dim is passed as `d_temporal`
        d_temporal = config.get('d_temporal', 8) 
        self.calendar_embed = nn.Linear(d_temporal, 2 * self.d_model)

        # Main Temporal Transformer Encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=self.d_model * 2, 
            nhead=config.get('n_heads', 4), 
            dim_feedforward=self.d_model * 4,
            batch_first=True, 
            dropout=config.get('dropout', 0.2)
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=config.get('e_layers', 2))

        # Flatten patches into channel sequences
        self.flat_dim = self.num_patches * (self.d_model * 2)
        self.channel_proj = nn.Linear(self.flat_dim, self.d_channel)
        
        # Cross-Variable Attention
        cross_layer = nn.TransformerEncoderLayer(
            d_model=self.d_channel, 
            nhead=config.get('n_heads', 8), 
            dim_feedforward=self.d_channel * 2,
            batch_first=True, 
            dropout=config.get('dropout', 0.2)
        )
        self.cross_var_attn = nn.TransformerEncoder(cross_layer, num_layers=1)
        
        # Prediction Head
        self.predict_head = nn.Linear(self.d_channel, self.forecast_horizon)

    def forward(self, x_targets, x_temporal=None):
        """
        x_targets: (Batch, Lookback, Num_Targets)
        x_temporal: (Batch, Lookback, d_temporal)
        """
        batch_size = x_targets.shape[0]
        
        # 1. Normalize
        x_norm, mean, stdev = self.revin(x_targets, mode='norm')
        
        # 2. Channel Independence -> (Batch * Num_Targets, Lookback, 1)
        x_ci = x_norm.transpose(1, 2).reshape(batch_size * self.num_targets, -1, 1)

        # 3. Multi-Scale Patching
        patches_1 = x_ci.unfold(dimension=1, size=self.patch_len_1, step=self.stride).squeeze(2)
        pad_len = self.patch_len_2 - self.patch_len_1
        x_ci_padded = torch.cat([x_ci[:, :1, :].repeat(1, pad_len, 1), x_ci], dim=1)
        patches_2 = x_ci_padded.unfold(dimension=1, size=self.patch_len_2, step=self.stride).squeeze(2)

        # Embed Patches
        embed_1 = self.embed_1(patches_1)
        embed_2 = self.embed_2(patches_2)
        feat_in = torch.cat([embed_1, embed_2], dim=-1) # (B*C, Num_Patches, 2*d_model)

        # 4. Temporal Features (Weather + Calendar)
        if x_temporal is not None:
            # Extract temporal info aligned with patches
            patch_indices = [i * self.stride + self.patch_len_1 - 1 for i in range(self.num_patches)]
            cal_patched = x_temporal[:, patch_indices, :] # (B, Num_Patches, d_temporal)
            cal_feat = self.calendar_embed(cal_patched)   # (B, Num_Patches, 2*d_model)
            cal_feat = cal_feat.repeat_interleave(self.num_targets, dim=0) # Match B*C
            feat_in = feat_in + cal_feat

        # 5. Temporal Transformer Encoder (Replaces GRU)
        tf_out = self.transformer(feat_in) # (B*C, Num_Patches, 2*d_model)

        # 6. Channel Projection
        tf_flat = tf_out.reshape(batch_size * self.num_targets, -1) # (B*C, Num_Patches * 2*d_model)
        channel_feats = tf_flat.reshape(batch_size, self.num_targets, -1) # (B, C, flat_dim)
        channel_feats = self.channel_proj(channel_feats) # (B, C, d_channel)
        
        # 7. Cross-Variable Attention
        cross_out = self.cross_var_attn(channel_feats) # (B, C, d_channel)

        # 8. Prediction Head
        preds = self.predict_head(cross_out) # (B, C, Horizon)
        preds = preds.transpose(1, 2)        # (B, Horizon, C)
        
        # 9. Denormalize
        pred_final = self.revin(preds, mode='denorm', mean=mean, stdev=stdev)
        return pred_final
