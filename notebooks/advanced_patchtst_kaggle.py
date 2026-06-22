import os
import math
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import pandas as pd
import numpy as np
from tqdm import tqdm
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, r2_score

# ==========================================
# 1. CORE LTSF LAYERS
# ==========================================

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

# ==========================================
# 2. SOTA ARCHITECTURES
# ==========================================

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

# ==========================================
# 3. DATASET & DATALOADER
# ==========================================

class EnergyDataset(Dataset):
    def __init__(self, data, stamps, lookback, horizon):
        self.data = data
        self.stamps = stamps
        self.lookback = lookback
        self.horizon = horizon

    def __len__(self):
        return len(self.data) - self.lookback - self.horizon + 1

    def __getitem__(self, idx):
        x = self.data[idx : idx + self.lookback]
        y = self.data[idx + self.lookback : idx + self.lookback + self.horizon]
        
        stamp_x = self.stamps[idx : idx + self.lookback]
        hour = stamp_x.hour.values
        dayofweek = stamp_x.dayofweek.values
        month = stamp_x.month.values - 1 # 0-indexed
        
        temporal = np.stack([hour, dayofweek, month], axis=1) # (lookback, 3)
        
        return (torch.tensor(x, dtype=torch.float32), 
                torch.tensor(y, dtype=torch.float32), 
                torch.tensor(temporal, dtype=torch.long))

def prepare_dataloaders(csv_path, lookback, horizon, batch_size=32):
    print(f"Loading dataset from {csv_path}...")
    df = pd.read_csv(csv_path, sep=';', na_values=['?'], dtype={'Date': str, 'Time': str})
    
    # 1. Fast DateTime parsing (explicit format optimization)
    print("Parsing datetime index...")
    df['datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='%d/%m/%Y %H:%M:%S')
    df = df.drop(columns=['Date', 'Time']).set_index('datetime')
    
    target_cols = [
        'Global_active_power', 'Global_reactive_power', 'Voltage',
        'Global_intensity', 'Sub_metering_1', 'Sub_metering_2', 'Sub_metering_3'
    ]
    
    # Basic data cleaning & forward-backward fill for missing values
    df[target_cols] = df[target_cols].astype(float)
    df[target_cols] = df[target_cols].ffill().bfill()
    
    # 2. Resample to hourly means (Strict Requirement 1)
    print("Resampling data to hourly frequency...")
    df_hourly = df[target_cols].resample('h').mean()
    df_hourly = df_hourly.ffill().bfill()
    
    data = df_hourly.values
    timestamps = df_hourly.index
    
    # Chronological Split: 80% Train, 20% Val
    split_idx = int(len(data) * 0.8)
    train_data = data[:split_idx]
    train_stamps = timestamps[:split_idx]
    
    val_data = data[split_idx:]
    val_stamps = timestamps[split_idx:]
    
    # Fit StandardScaler on train data ONLY (Strict Requirement 4)
    print("Fitting StandardScaler on training targets...")
    scaler = StandardScaler()
    train_data_scaled = scaler.fit_transform(train_data)
    val_data_scaled = scaler.transform(val_data)
    
    train_dataset = EnergyDataset(train_data_scaled, train_stamps, lookback, horizon)
    val_dataset = EnergyDataset(val_data_scaled, val_stamps, lookback, horizon)
    
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=2, pin_memory=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=2, pin_memory=True)
    
    return train_loader, val_loader, scaler

# ==========================================
# 4. TRAINING & EVALUATION LOOPS
# ==========================================

def train_model(model, train_loader, val_loader, epochs=10, lr=1e-4, device='cuda', save_path='model.pth'):
    model.to(device)
    criterion = nn.MSELoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=2)
    
    best_val_loss = float('inf')
    
    for epoch in range(epochs):
        model.train()
        train_loss = 0
        for x, y, temp in tqdm(train_loader, desc=f"Epoch {epoch+1}/{epochs} [Train]"):
            x, y, temp = x.to(device), y.to(device), temp.to(device)
            optimizer.zero_grad()
            preds = model(x, temp)
            loss = criterion(preds, y) # Calculated in normalized space
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
            
        model.eval()
        val_loss = 0
        with torch.no_grad():
            for x, y, temp in tqdm(val_loader, desc=f"Epoch {epoch+1}/{epochs} [Val]"):
                x, y, temp = x.to(device), y.to(device), temp.to(device)
                preds = model(x, temp)
                val_loss += criterion(preds, y).item()
                
        train_loss /= len(train_loader)
        val_loss /= len(val_loader)
        print(f"Epoch {epoch+1} | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f}")
        
        scheduler.step(val_loss)
        
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            # Safe save for DataParallel model configurations (Strict Requirement 3)
            if isinstance(model, nn.DataParallel):
                torch.save(model.module.state_dict(), save_path)
            else:
                torch.save(model.state_dict(), save_path)
            print(f"--> Saved best model weights to {save_path}")

def evaluate_model(model, val_loader, scaler, device, target_idx=0):
    """Evaluates actual MAE and R-squared on inverse-transformed (original scale) data (Strict Requirement 4)"""
    model.eval()
    all_preds = []
    all_trues = []
    
    with torch.no_grad():
        for x, y, temp in tqdm(val_loader, desc="[Evaluation]"):
            x, y, temp = x.to(device), y.to(device), temp.to(device)
            preds = model(x, temp)
            
            all_preds.append(preds.cpu().numpy())
            all_trues.append(y.cpu().numpy())
            
    all_preds = np.concatenate(all_preds, axis=0) # Shape: (N, Horizon, C)
    all_trues = np.concatenate(all_trues, axis=0) # Shape: (N, Horizon, C)
    
    N, H, C = all_preds.shape
    preds_flat = all_preds.reshape(-1, C)
    trues_flat = all_trues.reshape(-1, C)
    
    # Inverse scaling to calculate actual metrics
    preds_orig = scaler.inverse_transform(preds_flat).reshape(N, H, C)
    trues_orig = scaler.inverse_transform(trues_flat).reshape(N, H, C)
    
    # Extract target column ('Global_active_power', index 0)
    preds_gap = preds_orig[:, :, target_idx].flatten()
    trues_gap = trues_orig[:, :, target_idx].flatten()
    
    mae = mean_absolute_error(trues_gap, preds_gap)
    r2 = r2_score(trues_gap, preds_gap)
    
    print(f"\n--- Evaluation for Global_active_power ---")
    print(f"Actual MAE (Original Scale): {mae:.4f} kW")
    print(f"R-squared: {r2:.4f}\n")
    return mae, r2

# ==========================================
# 5. MAIN KAGGLE RUNNER
# ==========================================

if __name__ == "__main__":
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Using device: {device}")
    
    def find_file(filename, search_dir='/kaggle/input'):
        if not os.path.exists(search_dir):
            return None
        for root, dirs, files in os.walk(search_dir):
            if filename in files:
                path = os.path.join(root, filename)
                print(f"Found {filename} at: {path}")
                return path
        return None

    # Resolve target dataset path dynamically on Kaggle
    CSV_PATH = find_file('household_power_consumption.txt')
    if CSV_PATH is None:
        CSV_PATH = "c:/Users/salah/Documents/MASTER/PFE2/data/household_power_consumption.txt"
        if not os.path.exists(CSV_PATH):
            CSV_PATH = "../data/household_power_consumption.txt"
            if not os.path.exists(CSV_PATH):
                CSV_PATH = "data/household_power_consumption.txt"
    print(f"Resolved targets CSV_PATH: {CSV_PATH}")
        
    HORIZONS = [
        {"name": "1_week", "horizon": 168, "lookback": 512},   # 1 week prediction
        {"name": "1_month", "horizon": 720, "lookback": 1440}  # 1 month prediction (scaled lookback)
    ]
    
    results = {}
    
    for config in HORIZONS:
        print(f"\n{'='*60}")
        print(f"RUNNING EXPERIMENT: {config['name']} (Lookback: {config['lookback']}h, Horizon: {config['horizon']}h)")
        print(f"{'='*60}")
        
        train_loader, val_loader, scaler = prepare_dataloaders(
            CSV_PATH, lookback=config['lookback'], horizon=config['horizon'], batch_size=64
        )
        
        results[config['name']] = {}
        
        # Test both SOTA models to compare performance
        for model_name in ["AdvancedPatchTST", "iTransformer"]:
            print(f"\n{'-'*50}")
            print(f"Training {model_name}...")
            print(f"{'-'*50}")
            
            if model_name == "AdvancedPatchTST":
                model = AdvancedPatchTST(
                    c_in=7, 
                    context_window=config['lookback'],
                    target_window=config['horizon'],
                    patch_len=16, 
                    stride=8, 
                    d_model=128, 
                    n_heads=8, 
                    n_layers=3, 
                    d_ff=256,
                    dropout=0.2,
                    head_dropout=0.2,
                    individual=False, 
                    revin=True
                )
            else: # iTransformer
                model = iTransformer(
                    c_in=7,
                    lookback=config['lookback'],
                    forecast_horizon=config['horizon'],
                    d_model=128,
                    n_heads=8,
                    n_layers=3,
                    d_ff=256,
                    dropout=0.2,
                    revin=True
                )
                
            # Dual-GPU / Multi-GPU configuration (Strict Requirement 3)
            if torch.cuda.device_count() > 1:
                print(f"Using {torch.cuda.device_count()} GPUs with torch.nn.DataParallel!")
                model = nn.DataParallel(model)
                
            save_path = f"{model_name.lower()}_{config['name']}_weights.pth"
            
            # Train model
            train_model(model, train_loader, val_loader, epochs=10, lr=1e-4, device=device, save_path=save_path)
            
            # Load best weights safely (supports single/multi GPU loading compatibility)
            print(f"Loading best weights from {save_path} for final evaluation...")
            state_dict = torch.load(save_path, map_location=device)
            if isinstance(model, nn.DataParallel):
                model.module.load_state_dict(state_dict)
            else:
                model.load_state_dict(state_dict)
                
            # Evaluate model
            mae, r2 = evaluate_model(model, val_loader, scaler, device, target_idx=0)
            results[config['name']][model_name] = {"MAE": mae, "R2": r2}

    print("\n" + "="*50)
    print("ALL EXPERIMENTS COMPLETED - FINAL SUMMARY")
    print("="*50)
    for horizon, models in results.items():
        print(f"\nHorizon: {horizon}")
        for model_name, metrics in models.items():
            print(f"  {model_name}: MAE = {metrics['MAE']:.4f} kW, R2 = {metrics['R2']:.4f}")
