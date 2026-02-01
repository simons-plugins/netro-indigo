"""Utility functions for the Netro Sprinklers plugin.

This module provides common utility functions used throughout the plugin:

- get_key_from_dict: Safely retrieve values from dictionaries

These functions are extracted from plugin.py to enable reuse and testing.

Note:
    This module only imports from Python standard library.
    It has no dependencies on other plugin modules to prevent circular imports.
"""

from typing import Any


def get_key_from_dict(key: str, data: dict, default: Any = None) -> Any:
    """Safely get value from dictionary with graceful error handling.

    This function provides a safe way to retrieve values from API responses
    that may be missing expected keys or have unexpected structure.

    Args:
        key: Dictionary key to retrieve
        data: Dictionary to search
        default: Value to return if key not found (default: None)

    Returns:
        Value if key exists, otherwise:
        - "unavailable from API" for KeyError (when default is None)
        - "unknown error" for TypeError/AttributeError (when default is None)
        - default value if provided

    Example:
        >>> get_key_from_dict("name", {"name": "Zone 1"})
        'Zone 1'
        >>> get_key_from_dict("missing", {})
        'unavailable from API'
        >>> get_key_from_dict("missing", {}, default="N/A")
        'N/A'
        >>> get_key_from_dict("key", None)
        'unknown error'

    Note:
        This matches existing plugin.py behavior for backward compatibility
        with API response handling. The specific string returns are used
        in Indigo device state values.

    Warning:
        This function fails silently by design - errors are converted to
        fallback strings rather than raised. Callers should log when they
        receive "unavailable from API" or "unknown error" if visibility
        into missing data is important.
    """
    try:
        return data[key]
    except KeyError:
        return "unavailable from API" if default is None else default
    except (TypeError, AttributeError):
        # dict is None or not a dict-like object
        return "unknown error" if default is None else default
