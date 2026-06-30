import numpy as np

class WalkForwardValidator:
    """
    Implements rolling-origin evaluation (walk-forward validation) for time-series data.
    """
    def __init__(self, data_length, train_ratio=0.7, splits=3, forecast_horizon=24):
        self.data_length = data_length
        self.train_ratio = train_ratio
        self.splits = splits
        self.forecast_horizon = forecast_horizon

    def get_splits(self):
        """
        Yields (train_start, train_end, val_start, val_end) for each split.
        The train size grows over time, validating on the immediate next segment.
        """
        initial_train_size = int(self.data_length * self.train_ratio)
        val_size = (self.data_length - initial_train_size) // self.splits
        
        for i in range(self.splits):
            train_start = 0
            train_end = initial_train_size + i * val_size
            val_start = train_end - self.forecast_horizon # overlap to allow lookback for first prediction
            val_end = train_end + val_size
            
            # Ensure we don't exceed data boundaries
            if val_end > self.data_length:
                val_end = self.data_length
                
            yield train_start, train_end, val_start, val_end
