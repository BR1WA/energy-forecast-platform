"""
Generate sample data windows and fit the StandardScaler from the raw dataset.
Run this script once locally to create:
  - app_forecast/weights/target_scaler.pkl
  - app_forecast/samples/*.csv
"""
import os
import sys
import numpy as np
import pandas as pd
import joblib
from sklearn.preprocessing import StandardScaler

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, '..', 'data', 'household_power_consumption.txt')
WEIGHTS_DIR = os.path.join(BASE_DIR, 'weights')
SAMPLES_DIR = os.path.join(BASE_DIR, 'samples')

TARGET_COLS = [
    'Global_active_power', 'Global_reactive_power', 'Voltage',
    'Global_intensity', 'Sub_metering_1', 'Sub_metering_2', 'Sub_metering_3'
]

LOOKBACK = 96
HORIZON = 24
WINDOW_SIZE = LOOKBACK + HORIZON  # 120 rows per sample


def load_and_preprocess(filepath):
    """Replicate the exact preprocessing from the training notebook."""
    print(f"Loading data from {filepath}...")
    df = pd.read_csv(filepath, sep=';', na_values=['?'], dtype={'Date': str, 'Time': str})

    initial_len = len(df)
    df = df.dropna()
    print(f"Dropped {initial_len - len(df)} missing rows.")

    df['Datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='%d/%m/%Y %H:%M:%S')
    df = df.drop(columns=['Date', 'Time']).set_index('Datetime')

    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df_h = df.resample('h').mean()
    df_h = df_h.ffill().bfill()
    print(f"Processed Hourly Dataset Shape: {df_h.shape}")
    return df_h


def main():
    if not os.path.exists(DATA_PATH):
        print(f"ERROR: Dataset not found at {DATA_PATH}")
        sys.exit(1)

    df_h = load_and_preprocess(DATA_PATH)

    # --- 1. Fit and save the StandardScaler on training data ---
    os.makedirs(WEIGHTS_DIR, exist_ok=True)

    train_mask = df_h.index < '2009-01-01'
    train_data = df_h.loc[train_mask, TARGET_COLS].values

    scaler = StandardScaler()
    scaler.fit(train_data)

    scaler_path = os.path.join(WEIGHTS_DIR, 'target_scaler.pkl')
    joblib.dump(scaler, scaler_path)
    print(f"Saved StandardScaler to {scaler_path}")
    print(f"  Mean: {scaler.mean_[:3]}...")
    print(f"  Scale: {scaler.scale_[:3]}...")

    # --- 2. Extract sample windows from the 2010 test set ---
    os.makedirs(SAMPLES_DIR, exist_ok=True)

    test_mask = df_h.index >= '2010-01-01'
    df_test = df_h.loc[test_mask, TARGET_COLS]
    print(f"\nTest set: {len(df_test)} hours ({df_test.index[0]} to {df_test.index[-1]})")

    # Define diverse sample windows
    sample_specs = [
        {'name': 'winter_weekday_jan', 'start': '2010-01-11 00:00:00',
         'desc': 'Winter weekday (January) — high heating demand'},
        {'name': 'winter_weekend_feb', 'start': '2010-02-06 00:00:00',
         'desc': 'Winter weekend (February) — relaxed home consumption'},
        {'name': 'spring_transition_apr', 'start': '2010-04-12 00:00:00',
         'desc': 'Spring transition (April) — moderate, variable loads'},
        {'name': 'summer_weekday_jul', 'start': '2010-07-05 00:00:00',
         'desc': 'Summer weekday (July) — low heating, cooling spikes'},
        {'name': 'summer_weekend_aug', 'start': '2010-08-14 00:00:00',
         'desc': 'Summer weekend (August) — vacation/relaxed patterns'},
        {'name': 'autumn_evening_oct', 'start': '2010-10-18 00:00:00',
         'desc': 'Autumn weekday (October) — evening peaks returning'},
        {'name': 'late_autumn_nov', 'start': '2010-11-08 00:00:00',
         'desc': 'Late autumn (November) — heating ramp-up'},
    ]

    for spec in sample_specs:
        try:
            start = pd.Timestamp(spec['start'])
            end = start + pd.Timedelta(hours=WINDOW_SIZE - 1)
            window = df_test.loc[start:end]

            if len(window) < WINDOW_SIZE:
                print(f"  WARN: {spec['name']} has only {len(window)} rows, skipping.")
                continue

            window = window.iloc[:WINDOW_SIZE]
            csv_path = os.path.join(SAMPLES_DIR, f"sample_{spec['name']}.csv")
            window.to_csv(csv_path)
            print(f"  Saved {spec['name']}: {window.index[0]} -> {window.index[-1]} ({len(window)} rows)")

        except Exception as e:
            print(f"  ERROR creating {spec['name']}: {e}")

    # --- 3. Save a metadata file ---
    meta = {s['name']: s['desc'] for s in sample_specs}
    meta_path = os.path.join(SAMPLES_DIR, 'sample_metadata.csv')
    pd.DataFrame(list(meta.items()), columns=['name', 'description']).to_csv(meta_path, index=False)
    print(f"\nSaved metadata to {meta_path}")
    print("Done! Sample generation complete.")


if __name__ == '__main__':
    main()
