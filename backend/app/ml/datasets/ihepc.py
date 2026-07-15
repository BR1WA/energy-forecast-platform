import pandas as pd
import numpy as np
import os
from typing import Dict, Any, List
from .provider import DatasetProvider

class IHEPCDataset(DatasetProvider):
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.filepath = os.path.join(data_dir, "household_power_consumption.txt")
        self.weather_filepath = os.path.join(data_dir, "clamart_weather_2006_2010.csv")
        
    def load(self) -> pd.DataFrame:
        if not os.path.exists(self.filepath):
            raise FileNotFoundError(f"Dataset not found at {self.filepath}")
            
        df = pd.read_csv(self.filepath, sep=';', 
                         parse_dates={'Datetime': ['Date', 'Time']},
                         infer_datetime_format=True,
                         low_memory=False, 
                         na_values=['?'])
        return df

    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.set_index('Datetime')
        # Fill missing values
        df = df.ffill().bfill()
        # Resample to hourly data for forecasting
        df = df.resample('1H').mean()
        # Drop rows with any remaining NaNs after resampling
        df = df.dropna()
        df = df.reset_index()
        return df

    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df_out = df.copy()
        
        # We will merge weather data if requested by the pipeline
        # Calendar features will be added dynamically by the pipeline or here
        if self.supports_calendar():
            df_out['hour'] = df_out['Datetime'].dt.hour
            df_out['weekday'] = df_out['Datetime'].dt.weekday
            df_out['month'] = df_out['Datetime'].dt.month
            df_out['day_of_year'] = df_out['Datetime'].dt.dayofyear
            
        return df_out

    def create_targets(self, df: pd.DataFrame) -> pd.DataFrame:
        # IHEPC standard targets
        targets = [
            'Global_active_power', 'Global_reactive_power', 'Voltage',
            'Global_intensity', 'Sub_metering_1', 'Sub_metering_2', 'Sub_metering_3'
        ]
        return df[targets]

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "ihepc",
            "timezone": "Europe/Paris",
            "frequency": "1H",
            "targets": [
                'Global_active_power', 'Global_reactive_power', 'Voltage',
                'Global_intensity', 'Sub_metering_1', 'Sub_metering_2', 'Sub_metering_3'
            ],
            "covariates": ['hour', 'weekday', 'month', 'day_of_year', 'Temperature', 'Humidity', 'WindSpeed']
        }

    def supports_weather(self) -> bool:
        return True

    def supports_calendar(self) -> bool:
        return True
        
    def merge_weather(self, df: pd.DataFrame) -> pd.DataFrame:
        if not os.path.exists(self.weather_filepath):
            return df # Return unmodified if weather is missing
            
        weather_df = pd.read_csv(self.weather_filepath, parse_dates=['Datetime'])
        # Merge on Datetime using left join to preserve original timestamps
        merged = pd.merge(df, weather_df, on='Datetime', how='left')
        # Forward fill missing weather data
        merged[['Temperature', 'Humidity', 'WindSpeed']] = merged[['Temperature', 'Humidity', 'WindSpeed']].ffill().bfill()
        return merged
