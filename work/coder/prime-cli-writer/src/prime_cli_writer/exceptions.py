"""Custom exceptions for the prime CLI writer package."""


class PrimeCliWriterError(Exception):
    """Base exception for project-specific failures."""


class InputValidationError(PrimeCliWriterError):
    """Raised when CLI input values fail validation."""


class OutputWriteError(PrimeCliWriterError):
    """Raised when output file writing fails."""
