import pandas as pd
import numpy as np
from .exceptions import (
    MissingTimestampError,
    DuplicateTimestampError,
    NaNDetectedError,
    ImpossibleValueError,
    DataLeakageError
)

class DatasetValidator:
    """
    Validates energy forecasting datasets before training or inference to ensure
    no garbage data makes it into the pipeline.
    """
    
    def __init__(self, time_col='timestamp', target_cols=['gap']):
        self.time_col = time_col
        self.target_cols = target_cols
        
    def validate(self, df: pd.DataFrame, freq='1h', missing_strategy='fail'):
        """
        Run all validation checks on the dataset.
        missing_strategy: 'fail', 'interpolate', 'forward-fill', or 'ignore'
        """
        self._check_time_col_exists(df)
        self._check_duplicates(df)
        self._check_missing_timestamps(df, freq, missing_strategy)
        self._check_nans(df, missing_strategy)
        self._check_impossible_values(df)
        return True

    def _check_time_col_exists(self, df: pd.DataFrame):
        if self.time_col not in df.columns:
            raise KeyError(f"Time column '{self.time_col}' not found in dataset.")

    def _check_duplicates(self, df: pd.DataFrame):
        duplicates = df.duplicated(subset=[self.time_col]).sum()
        if duplicates > 0:
            raise DuplicateTimestampError(f"Found {duplicates} duplicate timestamps.")

    def _check_missing_timestamps(self, df: pd.DataFrame, freq: str, strategy: str):
        # Assumes df is sorted or sorts it temporarily
        timestamps = pd.to_datetime(df[self.time_col])
        timestamps = timestamps.sort_values()
        
        # Create a complete date range
        start = timestamps.min()
        end = timestamps.max()
        expected_range = pd.date_range(start=start, end=end, freq=freq)
        
        missing = set(expected_range) - set(timestamps)
        if len(missing) > 0:
            if strategy == 'fail':
                raise MissingTimestampError(f"Found {len(missing)} missing timestamps in sequence (freq={freq}).")
            else:
                # Return the missing count, but don't fail. FeaturePipeline will handle the imputation.
                print(f"Warning: {len(missing)} missing timestamps detected. Strategy: {strategy}")

    def _check_nans(self, df: pd.DataFrame, strategy: str):
        nan_counts = df[self.target_cols].isna().sum()
        total_nans = nan_counts.sum()
        if total_nans > 0:
            cols_with_nans = nan_counts[nan_counts > 0].index.tolist()
            if strategy == 'fail':
                raise NaNDetectedError(f"Found {total_nans} NaN values across critical columns: {cols_with_nans}")
            else:
                print(f"Warning: {total_nans} NaNs detected. Strategy: {strategy}")

    def _check_impossible_values(self, df: pd.DataFrame):
        # Specific check: target columns should not be negative
        for col in self.target_cols:
            if (df[col] < 0).any():
                neg_count = (df[col] < 0).sum()
                raise ImpossibleValueError(f"Found {neg_count} negative (impossible) values in column '{col}'.")
                
    def check_leakage(self, train_df: pd.DataFrame, val_df: pd.DataFrame):
        """
        Checks if there is overlap in timestamps between train and validation/test sets.
        """
        train_times = set(pd.to_datetime(train_df[self.time_col]))
        val_times = set(pd.to_datetime(val_df[self.time_col]))
        
        overlap = train_times.intersection(val_times)
        if len(overlap) > 0:
            raise DataLeakageError(f"Data leakage detected: {len(overlap)} overlapping timestamps between sets.")
        return True
