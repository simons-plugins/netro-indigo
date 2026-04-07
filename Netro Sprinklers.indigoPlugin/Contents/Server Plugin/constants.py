"""Netro API constants and configuration values.

This module contains all API URLs, default values, and event sets used by the
Netro Sprinklers plugin. Constants are organized into logical sections:

- API Configuration: Base URLs and version
- API Endpoints: Individual API endpoint URLs
- Default Values: Timing, limits, and thresholds
- Event Sets: Trigger event categories

All constants use SCREAMING_SNAKE_CASE naming convention and typing.Final
for immutability to prevent accidental modification.

Note:
    This module intentionally has no dependencies on other plugin modules
    to prevent circular imports. It only imports from Python standard library.
"""

from typing import Final


# =============================================================================
# API Configuration
# =============================================================================

NETRO_API_VERSION: Final[str] = "1"
"""Current default Netro API version."""

NETRO_API_V2_VERSION: Final[str] = "2"
"""Netro API version 2 (API key authentication)."""

API_BASE_URL: Final[str] = "https://api.netrohome.com/npa/v{apiVersion}/"
"""Base URL template for Netro API (requires apiVersion formatting)."""

API_URL: Final[str] = API_BASE_URL.format(apiVersion=NETRO_API_VERSION)
"""Formatted base URL for API v1."""

API_V2_URL: Final[str] = API_BASE_URL.format(apiVersion=NETRO_API_V2_VERSION)
"""Formatted base URL for API v2."""


# =============================================================================
# API v1 Endpoints (serial number authentication)
# =============================================================================

DEVICE_INFO_ENDPOINT: Final[str] = API_URL + "info.json"
"""Get device information and status."""

DEVICE_SCHEDULES_ENDPOINT: Final[str] = API_URL + "schedules.json"
"""Get device watering schedules."""

DEVICE_MOISTURES_ENDPOINT: Final[str] = API_URL + "moistures.json"
"""Get moisture levels for all zones."""

DEVICE_SENSOR_DATA_ENDPOINT: Final[str] = API_URL + "sensor_data.json"
"""Get Whisperer sensor readings."""

DEVICE_WATER_ENDPOINT: Final[str] = API_URL + "water.json"
"""Start watering with parameters (zones, duration, delay)."""

DEVICE_STOP_WATER_ENDPOINT: Final[str] = API_URL + "stop_water.json"
"""Stop all active watering."""

DEVICE_SET_STATUS_ENDPOINT: Final[str] = API_URL + "set_status.json"
"""Set device status (online/standby)."""

DEVICE_NO_WATER_ENDPOINT: Final[str] = API_URL + "no_water.json"
"""Set rain delay (no watering for N days)."""

DEVICE_REPORT_WEATHER_ENDPOINT: Final[str] = API_URL + "report_weather.json"
"""Report local weather data to improve scheduling."""

DEVICE_SET_MOISTURE_ENDPOINT: Final[str] = API_URL + "set_moisture.json"
"""Override moisture level for a specific zone."""

ZONE_START_ENDPOINT: Final[str] = API_URL + "zone/start"
"""Start a specific zone directly (legacy endpoint)."""


# =============================================================================
# API v2 Endpoints (API key authentication)
# =============================================================================

DEVICE_INFO_V2_ENDPOINT: Final[str] = API_V2_URL + "info.json"
"""Get device information and status (v2)."""

DEVICE_SCHEDULES_V2_ENDPOINT: Final[str] = API_V2_URL + "schedules.json"
"""Get device watering schedules (v2)."""

DEVICE_MOISTURES_V2_ENDPOINT: Final[str] = API_V2_URL + "moistures.json"
"""Get moisture levels for all zones (v2)."""

DEVICE_SENSOR_DATA_V2_ENDPOINT: Final[str] = API_V2_URL + "sensor_data.json"
"""Get Whisperer sensor readings (v2)."""

DEVICE_WATER_V2_ENDPOINT: Final[str] = API_V2_URL + "water.json"
"""Start watering with parameters (v2)."""

DEVICE_STOP_WATER_V2_ENDPOINT: Final[str] = API_V2_URL + "stop_water.json"
"""Stop all active watering (v2)."""

DEVICE_SET_STATUS_V2_ENDPOINT: Final[str] = API_V2_URL + "set_status.json"
"""Set device status (v2)."""

DEVICE_NO_WATER_V2_ENDPOINT: Final[str] = API_V2_URL + "no_water.json"
"""Set rain delay (v2)."""

DEVICE_REPORT_WEATHER_V2_ENDPOINT: Final[str] = API_V2_URL + "report_weather.json"
"""Report local weather data (v2)."""

DEVICE_SET_MOISTURE_V2_ENDPOINT: Final[str] = API_V2_URL + "set_moisture.json"
"""Override moisture level for a specific zone (v2)."""

DEVICE_EVENTS_V2_ENDPOINT: Final[str] = API_V2_URL + "events.json"
"""Get device events - online/offline/schedule changes (v2 only)."""


# =============================================================================
# Default Values
# =============================================================================

MAX_ZONE_DURATION_SECONDS: Final[int] = 10800
"""Maximum allowed zone runtime in seconds (3 hours)."""

DEFAULT_API_TIMEOUT_SECONDS: Final[int] = 5
"""Default timeout for API requests in seconds."""

MINIMUM_POLLING_INTERVAL_MINUTES: Final[int] = 3
"""Minimum polling interval in minutes to avoid API rate limits."""

DEFAULT_WEATHER_UPDATE_INTERVAL_MINUTES: Final[int] = 10
"""Default interval for weather updates in minutes."""

THROTTLE_LIMIT_MINUTES: Final[int] = 61
"""Duration to wait after rate limit error before retrying (minutes)."""

FORECAST_UPDATE_INTERVAL_MINUTES: Final[int] = 60
"""Interval between forecast updates in minutes."""

TOKEN_PAUSE_THRESHOLD: Final[int] = 100
"""Token count below which polling should pause proactively."""

TOKEN_WARNING_THRESHOLD: Final[int] = 200
"""Token count below which warnings are logged."""


# =============================================================================
# Event Sets
# =============================================================================

# =============================================================================
# V2 Online Status Values
# =============================================================================

V2_ONLINE_STATUSES: Final[frozenset] = frozenset({
    "ONLINE",
    "WATERING",
})
"""Device status values that indicate the device is online in API v2."""


# =============================================================================
# Event Sets
# =============================================================================

OPERATIONAL_ERROR_EVENTS: Final[frozenset] = frozenset({
    "startZoneFailed",
    "stopFailed",
    "setStandbyFailed",
    "setMoistureFailed",
})
"""Events indicating operational errors (device control failures)."""

COMM_ERROR_EVENTS: Final[frozenset] = frozenset({
    "personCall",
    "personInfoCall",
    "getScheduleCall",
    "forecastCall",
})
"""Events indicating communication errors (API call failures)."""
