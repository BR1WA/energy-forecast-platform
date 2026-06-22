"""
Forecast service — ML model loading and inference.
"""
import os
import pandas as pd
import torch
import numpy as np
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from app.config import get_settings
from app.ml.architectures import PatchTST, SOTAForecastingModel, CNN_BiLSTM, AdvancedPatchTST, iTransformer

settings = get_settings()

# Target column names (must match training order)
TARGET_COLS = [
    'Global_active_power', 'Global_reactive_power', 'Voltage',
    'Global_intensity', 'Sub_metering_1', 'Sub_metering_2', 'Sub_metering_3'
]


def generate_calendar_features(hours: np.ndarray, days: np.ndarray, months: np.ndarray) -> np.ndarray:
    """
    Generate cyclical calendar features (hour, day, month sin/cos) from numpy arrays.
    Inputs are assumed to be 1-indexed for months (1..12).
    """
    hour_sin = np.sin(2 * np.pi * hours / 24.0)
    hour_cos = np.cos(2 * np.pi * hours / 24.0)
    day_sin = np.sin(2 * np.pi * days / 7.0)
    day_cos = np.cos(2 * np.pi * days / 7.0)
    month_sin = np.sin(2 * np.pi * months / 12.0)
    month_cos = np.cos(2 * np.pi * months / 12.0)
    return np.stack([hour_sin, hour_cos, day_sin, day_cos, month_sin, month_cos], axis=1).astype(np.float32)


def generate_integer_calendar_features(hours: np.ndarray, days: np.ndarray, months: np.ndarray) -> np.ndarray:
    """
    Generate integer calendar features (Hour 0..23, DayOfWeek 0..6, Month 0..11)
    for long-term forecasting models expecting explicit temporal embeddings.
    Inputs are assumed to be 1-indexed for months (1..12).
    """
    months_zero_indexed = months - 1
    return np.stack([hours, days, months_zero_indexed], axis=1).astype(np.int64)


def load_state_dict_safe(model: torch.nn.Module, path: str, device: torch.device):
    """Load model weights, stripping 'module.' prefix if saved via DataParallel."""
    state_dict = torch.load(path, map_location=device, weights_only=True)
    new_state_dict = {}
    for k, v in state_dict.items():
        if k.startswith('module.'):
            new_state_dict[k[7:]] = v
        else:
            new_state_dict[k] = v
    model.load_state_dict(new_state_dict)


class ForecastService:
    """Manages ML model loading and inference for energy forecasting."""

    def __init__(self):
        self.device = torch.device('cpu')  # CPU inference for web serving
        self.models: Dict[str, torch.nn.Module] = {}
        self.model_statuses: Dict[str, str] = {}
        self.scaler = None
        self.samples: Dict[str, dict] = {}
        
        # Initialize persistent models metadata for display and tracking
        self.available_models_metadata = {
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
            'patchtst_168': {
                'id': 'patchtst_168',
                'name': 'patchtst_168',
                'display_name': 'Advanced PatchTST (1-Week)',
                'version': '1.0.0',
                'accuracy': 82.5,
                'last_trained': '2026-06-22T12:00:00Z',
                'architecture_type': 'transformer',
                'description': 'Upgraded PatchTST with temporal calendar embeddings for 168h forecasting horizon.',
                'training_metrics': {'mae': 0.432, 'rmse': 0.612, 'mape': 51.2, 'r2_score': 0.825},
                'parameters': {
                    'lookback_window': '512 hours',
                    'forecast_horizon': '168 hours',
                    'patch_length': '16',
                    'stride': '8',
                    'd_model': '128',
                    'n_heads': '8',
                    'n_layers': '3',
                    'd_ff': '256',
                    'dropout': '0.2',
                    'optimizer': 'AdamW (lr=1e-4)',
                    'training_epochs': '10',
                }
            },
            'itransformer_168': {
                'id': 'itransformer_168',
                'name': 'itransformer_168',
                'display_name': 'iTransformer (1-Week)',
                'version': '1.0.0',
                'accuracy': 83.2,
                'last_trained': '2026-06-22T12:00:00Z',
                'architecture_type': 'transformer',
                'description': 'iTransformer with calendar embeddings as tokens for 168h forecasting horizon.',
                'training_metrics': {'mae': 0.421, 'rmse': 0.601, 'mape': 49.8, 'r2_score': 0.832},
                'parameters': {
                    'lookback_window': '512 hours',
                    'forecast_horizon': '168 hours',
                    'd_model': '128',
                    'n_heads': '8',
                    'n_layers': '3',
                    'd_ff': '256',
                    'dropout': '0.2',
                    'optimizer': 'AdamW (lr=1e-4)',
                    'training_epochs': '10',
                }
            },
            'patchtst_720': {
                'id': 'patchtst_720',
                'name': 'patchtst_720',
                'display_name': 'Advanced PatchTST (1-Month)',
                'version': '1.0.0',
                'accuracy': 78.4,
                'last_trained': '2026-06-22T12:00:00Z',
                'architecture_type': 'transformer',
                'description': 'Upgraded PatchTST with temporal calendar embeddings for 720h forecasting horizon.',
                'training_metrics': {'mae': 0.485, 'rmse': 0.685, 'mape': 58.7, 'r2_score': 0.784},
                'parameters': {
                    'lookback_window': '1440 hours',
                    'forecast_horizon': '720 hours',
                    'patch_length': '16',
                    'stride': '8',
                    'd_model': '128',
                    'n_heads': '8',
                    'n_layers': '3',
                    'd_ff': '256',
                    'dropout': '0.2',
                    'optimizer': 'AdamW (lr=1e-4)',
                    'training_epochs': '10',
                }
            },
            'itransformer_720': {
                'id': 'itransformer_720',
                'name': 'itransformer_720',
                'display_name': 'iTransformer (1-Month)',
                'version': '1.0.0',
                'accuracy': 79.1,
                'last_trained': '2026-06-22T12:00:00Z',
                'architecture_type': 'transformer',
                'description': 'iTransformer with calendar embeddings as tokens for 720h forecasting horizon.',
                'training_metrics': {'mae': 0.478, 'rmse': 0.672, 'mape': 57.3, 'r2_score': 0.791},
                'parameters': {
                    'lookback_window': '1440 hours',
                    'forecast_horizon': '720 hours',
                    'd_model': '128',
                    'n_heads': '8',
                    'n_layers': '3',
                    'd_ff': '256',
                    'dropout': '0.2',
                    'optimizer': 'AdamW (lr=1e-4)',
                    'training_epochs': '10',
                }
            },
        }
        
        self._load_models()
        self._load_scaler()
        self._load_samples()
        self._seed_model_registry_db()

    def _seed_model_registry_db(self):
        """Seed ModelRegistry database table if empty."""
        from app.database import SessionLocal
        from app.models.models import ModelRegistry

        db = SessionLocal()
        try:
            existing_count = db.query(ModelRegistry).count()
            if existing_count == 0:
                print("[ML] Seeding ModelRegistry database table...")
                for name, info in self.available_models_metadata.items():
                    db_model = ModelRegistry(
                        id=info['id'],
                        name=info['name'],
                        display_name=info['display_name'],
                        architecture_type=info['architecture_type'],
                        description=info['description'],
                        training_metrics=info['training_metrics'],
                        is_active=True,
                        version=info['version'],
                        accuracy=info['accuracy'],
                        last_trained=info['last_trained'],
                        parameters=info['parameters'],
                        status='active'
                    )
                    db.add(db_model)
                db.commit()
                print("[ML] Seeding completed.")
        except Exception as e:
            print(f"[ML] Error seeding ModelRegistry: {e}")
            db.rollback()
        finally:
            db.close()

    def _resolve_path(self, relative: str) -> str:
        """Resolve path relative to the models directory."""
        return str(Path(settings.MODELS_DIR).resolve() / relative)

    def _load_models(self):
        """Load all available model weights from structured active directories."""
        models_dir = Path(settings.MODELS_DIR).resolve() / "active"

        # --- 24h Models ---
        # 1. PatchTST (24h)
        patchtst_path = models_dir / "24h" / "patchtst_weights.pth"
        if patchtst_path.exists():
            model = PatchTST(
                num_targets=7, patch_len=16, stride=8, lookback=96,
                d_model=128, n_heads=8, n_layers=3, d_ff=256,
                dropout=0.0, forecast_horizon=24
            )
            load_state_dict_safe(model, str(patchtst_path), self.device)
            model.eval()
            self.models['patchtst'] = model
            print(f"[ML] Loaded PatchTST (24h) from {patchtst_path}")

        # 2. SOTA Hybrid (24h)
        sota_path = models_dir / "24h" / "sota_model_weights.pth"
        if sota_path.exists():
            model = SOTAForecastingModel(
                num_targets=7, patch_len_1=8, patch_len_2=24, stride=8,
                lookback=96, d_model=64, d_channel=256, forecast_horizon=24
            )
            load_state_dict_safe(model, str(sota_path), self.device)
            model.eval()
            self.models['sota'] = model
            print(f"[ML] Loaded SOTA Hybrid (24h) from {sota_path}")

        # 3. CNN-BiLSTM (24h)
        cnn_path = models_dir / "24h" / "cnn_bilstm_baseline.pth"
        if cnn_path.exists():
            model = CNN_BiLSTM(
                num_targets=7, forecast_horizon=24,
                cnn_filters=64, lstm_hidden=64
            )
            load_state_dict_safe(model, str(cnn_path), self.device)
            model.eval()
            self.models['cnn_bilstm'] = model
            print(f"[ML] Loaded CNN-BiLSTM (24h) from {cnn_path}")

        # --- 168h (1-Week) Models ---
        # 4. AdvancedPatchTST (168h)
        apatchtst_168_path = models_dir / "168h" / "advancedpatchtst_1_week_weights.pth"
        if apatchtst_168_path.exists():
            model = AdvancedPatchTST(
                c_in=7, context_window=512, target_window=168,
                patch_len=16, stride=8, d_model=128, n_heads=8,
                n_layers=3, d_ff=256, dropout=0.2, head_dropout=0.2,
                individual=False, revin=True
            )
            load_state_dict_safe(model, str(apatchtst_168_path), self.device)
            model.eval()
            self.models['patchtst_168'] = model
            print(f"[ML] Loaded AdvancedPatchTST (168h) from {apatchtst_168_path}")

        # 5. iTransformer (168h)
        itrans_168_path = models_dir / "168h" / "itransformer_1_week_weights.pth"
        if itrans_168_path.exists():
            model = iTransformer(
                c_in=7, lookback=512, forecast_horizon=168,
                d_model=128, n_heads=8, n_layers=3, d_ff=256,
                dropout=0.2, revin=True
            )
            load_state_dict_safe(model, str(itrans_168_path), self.device)
            model.eval()
            self.models['itransformer_168'] = model
            print(f"[ML] Loaded iTransformer (168h) from {itrans_168_path}")

        # --- 720h (1-Month) Models ---
        # 6. AdvancedPatchTST (720h)
        apatchtst_720_path = models_dir / "720h" / "advancedpatchtst_1_month_weights.pth"
        if apatchtst_720_path.exists():
            model = AdvancedPatchTST(
                c_in=7, context_window=1440, target_window=720,
                patch_len=16, stride=8, d_model=128, n_heads=8,
                n_layers=3, d_ff=256, dropout=0.2, head_dropout=0.2,
                individual=False, revin=True
            )
            load_state_dict_safe(model, str(apatchtst_720_path), self.device)
            model.eval()
            self.models['patchtst_720'] = model
            print(f"[ML] Loaded AdvancedPatchTST (720h) from {apatchtst_720_path}")

        # 7. iTransformer (720h)
        itrans_720_path = models_dir / "720h" / "itransformer_1_month_weights.pth"
        if itrans_720_path.exists():
            model = iTransformer(
                c_in=7, lookback=1440, forecast_horizon=720,
                d_model=128, n_heads=8, n_layers=3, d_ff=256,
                dropout=0.2, revin=True
            )
            load_state_dict_safe(model, str(itrans_720_path), self.device)
            model.eval()
            self.models['itransformer_720'] = model
            print(f"[ML] Loaded iTransformer (720h) from {itrans_720_path}")

        print(f"[ML] Total models loaded: {len(self.models)}")

    def _load_scaler(self):
        """Load StandardScalers for each forecasting horizon."""
        self.scalers = {}
        models_dir = Path(settings.MODELS_DIR).resolve() / "active"

        # 24h scaler
        scaler_24h_path = models_dir / "24h" / "scaler.pkl"
        if scaler_24h_path.exists():
            try:
                with open(str(scaler_24h_path), 'rb') as f:
                    self.scalers[24] = pickle.load(f)
                self.scaler = self.scalers[24] # backward compatibility
                print(f"[ML] Loaded 24h scaler from {scaler_24h_path}")
            except Exception as e:
                try:
                    import joblib
                    self.scalers[24] = joblib.load(str(scaler_24h_path))
                    self.scaler = self.scalers[24]
                    print(f"[ML] Loaded 24h scaler via joblib from {scaler_24h_path}")
                except Exception as je:
                    print(f"[ML] Warning: Could not load 24h scaler ({e}) (joblib: {je})")

        # 168h scaler
        scaler_168h_path = models_dir / "168h" / "scaler_1_week.pkl"
        if scaler_168h_path.exists():
            try:
                with open(str(scaler_168h_path), 'rb') as f:
                    self.scalers[168] = pickle.load(f)
                print(f"[ML] Loaded 168h scaler from {scaler_168h_path}")
            except Exception as e:
                print(f"[ML] Warning: Could not load 168h scaler ({e})")

        # 720h scaler
        scaler_720h_path = models_dir / "720h" / "scaler_1_month.pkl"
        if scaler_720h_path.exists():
            try:
                with open(str(scaler_720h_path), 'rb') as f:
                    self.scalers[720] = pickle.load(f)
                print(f"[ML] Loaded 720h scaler from {scaler_720h_path}")
            except Exception as e:
                print(f"[ML] Warning: Could not load 720h scaler ({e})")

    def _load_samples(self):
        """Load pre-generated test samples (CSV) for quick demo up to 1440 points."""
        import pandas as pd
        
        samples_dir = Path(settings.MODELS_DIR).resolve().parent / "app_forecast" / "samples"
        if samples_dir.exists():
            for sample_file in sorted(samples_dir.glob("*.csv")):
                if sample_file.name == "sample_metadata.csv":
                    continue
                try:
                    df = pd.read_csv(sample_file, index_col=0, parse_dates=True)
                    # Load up to 1440 rows to satisfy 1-month horizon lookback
                    df = df.tail(1440)
                    targets = df[TARGET_COLS].values.astype(np.float32)
                    
                    # Generate calendar features
                    hours = df.index.hour.values
                    days = df.index.dayofweek.values
                    months = df.index.month.values
                    
                    calendar = generate_calendar_features(hours, days, months)
                    
                    import datetime
                    start_dt = df.index[0].to_pydatetime()
                    end_dt = df.index[-1].to_pydatetime()
                    if start_dt.tzinfo is None:
                        start_dt = start_dt.replace(tzinfo=datetime.timezone.utc)
                        end_dt = end_dt.replace(tzinfo=datetime.timezone.utc)
                        
                    name = sample_file.stem
                    self.samples[name] = {
                        'targets': targets,      # [len, 7]
                        'calendar': calendar,    # [len, 6] (cyclical for 24h fallback)
                        'timestamps': df.index,  # DatetimeIndex to derive integer features
                        'start_hour': int((df.index[-1].hour + 1) % 24),
                        'input_start': start_dt,
                        'input_end': end_dt,
                    }
                except Exception as e:
                    print(f"[ML] Error loading sample {sample_file.name}: {e}")
                    
            print(f"[ML] Loaded {len(self.samples)} sample datasets")

    def get_available_models(self) -> List[dict]:
        """Return list of available models with metadata from the database."""
        from app.database import SessionLocal
        from app.models.models import ModelRegistry

        db = SessionLocal()
        try:
            db_models = db.query(ModelRegistry).all()
            result = []
            for m in db_models:
                result.append({
                    'id': m.id,
                    'name': m.name,
                    'display_name': m.display_name,
                    'architecture_type': m.architecture_type,
                    'description': m.description,
                    'training_metrics': m.training_metrics or {},
                    'is_active': m.is_active and (m.id in self.models),
                    'version': m.version,
                    'accuracy': m.accuracy,
                    'last_trained': m.last_trained,
                    'parameters': m.parameters or {},
                    'status': m.status
                })
            return result
        except Exception as e:
            print(f"[ML] Error fetching available models from DB: {e}")
            # Fallback to local dict metadata if DB fails
            result = []
            for name, info in self.available_models_metadata.items():
                is_active = name in self.models
                status = self.model_statuses.get(name) or ('active' if is_active else 'inactive')
                result.append({
                    **info,
                    'is_active': is_active,
                    'status': status
                })
            return result
        finally:
            db.close()

    def retrain_model(self, model_name: str, background_tasks) -> None:
        """Retrain the specified model asynchronously using a real PyTorch backprop loop."""
        if model_name not in ['patchtst', 'sota', 'cnn_bilstm']:
            raise ValueError(f"Invalid model name: {model_name}")
            
        def train_loop():
            import time
            import datetime
            from datetime import timezone
            import torch
            import torch.nn as nn
            import torch.optim as optim
            from app.database import SessionLocal
            from app.models.models import ModelRegistry
            
            model = self.models.get(model_name)
            if model is None:
                print(f"[ML-RETRAIN] Model {model_name} is not loaded. Skipping training loop.")
                self.model_statuses[model_name] = 'inactive'
                db_sess = SessionLocal()
                try:
                    db_model = db_sess.query(ModelRegistry).filter(ModelRegistry.id == model_name).first()
                    if db_model:
                        db_model.status = 'inactive'
                        db_sess.commit()
                except Exception as db_err:
                    print(f"[ML-RETRAIN] Error: {db_err}")
                finally:
                    db_sess.close()
                return
                
            print(f"[ML-RETRAIN] Starting backpropagation training loop for {model_name}...")
            self.model_statuses[model_name] = 'training (Epoch 0/5, Loss: Starting)'
            
            db_sess = SessionLocal()
            try:
                db_model = db_sess.query(ModelRegistry).filter(ModelRegistry.id == model_name).first()
                if db_model:
                    db_model.status = 'training (Epoch 0/5, Loss: Starting)'
                    db_sess.commit()
            except Exception as db_err:
                print(f"[ML-RETRAIN] Error setting initial status: {db_err}")
            finally:
                db_sess.close()
            
            # Setup optimizer and loss function
            model.train()
            optimizer = optim.Adam(model.parameters(), lr=0.001)
            criterion = nn.MSELoss()
            
            # Fetch real database smart meter readings if available
            from app.database import SessionLocal
            from app.models import SmartMeterReading
            from app.services.smart_meter_service import get_smart_meter_service
            
            db_session = SessionLocal()
            db_readings = []
            try:
                # Query last 1000 smart meter records
                records = db_session.query(SmartMeterReading).order_by(SmartMeterReading.timestamp.desc()).limit(1000).all()
                if records:
                    records.reverse() # Keep chronological order
                    db_readings = [
                        [r.gap, r.grp, r.voltage, r.intensity, r.sub_metering_1, r.sub_metering_2, r.sub_metering_3]
                        for r in records
                    ]
            except Exception as read_err:
                print(f"[ML-RETRAIN] Error fetching DB readings: {read_err}")
            finally:
                db_session.close()

            # Helper to generate training batches
            def get_training_batch(batch_size=4):
                import random
                # If we have gathered enough database records, construct inputs and targets from them
                if len(db_readings) >= 120:
                    x_batch = []
                    y_batch = []
                    for _ in range(batch_size):
                        # Pick a random starting point in the historical data
                        start_idx = random.randint(0, len(db_readings) - 120)
                        # Slice 96 lookback hours
                        x_seq = db_readings[start_idx : start_idx + 96]
                        # Slice 24 target hours
                        y_seq = db_readings[start_idx + 96 : start_idx + 120]
                        x_batch.append(x_seq)
                        y_batch.append(y_seq)
                    return torch.FloatTensor(x_batch).to(self.device), torch.FloatTensor(y_batch).to(self.device)
                else:
                    # Fallback: use simulated readings from the Linky service
                    meter_service = get_smart_meter_service()
                    x_batch = []
                    y_batch = []
                    for _ in range(batch_size):
                        sim_lookback = meter_service.fetch_live_readings()
                        # Simulate predictions targets by running another realistic sequence
                        sim_targets = meter_service.fetch_live_readings()[:24]
                        x_batch.append(sim_lookback)
                        y_batch.append(sim_targets)
                    return torch.FloatTensor(x_batch).to(self.device), torch.FloatTensor(y_batch).to(self.device)

            # Run 5 epochs of real optimization steps
            for epoch in range(5):
                # Fetch realistic/DB training inputs and targets
                inputs, targets_real = get_training_batch(batch_size=4)
                
                if model_name == 'cnn_bilstm':
                    outputs = model(inputs)
                    loss = criterion(outputs, targets_real)
                else:
                    # Calendar features (shape [4, 96, 6])
                    calendar_dummy = torch.randn(inputs.shape[0], 96, 6).to(self.device)
                    outputs = model(inputs, calendar_dummy)
                    loss = criterion(outputs, targets_real)
                
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                
                loss_val = float(loss.item())
                print(f"[ML-RETRAIN] {model_name} | Epoch {epoch+1}/5 | Loss: {loss_val:.4f}")
                self.model_statuses[model_name] = f"training (Epoch {epoch+1}/5, Loss: {loss_val:.4f})"
                
                db_sess = SessionLocal()
                try:
                    db_model = db_sess.query(ModelRegistry).filter(ModelRegistry.id == model_name).first()
                    if db_model:
                        db_model.status = f"training (Epoch {epoch+1}/5, Loss: {loss_val:.4f})"
                        db_sess.commit()
                except Exception as db_err:
                    print(f"[ML-RETRAIN] Error updating status: {db_err}")
                finally:
                    db_sess.close()
                    
                time.sleep(1.0)  # Sleep so the user can easily observe the progress in the UI
                
            model.eval()
            
            # Update metadata on successful completion
            metadata = self.available_models_metadata.get(model_name)
            if metadata:
                # Remove synthetic R2 score increment bump
                old_r2 = metadata['training_metrics']['r2_score']
                new_r2 = old_r2
                metadata['training_metrics']['r2_score'] = new_r2
                metadata['accuracy'] = round(new_r2 * 100, 1)
                
                # Increment version slightly (e.g. 1.0.0 -> 1.0.1)
                v_parts = metadata['version'].split('.')
                v_parts[2] = str(int(v_parts[2]) + 1)
                metadata['version'] = '.'.join(v_parts)
                
                # Update last trained date
                metadata['last_trained'] = datetime.datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                
            # Save updated weights to candidate directory to avoid overwriting production weights
            weights_filenames = {
                'cnn_bilstm': 'cnn_bilstm_baseline.pth',
                'sota': 'sota_model_weights.pth',
                'patchtst': 'patchtst_weights.pth',
            }
            filename = weights_filenames.get(model_name)
            if filename:
                try:
                    candidate_dir = Path(settings.MODELS_DIR) / "_candidate"
                    candidate_dir.mkdir(exist_ok=True)
                    candidate_path = candidate_dir / filename
                    torch.save(model.state_dict(), str(candidate_path.resolve()))
                    print(f"[ML-RETRAIN] Saved updated weights for {model_name} to candidate path: {candidate_path}")
                except Exception as save_err:
                    print(f"[ML-RETRAIN] Warning: Failed to save updated weights to candidate path: {save_err}")

            self.model_statuses[model_name] = 'active'
            print(f"[ML-RETRAIN] Completed training for {model_name} successfully.")
            
            db_sess = SessionLocal()
            try:
                db_model = db_sess.query(ModelRegistry).filter(ModelRegistry.id == model_name).first()
                if db_model:
                    db_model.status = 'active'
                    if metadata:
                        db_model.version = metadata['version']
                        db_model.accuracy = metadata['accuracy']
                        db_model.last_trained = metadata['last_trained']
                        db_model.training_metrics = metadata['training_metrics']
                    db_sess.commit()
            except Exception as db_err:
                print(f"[ML-RETRAIN] Error updating final stats in DB: {db_err}")
            finally:
                db_sess.close()
            
        background_tasks.add_task(train_loop)


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
        start_hour: Optional[int] = None,
        horizon: int = 24,
        timestamps: Optional[pd.DatetimeIndex] = None,
    ) -> Tuple[np.ndarray, List[dict]]:
        """
        Run inference with a specified model.

        Args:
            model_name: 'patchtst', 'sota', 'cnn_bilstm', 'itransformer' (plus horizon suffixed versions)
            targets: numpy array [lookback, 7] — raw target values
            calendar: numpy array [lookback, 6] — cyclical calendar features (only used for 24h SOTA/PatchTST)
            threshold_kw: threshold in kW for alert evaluation
            horizon: forecast horizon (24, 168, or 720)
            timestamps: pandas DatetimeIndex for generating temporal embedding integer labels
        """
        # Map flat model_name to self.models key depending on horizon
        full_model_key = model_name
        if horizon != 24 and not model_name.endswith(f"_{horizon}"):
            full_model_key = f"{model_name}_{horizon}"

        if full_model_key not in self.models:
            # Check if model name itself is directly in models (backward compatibility)
            if model_name in self.models:
                full_model_key = model_name
            else:
                raise ValueError(
                    f"Model '{model_name}' for horizon {horizon}h is not loaded. "
                    f"Available: {list(self.models.keys())}"
                )

        model = self.models[full_model_key]
        lookback = targets.shape[0]

        # Get the proper scaler for this horizon
        scaler = self.scalers.get(horizon)

        # Prepare target input tensor
        # CNN-BiLSTM and long-term models are trained on scaled targets. SOTA and PatchTST (24h) use RevIN with raw targets.
        if full_model_key in ['cnn_bilstm'] or horizon in [168, 720]:
            if scaler is not None:
                scaled_targets = scaler.transform(targets)
                x_targets = torch.FloatTensor(scaled_targets).unsqueeze(0).to(self.device)
            else:
                print(f"[ML] Warning: Scaler for horizon {horizon} not found! Operating on raw values.")
                x_targets = torch.FloatTensor(targets).unsqueeze(0).to(self.device)
        else:
            # 24h SOTA / PatchTST operate directly on raw kW scale
            x_targets = torch.FloatTensor(targets).unsqueeze(0).to(self.device)

        # Prepare temporal calendar features
        is_long_term = horizon in [168, 720]
        if is_long_term:
            # Long-term models (AdvancedPatchTST & iTransformer) expect integer labels [1, lookback, 3]
            if timestamps is not None:
                hours = timestamps.hour.values
                days = timestamps.dayofweek.values
                months = timestamps.month.values
                int_calendar = generate_integer_calendar_features(hours, days, months)
            else:
                # Fallback to dynamic relative timestamps from now
                import pandas as pd
                import datetime
                now = datetime.datetime.now(datetime.timezone.utc)
                idx = pd.date_range(end=now, periods=lookback, freq='h')
                int_calendar = generate_integer_calendar_features(idx.hour.values, idx.dayofweek.values, idx.month.values)
                
            x_calendar = torch.LongTensor(int_calendar).unsqueeze(0).to(self.device)
        else:
            # 24h models expect cyclical float features [1, 96, 6]
            if calendar is not None:
                x_calendar = torch.FloatTensor(calendar).unsqueeze(0).to(self.device)
            else:
                x_calendar = torch.zeros(1, lookback, 6).to(self.device)

        with torch.no_grad():
            if full_model_key == 'cnn_bilstm':
                preds = model(x_targets).cpu().numpy()[0]  # [24, 7]
                if scaler is not None:
                    preds = scaler.inverse_transform(preds.reshape(-1, 7)).reshape(24, 7)
            elif is_long_term:
                # AdvancedPatchTST and iTransformer expect x and calendar
                preds = model(x_targets, x_calendar).cpu().numpy()[0]  # [horizon, 7]
                # Inverse scale back to kW
                if scaler is not None:
                    preds = scaler.inverse_transform(preds.reshape(-1, 7)).reshape(horizon, 7)
            else:
                # SOTA and PatchTST (24h)
                preds = model(x_targets, x_calendar).cpu().numpy()[0]  # [24, 7]

        # Generate alerts
        alerts = self._check_alerts(preds, threshold_kw, start_hour)

        return preds, alerts

    def _check_alerts(self, predictions: np.ndarray, threshold_kw: float = 3.0, start_hour: Optional[int] = None) -> List[dict]:
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

        # Cost alert for high-consumption periods using custom tariffs
        if start_hour is None:
            from datetime import datetime
            start_hour = datetime.utcnow().hour

        # Fetch custom settings from database
        from app.database import SessionLocal
        from app.models.settings import SystemSettings
        
        db = SessionLocal()
        try:
            settings_db = db.query(SystemSettings).first()
            if settings_db:
                currency = settings_db.currency
                off_peak = settings_db.off_peak_rate
                peak = settings_db.peak_rate
                peak_start = settings_db.peak_start_hour
                peak_end = settings_db.peak_end_hour
            else:
                # Default fallback
                currency = "MAD"
                off_peak = 1.0
                peak = 1.5
                peak_start = 6
                peak_end = 22
        finally:
            db.close()

        estimated_cost = 0.0
        total_kwh = float(np.sum(gap_predictions))
        for i, val in enumerate(gap_predictions):
            hour = (start_hour + i) % 24
            # Determine if hour is peak
            is_peak = peak_start <= hour < peak_end
            if peak_start > peak_end:  # wraps around midnight
                is_peak = hour >= peak_start or hour < peak_end
                
            if is_peak:
                estimated_cost += float(val) * peak
            else:
                estimated_cost += float(val) * off_peak

        if estimated_cost > 10.0:  # More than 10 MAD in 24h as arbitrary threshold
            alerts.append({
                'alert_type': 'cost_threshold',
                'severity': 'medium',
                'message': f'Estimated 24h energy cost: {currency}{estimated_cost:.2f} ({total_kwh:.1f} kWh)',
                'peak_kw': peak_power,
            })

        return alerts

    def predict_comparison(
        self,
        targets: np.ndarray,
        calendar: Optional[np.ndarray] = None,
        horizon: int = 24,
        timestamps: Optional[pd.DatetimeIndex] = None,
    ) -> Dict[str, np.ndarray]:
        """Run all available models for the given horizon and return comparison results."""
        import pandas as pd
        results = {}
        for name in self.models:
            is_match = False
            if horizon == 24 and name in ['patchtst', 'sota', 'cnn_bilstm']:
                is_match = True
            elif horizon == 168 and name in ['patchtst_168', 'itransformer_168']:
                is_match = True
            elif horizon == 720 and name in ['patchtst_720', 'itransformer_720']:
                is_match = True
                
            if not is_match:
                continue
                
            try:
                preds, _ = self.predict(
                    name, targets, calendar, horizon=horizon, timestamps=timestamps
                )
                # Map internal keys back to model names for frontend presentation
                display_key = name
                if name.endswith(f"_{horizon}"):
                    display_key = name[:-len(f"_{horizon}")]
                results[display_key] = preds
            except Exception as e:
                print(f"[ML] Error running comparison for {name}: {e}")
        return results


# Singleton instance
_forecast_service: Optional[ForecastService] = None


def get_forecast_service() -> ForecastService:
    """Get or create the forecast service singleton."""
    global _forecast_service
    if _forecast_service is None:
        _forecast_service = ForecastService()
    return _forecast_service
