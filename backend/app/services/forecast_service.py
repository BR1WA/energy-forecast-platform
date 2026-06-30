import os
import torch
import json
import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.models import ModelRegistry
from training.features.feature_engineering import FeaturePipeline
from training.train import prepare_tensors

class ForecastService:
    def __init__(self):
        self._active_model_id = None
        self._model = None
        self._pipeline = None
        self._config = None
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self._cached_settings = None
        self._settings_last_fetched = 0

    def load_active_model(self, db: Session):
        active_model = db.query(ModelRegistry).filter(ModelRegistry.active == True).first()
        if not active_model:
            return False
            
        if self._active_model_id == active_model.id:
            return True # Already loaded
            
        # Need to load new model
        exp_path = active_model.experiment_path
        pipeline_path = os.path.join(exp_path, 'pipeline.pkl')
        model_path = os.path.join(exp_path, 'model.pt')
        config_path = os.path.join(exp_path, 'config.yaml')
        
        if not os.path.exists(model_path):
            raise Exception(f"Model path missing: {model_path}")
            
        # Load config
        import yaml
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            
        self._config = config
        
        # Load pipeline
        self._pipeline = FeaturePipeline(time_col='timestamp', target_cols=['gap'])
        self._pipeline.load(pipeline_path)
        
        # Load Model
        model_name = config['model']['name']
        if model_name == 'Hybrid_v2':
            from training.models.hybrid_v2 import Hybrid_v2
            model = Hybrid_v2(config['model'])
        elif model_name == 'iTransformer':
            from training.models.itransformer import iTransformer
            model = iTransformer(config['model'])
        else:
            raise ValueError(f"Unknown model architecture: {model_name}")
            
        model.to(self.device)
        model.load(model_path, self.device)
        model.eval()
        
        self._model = model
        self._active_model_id = active_model.id
        return True
        
    def predict(self, raw_df: pd.DataFrame, db: Session, threshold_kw: float = 3.0):
        # raw_df expects timestamp and gap columns
        if not self.load_active_model(db):
            raise Exception("No active model available in registry.")
            
        # process through pipeline
        missing_strat = self._config['training'].get('missing_strategy', 'interpolate')
        processed_df = self._pipeline.transform(raw_df, validate=True, missing_strategy=missing_strat)
        
        lookback = self._config['model']['lookback']
        horizon = self._config['model']['forecast_horizon']
        
        if len(processed_df) < lookback:
            raise ValueError(f"Not enough data. Need at least {lookback} points, got {len(processed_df)}.")
        
        # generate tensors
        # X: [1, lookback, 1]
        x_last = torch.tensor(processed_df['gap'].values, dtype=torch.float32).unsqueeze(0).unsqueeze(-1)
        
        # Temp: [1, lookback, num_features]
        features_df = processed_df.drop(columns=['timestamp', 'gap'])
        temp_last = torch.tensor(features_df.values, dtype=torch.float32).unsqueeze(0)
        
        x_last = x_last.to(self.device)
        temp_last = temp_last.to(self.device)
        
        with torch.no_grad():
            preds = self._model.predict(x_last, temp_last)
            
        preds_np = preds.cpu().numpy()[0] # shape [horizon, num_targets]
        
        # generate alerts
        alerts = self._check_alerts(preds_np, threshold_kw)
        
        return preds_np, alerts

    def _check_alerts(self, predictions: np.ndarray, threshold_kw: float = 3.0) -> List[dict]:
        """Check predictions against alert thresholds."""
        alerts = []
        gap_predictions = predictions[:, 0]  # Global Active Power is target 0
        peak_power = float(np.max(gap_predictions))

        if peak_power > threshold_kw:
            severity = 'high' if peak_power > threshold_kw * 1.5 else 'medium'
            alerts.append({
                'alert_type': 'peak_demand',
                'severity': severity,
                'message': f'Predicted peak demand of {peak_power:.2f} kW exceeds threshold of {threshold_kw:.1f} kW',
                'peak_kw': peak_power,
            })
        return alerts

# Singleton instance
_forecast_service: Optional[ForecastService] = None

def get_forecast_service() -> ForecastService:
    """Get or create the forecast service singleton."""
    global _forecast_service
    if _forecast_service is None:
        _forecast_service = ForecastService()
    return _forecast_service
