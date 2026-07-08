import os
import time
import torch
import hashlib
import torch.nn as nn
import torch.optim as optim
import pandas as pd
import numpy as np
from torch.cuda.amp import autocast, GradScaler
from torch.utils.data import DataLoader, TensorDataset

from training.utils.config import get_args_and_config
from training.utils.tracker import ExperimentTracker
from training.utils.seed import set_seed
from training.utils.metrics import compute_metrics
from training.features.feature_engineering import FeaturePipeline

# Dynamic loading of models
from training.models.baseline import NaivePersistence
from training.models.autoformer import Autoformer
from training.models.hybrid_v2 import Hybrid_v2
from training.models.itransformer import iTransformer

def load_real_data(filepath, limit_rows=None):
    """Loads the real UCI household power consumption dataset."""
    print(f"Loading real dataset from {filepath}...")
    
    # The dataset uses ';' as delimiter and '?' for missing values
    df = pd.read_csv(filepath, sep=';', na_values=['?'], nrows=limit_rows)
    
    # Combine Date and Time into a single timestamp column
    df['timestamp'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='%d/%m/%Y %H:%M:%S')
    
    # Rename target column to 'gap' for consistency with our pipeline
    df = df.rename(columns={'Global_active_power': 'gap'})
    
    # Keep only relevant columns to save memory
    df = df[['timestamp', 'gap']]
    
    # Resample to hourly frequency since the original is minutely
    print("Resampling to hourly frequency...")
    df = df.set_index('timestamp').resample('1h').mean().reset_index()
    
    return df

def prepare_tensors(df: pd.DataFrame, time_col: str, target_col: str, lookback: int, horizon: int):
    # This is a very simplified windowing approach
    features = df.drop(columns=[time_col, target_col]).values
    targets = df[target_col].values
    
    X, Y, Temporal = [], [], []
    for i in range(len(df) - lookback - horizon):
        X.append(targets[i:i+lookback])
        Y.append(targets[i+lookback:i+lookback+horizon])
        Temporal.append(features[i:i+lookback])
        
    # Shape: (B, Lookback, 1)
    X = torch.tensor(np.array(X), dtype=torch.float32).unsqueeze(-1)
    # Shape: (B, Horizon, 1)
    Y = torch.tensor(np.array(Y), dtype=torch.float32).unsqueeze(-1)
    # Shape: (B, Lookback, NumFeatures)
    Temporal = torch.tensor(np.array(Temporal), dtype=torch.float32)
    return X, Y, Temporal

def train():
    args, config = get_args_and_config()
    
    # 1. Set seed
    set_seed(config.get('seed', 42))
    
    tracker = ExperimentTracker(config)
    
    # Setup training log capture
    import sys
    out_dir = os.path.join(tracker.experiment_dir, tracker.experiment_id)
    os.makedirs(out_dir, exist_ok=True)
    log_file = open(os.path.join(out_dir, "training.log"), "w")
    class LoggerWriter:
        def __init__(self, stdout, file):
            self.stdout = stdout
            self.file = file
        def write(self, message):
            self.stdout.write(message)
            self.file.write(message)
            self.file.flush()
        def flush(self):
            self.stdout.flush()
            self.file.flush()
    sys.stdout = LoggerWriter(sys.stdout, log_file)
    
    # 2. Data Validation & Feature Engineering
    data_path = os.path.join(os.path.dirname(__file__), "..", "data", "household_power_consumption.txt")
    limit = config['training'].get('limit_rows', 10000) # Process 10k hourly rows by default to save time in tests
    # Note: limit in read_csv applies to raw minutely data, so 600,000 minutely = 10,000 hourly rows.
    df = load_real_data(data_path, limit_rows=limit * 60) 
    
    # We choose interpolate strategy for missing timestamps/NaNs
    missing_strategy = config['training'].get('missing_strategy', 'interpolate')
    pipeline = FeaturePipeline(time_col='timestamp', target_cols=['gap'])
    
    # Split into train/val
    train_size = int(len(df) * 0.8)
    train_df = df.iloc[:train_size].copy()
    val_df = df.iloc[train_size:].copy()
    
    # Validate leakage
    pipeline.validator.check_leakage(train_df, val_df)
    
    # Fit transform train, transform val
    print(f"Fitting pipeline on train data (strategy: {missing_strategy})...")
    train_processed = pipeline.fit_transform(train_df, freq='1h', missing_strategy=missing_strategy)
    val_processed = pipeline.transform(val_df, freq='1h', missing_strategy=missing_strategy)
    
    lookback = config['model']['lookback']
    horizon = config['model']['forecast_horizon']
    
    X_train, Y_train, Temp_train = prepare_tensors(train_processed, 'timestamp', 'gap', lookback, horizon)
    X_val, Y_val, Temp_val = prepare_tensors(val_processed, 'timestamp', 'gap', lookback, horizon)
    
    train_loader = DataLoader(TensorDataset(X_train, Y_train, Temp_train), batch_size=config['data']['batch_size'], shuffle=True)
    val_loader = DataLoader(TensorDataset(X_val, Y_val, Temp_val), batch_size=config['data']['batch_size'])
    
    # 3. Setup Model
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    config['model']['num_targets'] = 1 # Force for mock data
    config['model']['d_temporal'] = Temp_train.shape[-1]
    model_name = config['model']['name']
    if model_name == 'Autoformer':
        model = Autoformer(config['model'])
    elif model_name == 'Hybrid_v2':
        model = Hybrid_v2(config['model'])
    elif model_name == 'iTransformer':
        model = iTransformer(config['model'])
    else:
        model = NaivePersistence(horizon, config['model'].get('num_targets', 1))
        
    model.to(device)
    
    # 4. Setup Loss & Optimizer
    criterion = nn.HuberLoss() if config['training']['loss'] == 'huber' else nn.MSELoss()
    print(f"Total trainable parameters: {sum(p.numel() for p in model.parameters() if p.requires_grad)}")
    metadata = {
        "device": str(device),
        "trainable_parameters": sum(p.numel() for p in model.parameters() if p.requires_grad),
        "model_size_mb": sum(p.element_size() * p.nelement() for p in model.parameters()) / (1024 * 1024)
    }
    
    # 4. Optimizer and Loss
    optimizer = optim.Adam(model.parameters(), lr=float(config['training'].get('learning_rate', 1e-3)), weight_decay=float(config['training'].get('weight_decay', 1e-4)))
                            
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=config['training'].get('lr_patience', 3), factor=0.5)
    scaler = GradScaler(enabled=config['training'].get('mixed_precision', False))
    
    # 5. Training Loop
    best_val_loss = float('inf')
    best_epoch = 0
    patience = config['training'].get('early_stopping_patience', 10)
    patience_counter = 0
    
    total_train_time = 0
    total_val_time = 0
    epochs_run = 0

    print("Starting training loop...")
    for epoch in range(config['training'].get('epochs', 100)):
        epochs_run += 1
        model.train()
        train_loss = 0.0
        
        epoch_start_time = time.time()
        for batch_x, batch_y, batch_temp in train_loader:
            batch_x, batch_y, batch_temp = batch_x.to(device), batch_y.to(device), batch_temp.to(device)
            optimizer.zero_grad()
            
            with autocast(enabled=config['training'].get('mixed_precision', False)):
                output = model(batch_x, batch_temp)
                loss = criterion(output, batch_y)
                
            scaler.scale(loss).backward()
            nn.utils.clip_grad_norm_(model.parameters(), config['training'].get('gradient_clipping', 1.0))
            scaler.step(optimizer)
            scaler.update()
            
            train_loss += loss.item()
            
        train_loss /= len(train_loader)
        total_train_time += time.time() - epoch_start_time
            
        # Validation
        val_start_time = time.time()
        model.eval()
        val_loss = 0.0
        all_preds = []
        all_trues = []
        
        with torch.no_grad():
            for batch_x, batch_y, batch_temp in val_loader:
                batch_x, batch_y, batch_temp = batch_x.to(device), batch_y.to(device), batch_temp.to(device)
                with autocast(enabled=config['training'].get('mixed_precision', False)):
                    output = model(batch_x, batch_temp)
                    loss = criterion(output, batch_y)
                val_loss += loss.item()
                all_preds.append(output)
                all_trues.append(batch_y)
                
        val_loss /= len(val_loader)
        total_val_time += time.time() - val_start_time
        scheduler.step(val_loss)
        
        print(f"Epoch {epoch+1} | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f}")
        
        # Calculate full metrics on validation set
        y_pred = torch.cat(all_preds, dim=0).detach().cpu().numpy()
        y_true = torch.cat(all_trues, dim=0).detach().cpu().numpy()
        
        # Inverse transform to compute metrics on real kW values
        orig_shape = y_pred.shape
        y_pred_inv = pipeline.scaler.inverse_transform(y_pred.reshape(-1, len(pipeline.target_cols))).reshape(orig_shape)
        y_true_inv = pipeline.scaler.inverse_transform(y_true.reshape(-1, len(pipeline.target_cols))).reshape(orig_shape)
        
        num_samples = len(y_pred)
        num_batches = len(val_loader)
        
        val_metrics = compute_metrics(
            y_true_inv, 
            y_pred_inv, 
            inference_time_total=total_val_time, 
            num_samples=num_samples, 
            num_batches=num_batches
        )
        val_metrics["train_loss"] = train_loss
        val_metrics["val_loss"] = val_loss
        val_metrics["lr"] = optimizer.param_groups[0]['lr']
        
        tracker.log_metrics(val_metrics, epoch)
        
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_epoch = epoch + 1
            tracker.save_checkpoint(model, optimizer, epoch, val_loss)
            patience_counter = 0
        else:
            patience_counter += 1
            
        if patience_counter >= patience:
            print(f"Early stopping triggered at epoch {epoch+1}.")
            metadata['early_stopping_epoch'] = epoch + 1
            break
            
    metadata['total_epochs_run'] = epochs_run
    metadata['best_epoch'] = best_epoch
    metadata['total_train_time_sec'] = total_train_time
    metadata['total_val_time_sec'] = total_val_time
    tracker.metrics["metadata"] = metadata
    
    # Final evaluation and saving artifacts
    out_dir = os.path.join(tracker.experiment_dir, tracker.experiment_id)
    os.makedirs(out_dir, exist_ok=True)
    
    # Save Model
    model_path = os.path.join(out_dir, "model.pt")
    model.save(model_path)
    
    # Save Pipeline (preprocessing/scaler)
    pipeline_path = os.path.join(out_dir, "pipeline.pkl")
    pipeline.save(pipeline_path)
    
    # Calculate Model Fingerprint (SHA-256)
    hasher = hashlib.sha256()
    with open(model_path, 'rb') as f:
        hasher.update(f.read())
    model_fingerprint = hasher.hexdigest()
    
    # Save feature columns
    import json
    with open(os.path.join(out_dir, "feature_columns.json"), "w") as f:
        json.dump(pipeline.feature_columns, f, indent=4)
        
    # Save summary.json
    summary = {
        "experiment_id": tracker.experiment_id,
        "model_name": model_name,
        "model_fingerprint": model_fingerprint,
        "pipeline_version": "1.0", # Can be bumped as feature sets evolve
        "feature_set": pipeline.feature_columns,
        "lookback": lookback,
        "horizon": horizon,
        "metrics": val_metrics,
        "metadata": metadata
    }
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=4)
        
    # Save config and finalize tracking
    tracker.config['out_dir'] = out_dir
    tracker.end_experiment(final_metrics=val_metrics, save_dir=out_dir)

    # --- Verification Phase (Phase 2.5) ---
    print("\n--- Running Serialization Verification ---")
    
    # 1. Verify Pipeline save/load
    loaded_pipeline = FeaturePipeline(time_col='timestamp', target_cols=['gap'])
    loaded_pipeline.load(pipeline_path)
    
    # Transform on a small sample to check
    sample_df = val_df.iloc[:20].copy()
    missing_strategy = config['training'].get('missing_strategy', 'interpolate')
    feat_original = pipeline.transform(sample_df, validate=False, missing_strategy=missing_strategy)
    feat_loaded = loaded_pipeline.transform(sample_df, validate=False, missing_strategy=missing_strategy)
    
    # The arrays should match exactly
    if not np.allclose(feat_original['gap'].values, feat_loaded['gap'].values, equal_nan=True):
        print("WARNING: Pipeline serialization mismatch!")
    else:
        print("Pipeline save/load verification: PASSED")
        
    # 2. Verify Model save/load
    # Re-instantiate the model to check
    if model_name == 'Autoformer':
        loaded_model = Autoformer(config['model']).to(device)
    elif model_name == 'iTransformer':
        loaded_model = iTransformer(config['model']).to(device)
    elif model_name == 'Hybrid_v2':
        loaded_model = Hybrid_v2(config['model']).to(device)
    else:
        loaded_model = NaivePersistence(config['model']).to(device)
        
    loaded_model.load(model_path, device)
    
    # Run prediction
    model.eval()
    sample_x, sample_temp = batch_x[:2], batch_temp[:2]
    pred_original = model.predict(sample_x, sample_temp)
    pred_loaded = loaded_model.predict(sample_x, sample_temp)
    
    if not torch.allclose(pred_original, pred_loaded, atol=1e-6):
        print("WARNING: Model serialization mismatch!")
    else:
        print("Model save/load verification: PASSED")
        
    print("\nTraining completed successfully!")

if __name__ == "__main__":
    train()
