import os
import json
import torch
import numpy as np
import pandas as pd
import yaml
from torch.utils.data import DataLoader, TensorDataset

# Make sure we can import from the project root
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from training.features.feature_engineering import FeaturePipeline
from training.utils.metrics import compute_metrics
from training.models.hybrid_v2 import Hybrid_v2
from training.models.itransformer import iTransformer
from training.models.baseline import NaivePersistence
from training.train import load_real_data, prepare_tensors

def recompute():
    # Load dataset
    data_path = os.path.join(os.path.dirname(__file__), "..", "data", "household_power_consumption.txt")
    limit = 10000
    df = load_real_data(data_path, limit_rows=limit * 60)
    
    train_size = int(len(df) * 0.8)
    val_df = df.iloc[train_size:].copy()
    
    experiments_dir = "experiments"
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    report = ["| Model | Old MAE | New MAE | Old RMSE | New RMSE | Old MAPE | New MAPE | Old R2 | New R2 |", 
              "|---|---|---|---|---|---|---|---|---|"]
    
    for exp_name in os.listdir(experiments_dir):
        exp_path = os.path.join(experiments_dir, exp_name)
        if not os.path.isdir(exp_path):
            continue
            
        config_path = os.path.join(exp_path, "config.yaml")
        metrics_path = os.path.join(exp_path, "metrics.json")
        pipeline_path = os.path.join(exp_path, "pipeline.pkl")
        model_path = os.path.join(exp_path, "model.pt")
        
        if not all(os.path.exists(p) for p in [config_path, metrics_path, pipeline_path, model_path]):
            continue
            
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            
        with open(metrics_path, 'r') as f:
            old_metrics_data = json.load(f)
            old_metrics = old_metrics_data.get("final", {})
            if "mae" not in old_metrics:
                old_metrics = old_metrics_data.get("metrics", {}).get("final", {})
                
        # Load pipeline
        pipeline = FeaturePipeline(time_col='timestamp', target_cols=['gap'])
        pipeline.load(pipeline_path)
        
        # Transform val data
        missing_strat = config.get("training", {}).get("missing_strategy", "interpolate")
        val_processed = pipeline.transform(val_df, freq='1h', missing_strategy=missing_strat)
        
        lookback = config["model"]["lookback"]
        horizon = config["model"]["forecast_horizon"]
        
        X_val, Y_val, Temp_val = prepare_tensors(val_processed, 'timestamp', 'gap', lookback, horizon)
        val_loader = DataLoader(TensorDataset(X_val, Y_val, Temp_val), batch_size=config.get("data", {}).get("batch_size", 64), shuffle=False)
        
        # Load model
        arch = config["model"].get("architecture", "Hybrid_v2")
        if arch == "Hybrid_v2":
            model = Hybrid_v2(config["model"])
        elif arch == "iTransformer":
            model = iTransformer(config["model"])
        else:
            continue
            
        model.load_state_dict(torch.load(model_path, map_location=device, weights_only=True))
        model.to(device)
        model.eval()
        
        all_preds = []
        all_trues = []
        
        with torch.no_grad():
            for batch_x, batch_y, batch_temp in val_loader:
                batch_x = batch_x.to(device)
                batch_temp = batch_temp.to(device)
                output = model(batch_x, batch_temp)
                all_preds.append(output.cpu())
                all_trues.append(batch_y)
                
        y_pred = torch.cat(all_preds, dim=0).numpy()
        y_true = torch.cat(all_trues, dim=0).numpy()
        
        orig_shape = y_pred.shape
        y_pred_inv = pipeline.scaler.inverse_transform(y_pred.reshape(-1, 1)).reshape(orig_shape)
        y_true_inv = pipeline.scaler.inverse_transform(y_true.reshape(-1, 1)).reshape(orig_shape)
        
        new_metrics = compute_metrics(
            y_true_inv, 
            y_pred_inv
        )
        
        # Update metrics.json
        old_metrics_data["final_unscaled"] = new_metrics
        with open(metrics_path, 'w') as f:
            json.dump(old_metrics_data, f, indent=4)
            
        report.append(f"| {exp_name[:20]}... | {old_metrics.get('mae', 0):.4f} | {new_metrics.get('mae', 0):.4f} | {old_metrics.get('rmse', 0):.4f} | {new_metrics.get('rmse', 0):.4f} | {old_metrics.get('mape', 0):.4f}% | {new_metrics.get('mape', 0):.4f}% | {old_metrics.get('r2', 0):.4f} | {new_metrics.get('r2', 0):.4f} |")
        
    print("\n".join(report))

if __name__ == "__main__":
    recompute()
