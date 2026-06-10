"""
Forecast service — ML model loading and inference.
"""
import os
import torch
import numpy as np
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from app.config import get_settings
from app.ml.architectures import PatchTST, SOTAForecastingModel, CNN_BiLSTM

settings = get_settings()

# Target column names (must match training order)
TARGET_COLS = [
    'Global_active_power', 'Global_reactive_power', 'Voltage',
    'Global_intensity', 'Sub_metering_1', 'Sub_metering_2', 'Sub_metering_3'
]

# French EDF tariffs (EUR/kWh)
EDF_TARIFFS = {
    'heures_creuses': 0.1828,   # Off-peak (22h-6h)
    'heures_pleines': 0.2460,   # Peak hours
}


class ForecastService:
    """Manages ML model loading and inference for energy forecasting."""

    def __init__(self):
        self.device = torch.device('cpu')  # CPU inference for web serving
        self.models: Dict[str, torch.nn.Module] = {}
        self.model_statuses: Dict[str, str] = {}
        self.scaler = None
        self.samples: Dict[str, dict] = {}
        self._load_models()
        self._load_scaler()
        self._load_samples()

    def _resolve_path(self, relative: str) -> str:
        """Resolve path relative to the models directory."""
        return str(Path(settings.MODELS_DIR).resolve() / relative)

    def _load_models(self):
        """Load all available model weights."""
        models_dir = Path(settings.MODELS_DIR).resolve()

        # 1. PatchTST
        patchtst_path = models_dir / "patchtst_weights.pth"
        if patchtst_path.exists():
            model = PatchTST(
                num_targets=7, patch_len=16, stride=8, lookback=96,
                d_model=128, n_heads=8, n_layers=3, d_ff=256,
                dropout=0.0, forecast_horizon=24
            )
            model.load_state_dict(torch.load(str(patchtst_path), map_location=self.device, weights_only=True))
            model.eval()
            self.models['patchtst'] = model
            print(f"[ML] Loaded PatchTST from {patchtst_path}")

        # 2. SOTA Hybrid
        sota_path = models_dir / "sota_model_weights.pth"
        if sota_path.exists():
            model = SOTAForecastingModel(
                num_targets=7, patch_len_1=8, patch_len_2=24, stride=8,
                lookback=96, d_model=64, d_channel=256, forecast_horizon=24
            )
            model.load_state_dict(torch.load(str(sota_path), map_location=self.device, weights_only=True))
            model.eval()
            self.models['sota'] = model
            print(f"[ML] Loaded SOTA Hybrid from {sota_path}")

        # 3. CNN-BiLSTM
        cnn_path = models_dir / "cnn_bilstm_baseline.pth"
        if cnn_path.exists():
            model = CNN_BiLSTM(
                num_targets=7, forecast_horizon=24,
                cnn_filters=64, lstm_hidden=64
            )
            model.load_state_dict(torch.load(str(cnn_path), map_location=self.device, weights_only=True))
            model.eval()
            self.models['cnn_bilstm'] = model
            print(f"[ML] Loaded CNN-BiLSTM from {cnn_path}")

        print(f"[ML] Total models loaded: {len(self.models)}")

    def _load_scaler(self):
        """Load the StandardScaler for CNN-BiLSTM inverse transform."""
        scaler_path = Path(settings.MODELS_DIR).resolve() / "scaler.pkl"
        if scaler_path.exists():
            try:
                with open(str(scaler_path), 'rb') as f:
                    self.scaler = pickle.load(f)
                print(f"[ML] Loaded scaler from {scaler_path}")
            except Exception as e:
                print(f"[ML] Warning: Could not load scaler ({e}). CNN-BiLSTM will use raw predictions.")
                self.scaler = None

    def _load_samples(self):
        """Load pre-generated test samples (CSV) for quick demo."""
        import pandas as pd
        
        samples_dir = Path(settings.MODELS_DIR).resolve().parent / "app_forecast" / "samples"
        if samples_dir.exists():
            for sample_file in sorted(samples_dir.glob("*.csv")):
                if sample_file.name == "sample_metadata.csv":
                    continue
                try:
                    df = pd.read_csv(sample_file, index_col=0, parse_dates=True)
                    # Take only the last 96 rows for inference
                    df = df.tail(96)
                    targets = df[TARGET_COLS].values.astype(np.float32)
                    
                    # Generate calendar features
                    hours = df.index.hour.values
                    days = df.index.dayofweek.values
                    months = df.index.month.values
                    
                    hour_sin = np.sin(2 * np.pi * hours / 24.0)
                    hour_cos = np.cos(2 * np.pi * hours / 24.0)
                    day_sin = np.sin(2 * np.pi * days / 7.0)
                    day_cos = np.cos(2 * np.pi * days / 7.0)
                    month_sin = np.sin(2 * np.pi * months / 12.0)
                    month_cos = np.cos(2 * np.pi * months / 12.0)
                    
                    calendar = np.stack([hour_sin, hour_cos, day_sin, day_cos, month_sin, month_cos], axis=1).astype(np.float32)
                    
                    name = sample_file.stem
                    self.samples[name] = {
                        'targets': targets,     # [96, 7]
                        'calendar': calendar,   # [96, 6]
                    }
                except Exception as e:
                    print(f"[ML] Error loading sample {sample_file.name}: {e}")
                    
            print(f"[ML] Loaded {len(self.samples)} sample datasets")

    def get_available_models(self) -> List[dict]:
        """Return list of available models with metadata."""
        model_info = {
            'patchtst': {
                'id': 'patchtst',
                'name': 'patchtst',
                'display_name': 'PatchTST (Pure Transformer)',
                'version': '1.0.0',
                'accuracy': 81.4,
                'last_trained': '2026-06-01T12:00:00Z',
                'architecture_type': 'transformer',
                'description': 'ICLR 2023 — Channel-independent patching with vanilla Transformer encoder. Best MAE/RMSE.',
                'training_metrics': {'mae': 0.4519, 'rmse': 0.6445, 'mape': 55.97, 'r2_score': 0.8142},
                'parameters': {
                    'lookback_window': '96 hours',
                    'forecast_horizon': '24 hours',
                    'patch_length': '16',
                    'stride': '8',
                    'd_model': '128',
                    'n_heads': '8',
                    'n_layers': '3',
                    'd_ff': '256',
                    'dropout': '0.0',
                    'optimizer': 'AdamW (lr=1e-4)',
                    'training_epochs': '50',
                }
            },
            'sota': {
                'id': 'sota',
                'name': 'sota',
                'display_name': 'SOTA Hybrid (Recurrent-Attention)',
                'version': '1.0.0',
                'accuracy': 84.1,
                'last_trained': '2026-06-03T10:30:00Z',
                'architecture_type': 'hybrid',
                'description': 'RevIN + Multi-Scale Patching + BiGRU + Transformer + Cross-Variable Attention. Best MAPE.',
                'training_metrics': {'mae': 0.4614, 'rmse': 0.6623, 'mape': 55.13, 'r2_score': 0.8407},
                'parameters': {
                    'lookback_window': '96 hours',
                    'forecast_horizon': '24 hours',
                    'patch_scale_1': '8',
                    'patch_scale_2': '24',
                    'stride': '8',
                    'd_model': '64',
                    'd_channel': '256',
                    'cross_variable_attention': 'Enabled',
                    'revin': 'Enabled',
                    'optimizer': 'AdamW (lr=2e-4)',
                    'training_epochs': '60',
                }
            },
            'cnn_bilstm': {
                'id': 'cnn_bilstm',
                'name': 'cnn_bilstm',
                'display_name': 'CNN-BiLSTM (Baseline)',
                'version': '1.0.0',
                'accuracy': 69.1,
                'last_trained': '2026-05-28T09:15:00Z',
                'architecture_type': 'cnn-rnn',
                'description': 'Convolutional feature extraction + Bidirectional LSTM. Standard deep learning baseline.',
                'training_metrics': {'mae': 0.5335, 'rmse': 0.7072, 'mape': 77.36, 'r2_score': 0.6914},
                'parameters': {
                    'lookback_window': '96 hours',
                    'forecast_horizon': '24 hours',
                    'cnn_filters': '64',
                    'lstm_hidden': '64',
                    'scaler': 'StandardScaler',
                    'dropout': '0.2',
                    'optimizer': 'Adam (lr=1e-3)',
                    'training_epochs': '30',
                }
            },
        }
        
        result = []
        for name, info in model_info.items():
            is_active = name in self.models
            status = self.model_statuses.get(name)
            if not status:
                status = 'active' if is_active else 'inactive'
            
            result.append({
                **info,
                'is_active': is_active,
                'status': status
            })
        return result

    def retrain_model(self, model_name: str, background_tasks) -> None:
        """Simulate retraining a model asynchronously using background tasks."""
        if model_name not in ['patchtst', 'sota', 'cnn_bilstm']:
            raise ValueError(f"Invalid model name: {model_name}")
            
        def simulation():
            import time
            from datetime import datetime
            
            self.model_statuses[model_name] = 'training'
            print(f"[ML] Retraining started for {model_name}...")
            time.sleep(5)
            self.model_statuses[model_name] = 'active'
            print(f"[ML] Retraining completed for {model_name}!")
            
        background_tasks.add_task(simulation)


    def get_sample_datasets(self) -> List[dict]:
        """Return available sample datasets."""
        season_map = {
            'winter': ('Winter', 'Dec-Feb'),
            'spring': ('Spring', 'Mar-May'),
            'summer': ('Summer', 'Jun-Aug'),
            'autumn': ('Autumn', 'Sep-Nov'),
            'fall': ('Autumn', 'Sep-Nov'),
        }
        result = []
        for name in sorted(self.samples.keys()):
            season = 'Unknown'
            date_range = ''
            for key, (s, d) in season_map.items():
                if key in name.lower():
                    season = s
                    date_range = d
                    break
            result.append({
                'name': name,
                'description': f'{season} sample — 96-hour lookback window',
                'season': season,
                'date_range': date_range,
            })
        return result

    def predict(
        self,
        model_name: str,
        targets: np.ndarray,
        calendar: Optional[np.ndarray] = None,
        threshold_kw: float = 3.0,
    ) -> Tuple[np.ndarray, List[dict]]:
        """
        Run inference with a specified model.

        Args:
            model_name: 'patchtst', 'sota', or 'cnn_bilstm'
            targets: numpy array [96, 7] — raw target values
            calendar: numpy array [96, 6] — cyclical calendar features
            threshold_kw: threshold in kW for alert evaluation

        Returns:
            predictions: numpy array [24, 7] — forecasted values in kW
            alerts: list of alert dicts if thresholds exceeded
        """
        if model_name not in self.models:
            raise ValueError(f"Model '{model_name}' not loaded. Available: {list(self.models.keys())}")

        model = self.models[model_name]

        # Prepare tensors
        x_targets = torch.FloatTensor(targets).unsqueeze(0).to(self.device)  # [1, 96, 7]

        if calendar is not None:
            x_calendar = torch.FloatTensor(calendar).unsqueeze(0).to(self.device)  # [1, 96, 6]
        else:
            # Generate dummy calendar if not provided
            x_calendar = torch.zeros(1, 96, 6).to(self.device)

        with torch.no_grad():
            if model_name == 'cnn_bilstm':
                # CNN-BiLSTM operates on scaled data
                if self.scaler is not None:
                    scaled = self.scaler.transform(targets)
                    x_scaled = torch.FloatTensor(scaled).unsqueeze(0).to(self.device)
                    preds = model(x_scaled).cpu().numpy()[0]  # [24, 7]
                    # Inverse transform back to kW
                    preds = self.scaler.inverse_transform(preds.reshape(-1, 7)).reshape(24, 7)
                else:
                    preds = model(x_targets).cpu().numpy()[0]
            else:
                # SOTA and PatchTST use raw targets with internal RevIN
                preds = model(x_targets, x_calendar).cpu().numpy()[0]  # [24, 7]

        # Generate alerts
        alerts = self._check_alerts(preds, threshold_kw)

        return preds, alerts

    def _check_alerts(self, predictions: np.ndarray, threshold_kw: float = 3.0) -> List[dict]:
        """Check predictions against alert thresholds."""
        alerts = []
        gap_predictions = predictions[:, 0]  # Global Active Power

        peak_power = float(np.max(gap_predictions))
        avg_power = float(np.mean(gap_predictions))

        if peak_power > threshold_kw:
            severity = 'high' if peak_power > threshold_kw * 1.5 else 'medium'
            alerts.append({
                'alert_type': 'peak_demand',
                'severity': severity,
                'message': f'Predicted peak demand of {peak_power:.2f} kW exceeds threshold of {threshold_kw:.1f} kW',
                'peak_kw': peak_power,
            })

        # Cost alert for high-consumption periods
        total_kwh = float(np.sum(gap_predictions))
        estimated_cost = total_kwh * EDF_TARIFFS['heures_pleines']
        if estimated_cost > 2.0:  # More than 2 EUR in 24h
            alerts.append({
                'alert_type': 'cost_threshold',
                'severity': 'medium',
                'message': f'Estimated 24h energy cost: €{estimated_cost:.2f} ({total_kwh:.1f} kWh)',
                'peak_kw': peak_power,
            })

        return alerts

    def predict_comparison(
        self,
        targets: np.ndarray,
        calendar: Optional[np.ndarray] = None,
    ) -> Dict[str, np.ndarray]:
        """Run all available models and return comparison results."""
        results = {}
        for name in self.models:
            try:
                preds, _ = self.predict(name, targets, calendar)
                results[name] = preds
            except Exception as e:
                print(f"[ML] Error running {name}: {e}")
        return results


# Singleton instance
_forecast_service: Optional[ForecastService] = None


def get_forecast_service() -> ForecastService:
    """Get or create the forecast service singleton."""
    global _forecast_service
    if _forecast_service is None:
        _forecast_service = ForecastService()
    return _forecast_service
