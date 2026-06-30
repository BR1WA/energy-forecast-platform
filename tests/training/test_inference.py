import os
import torch
import pandas as pd
import numpy as np
import pytest

from training.features.feature_engineering import FeaturePipeline
from training.train import prepare_tensors
from training.models.hybrid_v2 import Hybrid_v2

def test_end_to_end_inference(tmp_path):
    # 1. Create a dummy configuration
    config = {
        'model': {
            'lookback': 48,
            'forecast_horizon': 24,
            'num_targets': 1,
            'd_model': 16,
            'd_channel': 32,
            'd_temporal': 4
        }
    }
    
    # 2. Create mock raw dataset (simulating reading from CSV)
    rows = 200
    dates = pd.date_range(start="2026-01-01", periods=rows, freq='h')
    raw_df = pd.DataFrame({
        'timestamp': dates,
        'gap': np.random.uniform(2.0, 5.0, rows) + np.sin(np.arange(rows) * (2 * np.pi / 24))
    })
    
    # 3. Initialize FeaturePipeline and Model
    pipeline = FeaturePipeline(time_col='timestamp', target_cols=['gap'])
    model = Hybrid_v2(config['model'])
    model.eval()
    
    # 4. End-to-End Inference flow
    # A. Validation & Processing
    # We fit the pipeline (simulating loading a pre-fitted one)
    processed_df = pipeline.fit_transform(raw_df, freq='1h', missing_strategy='fail')
    
    # B. Tensor Preparation (simulating inference batching)
    lookback = config['model']['lookback']
    horizon = config['model']['forecast_horizon']
    
    # Normally we'd only take the last 'lookback' steps for inference
    # We use prepare_tensors to generate sequences
    x, y, temp = prepare_tensors(processed_df, 'timestamp', 'gap', lookback, horizon)
    
    # C. Inference
    with torch.no_grad():
        preds = model.predict(x, temp)
        
    # 5. Assertions
    # preds should be of shape (batch, horizon, num_targets)
    assert preds.shape[0] == x.shape[0]
    assert preds.shape[1] == horizon
    assert preds.shape[2] == config['model']['num_targets']
    
    # Verify no NaNs in predictions
    assert not torch.isnan(preds).any()
