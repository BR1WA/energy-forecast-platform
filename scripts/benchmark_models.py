import os
import sys
import yaml
import json
import time
import torch
import numpy as np
import pandas as pd
from torch.utils.data import Dataset, DataLoader
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
import inspect
import pickle

backend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend")
sys.path.append(backend_dir)
from app.ml.model_registry import get_model_class

LOOKBACK = 96
HORIZON = 24
BATCH_SIZE = 128
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

class TimeSeriesDataset(Dataset):
    def __init__(self, targets_raw, targets_scaled, calendar, lookback, horizon):
        self.targets_raw = targets_raw
        self.targets_scaled = targets_scaled
        self.calendar = calendar
        self.lookback = lookback
        self.horizon = horizon
        
    def __len__(self):
        return len(self.targets_raw) - self.lookback - self.horizon + 1
        
    def __getitem__(self, idx):
        x_raw = self.targets_raw[idx : idx + self.lookback]
        x_scaled = self.targets_scaled[idx : idx + self.lookback]
        x_calendar = self.calendar[idx : idx + self.lookback]
        y_raw = self.targets_raw[idx + self.lookback : idx + self.lookback + self.horizon]
        y_scaled = self.targets_scaled[idx + self.lookback : idx + self.lookback + self.horizon]
        
        return (torch.FloatTensor(x_raw), 
                torch.FloatTensor(x_scaled), 
                torch.FloatTensor(x_calendar), 
                torch.FloatTensor(y_raw),
                torch.FloatTensor(y_scaled))

def get_cyclical_calendar_features(df_index):
    hours = df_index.hour.values
    days = df_index.dayofweek.values
    months = df_index.month.values
    
    hour_sin = np.sin(2 * np.pi * hours / 24.0)
    hour_cos = np.cos(2 * np.pi * hours / 24.0)
    day_sin = np.sin(2 * np.pi * days / 7.0)
    day_cos = np.cos(2 * np.pi * days / 7.0)
    month_sin = np.sin(2 * np.pi * months / 12.0)
    month_cos = np.cos(2 * np.pi * months / 12.0)
    
    calendar_feats = np.stack([hour_sin, hour_cos, day_sin, day_cos, month_sin, month_cos], axis=1)
    return calendar_feats

def load_and_preprocess_data(filepath):
    print(f"Loading data from {filepath}...")
    df = pd.read_csv(filepath, sep=';', na_values=['?'], dtype={'Date': str, 'Time': str})
    df = df.dropna()
    df['Datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='%d/%m/%Y %H:%M:%S')
    df = df.drop(columns=['Date', 'Time']).set_index('Datetime')
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df_h = df.resample('h').mean()
    df_h = df_h.ffill().bfill()
    print(f"Hourly shape: {df_h.shape}")
    return df_h

def evaluate_model(model, loader, scaler_obj, is_raw_model):
    model.eval()
    model.to(DEVICE)
    
    all_preds_scaled = []
    all_preds_unscaled = []
    all_actuals_scaled = []
    all_actuals_unscaled = []
    
    start_time = time.time()
    
    with torch.no_grad():
        for x_raw, x_scaled, x_cal, y_raw, y_scaled in loader:
            x_raw, x_scaled, x_cal = x_raw.to(DEVICE), x_scaled.to(DEVICE), x_cal.to(DEVICE)
            
            if is_raw_model:
                preds = model(x_raw, x_cal)
                preds_np = preds.cpu().numpy()
                all_preds_unscaled.append(preds_np)
                all_actuals_unscaled.append(y_raw.numpy())
                
                N, H, C = preds_np.shape
                preds_scaled = scaler_obj.transform(preds_np.reshape(-1, C)).reshape(N, H, C)
                all_preds_scaled.append(preds_scaled)
                all_actuals_scaled.append(y_scaled.numpy())
            else:
                preds = model(x_scaled)
                preds_np = preds.cpu().numpy()
                
                all_preds_scaled.append(preds_np)
                all_actuals_scaled.append(y_scaled.numpy())
                
                N, H, C = preds_np.shape
                preds_kw = scaler_obj.inverse_transform(preds_np.reshape(-1, C)).reshape(N, H, C)
                all_preds_unscaled.append(preds_kw)
                all_actuals_unscaled.append(y_raw.numpy())
                
    end_time = time.time()
    latency = (end_time - start_time) / len(loader.dataset) * 1000 # ms per sample
                
    preds_scaled = np.concatenate(all_preds_scaled, axis=0)
    actuals_scaled = np.concatenate(all_actuals_scaled, axis=0)
    preds_unscaled = np.concatenate(all_preds_unscaled, axis=0)
    actuals_unscaled = np.concatenate(all_actuals_unscaled, axis=0)
    
    # GAP is index 0
    y_true_s = actuals_scaled[:, :, 0].flatten()
    y_pred_s = preds_scaled[:, :, 0].flatten()
    y_true_u = actuals_unscaled[:, :, 0].flatten()
    y_pred_u = preds_unscaled[:, :, 0].flatten()
    
    mae_u = mean_absolute_error(y_true_u, y_pred_u)
    rmse_u = np.sqrt(mean_squared_error(y_true_u, y_pred_u))
    r2_unscaled = r2_score(y_true_u, y_pred_u)
    
    return {
        "mae": float(mae_u),
        "rmse": float(rmse_u),
        "r2": float(r2_unscaled),
        "latency_ms": float(latency)
    }

def main():
    data_path = 'data/household_power_consumption.txt'
    if not os.path.exists(data_path):
        print(f"Data file not found: {data_path}. Please download it.")
        sys.exit(1)
        
    df_h = load_and_preprocess_data(data_path)
    calendar_features = get_cyclical_calendar_features(df_h.index)
    
    target_cols = ['Global_active_power', 'Global_reactive_power', 'Voltage', 'Global_intensity', 
                   'Sub_metering_1', 'Sub_metering_2', 'Sub_metering_3']

    # Test set is 2010+
    test_mask = df_h.index >= '2010-01-01'
    df_test = df_h.loc[test_mask]
    test_raw = df_test[target_cols].values
    test_cal = calendar_features[test_mask]

    experiments_dir = os.path.join(backend_dir, "experiments")
    
    results = {}
    
    for exp_name in sorted(os.listdir(experiments_dir)):
        exp_path = os.path.join(experiments_dir, exp_name)
        if not os.path.isdir(exp_path):
            continue
            
        print(f"\nBenchmarking {exp_name}...")
        
        # Load scaler
        try:
            with open(os.path.join(exp_path, 'pipeline.pkl'), 'rb') as f:
                pipeline_data = pickle.load(f)
                scaler_obj = pipeline_data['scaler']
        except Exception as e:
            print(f"  Skipping {exp_name}, could not load pipeline.pkl: {e}")
            continue
            
        test_scaled = scaler_obj.transform(test_raw)
        
        # Load config
        with open(os.path.join(exp_path, "config.yaml")) as f:
            config = yaml.safe_load(f)
            
        arch_name = config.get("architecture", {}).get("name") or config.get("model", {}).get("name")
        ModelClass = get_model_class(arch_name)
        
        model_kwargs = config.get("architecture", config.get("model", {}))
        if isinstance(model_kwargs, dict) and "name" in model_kwargs:
            model_kwargs = model_kwargs.copy()
            del model_kwargs["name"]
            
        if arch_name in ("Hybrid_v2", "HybridV2", "iTransformer"):
            model = ModelClass(config.get("model", {}))
        else:
            sig = inspect.signature(ModelClass.__init__)
            valid_keys = set(sig.parameters.keys())
            filtered_kwargs = {k: v for k, v in model_kwargs.items() if k in valid_keys}
            model = ModelClass(**filtered_kwargs)
            
        weights_path = os.path.join(exp_path, "model.pt")
        state_dict = torch.load(weights_path, map_location=DEVICE, weights_only=True)
        if isinstance(state_dict, dict) and "model_state_dict" in state_dict:
            state_dict = state_dict["model_state_dict"]
        elif hasattr(state_dict, "state_dict"):
            state_dict = state_dict.state_dict()
            
        model.load_state_dict(state_dict, strict=False)
        
        test_dataset = TimeSeriesDataset(test_raw, test_scaled, test_cal, LOOKBACK, HORIZON)
        test_loader = DataLoader(test_dataset, batch_size=BATCH_SIZE, shuffle=False)
        
        is_raw_model = arch_name not in ("CNN-BiLSTM", "CNN_BiLSTM") # Transformers take raw usually
        
        try:
            metrics = evaluate_model(model, test_loader, scaler_obj, is_raw_model)
            print(f"  Result: {metrics}")
            results[exp_name] = metrics
            
            # Optionally update metrics.json inside the experiment
            metrics_path = os.path.join(exp_path, "metrics.json")
            if os.path.exists(metrics_path):
                with open(metrics_path, "r") as f:
                    exp_metrics = json.load(f)
                if "final_unscaled" not in exp_metrics:
                    exp_metrics["final_unscaled"] = {}
                exp_metrics["final_unscaled"]["mae"] = metrics["mae"]
                exp_metrics["final_unscaled"]["rmse"] = metrics["rmse"]
                exp_metrics["final_unscaled"]["r2"] = metrics["r2"]
                exp_metrics["latency_ms"] = metrics["latency_ms"]
                
                with open(metrics_path, "w") as f:
                    json.dump(exp_metrics, f, indent=4)
                    
        except Exception as e:
            print(f"  Failed to evaluate: {e}")
            
    with open("benchmark_report.json", "w") as f:
        json.dump(results, f, indent=4)
        
    print("\nBenchmark completed. Report saved to benchmark_report.json")

if __name__ == "__main__":
    main()
