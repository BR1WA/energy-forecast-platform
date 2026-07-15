import pandas as pd
from typing import Tuple

class ChronologicalSplitter:
    """
    Splits time series data strictly chronologically to prevent temporal data leakage.
    Simulates Walk-Forward Validation structure.
    """
    def __init__(self, train_ratio: float = 0.7, val_ratio: float = 0.1):
        """
        Args:
            train_ratio: Proportion of data to use for training
            val_ratio: Proportion of data to use for validation
            (Remaining data is used for testing)
        """
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        
    def split(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Splits a DataFrame chronologically into Train, Validation, and Test sets.
        Assumes the DataFrame is already sorted by time.
        """
        n = len(df)
        train_end = int(n * self.train_ratio)
        val_end = int(n * (self.train_ratio + self.val_ratio))
        
        train_df = df.iloc[:train_end].copy()
        val_df = df.iloc[train_end:val_end].copy()
        test_df = df.iloc[val_end:].copy()
        
        return train_df, val_df, test_df
