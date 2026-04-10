"""Utility functions for the Netro Sprinklers plugin.

This module provides common utility functions used throughout the plugin:

- Unit conversions: Bidirectional metric/US conversions for temperature,
  rainfall, wind speed, and pressure
- Weather data conversion: convert_weather_us_to_metric / convert_weather_metric_to_us
  for transforming weather dicts between API v1 (US) and v2 (metric) formats
- get_key_from_dict: Safely retrieve values from dictionaries

These functions are extracted from plugin.py to enable reuse and testing.

Note:
    This module only imports from Python standard library.
    It has no dependencies on other plugin modules to prevent circular imports.
"""

from typing import Any, Dict


def fahrenheit_to_celsius(f: float) -> float:
    """Convert Fahrenheit to Celsius."""
    return (f - 32) * 5 / 9


def inches_to_mm(inches: float) -> float:
    """Convert inches to millimeters."""
    return inches * 25.4


def mph_to_ms(mph: float) -> float:
    """Convert miles per hour to meters per second."""
    return mph * 0.44704


def inhg_to_hpa(inhg: float) -> float:
    """Convert inches of mercury to hectopascals."""
    return inhg * 33.8639


def convert_weather_us_to_metric(weather_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert weather data from US units to metric for API v2.

    V1 API expects US units (°F, inches, mph, inHg).
    V2 API expects metric (°C, mm, m/s, hPa).

    Args:
        weather_data: Weather dict with US-unit values

    Returns:
        New dict with values converted to metric units
    """
    converted = dict(weather_data)

    # Temperature fields: °F → °C
    for temp_key in ("t", "t_max", "t_min"):
        if temp_key in converted and converted[temp_key] is not None:
            converted[temp_key] = round(fahrenheit_to_celsius(float(converted[temp_key])), 1)

    # Rainfall: inches → mm
    if "rain" in converted and converted["rain"] is not None:
        converted["rain"] = round(inches_to_mm(float(converted["rain"])), 1)

    # Wind speed: mph → m/s
    if "wind_speed" in converted and converted["wind_speed"] is not None:
        converted["wind_speed"] = round(mph_to_ms(float(converted["wind_speed"])), 1)

    # Pressure: inHg → hPa
    if "pressure" in converted and converted["pressure"] is not None:
        converted["pressure"] = round(inhg_to_hpa(float(converted["pressure"])), 1)

    return converted


def celsius_to_fahrenheit(c: float) -> float:
    """Convert Celsius to Fahrenheit."""
    return c * 9 / 5 + 32


def mm_to_inches(mm: float) -> float:
    """Convert millimeters to inches."""
    return mm / 25.4


def ms_to_mph(ms: float) -> float:
    """Convert meters per second to miles per hour."""
    return ms / 0.44704


def hpa_to_inhg(hpa: float) -> float:
    """Convert hectopascals to inches of mercury."""
    return hpa / 33.8639


def convert_weather_metric_to_us(weather_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert weather data from metric to US units for API v1.

    V1 API expects US units (F, inches, mph, inHg).
    V2 API expects metric (C, mm, m/s, hPa).

    Args:
        weather_data: Weather dict with metric-unit values

    Returns:
        New dict with values converted to US units
    """
    converted = dict(weather_data)

    # Temperature fields: C -> F
    for temp_key in ("t", "t_max", "t_min"):
        if temp_key in converted and converted[temp_key] is not None:
            converted[temp_key] = round(celsius_to_fahrenheit(float(converted[temp_key])), 1)

    # Rainfall: mm -> inches
    if "rain" in converted and converted["rain"] is not None:
        converted["rain"] = round(mm_to_inches(float(converted["rain"])), 2)

    # Wind speed: m/s -> mph
    if "wind_speed" in converted and converted["wind_speed"] is not None:
        converted["wind_speed"] = round(ms_to_mph(float(converted["wind_speed"])), 1)

    # Pressure: hPa -> inHg
    if "pressure" in converted and converted["pressure"] is not None:
        converted["pressure"] = round(hpa_to_inhg(float(converted["pressure"])), 2)

    return converted


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
