"""Utility functions for the Netro Sprinklers plugin.

This module provides common utility functions used throughout the plugin:

- convert_timestamp: Convert Unix timestamps to local datetime
- get_key_from_dict: Safely retrieve values from dictionaries

These functions are extracted from plugin.py to enable reuse and testing.

Note:
    This module only imports from Python standard library and dateutil.
    It has no dependencies on other plugin modules to prevent circular imports.
"""

from datetime import datetime
from typing import Any

from dateutil import tz


def convert_timestamp(timestamp_ms: int) -> datetime:
    """Convert Unix timestamp (milliseconds) to local timezone datetime.

    The Netro API returns timestamps as Unix epoch time in milliseconds.
    This function converts them to Python datetime objects in the local
    timezone for display and comparison.

    Args:
        timestamp_ms: Unix timestamp in milliseconds (e.g., 1706889600000)

    Returns:
        datetime object in local timezone

    Example:
        >>> dt = convert_timestamp(1706889600000)
        >>> print(dt.strftime('%Y-%m-%d'))
        '2024-02-02'

    Note:
        Uses dateutil.tz for reliable timezone handling across platforms.
        The function converts from UTC to local time automatically.
    """
    from_zone = tz.tzutc()
    to_zone = tz.tzlocal()
    time_utc = datetime.utcfromtimestamp(timestamp_ms / 1000)
    time_utc_gmt = time_utc.replace(tzinfo=from_zone)
    return time_utc_gmt.astimezone(to_zone)


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
    """
    try:
        return data[key]
    except KeyError:
        return "unavailable from API" if default is None else default
    except (TypeError, AttributeError):
        # dict is None or not a dict-like object
        return "unknown error" if default is None else default
