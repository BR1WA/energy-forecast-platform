import sys, os
import pandas as pd, numpy as np
from pathlib import Path
from sklearn.metrics import r2_score

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from app.services.forecast_service import get_forecast_service
from app.config import get_settings

TARGET_COLS = [
    'Global_active_power', 'Global_reactive_power', 'Voltage',
    'Global_intensity', 'Sub_metering_1', 'Sub_metering_2', 'Sub_metering_3'
]

def main():
    service = get_forecast_service()
    if not service.models:
        print("No models loaded!")
        return
        
    print("Models loaded:", list(service.models.keys()))
    
    samples_dir = Path("C:/Users/salah/Documents/MASTER/PFE2/app_forecast/samples")
    
    all_actuals = []
    all_preds = {name: [] for name in service.models.keys()}
    
    for sample_file in samples_dir.glob("*.csv"):
        if sample_file.name == "sample_metadata.csv": continue
        
        df = pd.read_csv(sample_file, index_col=0, parse_dates=True)
        if len(df) < 120: continue
        
        df_input = df.iloc[:96]
        df_actual = df.iloc[96:120]
        
        targets = df_input[TARGET_COLS].values.astype(np.float32)
        
        hours = df_input.index.hour.values
        days = df_input.index.dayofweek.values
        months = df_input.index.month.values
        
        hour_sin = np.sin(2 * np.pi * hours / 24.0)
        hour_cos = np.cos(2 * np.pi * hours / 24.0)
        day_sin = np.sin(2 * np.pi * days / 7.0)
        day_cos = np.cos(2 * np.pi * days / 7.0)
        month_sin = np.sin(2 * np.pi * months / 12.0)
        month_cos = np.cos(2 * np.pi * months / 12.0)
        
        calendar = np.stack([hour_sin, hour_cos, day_sin, day_cos, month_sin, month_cos], axis=1).astype(np.float32)
        
        all_actuals.append(df_actual[TARGET_COLS].values)
        
        for name in service.models.keys():
            preds, _ = service.predict(name, targets, calendar)
            all_preds[name].append(preds)
            
    # Compute overall R2
    actuals = np.concatenate(all_actuals, axis=0) # [N*24, 7]
    print("\n--- R2 Scores (Global Active Power) ---")
    for name in service.models.keys():
        preds = np.concatenate(all_preds[name], axis=0)
        # Calculate R2 for the primary target (Global_active_power)
        r2 = r2_score(actuals[:, 0], preds[:, 0])
        print(f"{name}: {r2:.4f}")
        
    print("\n--- R2 Scores (Average over all 7 variables) ---")
    for name in service.models.keys():
        preds = np.concatenate(all_preds[name], axis=0)
        r2 = r2_score(actuals, preds, multioutput='uniform_average')
        print(f"{name}: {r2:.4f}")

if __name__ == "__main__":
    main()
