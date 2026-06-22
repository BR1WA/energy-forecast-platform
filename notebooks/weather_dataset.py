import os
import pandas as pd
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler

class ExogenousEnergyDataset(Dataset):
    """Custom Sliding Window Dataset incorporating Exogenous Weather Features"""
    def __init__(self, targets, weather, stamps, lookback, horizon):
        self.targets = targets
        self.weather = weather
        self.stamps = stamps
        self.lookback = lookback
        self.horizon = horizon

    def __len__(self):
        return len(self.targets) - self.lookback - self.horizon + 1

    def __getitem__(self, idx):
        x_t = self.targets[idx : idx + self.lookback]
        x_w = self.weather[idx : idx + self.lookback]
        y_t = self.targets[idx + self.lookback : idx + self.lookback + self.horizon]
        
        stamp_x = self.stamps[idx : idx + self.lookback]
        hour = stamp_x.hour.values
        dayofweek = stamp_x.dayofweek.values
        month = stamp_x.month.values - 1 # 0-indexed for embeddings
        
        temporal = np.stack([hour, dayofweek, month], axis=1)
        
        return (torch.tensor(x_t, dtype=torch.float32),
                torch.tensor(x_w, dtype=torch.float32),
                torch.tensor(y_t, dtype=torch.float32),
                torch.tensor(temporal, dtype=torch.long))

def prepare_weather_dataloaders(targets_csv_path, weather_csv_path, lookback, horizon, batch_size=32):
    print(f"Loading energy dataset from {targets_csv_path}...")
    df_t = pd.read_csv(targets_csv_path, sep=';', na_values=['?'], dtype={'Date': str, 'Time': str})
    
    print("Parsing datetime index...")
    df_t['Datetime'] = pd.to_datetime(df_t['Date'] + ' ' + df_t['Time'], format='%d/%m/%Y %H:%M:%S')
    df_t = df_t.drop(columns=['Date', 'Time']).set_index('Datetime')
    
    target_cols = [
        'Global_active_power', 'Global_reactive_power', 'Voltage',
        'Global_intensity', 'Sub_metering_1', 'Sub_metering_2', 'Sub_metering_3'
    ]
    df_t[target_cols] = df_t[target_cols].astype(float).ffill().bfill()
    
    print("Resampling energy data to hourly means...")
    df_t_hourly = df_t[target_cols].resample('h').mean().ffill().bfill()
    
    print(f"Loading weather dataset from {weather_csv_path}...")
    df_w = pd.read_csv(weather_csv_path, parse_dates=['Datetime']).set_index('Datetime')
    weather_cols = ['Temperature', 'Humidity', 'WindSpeed']
    df_w = df_w[weather_cols].ffill().bfill()
    
    print("Merging datasets on Datetime index...")
    df_merged = df_t_hourly.join(df_w, how='inner').ffill().bfill()
    print(f"Merged hourly dataset has {len(df_merged)} total records.")
    
    # Chronological Split (80% Train, 20% Val)
    split_idx = int(len(df_merged) * 0.8)
    train_df = df_merged.iloc[:split_idx]
    val_df = df_merged.iloc[split_idx:]
    
    # Scale weather covariates globally (fit strictly on train)
    print("Scaling weather features...")
    weather_scaler = StandardScaler()
    train_w_scaled = weather_scaler.fit_transform(train_df[weather_cols].values)
    val_w_scaled = weather_scaler.transform(val_df[weather_cols].values)
    
    # Scale target variables globally (fit strictly on train)
    print("Scaling target features...")
    target_scaler = StandardScaler()
    train_t_scaled = target_scaler.fit_transform(train_df[target_cols].values)
    val_t_scaled = target_scaler.transform(val_df[target_cols].values)
    
    train_stamps = train_df.index
    val_stamps = val_df.index
    
    train_dataset = ExogenousEnergyDataset(train_t_scaled, train_w_scaled, train_stamps, lookback, horizon)
    val_dataset = ExogenousEnergyDataset(val_t_scaled, val_w_scaled, val_stamps, lookback, horizon)
    
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=2, pin_memory=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=2, pin_memory=True)
    
    return train_loader, val_loader, target_scaler, weather_scaler
