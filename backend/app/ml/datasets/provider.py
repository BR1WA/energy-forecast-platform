from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, Any, List

class DatasetProvider(ABC):
    """
    Abstract base class for all datasets in the platform.
    Defines capabilities and provides a unified interface for loading data.
    """
    
    @abstractmethod
    def load(self) -> pd.DataFrame:
        """Load the raw dataset into a DataFrame."""
        pass
        
    @abstractmethod
    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply dataset-specific cleaning and formatting."""
        pass
        
    @abstractmethod
    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create time-based or derived features."""
        pass
        
    @abstractmethod
    def create_targets(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare the target variables."""
        pass
        
    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Return dataset metadata (timezone, frequency, columns)."""
        pass
        
    @abstractmethod
    def supports_weather(self) -> bool:
        """Return True if the dataset supports weather covariates."""
        pass
        
    @abstractmethod
    def supports_calendar(self) -> bool:
        """Return True if the dataset supports calendar covariates."""
        pass
