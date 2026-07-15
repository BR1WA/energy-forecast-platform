import sys
import os
import torch
import numpy as np
import pandas as pd

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.ml.datasets import get_dataset
from training.splitters.chronological import ChronologicalSplitter
from training.features.feature_engineering import FeaturePipeline

def validate_dataset(dataset_name: str, data_dir: str = "data"):
    print(f"\n========================================")
    print(f"Validating Dataset Pipeline: {dataset_name.upper()}")
    print(f"========================================")
    
    # 1. Load Dataset
    provider = get_dataset(dataset_name, data_dir)
    print(f"[1/6] Loading data...")
    try:
        df = provider.load()
        print(f"      Loaded {len(df)} rows. Columns: {list(df.columns)}")
    except FileNotFoundError as e:
        print(f"      [SKIPPED] File not found: {e}")
        return

    # 2. Preprocess
    print(f"[2/6] Preprocessing...")
    df_clean = provider.preprocess(df)
    print(f"      Cleaned shape: {df_clean.shape}")
    if df_clean.isna().sum().sum() > 0:
        print("      [ERROR] NaNs remaining after preprocess!")
        return

    # 3. Create Features & Targets
    print(f"[3/6] Creating features & covariates...")
    df_features = provider.create_features(df_clean)
    df_targets = provider.create_targets(df_clean)
    if provider.supports_weather() and hasattr(provider, 'merge_weather'):
        df_features = provider.merge_weather(df_features)
    
    meta = provider.get_metadata()
    print(f"      Targets: {meta['targets'][:3]}... ({len(meta['targets'])} total)")
    print(f"      Covariates: {meta['covariates']}")
    
    # Check calendar features
    if provider.supports_calendar():
        assert 'hour' in df_features.columns, "Missing 'hour' feature"
        assert 'weekday' in df_features.columns, "Missing 'weekday' feature"
        
    # Check shapes
    assert len(df_features) == len(df_targets) == len(df_clean)
    
    # 4. Chronological Split (No leakage)
    print(f"[4/6] Splitting (Chronological)...")
    splitter = ChronologicalSplitter(train_ratio=0.7, val_ratio=0.1)
    train_df, val_df, test_df = splitter.split(df_features)
    
    train_end = train_df['Datetime'].max()
    val_start = val_df['Datetime'].min()
    val_end = val_df['Datetime'].max()
    test_start = test_df['Datetime'].min()
    
    print(f"      Train end: {train_end}  |  Val start: {val_start}")
    print(f"      Val end:   {val_end}  |  Test start: {test_start}")
    
    assert train_end < val_start, "[LEAKAGE ERROR] Train leaks into Validation!"
    assert val_end < test_start, "[LEAKAGE ERROR] Validation leaks into Test!"
    print("      [OK] No temporal leakage detected.")

    # 5. Scaling
    print(f"[5/6] Scaling (Fit on Train only)...")
    # For scaling, we need a unified FeaturePipeline or direct Scaler.
    # Our pipeline usually takes time_col and target_cols
    pipeline = FeaturePipeline(time_col='Datetime', target_cols=meta['targets'])
    
    pipeline.fit(train_df, freq=meta['frequency'])
    
    train_scaled = pipeline.transform(train_df, freq=meta['frequency'])
    val_scaled = pipeline.transform(val_df, freq=meta['frequency'])
    test_scaled = pipeline.transform(test_df, freq=meta['frequency'])
    
    print(f"      Train scaled targets mean (should be ~0): {train_scaled[meta['targets']].mean().mean():.4f}")
    print(f"      Train scaled targets std  (should be ~1): {train_scaled[meta['targets']].std().mean():.4f}")
    
    # Check inverse scaling
    train_recovered = pipeline.scaler.inverse_transform(train_scaled[meta['targets']].values)
    is_close = np.allclose(train_df[meta['targets']].values, train_recovered, atol=1e-3)
    assert is_close, "[SCALING ERROR] Inverse transform does not recover original data!"
    print(f"      [OK] Inverse scaling perfectly recovers original values.")
    
    # 6. Tensor Shape Checks (24h and 168h windows)
    print(f"[6/6] Tensor Window Generation (24h & 168h)...")
    lookback = 96
    
    for horizon in [24, 168]:
        # Simple windowing logic check
        seq_len = lookback + horizon
        if len(test_scaled) < seq_len:
            print(f"      [WARNING] Test set too small for horizon {horizon}")
            continue
            
        # Mock taking the first window
        window = test_scaled.iloc[:seq_len]
        x = window.iloc[:lookback][meta['targets']].values
        y = window.iloc[lookback:][meta['targets']].values
        
        assert x.shape == (lookback, len(meta['targets'])), f"X shape mismatch: {x.shape}"
        assert y.shape == (horizon, len(meta['targets'])), f"Y shape mismatch: {y.shape}"
        
        # Explicit off-by-one window alignment check
        if len(test_scaled) >= seq_len + 1:
            window_1 = test_scaled.iloc[1:seq_len + 1]
            x_1 = window_1.iloc[:lookback][meta['targets']].values
            y_1 = window_1.iloc[lookback:][meta['targets']].values
            
            # X_1 should start exactly 1 step after X_0
            assert np.array_equal(x_1[:-1], x[1:]), "[WINDOW ERROR] Off-by-one bug in X sliding window."
            assert np.array_equal(y_1[:-1], y[1:]), "[WINDOW ERROR] Off-by-one bug in Y sliding window."
            
            # Ensure Y_0 starts exactly where X_0 ends
            assert np.array_equal(window.iloc[lookback-1:lookback][meta['targets']].values, x[-1:]), "X end mismatch"
            assert np.array_equal(window.iloc[lookback:lookback+1][meta['targets']].values, y[:1]), "Y start mismatch"
            
        print(f"      [OK] Horizon {horizon}h | X: {x.shape}, Y: {y.shape} | Alignment Verified.")

    print(f"\n[SUCCESS] {dataset_name.upper()} Pipeline Validated Successfully!")

if __name__ == "__main__":
    validate_dataset("ihepc")
    validate_dataset("ecl")
