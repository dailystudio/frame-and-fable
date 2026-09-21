"""
Custom exceptions for the model-creator library.
"""


class ModelCreatorError(Exception):
    """Base exception for all model-creator errors."""
    pass


class ConfigurationError(ModelCreatorError):
    """Raised when configuration or options are invalid."""
    pass


class ProviderNotFoundError(ModelCreatorError):
    """Raised when a requested provider is not found."""
    pass


class ProviderError(ModelCreatorError):
    """Base exception for provider-specific API errors."""

    def __init__(self, message: str, provider: str, status_code: int = None, error_code: str = None, details: dict = None):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}

    def __str__(self):
        parts = [f"[{self.provider}] {super().__str__()}"]
        if self.status_code:
            parts.append(f"(HTTP {self.status_code})")
        if self.error_code:
            parts.append(f"(Code: {self.error_code})")
        return " ".join(parts)


class AuthenticationError(ProviderError):
    """Raised when authentication fails (invalid or missing API key)."""
    pass


class InsufficientCreditsError(ProviderError):
    """Raised when the account does not have sufficient credits or subscription plan."""
    pass


class RateLimitError(ProviderError):
    """Raised when API rate limit is exceeded."""

    def __init__(self, message: str, provider: str, retry_after: float = None, **kwargs):
        super().__init__(message, provider, **kwargs)
        self.retry_after = retry_after


class InvalidRequestError(ProviderError):
    """Raised when input parameters, files, or options are invalid."""
    pass


class ContentViolationError(ProviderError):
    """Raised when prompt or images violate provider content policy."""
    pass


class TaskFailedError(ProviderError):
    """Raised when model generation fails remotely."""
    pass


class TaskTimeoutError(ModelCreatorError):
    """Raised when model generation polling exceeds deadline."""
    pass
