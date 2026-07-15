import pandas as pd
import numpy as np
import os
from typing import Dict, Any, List
from .provider import DatasetProvider

class ECLDataset(DatasetProvider):
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.filepath = os.path.join(data_dir, "electricity.csv")
        
    def load(self) -> pd.DataFrame:
        if not os.path.exists(self.filepath):
            raise FileNotFoundError(f"ECL dataset not found at {self.filepath}. Please download it via scripts/download_ecl.py")
            
        df = pd.read_csv(self.filepath, parse_dates=['date'])
        df = df.rename(columns={'date': 'Datetime'})
        return df

    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.set_index('Datetime')
        # Fill missing values if any
        df = df.ffill().bfill()
        df = df.reset_index()
        return df

    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df_out = df.copy()
        
        if self.supports_calendar():
            df_out['hour'] = df_out['Datetime'].dt.hour
            df_out['weekday'] = df_out['Datetime'].dt.weekday
            df_out['month'] = df_out['Datetime'].dt.month
            df_out['day_of_year'] = df_out['Datetime'].dt.dayofyear
            
        return df_out

    def create_targets(self, df: pd.DataFrame) -> pd.DataFrame:
        # ECL has 321 clients (MT_001 to MT_321)
        target_cols = [col for col in df.columns if col.startswith('MT_')]
        return df[target_cols]

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "ecl",
            "timezone": "UTC",
            "frequency": "1H",
            "targets": [f"MT_{str(i).zfill(3)}" for i in range(1, 322)],
            "covariates": ['hour', 'weekday', 'month', 'day_of_year']
        }

    def supports_weather(self) -> bool:
        # Standard ECL benchmark does not use weather covariates
        return False

    def supports_calendar(self) -> bool:
        return True
