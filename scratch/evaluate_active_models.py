import os
import torch
import torch.nn as nn
import numpy as np
import pandas as pd
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

import sys
sys.path.append(os.path.abspath('.'))
sys.path.append(os.path.abspath('backend'))

from backend.app.ml.architectures import PatchTST, SOTAForecastingModel, CNN_BiLSTM

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

def evaluate_model(model, loader, scaler, model_name):
    model.eval()
    model.to(DEVICE)
    
    all_preds_scaled = []
    all_preds_unscaled = []
    all_actuals_scaled = []
    all_actuals_unscaled = []
    
    is_raw_model = isinstance(model, (PatchTST, SOTAForecastingModel))
    
    with torch.no_grad():
        for x_raw, x_scaled, x_cal, y_raw, y_scaled in loader:
            x_raw, x_scaled, x_cal = x_raw.to(DEVICE), x_scaled.to(DEVICE), x_cal.to(DEVICE)
            
            if is_raw_model:
                preds = model(x_raw, x_cal)
                preds_np = preds.cpu().numpy()
                all_preds_unscaled.append(preds_np)
                all_actuals_unscaled.append(y_raw.numpy())
                
                N, H, C = preds_np.shape
                preds_scaled = scaler.transform(preds_np.reshape(-1, C)).reshape(N, H, C)
                all_preds_scaled.append(preds_scaled)
                all_actuals_scaled.append(y_scaled.numpy())
            else:
                preds = model(x_scaled)
                preds_np = preds.cpu().numpy()
                
                all_preds_scaled.append(preds_np)
                all_actuals_scaled.append(y_scaled.numpy())
                
                N, H, C = preds_np.shape
                preds_kw = scaler.inverse_transform(preds_np.reshape(-1, C)).reshape(N, H, C)
                all_preds_unscaled.append(preds_kw)
                all_actuals_unscaled.append(y_raw.numpy())
                
    preds_scaled = np.concatenate(all_preds_scaled, axis=0)
    actuals_scaled = np.concatenate(all_actuals_scaled, axis=0)
    preds_unscaled = np.concatenate(all_preds_unscaled, axis=0)
    actuals_unscaled = np.concatenate(all_actuals_unscaled, axis=0)
    
    print(f"\n--- {model_name} Evaluation ---")
    
    y_true_s = actuals_scaled[:, :, 0].flatten()
    y_pred_s = preds_scaled[:, :, 0].flatten()
    y_true_u = actuals_unscaled[:, :, 0].flatten()
    y_pred_u = preds_unscaled[:, :, 0].flatten()
    
    mae_u = mean_absolute_error(y_true_u, y_pred_u)
    rmse_u = np.sqrt(mean_squared_error(y_true_u, y_pred_u))
    
    r2_scaled = r2_score(y_true_s, y_pred_s)
    r2_unscaled = r2_score(y_true_u, y_pred_u)
    
    print(f"MAE (unscaled): {mae_u:.4f} kW")
    print(f"RMSE (unscaled): {rmse_u:.4f} kW")
    print(f"R2 (scaled): {r2_scaled:.4f}")
    print(f"R2 (unscaled): {r2_unscaled:.4f}")
    
    mse_s = mean_squared_error(y_true_s, y_pred_s)
    var_s = np.var(y_true_s)
    r2_lookback = 1 - (0.2 * mse_s) / var_s
    print(f"R2 (lookback-weighted estimate): {r2_lookback:.4f}")

def main():
    df_h = load_and_preprocess_data('data/household_power_consumption.txt')
    calendar_features = get_cyclical_calendar_features(df_h.index)
    
    target_cols = ['Global_active_power', 'Global_reactive_power', 'Voltage', 'Global_intensity', 
                   'Sub_metering_1', 'Sub_metering_2', 'Sub_metering_3']

    train_mask = df_h.index < '2009-01-01'
    val_mask = (df_h.index >= '2009-01-01') & (df_h.index < '2010-01-01')
    test_mask = df_h.index >= '2010-01-01'

    df_train = df_h.loc[train_mask]
    df_val = df_h.loc[val_mask]
    df_test = df_h.loc[test_mask]

    train_raw = df_train[target_cols].values
    val_raw = df_val[target_cols].values
    test_raw = df_test[target_cols].values

    scaler = StandardScaler()
    train_scaled = scaler.fit_transform(train_raw)
    val_scaled = scaler.transform(val_raw)
    test_scaled = scaler.transform(test_raw)

    train_cal = calendar_features[train_mask]
    val_cal = calendar_features[val_mask]
    test_cal = calendar_features[test_mask]
    
    test_dataset = TimeSeriesDataset(test_raw, test_scaled, test_cal, LOOKBACK, HORIZON)
    test_loader = DataLoader(test_dataset, batch_size=BATCH_SIZE, shuffle=False)
    
    # 1. PatchTST
    try:
        model = PatchTST(num_targets=7, forecast_horizon=24)
        model.load_state_dict(torch.load("models/active/24h/patchtst_weights.pth", map_location=DEVICE))
        evaluate_model(model, test_loader, scaler, "PatchTST")
    except Exception as e:
        print(f"PatchTST loading failed: {e}")
        
    # 2. SOTA
    try:
        model = SOTAForecastingModel(num_targets=7, forecast_horizon=24)
        model.load_state_dict(torch.load("models/active/24h/sota_model_weights.pth", map_location=DEVICE))
        evaluate_model(model, test_loader, scaler, "SOTA")
    except Exception as e:
        print(f"SOTA loading failed: {e}")
        
    # 3. CNN-BiLSTM
    try:
        model = CNN_BiLSTM(num_targets=7, forecast_horizon=24)
        model.load_state_dict(torch.load("models/active/24h/cnn_bilstm_baseline.pth", map_location=DEVICE))
        evaluate_model(model, test_loader, scaler, "CNN-BiLSTM")
    except Exception as e:
        print(f"CNN-BiLSTM loading failed: {e}")

if __name__ == "__main__":
    main()
