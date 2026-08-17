"""Pure validation functions for ConfigUi callbacks.

This module contains pure validation functions extracted from plugin.py's
validateConfigUi callbacks. All functions are side-effect free and return
consistent validation results.

The module is designed to be:
- Testable in isolation (no Indigo dependencies)
- Pure functions (no logging, no state modification)
- Consistent return types (ValidationResult tuple)

Typical usage:
    from validators import validate_device_config, validate_prefs_config

    is_valid, sanitized, errors = validate_device_config(values, "sprinkler")
    if not is_valid:
        return (False, values, errors)

Note:
    This module only imports from constants.py and Python standard library
    to prevent circular imports and maintain testability.
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from constants import (
    MINIMUM_EVENTS_INTERVAL_MINUTES,
    MINIMUM_DEVICE_INFO_INTERVAL_MINUTES,
    MINIMUM_SCHEDULES_INTERVAL_MINUTES,
    MINIMUM_MOISTURES_INTERVAL_MINUTES,
    MINIMUM_SENSOR_INTERVAL_MINUTES,
    MINIMUM_WEATHER_UPDATE_INTERVAL_MINUTES,
    MINIMUM_FORECAST_INTERVAL_MINUTES,
)


# Type alias for validation function return values
ValidationResult = Tuple[bool, Dict[str, Any], Dict[str, str]]
"""Standard return type: (is_valid, sanitized_values, errors_dict)"""


__all__ = [
    "validate_device_config",
    "validate_action_config",
    "validate_event_config",
    "validate_prefs_config",
]


# =============================================================================
# Helper Functions
# =============================================================================


def validate_integer_range(
    value: Any,
    field_name: str,
    min_val: int,
    max_val: int,
    default: Optional[int] = None,
) -> Tuple[bool, Optional[int], Optional[str]]:
    """Validate and parse an integer value within a range.

    Handles empty/None values with optional default. Converts string input
    to integer and validates against min/max bounds.

    Args:
        value: The value to validate (may be string, int, or None)
        field_name: Human-readable field name for error messages
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)
        default: Optional default value if input is empty/None

    Returns:
        Tuple of (is_valid, parsed_value, error_message).
        If is_valid is True, error_message is None.
        If is_valid is False, parsed_value may be None.
    """
    # Handle empty/None with default
    if value is None or (isinstance(value, str) and not value.strip()):
        if default is not None:
            return (True, default, None)
        return (False, None, f"{field_name} is required")

    # Convert to int
    try:
        int_value = int(value)
    except (ValueError, TypeError):
        return (False, None, f"{field_name} must be a valid number")

    # Validate range
    if int_value < min_val or int_value > max_val:
        return (False, int_value, f"{field_name} must be between {min_val} and {max_val}")

    return (True, int_value, None)


def validate_serial_number(
    serial: Any,
    device_type: str,
) -> Tuple[bool, str, Optional[str]]:
    """Validate a device serial number.

    Strips whitespace, checks for empty values, and validates minimum length.

    Args:
        serial: The serial number to validate (typically string)
        device_type: Device type for error messages (e.g., "Netro controller")

    Returns:
        Tuple of (is_valid, sanitized_serial, error_message).
        sanitized_serial is stripped of whitespace.
        If is_valid is True, error_message is None.
    """
    # Handle None
    if serial is None:
        return (False, "", f"Serial number is required for {device_type}")

    # Strip whitespace
    sanitized = str(serial).strip()

    # Check for empty
    if not sanitized:
        return (False, "", f"Serial number is required for {device_type}")

    # Check minimum length
    if len(sanitized) < 8:
        return (False, sanitized, "Serial number appears too short (should be 12 hex characters)")

    return (True, sanitized, None)


def validate_required_float(
    value: Any,
    field_name: str,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
) -> Tuple[bool, Optional[float], Optional[str]]:
    """Validate a required float value with optional range checking.

    Args:
        value: The value to validate (may be string or number)
        field_name: Human-readable field name for error messages
        min_val: Optional minimum value (inclusive)
        max_val: Optional maximum value (inclusive)

    Returns:
        Tuple of (is_valid, parsed_value, error_message).
        If is_valid is True, error_message is None.
    """
    # Handle empty/None
    if value is None or (isinstance(value, str) and not value.strip()):
        return (False, None, f"{field_name} is required")

    # Convert to float
    try:
        float_value = float(value)
    except (ValueError, TypeError):
        return (False, None, f"{field_name} must be a valid number")

    # Validate range if specified
    if min_val is not None and float_value < min_val:
        return (False, float_value, f"{field_name} must be at least {min_val}")
    if max_val is not None and float_value > max_val:
        return (False, float_value, f"{field_name} must be at most {max_val}")

    return (True, float_value, None)


def validate_optional_float(
    value: Any,
    field_name: str,
    min_val: float,
    max_val: float,
) -> Tuple[bool, Optional[float], Optional[str]]:
    """Validate an optional float value within a range.

    Returns success with None value if the input is empty. Otherwise
    validates that the value is a number within the specified range.

    Args:
        value: The value to validate (may be string, number, or None)
        field_name: Human-readable field name for error messages
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)

    Returns:
        Tuple of (is_valid, parsed_value, error_message).
        If input is empty, returns (True, None, None).
        If is_valid is True, error_message is None.
    """
    # Handle empty/None - this is valid for optional fields
    if value is None or (isinstance(value, str) and not value.strip()):
        return (True, None, None)

    # Convert to float
    try:
        float_value = float(value)
    except (ValueError, TypeError):
        return (False, None, f"{field_name} must be a valid number")

    # Validate range
    if float_value < min_val or float_value > max_val:
        return (False, float_value, f"{field_name} must be between {min_val} and {max_val}")

    return (True, float_value, None)


def validate_api_key(
    api_key: Any,
) -> Tuple[bool, str, Optional[str]]:
    """Validate an optional API key for Netro API v2.

    An empty key is valid — it means v1 mode (serial number auth).
    A non-empty key must be a reasonable length string.

    Args:
        api_key: The API key to validate (typically string)

    Returns:
        Tuple of (is_valid, sanitized_key, error_message).
        If is_valid is True, error_message is None.
    """
    # Handle None
    if api_key is None:
        return (True, "", None)

    # Strip whitespace
    sanitized = str(api_key).strip()

    # Empty is valid (means v1 mode)
    if not sanitized:
        return (True, "", None)

    # Validate minimum length — API keys are typically 32+ chars
    if len(sanitized) < 16:
        return (False, sanitized, "API key appears too short")

    # Validate maximum length
    if len(sanitized) > 128:
        return (False, sanitized, "API key appears too long — paste only the key value")

    # Validate characters — keys are alphanumeric with hyphens and underscores
    if not all(c.isalnum() or c in '-_' for c in sanitized):
        return (False, sanitized, "API key contains invalid characters")

    return (True, sanitized, None)


_INDIGO_SUB_RE = re.compile(r'^%%[vd]:\d+(?::[a-zA-Z_]\w*)?%%$')
"""Regex matching valid Indigo substitution patterns: %%v:ID%% or %%d:ID:state%%."""


def is_indigo_substitution(value: Any) -> bool:
    """Check if a value is an Indigo variable/device state substitution.

    Indigo supports %%v:ID%% (variable) and %%d:ID:state%% (device state)
    patterns that are resolved at action execution time, not config time.

    Args:
        value: The value to check

    Returns:
        True if value matches a valid Indigo substitution pattern
    """
    if not isinstance(value, str):
        return False
    return bool(_INDIGO_SUB_RE.match(value.strip()))


def validate_date_format(
    date_str: Any,
    format_str: str = "%Y-%m-%d",
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Validate an optional date string format.

    Returns success with None if the input is empty. Otherwise validates
    that the string matches the expected date format.

    Args:
        date_str: The date string to validate
        format_str: Expected date format (default: YYYY-MM-DD)

    Returns:
        Tuple of (is_valid, sanitized_date, error_message).
        If input is empty, returns (True, None, None).
        sanitized_date is stripped of whitespace.
    """
    # Handle None
    if date_str is None:
        return (True, None, None)

    # Strip whitespace
    sanitized = str(date_str).strip()

    # Empty is valid for optional date
    if not sanitized:
        return (True, None, None)

    # Validate format
    try:
        datetime.strptime(sanitized, format_str)
    except ValueError:
        return (False, sanitized, "Date must be in YYYY-MM-DD format")

    return (True, sanitized, None)


# =============================================================================
# Main Validation Functions
# =============================================================================


def _is_valid_external_sensor_entry(entry: Any) -> bool:
    """Check a single `externalSensorsJson` entry for the shape the runtime needs.

    Mirrors what plugin.py's `_compute_external_average` / `_rebuild_external_sensor_index`
    can actually use, so validation doesn't accept entries the runtime would
    silently discard:
        - "dev_id": an int, or a str/float that's int-coercible. bool is
          rejected even though it's technically int-coercible (Indigo dropdown
          values are strings; a bool here only appears from hand-edited JSON).
        - "state_id": a non-empty string.
        - "scale": exactly "percent" or "fraction".
    """
    if not isinstance(entry, dict):
        return False

    dev_id = entry.get("dev_id")
    if isinstance(dev_id, bool):
        return False
    if isinstance(dev_id, int):
        pass
    elif isinstance(dev_id, (str, float)):
        try:
            int(dev_id)
        except (TypeError, ValueError):
            return False
    else:
        return False

    if not isinstance(entry.get("state_id"), str) or not entry.get("state_id"):
        return False

    return entry.get("scale") in ("percent", "fraction")


def _validate_zone_external_sensors_json(
    values: Dict[str, Any],
    errors: Dict[str, str],
) -> None:
    """Validate the zone device's `externalSensorsJson` pluginProp.

    An absent/empty value is valid (no sensors linked yet). A non-empty
    value must parse as a JSON list of entries, each with a usable
    "dev_id", a non-empty string "state_id", and a "scale" of "percent" or
    "fraction" — see `_is_valid_external_sensor_entry`.

    Args:
        values: Device configuration values from UI
        errors: Dict to store error messages (modified in place)
    """
    raw_json = values.get("externalSensorsJson", "")
    if not raw_json:
        return

    try:
        parsed = json.loads(raw_json)
        is_valid_shape = isinstance(parsed, list) and all(
            _is_valid_external_sensor_entry(entry) for entry in parsed
        )
    except (json.JSONDecodeError, TypeError):
        is_valid_shape = False

    if not is_valid_shape:
        errors["externalSensorsJson"] = (
            "External sensor configuration is corrupt — remove and re-add sensors"
        )


def _validate_zone_external_max_age_days(
    values: Dict[str, Any],
    errors: Dict[str, str],
) -> None:
    """Validate the zone device's `externalMaxAgeDays` pluginProp.

    Empty/whitespace is valid (no age limit). A non-empty value must parse
    as a number >= 0 — 0 is accepted here and treated as "no limit" at
    runtime (see `Plugin._parse_external_max_age_days`).

    Args:
        values: Device configuration values from UI
        errors: Dict to store error messages (modified in place)
    """
    raw = values.get("externalMaxAgeDays", "")
    if not str(raw).strip():
        return

    try:
        days = float(raw)
    except (TypeError, ValueError):
        days = None

    if days is None or days < 0:
        errors["externalMaxAgeDays"] = (
            "Must be a number of days (leave empty for no limit)"
        )


def validate_device_config(
    values: Dict[str, Any],
    type_id: str,
) -> ValidationResult:
    """Validate device configuration before saving.

    Validates serial numbers for sprinkler controllers and Whisperer sensors.
    For Whisperer devices, also sets capability flags in the sanitized values.
    For zones, validates the `externalSensorsJson` and `externalMaxAgeDays`
    pluginProps.

    Args:
        values: Device configuration values from UI
        type_id: Device type ID ("sprinkler", "Whisperer", or "zone")

    Returns:
        ValidationResult tuple of (is_valid, sanitized_values, errors_dict).
        sanitized_values contains the input values with any modifications.
        errors_dict maps field names to error messages.
    """
    if type_id == "zone":
        sanitized_zone: Dict[str, Any] = dict(values)
        zone_errors: Dict[str, str] = {}
        _validate_zone_external_sensors_json(values, zone_errors)
        _validate_zone_external_max_age_days(values, zone_errors)
        return (len(zone_errors) == 0, sanitized_zone, zone_errors)

    sanitized: Dict[str, Any] = dict(values)
    errors: Dict[str, str] = {}

    if type_id == "sprinkler":
        is_valid, serial, error = validate_serial_number(
            values.get("address", ""),
            "Netro controller",
        )
        if is_valid:
            sanitized["address"] = serial
        elif error:
            errors["address"] = error

        # Validate optional API key (v2)
        is_valid, api_key, error = validate_api_key(values.get("apiKey", ""))
        if is_valid:
            sanitized["apiKey"] = api_key
        elif error:
            errors["apiKey"] = error

    elif type_id == "Whisperer":
        is_valid, serial, error = validate_serial_number(
            values.get("address", ""),
            "Whisperer sensor",
        )
        if is_valid:
            sanitized["address"] = serial
        elif error:
            # Use shorter message for Whisperer
            if "too short" in (error or ""):
                errors["address"] = "Serial number appears too short"
            else:
                errors["address"] = error

        # Validate optional API key (v2)
        is_valid, api_key, error = validate_api_key(values.get("apiKey", ""))
        if is_valid:
            sanitized["apiKey"] = api_key
        elif error:
            errors["apiKey"] = error

        # Set sensor capabilities regardless of validation result
        sanitized["SupportsBatteryLevel"] = True
        sanitized["NumTemperatureInputs"] = 1
        sanitized["NumHumidityInputs"] = 1
        sanitized["SupportsTemperatureReporting"] = True

    return (len(errors) == 0, sanitized, errors)


def _validate_start_zone_action(
    values: Dict[str, Any],
    sanitized: Dict[str, Any],
    errors: Dict[str, str],
) -> None:
    """Validate startZoneWithDelay action parameters.

    Args:
        values: Input values dict
        sanitized: Dict to store sanitized values (modified in place)
        errors: Dict to store error messages (modified in place)
    """
    # Validate duration (1-180 minutes)
    is_valid, duration, error = validate_integer_range(
        values.get("duration", 15), "Duration", 1, 180, default=15
    )
    if is_valid and duration is not None:
        sanitized["duration"] = duration
    elif error:
        errors["duration"] = error

    # Validate delay (0-60 minutes)
    is_valid, delay, error = validate_integer_range(
        values.get("delay", 0), "Delay", 0, 60, default=0
    )
    if is_valid and delay is not None:
        sanitized["delay"] = delay
    elif error:
        errors["delay"] = error

    # Validate start_time if provided (must be valid Unix timestamp)
    start_time = values.get("start_time", "")
    if isinstance(start_time, str):
        start_time = start_time.strip()
    if start_time:
        try:
            sanitized["start_time"] = int(start_time)
        except (ValueError, TypeError):
            errors["start_time"] = "Start time must be a valid Unix timestamp (integer)"

    # Validate zone selected ("-1" is the getZoneList sentinel for "none selected")
    zone = values.get("zone")
    if not zone or zone == "-1":
        errors["zone"] = "You must select a zone"


def _validate_report_weather_action(
    values: Dict[str, Any],
    sanitized: Dict[str, Any],
    errors: Dict[str, str],
) -> None:
    """Validate reportWeather action parameters.

    Args:
        values: Input values dict
        sanitized: Dict to store sanitized values (modified in place)
        errors: Dict to store error messages (modified in place)
    """
    # Validate required temperature field
    is_valid, temp, error = validate_required_float(
        values.get("temperature", ""), "Current temperature"
    )
    if is_valid and temp is not None:
        sanitized["temperature"] = temp
    elif error:
        errors["temperature"] = error

    # Validate optional numeric fields
    optional_fields = [
        ("t_max", "Max temperature", -50.0, 150.0),
        ("t_min", "Min temperature", -50.0, 150.0),
        ("humidity", "Humidity", 0.0, 100.0),
        ("rain", "Rainfall", 0.0, 100.0),
        ("rain_prob", "Rain probability", 0.0, 100.0),
        ("wind_speed", "Wind speed", 0.0, 200.0),
        ("pressure", "Pressure", 20.0, 35.0),
    ]

    for field, label, min_val, max_val in optional_fields:
        is_valid, val, error = validate_optional_float(
            values.get(field, ""), label, min_val, max_val
        )
        if is_valid and val is not None:
            sanitized[field] = val
        elif error:
            errors[field] = error

    # Validate date format if provided
    is_valid, date_val, error = validate_date_format(values.get("date", ""))
    if is_valid and date_val is not None:
        sanitized["date"] = date_val
    elif error:
        errors["date"] = error


def _validate_set_moisture_action(
    values: Dict[str, Any],
    sanitized: Dict[str, Any],
    errors: Dict[str, str],
) -> None:
    """Validate setMoisture action parameters.

    Args:
        values: Input values dict
        sanitized: Dict to store sanitized values (modified in place)
        errors: Dict to store error messages (modified in place)
    """
    # Validate zone is selected and is a valid integer
    zone_str = values.get("zone", "")
    if not zone_str:
        errors["zone"] = "You must select a zone"
    else:
        try:
            sanitized["zone"] = int(zone_str)
        except (ValueError, TypeError):
            errors["zone"] = "Zone must be a valid number"

    # Validate moisture — allow integer 0-100 or Indigo variable substitution
    moisture_str = values.get("moisture", "")
    if is_indigo_substitution(moisture_str):
        # Variable substitution — resolved at runtime, skip numeric validation
        sanitized["moisture"] = moisture_str.strip()
    else:
        try:
            moisture = int(moisture_str)
            if moisture < 0 or moisture > 100:
                errors["moisture"] = "Moisture must be between 0 and 100"
            else:
                sanitized["moisture"] = moisture
        except (ValueError, TypeError):
            errors["moisture"] = "Moisture must be a whole number (0-100) or %%v:variableID%%"


def validate_action_config(
    values: Dict[str, Any],
    type_id: str,
) -> ValidationResult:
    """Validate action configuration before saving.

    Validates parameters for startZoneWithDelay and reportWeather actions.

    Args:
        values: Action configuration values from UI
        type_id: Action type ID

    Returns:
        ValidationResult tuple of (is_valid, sanitized_values, errors_dict).
    """
    sanitized: Dict[str, Any] = dict(values)
    errors: Dict[str, str] = {}

    if type_id == "startZoneWithDelay":
        _validate_start_zone_action(values, sanitized, errors)
    elif type_id == "reportWeather":
        _validate_report_weather_action(values, sanitized, errors)
    elif type_id == "setMoisture":
        _validate_set_moisture_action(values, sanitized, errors)

    return (len(errors) == 0, sanitized, errors)


def validate_event_config(
    values: Dict[str, Any],
    type_id: str,
) -> ValidationResult:
    """Validate event/trigger configuration before saving.

    Args:
        values: Event configuration values from UI
        type_id: Event type ID

    Returns:
        ValidationResult tuple of (is_valid, sanitized_values, errors_dict).
    """
    sanitized: Dict[str, Any] = dict(values)
    errors: Dict[str, str] = {}

    if type_id == "sprinklerError":
        serial = values.get("serial", "")
        if not serial:
            errors["serial"] = "You must select a Netro Sprinkler device."

    elif type_id == "deviceEvent":
        device_id = values.get("id", "")
        if not device_id:
            errors["id"] = "You must select a device."

    return (len(errors) == 0, sanitized, errors)


@dataclass(frozen=True)
class PrefsFieldSpec:
    """Specification for a preferences field validation."""
    field: str
    min_val: int
    max_val: int
    default: int
    min_error: str
    max_error: str


# Preferences field validation specifications
_PREFS_FIELDS: List[PrefsFieldSpec] = [
    PrefsFieldSpec(
        "eventsInterval", MINIMUM_EVENTS_INTERVAL_MINUTES, 1440, 5,
        f"Events interval must be at least {MINIMUM_EVENTS_INTERVAL_MINUTES} minutes",
        "Events interval cannot exceed 1440 minutes (24 hours)",
    ),
    PrefsFieldSpec(
        "deviceInfoInterval", MINIMUM_DEVICE_INFO_INTERVAL_MINUTES, 1440, 10,
        f"Device info interval must be at least {MINIMUM_DEVICE_INFO_INTERVAL_MINUTES} minutes",
        "Device info interval cannot exceed 1440 minutes (24 hours)",
    ),
    PrefsFieldSpec(
        "moisturesInterval", MINIMUM_MOISTURES_INTERVAL_MINUTES, 1440, 10,
        f"Moistures interval must be at least {MINIMUM_MOISTURES_INTERVAL_MINUTES} minutes",
        "Moistures interval cannot exceed 1440 minutes (24 hours)",
    ),
    PrefsFieldSpec(
        "schedulesInterval", MINIMUM_SCHEDULES_INTERVAL_MINUTES, 1440, 30,
        f"Schedules interval must be at least {MINIMUM_SCHEDULES_INTERVAL_MINUTES} minutes",
        "Schedules interval cannot exceed 1440 minutes (24 hours)",
    ),
    PrefsFieldSpec(
        "sensorInterval", MINIMUM_SENSOR_INTERVAL_MINUTES, 1440, 30,
        f"Sensor interval must be at least {MINIMUM_SENSOR_INTERVAL_MINUTES} minutes",
        "Sensor interval cannot exceed 1440 minutes (24 hours)",
    ),
    PrefsFieldSpec(
        "apiTimeout", 1, 60, 5,
        "Timeout must be at least 1 second",
        "Timeout cannot exceed 60 seconds",
    ),
    PrefsFieldSpec(
        "maxZoneRunTime", 60, 10800, 3600,
        "Max runtime must be at least 60 seconds (1 minute)",
        "Max runtime cannot exceed 10800 seconds (3 hours)",
    ),
    PrefsFieldSpec(
        "weatherUpdateInterval", MINIMUM_WEATHER_UPDATE_INTERVAL_MINUTES, 1440, 30,
        f"Weather update interval must be at least {MINIMUM_WEATHER_UPDATE_INTERVAL_MINUTES} minutes",
        "Weather update interval cannot exceed 1440 minutes (24 hours)",
    ),
    PrefsFieldSpec(
        "forecastInterval", MINIMUM_FORECAST_INTERVAL_MINUTES, 1440, 240,
        f"Forecast interval must be at least {MINIMUM_FORECAST_INTERVAL_MINUTES} minutes",
        "Forecast interval cannot exceed 1440 minutes (24 hours)",
    ),
]


def validate_prefs_config(
    values: Dict[str, Any],
) -> ValidationResult:
    """Validate plugin configuration before saving.

    Validates polling interval, API timeout, max zone runtime, and
    Tomorrow.io weather integration settings.

    Args:
        values: Configuration values from plugin preferences UI

    Returns:
        ValidationResult tuple of (is_valid, sanitized_values, errors_dict).
    """
    sanitized: Dict[str, Any] = dict(values)
    errors: Dict[str, str] = {}

    for spec in _PREFS_FIELDS:
        is_valid, parsed, error = validate_integer_range(
            values.get(spec.field, spec.default),
            spec.field,
            spec.min_val,
            spec.max_val,
            default=spec.default,
        )
        if is_valid and parsed is not None:
            sanitized[spec.field] = parsed
        elif error:
            if "must be between" in (error or ""):
                is_below_min = parsed is not None and parsed < spec.min_val
                errors[spec.field] = spec.min_error if is_below_min else spec.max_error
            else:
                errors[spec.field] = error

    # Validate Tomorrow.io fields when enabled
    tomorrow_enabled = values.get("tomorrowEnabled", False)
    if tomorrow_enabled:
        api_key = str(values.get("tomorrowApiKey", "")).strip()
        if not api_key:
            errors["tomorrowApiKey"] = "API key is required when Tomorrow.io weather is enabled"
        else:
            sanitized["tomorrowApiKey"] = api_key

        location = str(values.get("tomorrowLocation", "")).strip()
        if not location:
            errors["tomorrowLocation"] = "Location is required when Tomorrow.io weather is enabled"
        else:
            sanitized["tomorrowLocation"] = location

    return (len(errors) == 0, sanitized, errors)
