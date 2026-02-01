"""Custom exception classes for the Netro Sprinklers plugin.

This module defines a hierarchy of exceptions for handling various error
conditions in the plugin. All exceptions inherit from NetroError, allowing
callers to catch all plugin exceptions with a single except clause.

Exception Hierarchy:
    NetroError (base)
    ├── ThrottleDelayError   - API rate limit exceeded
    ├── NetroAPIError        - API returned error response
    ├── NetroConnectionError - Network connection failed
    └── NetroTimeoutError    - Request timed out

Note:
    This module intentionally has no external dependencies (pure Python)
    to prevent circular imports and ensure it can be imported anywhere.
"""

from datetime import datetime
from typing import Optional


class NetroError(Exception):
    """Base exception for all Netro plugin errors.

    All plugin-specific exceptions inherit from this class, allowing
    callers to catch all Netro errors with: except NetroError
    """


class ThrottleDelayError(NetroError):
    """Raised when API calls are throttled due to rate limit violations.

    The Netro API allows 2000 calls per day. When the limit is exceeded,
    the API returns HTTP 429 or error code 3. This exception is raised
    to prevent further API calls until the throttle period expires.

    Attributes:
        message: Human-readable error description
        retry_after: Optional datetime when API calls can resume

    Example:
        >>> raise ThrottleDelayError("Rate limit exceeded", retry_after=datetime.now())
        >>> try:
        ...     make_api_call()
        ... except ThrottleDelayError as e:
        ...     print(f"Throttled until {e.retry_after}")
    """

    def __init__(
        self,
        message: str = "API rate limit exceeded",
        retry_after: Optional[datetime] = None
    ) -> None:
        """Initialize ThrottleDelayError.

        Args:
            message: Human-readable error description
            retry_after: Optional datetime when API calls can resume
        """
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after


class NetroAPIError(NetroError):
    """Raised when the Netro API returns an error response.

    This exception is raised for API-level errors (e.g., invalid key,
    bad parameters) as opposed to network-level errors.

    Attributes:
        message: Human-readable error description
        status_code: HTTP status code (if available)
        error_code: Netro API error code (if available)

    Example:
        >>> raise NetroAPIError("Invalid serial number", error_code=1)
    """

    def __init__(
        self,
        message: str = "API error occurred",
        status_code: Optional[int] = None,
        error_code: Optional[int] = None
    ) -> None:
        """Initialize NetroAPIError.

        Args:
            message: Human-readable error description
            status_code: HTTP status code (if available)
            error_code: Netro API error code (if available)
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


class NetroConnectionError(NetroError):
    """Raised when connection to the Netro API fails.

    This exception is raised for network-level failures such as
    DNS resolution errors, connection refused, or network unreachable.

    Attributes:
        message: Human-readable error description
        original_error: The underlying exception that caused this error
    """

    def __init__(
        self,
        message: str = "Connection to Netro API failed",
        original_error: Optional[Exception] = None
    ) -> None:
        """Initialize NetroConnectionError.

        Args:
            message: Human-readable error description
            original_error: The underlying exception that caused this error
        """
        super().__init__(message)
        self.message = message
        self.original_error = original_error


class NetroTimeoutError(NetroError):
    """Raised when a request to the Netro API times out.

    This exception is raised when the API doesn't respond within
    the configured timeout period.

    Attributes:
        message: Human-readable error description
        timeout_seconds: The timeout value that was exceeded
    """

    def __init__(
        self,
        message: str = "Request to Netro API timed out",
        timeout_seconds: Optional[float] = None
    ) -> None:
        """Initialize NetroTimeoutError.

        Args:
            message: Human-readable error description
            timeout_seconds: The timeout value that was exceeded
        """
        super().__init__(message)
        self.message = message
        self.timeout_seconds = timeout_seconds
