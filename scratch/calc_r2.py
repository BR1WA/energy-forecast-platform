import sys, os
import pandas as pd, numpy as np
from pathlib import Path
from sklearn.metrics import r2_score

# Add backend and root to path
sys.path.append(os.path.abspath('.'))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from app.services.forecast_service import get_forecast_service
from app.config import get_settings
from app.database import SessionLocal
from app.models import ModelRegistry

TARGET_COLS = [
    'Global_active_power', 'Global_reactive_power', 'Voltage',
    'Global_intensity', 'Sub_metering_1', 'Sub_metering_2', 'Sub_metering_3'
]

def main():
    db = SessionLocal()
    service = get_forecast_service()
    try:
        service._seed_registry_from_disk(db)
        entries = db.query(ModelRegistry).all()
        model_names = [e.name for e in entries]
    finally:
        db.close()
        
    if not model_names:
        print("No models registered!")
        return
        
    print("Models loaded:", model_names)
    
    samples_dir = Path("C:/Users/salah/Documents/MASTER/PFE2/app_forecast/samples")
    
    all_actuals = []
    all_preds = {name: [] for name in model_names}
    
    for sample_file in samples_dir.glob("*.csv"):
        if sample_file.name == "sample_metadata.csv": continue
        
        df = pd.read_csv(sample_file, index_col=0, parse_dates=True)
        if len(df) < 120: continue
        
        df_input = df.iloc[:96]
        df_actual = df.iloc[96:120]
        
        targets = df_input[TARGET_COLS].values.astype(np.float32)
        timestamps = df_input.index
        
        # Calendar feature array (ignored by predict but kept for call compatibility)
        calendar = np.zeros((96, 6), dtype=np.float32)
        
        all_actuals.append(df_actual[TARGET_COLS].values)
        
        for name in model_names:
            preds, _ = service.predict(name, targets, calendar, timestamps=timestamps)
            all_preds[name].append(preds)
            
    # Compute overall R2
    actuals = np.concatenate(all_actuals, axis=0) # [N*24, 7]
    print("\n--- R2 Scores (Global Active Power) ---")
    for name in model_names:
        preds = np.concatenate(all_preds[name], axis=0)
        # Calculate R2 for the primary target (Global_active_power)
        # preds might be [N*24, 1] or [N*24, 7] depending on the model.
        # We only compare the first column (Global Active Power)
        y_true = actuals[:, 0]
        y_pred = preds[:, 0] if preds.ndim > 1 and preds.shape[1] > 1 else preds.flatten()
        r2 = r2_score(y_true, y_pred)
        print(f"{name}: {r2:.4f}")

if __name__ == "__main__":
    main()
