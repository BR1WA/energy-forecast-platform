"""
Inference wrapper for the SOTA and CNN-BiLSTM forecasting models.
Handles data intake, calendar encoding, forward pass, and denormalization.
"""
import os
import numpy as np
import pandas as pd
import torch
import joblib
from sota_model import SOTAForecastingModel, CNN_BiLSTM, PatchTST

# Column names matching the training pipeline
TARGET_COLS = [
    'Global_active_power', 'Global_reactive_power', 'Voltage',
    'Global_intensity', 'Sub_metering_1', 'Sub_metering_2', 'Sub_metering_3'
]

# Sub-metering labels for the breakdown module
SUB_METER_LABELS = {
    'Sub_metering_1': {'name': 'Kitchen', 'icon': '🍳', 'desc': 'Dishwasher, oven, microwave'},
    'Sub_metering_2': {'name': 'Laundry', 'icon': '👕', 'desc': 'Washing machine, tumble dryer'},
    'Sub_metering_3': {'name': 'Climate Control', 'icon': '❄️', 'desc': 'Water heater, AC, heating'},
}

# French EDF Tempo tariff rates (€/kWh)
TARIFF_PEAK = 0.1369       # Heures Pleines: 06:00 – 22:00
TARIFF_OFF_PEAK = 0.1056   # Heures Creuses: 22:00 – 06:00

LOOKBACK = 96
HORIZON = 24


def get_cyclical_calendar_features(datetimes):
    """Generate 6 sine/cosine cyclical features from a DatetimeIndex."""
    hours = datetimes.hour.values
    days = datetimes.dayofweek.values
    months = datetimes.month.values

    hour_sin = np.sin(2 * np.pi * hours / 24.0)
    hour_cos = np.cos(2 * np.pi * hours / 24.0)
    day_sin = np.sin(2 * np.pi * days / 7.0)
    day_cos = np.cos(2 * np.pi * days / 7.0)
    month_sin = np.sin(2 * np.pi * months / 12.0)
    month_cos = np.cos(2 * np.pi * months / 12.0)

    return np.stack([hour_sin, hour_cos, day_sin, day_cos, month_sin, month_cos], axis=1)


class AppPredictor:
    """Loads model weights and performs inference for both SOTA and baseline."""

    def __init__(self, weights_dir):
        self.device = torch.device('cpu')
        self.weights_dir = weights_dir
        self.models_loaded = {}

        # Load SOTA model
        sota_path = os.path.join(weights_dir, 'sota_model_weights.pth')
        if os.path.exists(sota_path):
            self.sota_model = SOTAForecastingModel(num_targets=7, forecast_horizon=HORIZON)
            self.sota_model.load_state_dict(
                torch.load(sota_path, map_location=self.device, weights_only=True)
            )
            self.sota_model.eval()
            self.models_loaded['SOTA Model'] = True
        else:
            self.sota_model = None
            self.models_loaded['SOTA Model'] = False

        # Load CNN-BiLSTM baseline
        cnn_path = os.path.join(weights_dir, 'cnn_bilstm_baseline.pth')
        if os.path.exists(cnn_path):
            self.cnn_model = CNN_BiLSTM(num_targets=7, forecast_horizon=HORIZON)
            self.cnn_model.load_state_dict(
                torch.load(cnn_path, map_location=self.device, weights_only=True)
            )
            self.cnn_model.eval()
            self.models_loaded['CNN-BiLSTM'] = True
        else:
            self.cnn_model = None
            self.models_loaded['CNN-BiLSTM'] = False

        # Load PatchTST
        patchtst_path = os.path.join(weights_dir, 'patchtst_weights.pth')
        if os.path.exists(patchtst_path):
            self.patchtst_model = PatchTST(
                num_targets=7, patch_len=16, stride=8, lookback=96,
                d_model=128, n_heads=8, n_layers=3, d_ff=256,
                dropout=0.0, forecast_horizon=HORIZON
            )
            self.patchtst_model.load_state_dict(
                torch.load(patchtst_path, map_location=self.device, weights_only=True)
            )
            self.patchtst_model.eval()
            self.models_loaded['PatchTST'] = True
        else:
            self.patchtst_model = None
            self.models_loaded['PatchTST'] = False

        # Load scaler (needed for CNN-BiLSTM inverse transform)
        scaler_path = os.path.join(weights_dir, 'target_scaler.pkl')
        if os.path.exists(scaler_path):
            self.scaler = joblib.load(scaler_path)
        else:
            self.scaler = None

    def is_ready(self):
        """Check if at least one model is loaded."""
        return any(self.models_loaded.values())

    def get_available_models(self):
        """Return list of loaded model names."""
        return [name for name, loaded in self.models_loaded.items() if loaded]

    def predict_sota(self, df_input):
        """
        Run SOTA model inference.
        Args:
            df_input: DataFrame with 96 rows, 7 target columns, and DatetimeIndex.
        Returns:
            DataFrame with 24 rows of forecasted values (raw kW scale).
        """
        if self.sota_model is None:
            raise RuntimeError("SOTA model weights not loaded.")

        targets = df_input[TARGET_COLS].values.astype(np.float32)
        cal_features = get_cyclical_calendar_features(df_input.index).astype(np.float32)

        x_targets = torch.tensor(targets).unsqueeze(0)   # [1, 96, 7]
        x_calendar = torch.tensor(cal_features).unsqueeze(0)  # [1, 96, 6]

        with torch.no_grad():
            preds = self.sota_model(x_targets, x_calendar)  # [1, 24, 7]

        preds_np = preds.squeeze(0).numpy()
        future_index = pd.date_range(
            start=df_input.index[-1] + pd.Timedelta(hours=1), periods=HORIZON, freq='h'
        )
        return pd.DataFrame(preds_np, index=future_index, columns=TARGET_COLS)

    def predict_baseline(self, df_input):
        """
        Run CNN-BiLSTM baseline inference.
        Args:
            df_input: DataFrame with 96 rows, 7 target columns, and DatetimeIndex.
        Returns:
            DataFrame with 24 rows of forecasted values (raw kW scale).
        """
        if self.cnn_model is None:
            raise RuntimeError("CNN-BiLSTM model weights not loaded.")
        if self.scaler is None:
            raise RuntimeError("Target scaler not loaded.")

        targets = df_input[TARGET_COLS].values.astype(np.float32)
        scaled = self.scaler.transform(targets)
        x_scaled = torch.tensor(scaled).unsqueeze(0)  # [1, 96, 7]

        with torch.no_grad():
            preds_scaled = self.cnn_model(x_scaled)  # [1, 24, 7]

        preds_np = preds_scaled.squeeze(0).numpy()
        preds_kw = self.scaler.inverse_transform(preds_np)

        future_index = pd.date_range(
            start=df_input.index[-1] + pd.Timedelta(hours=1), periods=HORIZON, freq='h'
        )
        return pd.DataFrame(preds_kw, index=future_index, columns=TARGET_COLS)

    def predict_patchtst(self, df_input):
        """
        Run PatchTST inference.
        Args:
            df_input: DataFrame with 96 rows, 7 target columns, and DatetimeIndex.
        Returns:
            DataFrame with 24 rows of forecasted values (raw kW scale).
        """
        if self.patchtst_model is None:
            raise RuntimeError("PatchTST model weights not loaded.")

        targets = df_input[TARGET_COLS].values.astype(np.float32)
        cal_features = get_cyclical_calendar_features(df_input.index).astype(np.float32)

        x_targets = torch.tensor(targets).unsqueeze(0)   # [1, 96, 7]
        x_calendar = torch.tensor(cal_features).unsqueeze(0)  # [1, 96, 6]

        with torch.no_grad():
            preds = self.patchtst_model(x_targets, x_calendar)  # [1, 24, 7]

        preds_np = preds.squeeze(0).numpy()
        future_index = pd.date_range(
            start=df_input.index[-1] + pd.Timedelta(hours=1), periods=HORIZON, freq='h'
        )
        return pd.DataFrame(preds_np, index=future_index, columns=TARGET_COLS)

    def predict(self, df_input, model_name='SOTA Model'):
        """Unified predict interface."""
        if model_name == 'SOTA Model':
            return self.predict_sota(df_input)
        elif model_name == 'CNN-BiLSTM':
            return self.predict_baseline(df_input)
        elif model_name == 'PatchTST':
            return self.predict_patchtst(df_input)
        else:
            raise ValueError(f"Unknown model: {model_name}")

    @staticmethod
    def compute_sub_metering_breakdown(forecast_df):
        """
        Compute 24-hour sub-metering energy breakdown from forecast.
        Returns dict with category name -> total Wh and percentage.
        """
        s1 = forecast_df['Sub_metering_1'].clip(lower=0).sum()
        s2 = forecast_df['Sub_metering_2'].clip(lower=0).sum()
        s3 = forecast_df['Sub_metering_3'].clip(lower=0).sum()

        # "Other" = total active power (kW → Wh * 1000 for hourly) minus metered
        gap_wh = forecast_df['Global_active_power'].clip(lower=0).sum() * 1000.0
        sub_total = s1 + s2 + s3
        other = max(0, gap_wh - sub_total)
        total = sub_total + other

        if total < 1e-6:
            total = 1.0  # avoid division by zero

        breakdown = {
            'Kitchen (Sub 1)': {'wh': s1, 'pct': s1 / total * 100, 'icon': '🍳',
                                'color': '#f59e0b'},
            'Laundry (Sub 2)': {'wh': s2, 'pct': s2 / total * 100, 'icon': '👕',
                                'color': '#3b82f6'},
            'Climate (Sub 3)': {'wh': s3, 'pct': s3 / total * 100, 'icon': '❄️',
                                'color': '#10b981'},
            'Other (Unmetered)': {'wh': other, 'pct': other / total * 100, 'icon': '💡',
                                  'color': '#8b5cf6'},
        }
        return breakdown, total

    @staticmethod
    def compute_cost_estimate(forecast_df):
        """
        Compute estimated electricity cost using French EDF tariffs.
        Returns dict with cost details.
        """
        hours = forecast_df.index.hour
        gap = forecast_df['Global_active_power'].clip(lower=0).values  # kW (hourly mean = kWh)

        peak_mask = (hours >= 6) & (hours < 22)
        off_peak_mask = ~peak_mask

        peak_kwh = gap[peak_mask].sum()
        off_peak_kwh = gap[off_peak_mask].sum()
        total_kwh = peak_kwh + off_peak_kwh

        peak_cost = peak_kwh * TARIFF_PEAK
        off_peak_cost = off_peak_kwh * TARIFF_OFF_PEAK
        total_cost = peak_cost + off_peak_cost

        # Find peak hour
        peak_hour_idx = np.argmax(gap)
        peak_hour = hours[peak_hour_idx]
        peak_kw = gap[peak_hour_idx]

        # Savings estimate: shift 1 kWh from peak to off-peak
        savings_per_kwh = TARIFF_PEAK - TARIFF_OFF_PEAK

        return {
            'total_kwh': total_kwh,
            'peak_kwh': peak_kwh,
            'off_peak_kwh': off_peak_kwh,
            'total_cost': total_cost,
            'peak_cost': peak_cost,
            'off_peak_cost': off_peak_cost,
            'peak_hour': int(peak_hour),
            'peak_kw': float(peak_kw),
            'savings_per_kwh': savings_per_kwh,
            'hourly_costs': gap * np.where(peak_mask, TARIFF_PEAK, TARIFF_OFF_PEAK),
            'hourly_kwh': gap,
            'is_peak': peak_mask,
        }

    @staticmethod
    def detect_peak_alerts(forecast_df, threshold_pct=0.75):
        """
        Detect peak demand hours (above threshold percentile).
        Returns list of alert dicts.
        """
        gap = forecast_df['Global_active_power'].values
        threshold = np.percentile(gap[gap > 0], threshold_pct * 100) if np.any(gap > 0) else 0
        alerts = []

        peak_hours = forecast_df.index[gap > threshold]
        if len(peak_hours) > 0:
            start_hour = peak_hours[0].strftime('%H:%M')
            end_hour = peak_hours[-1].strftime('%H:%M')
            max_kw = gap.max()
            alerts.append({
                'type': 'peak',
                'severity': 'high' if max_kw > 3.0 else 'medium',
                'start': start_hour,
                'end': end_hour,
                'max_kw': float(max_kw),
                'hours': [h.strftime('%H:%M') for h in peak_hours],
                'message': (
                    f"Peak load of {max_kw:.2f} kW predicted between "
                    f"{start_hour} and {end_hour}. Consider delaying heavy "
                    f"appliances to off-peak hours (after 22:00) to reduce costs."
                )
            })

        return alerts
