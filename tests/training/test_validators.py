import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from training.features.validators import DatasetValidator
from training.features.exceptions import (
    MissingTimestampError,
    DuplicateTimestampError,
    NaNDetectedError,
    ImpossibleValueError,
    DataLeakageError
)

def create_mock_dataset(rows=10, freq='h', start="2026-01-01 00:00:00"):
    dates = pd.date_range(start=start, periods=rows, freq=freq)
    df = pd.DataFrame({
        'timestamp': dates,
        'gap': np.random.uniform(0.5, 5.0, rows)
    })
    return df

def test_validator_passes_valid_data():
    df = create_mock_dataset()
    validator = DatasetValidator()
    assert validator.validate(df, freq='h') == True

def test_validator_catches_duplicates():
    df = create_mock_dataset()
    # duplicate row 1
    df = pd.concat([df, df.iloc[[1]]], ignore_index=True)
    
    validator = DatasetValidator()
    with pytest.raises(DuplicateTimestampError):
        validator.validate(df, freq='h')

def test_validator_catches_missing_timestamps():
    df = create_mock_dataset()
    # drop a row in the middle
    df = df.drop(index=[3]).reset_index(drop=True)
    
    validator = DatasetValidator()
    with pytest.raises(MissingTimestampError):
        validator.validate(df, freq='h')

def test_validator_catches_nans():
    df = create_mock_dataset()
    df.loc[2, 'gap'] = np.nan
    
    validator = DatasetValidator()
    with pytest.raises(NaNDetectedError):
        validator.validate(df, freq='h')

def test_validator_catches_impossible_values():
    df = create_mock_dataset()
    df.loc[4, 'gap'] = -1.5
    
    validator = DatasetValidator()
    with pytest.raises(ImpossibleValueError):
        validator.validate(df, freq='h')

def test_validator_catches_leakage():
    train_df = create_mock_dataset(rows=5, start="2026-01-01 00:00:00")
    # overlap by starting val at same day 04:00
    val_df = create_mock_dataset(rows=5, start="2026-01-01 04:00:00")
    
    validator = DatasetValidator()
    with pytest.raises(DataLeakageError):
        validator.check_leakage(train_df, val_df)
