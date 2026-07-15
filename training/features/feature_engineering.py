import pandas as pd
import numpy as np
import pickle
from typing import List, Optional
from sklearn.preprocessing import StandardScaler
from .validators import DatasetValidator

class FeaturePipeline:
    """
    A unified preprocessing pipeline that applies data validation, feature engineering,
    and scaling. This ensures that both training and backend inference use the exact
    same transformations.
    """
    def __init__(self, time_col: str = 'timestamp', target_cols: List[str] = ['gap']):
        self.time_col = time_col
        self.target_cols = target_cols
        self.scaler = StandardScaler()
        self.validator = DatasetValidator(time_col=time_col, target_cols=target_cols)
        self.is_fitted = False
        self.feature_columns = []
        self.scale_cols = []

    def fit(self, df: pd.DataFrame, freq: str = 'h', missing_strategy: str = 'fail'):
        # Validate data quality before fitting
        self.validator.validate(df, freq=freq, missing_strategy=missing_strategy)
        
        df_sorted = df.sort_values(by=self.time_col)
        df_sorted = self._handle_missing(df_sorted, freq, missing_strategy)
        
        # Scale all numeric columns (excluding time column)
        numeric_cols = df_sorted.select_dtypes(include=[np.number]).columns.tolist()
        self.scale_cols = [c for c in numeric_cols if c != self.time_col]
        
        self.scaler.fit(df_sorted[self.scale_cols])
        self.is_fitted = True
        
        # Process once to get feature columns
        transformed_df = self._add_time_features(df_sorted)
        # Exclude timestamp
        self.feature_columns = [col for col in transformed_df.columns if col != self.time_col]

    def transform(self, df: pd.DataFrame, validate: bool = True, freq: str = 'h', missing_strategy: str = 'fail') -> pd.DataFrame:
        if not self.is_fitted:
            raise RuntimeError("Pipeline is not fitted. Call fit() first.")
            
        if validate:
            self.validator.validate(df, freq=freq, missing_strategy=missing_strategy)
            
        df_out = df.copy()
        df_out = df_out.sort_values(by=self.time_col)
        df_out = self._handle_missing(df_out, freq, missing_strategy)
        
        # Scale all continuous features
        df_out[self.scale_cols] = self.scaler.transform(df_out[self.scale_cols])
        
        # Add time features
        df_out = self._add_time_features(df_out)
        
        return df_out

    def fit_transform(self, df: pd.DataFrame, freq: str = 'h', missing_strategy: str = 'fail') -> pd.DataFrame:
        self.fit(df, freq, missing_strategy)
        return self.transform(df, validate=False, freq=freq, missing_strategy=missing_strategy)

    def inverse_transform_targets(self, y: np.ndarray) -> np.ndarray:
        """
        Inverse transform an array of predictions or ground truths that correspond
        exactly to self.target_cols.
        """
        indices = [self.scale_cols.index(c) for c in self.target_cols]
        means = self.scaler.mean_[indices]
        scales = self.scaler.scale_[indices]
        return y * scales + means

    def _handle_missing(self, df: pd.DataFrame, freq: str, strategy: str) -> pd.DataFrame:
        if strategy == 'fail' or strategy == 'ignore':
            return df
            
        # Reindex to create explicit rows for missing timestamps
        df = df.set_index(pd.to_datetime(df[self.time_col]))
        full_index = pd.date_range(start=df.index.min(), end=df.index.max(), freq=freq)
        df = df.reindex(full_index)
        df[self.time_col] = df.index
        
        if strategy == 'interpolate':
            df[self.target_cols] = df[self.target_cols].interpolate(method='linear')
        elif strategy == 'forward-fill':
            df[self.target_cols] = df[self.target_cols].ffill()
            
        df = df.reset_index(drop=True)
        return df

    def _add_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df_out = df.copy()
        timestamps = pd.to_datetime(df_out[self.time_col])
        df_out['hour'] = timestamps.dt.hour
        df_out['weekday'] = timestamps.dt.weekday
        df_out['month'] = timestamps.dt.month
        df_out['day_of_year'] = timestamps.dt.dayofyear
        return df_out

    def save(self, filepath: str):
        with open(filepath, 'wb') as f:
            pickle.dump({
                'scaler': self.scaler,
                'feature_columns': self.feature_columns,
                'time_col': self.time_col,
                'target_cols': self.target_cols,
                'scale_cols': getattr(self, 'scale_cols', []),
            }, f)

    def load(self, filepath: str):
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
            self.scaler = data['scaler']
            self.feature_columns = data['feature_columns']
            self.time_col = data['time_col']
            self.target_cols = data['target_cols']
            self.scale_cols = data.get('scale_cols', [])
            self.is_fitted = True
