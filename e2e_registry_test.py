import os
import sys
sys.path.append('backend')
import pandas as pd
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.models import ModelRegistry
from app.services.forecast_service import get_forecast_service

def validate_e2e():
    db = SessionLocal()
    
    # 1. Find the latest experiment folder
    exp_dir = "experiments"
    experiments = [os.path.join(exp_dir, d) for d in os.listdir(exp_dir) if os.path.isdir(os.path.join(exp_dir, d))]
    latest_exp = max(experiments, key=os.path.getmtime)
    print(f"Latest experiment found: {latest_exp}")
    
    # Check artifacts
    import json
    with open(os.path.join(latest_exp, "summary.json"), 'r') as f:
        summary = json.load(f)
        
    # 2. Register the experiment
    print(f"Registering model fingerprint: {summary['model_fingerprint']}")
    registry_entry = ModelRegistry(
        name=summary['model_name'],
        version="1.0.0",
        experiment_path=latest_exp,
        model_fingerprint=summary['model_fingerprint'],
        active=True,
        mae=summary['metrics']['mae'],
        rmse=summary['metrics']['rmse']
    )
    
    # Deactivate others
    db.query(ModelRegistry).update({"active": False})
    db.add(registry_entry)
    db.commit()
    db.refresh(registry_entry)
    print(f"Registered and activated model id={registry_entry.id}")
    
    # 3. Predict via ForecastService (simulating Backend loading strategy)
    service = get_forecast_service()
    
    # Create a dummy raw dataframe mimicking DB data
    # Hybrid_v2 expects 48 lookback
    lookback = summary['lookback']
    dates = pd.date_range(end=pd.Timestamp.now(), periods=lookback, freq='h')
    raw_df = pd.DataFrame({
        'timestamp': dates,
        'gap': [1.5 + (i % 24)*0.1 for i in range(lookback)]
    })
    
    print("Calling forecast endpoint (predict)...")
    preds, alerts = service.predict(raw_df, db)
    
    print(f"Received prediction shape: {preds.shape}")
    print(f"Horizon expected: {summary['horizon']}")
    assert preds.shape[0] == summary['horizon']
    
    print("End-to-End Validation Successful!")
    
if __name__ == "__main__":
    validate_e2e()
