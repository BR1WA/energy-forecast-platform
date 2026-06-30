class DataValidationError(Exception):
    """Base class for data validation errors."""
    pass

class MissingTimestampError(DataValidationError):
    """Raised when there are missing timestamps in the sequence."""
    pass

class DuplicateTimestampError(DataValidationError):
    """Raised when there are duplicate timestamps in the sequence."""
    pass

class NaNDetectedError(DataValidationError):
    """Raised when NaN values are detected in critical columns."""
    pass

class ImpossibleValueError(DataValidationError):
    """Raised when values are physically impossible (e.g., negative consumption)."""
    pass

class DataLeakageError(DataValidationError):
    """Raised when there is an overlap between training and validation/test sets."""
    pass

class SequenceLengthError(DataValidationError):
    """Raised when the sequence length is shorter than required."""
    pass
