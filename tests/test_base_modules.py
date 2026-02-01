"""Unit tests for extracted base modules (constants, exceptions, utils).

Tests verify the foundation modules work correctly in isolation.
These tests do not require Indigo runtime and can run with pytest.
"""
import sys
from pathlib import Path
from datetime import datetime
import pytest

# Add Server Plugin directory to path for imports
SERVER_PLUGIN_DIR = Path(__file__).parent.parent / "Netro Sprinklers.indigoPlugin" / "Contents" / "Server Plugin"
sys.path.insert(0, str(SERVER_PLUGIN_DIR))

from constants import (
    NETRO_API_VERSION,
    API_URL,
    API_BASE_URL,
    DEVICE_INFO_ENDPOINT,
    DEVICE_SCHEDULES_ENDPOINT,
    DEVICE_MOISTURES_ENDPOINT,
    DEVICE_SENSOR_DATA_ENDPOINT,
    DEVICE_WATER_ENDPOINT,
    DEVICE_STOP_WATER_ENDPOINT,
    DEVICE_SET_STATUS_ENDPOINT,
    DEVICE_NO_WATER_ENDPOINT,
    DEVICE_REPORT_WEATHER_ENDPOINT,
    ZONE_START_ENDPOINT,
    MAX_ZONE_DURATION_SECONDS,
    DEFAULT_API_TIMEOUT_SECONDS,
    MINIMUM_POLLING_INTERVAL_MINUTES,
    DEFAULT_WEATHER_UPDATE_INTERVAL_MINUTES,
    THROTTLE_LIMIT_MINUTES,
    FORECAST_UPDATE_INTERVAL_MINUTES,
    OPERATIONAL_ERROR_EVENTS,
    COMM_ERROR_EVENTS,
)
from exceptions import (
    NetroError,
    ThrottleDelayError,
    NetroAPIError,
    NetroConnectionError,
    NetroTimeoutError,
)
from utils import get_key_from_dict


class TestConstants:
    """Tests for constants.py module."""

    def test_api_version_is_string(self):
        """NETRO_API_VERSION should be a string."""
        assert isinstance(NETRO_API_VERSION, str)
        assert NETRO_API_VERSION == "1"

    def test_api_url_format(self):
        """API_URL should be properly formatted with version."""
        assert "v1" in API_URL
        assert API_URL.startswith("https://api.netrohome.com")

    def test_api_base_url_contains_placeholder(self):
        """API_BASE_URL should contain apiVersion placeholder."""
        assert "{apiVersion}" in API_BASE_URL

    def test_device_info_endpoint(self):
        """DEVICE_INFO_ENDPOINT should be full URL ending with info.json."""
        assert DEVICE_INFO_ENDPOINT.startswith(API_URL)
        assert DEVICE_INFO_ENDPOINT.endswith("info.json")

    def test_device_schedules_endpoint(self):
        """DEVICE_SCHEDULES_ENDPOINT should be full URL."""
        assert DEVICE_SCHEDULES_ENDPOINT.startswith(API_URL)
        assert "schedules.json" in DEVICE_SCHEDULES_ENDPOINT

    def test_device_moistures_endpoint(self):
        """DEVICE_MOISTURES_ENDPOINT should be full URL."""
        assert DEVICE_MOISTURES_ENDPOINT.startswith(API_URL)
        assert "moistures.json" in DEVICE_MOISTURES_ENDPOINT

    def test_device_sensor_data_endpoint(self):
        """DEVICE_SENSOR_DATA_ENDPOINT should be full URL."""
        assert DEVICE_SENSOR_DATA_ENDPOINT.startswith(API_URL)
        assert "sensor_data.json" in DEVICE_SENSOR_DATA_ENDPOINT

    def test_device_water_endpoint(self):
        """DEVICE_WATER_ENDPOINT should be full URL."""
        assert DEVICE_WATER_ENDPOINT.startswith(API_URL)
        assert "water.json" in DEVICE_WATER_ENDPOINT

    def test_device_stop_water_endpoint(self):
        """DEVICE_STOP_WATER_ENDPOINT should be full URL."""
        assert DEVICE_STOP_WATER_ENDPOINT.startswith(API_URL)
        assert "stop_water.json" in DEVICE_STOP_WATER_ENDPOINT

    def test_device_set_status_endpoint(self):
        """DEVICE_SET_STATUS_ENDPOINT should be full URL."""
        assert DEVICE_SET_STATUS_ENDPOINT.startswith(API_URL)
        assert "set_status.json" in DEVICE_SET_STATUS_ENDPOINT

    def test_device_no_water_endpoint(self):
        """DEVICE_NO_WATER_ENDPOINT should be full URL."""
        assert DEVICE_NO_WATER_ENDPOINT.startswith(API_URL)
        assert "no_water.json" in DEVICE_NO_WATER_ENDPOINT

    def test_device_report_weather_endpoint(self):
        """DEVICE_REPORT_WEATHER_ENDPOINT should be full URL."""
        assert DEVICE_REPORT_WEATHER_ENDPOINT.startswith(API_URL)
        assert "report_weather.json" in DEVICE_REPORT_WEATHER_ENDPOINT

    def test_zone_start_endpoint(self):
        """ZONE_START_ENDPOINT should be full URL."""
        assert ZONE_START_ENDPOINT.startswith(API_URL)
        assert "zone/start" in ZONE_START_ENDPOINT

    def test_max_zone_duration(self):
        """MAX_ZONE_DURATION_SECONDS should be 3 hours in seconds."""
        assert MAX_ZONE_DURATION_SECONDS == 10800
        assert MAX_ZONE_DURATION_SECONDS == 3 * 60 * 60

    def test_default_timeout(self):
        """DEFAULT_API_TIMEOUT_SECONDS should be reasonable (1-60 seconds)."""
        assert 1 <= DEFAULT_API_TIMEOUT_SECONDS <= 60
        assert DEFAULT_API_TIMEOUT_SECONDS == 5

    def test_minimum_polling_interval(self):
        """MINIMUM_POLLING_INTERVAL_MINUTES should be at least 3."""
        assert MINIMUM_POLLING_INTERVAL_MINUTES >= 3
        assert MINIMUM_POLLING_INTERVAL_MINUTES == 3

    def test_default_weather_update_interval(self):
        """DEFAULT_WEATHER_UPDATE_INTERVAL_MINUTES should be reasonable."""
        assert DEFAULT_WEATHER_UPDATE_INTERVAL_MINUTES >= 1
        assert DEFAULT_WEATHER_UPDATE_INTERVAL_MINUTES == 10

    def test_throttle_limit(self):
        """THROTTLE_LIMIT_MINUTES should be ~1 hour."""
        assert THROTTLE_LIMIT_MINUTES == 61

    def test_forecast_update_interval(self):
        """FORECAST_UPDATE_INTERVAL_MINUTES should be 1 hour."""
        assert FORECAST_UPDATE_INTERVAL_MINUTES == 60

    def test_operational_error_events_immutable(self):
        """OPERATIONAL_ERROR_EVENTS should be a frozenset."""
        assert isinstance(OPERATIONAL_ERROR_EVENTS, frozenset)
        assert "startZoneFailed" in OPERATIONAL_ERROR_EVENTS
        assert "stopFailed" in OPERATIONAL_ERROR_EVENTS
        assert "setStandbyFailed" in OPERATIONAL_ERROR_EVENTS

    def test_operational_error_events_count(self):
        """OPERATIONAL_ERROR_EVENTS should have exactly 3 events."""
        assert len(OPERATIONAL_ERROR_EVENTS) == 3

    def test_comm_error_events_immutable(self):
        """COMM_ERROR_EVENTS should be a frozenset."""
        assert isinstance(COMM_ERROR_EVENTS, frozenset)
        assert "personCall" in COMM_ERROR_EVENTS
        assert "personInfoCall" in COMM_ERROR_EVENTS
        assert "getScheduleCall" in COMM_ERROR_EVENTS
        assert "forecastCall" in COMM_ERROR_EVENTS

    def test_comm_error_events_count(self):
        """COMM_ERROR_EVENTS should have exactly 4 events."""
        assert len(COMM_ERROR_EVENTS) == 4


class TestExceptions:
    """Tests for exceptions.py module."""

    def test_netro_error_base_class(self):
        """NetroError should be catchable as base class."""
        with pytest.raises(NetroError):
            raise ThrottleDelayError("test")

    def test_netro_error_is_exception(self):
        """NetroError should inherit from Exception."""
        assert issubclass(NetroError, Exception)

    def test_throttle_delay_error_message(self):
        """ThrottleDelayError should store message."""
        error = ThrottleDelayError("Rate limited")
        assert str(error) == "Rate limited"
        assert error.message == "Rate limited"

    def test_throttle_delay_error_default_message(self):
        """ThrottleDelayError should have default message."""
        error = ThrottleDelayError()
        assert "rate limit" in error.message.lower()

    def test_throttle_delay_error_retry_after(self):
        """ThrottleDelayError should optionally store retry_after."""
        retry_time = datetime.now()
        error = ThrottleDelayError("test", retry_after=retry_time)
        assert error.retry_after == retry_time

    def test_throttle_delay_error_retry_after_default(self):
        """ThrottleDelayError retry_after should default to None."""
        error = ThrottleDelayError("test")
        assert error.retry_after is None

    def test_netro_api_error_message(self):
        """NetroAPIError should store message."""
        error = NetroAPIError("API error")
        assert str(error) == "API error"
        assert error.message == "API error"

    def test_netro_api_error_default_message(self):
        """NetroAPIError should have default message."""
        error = NetroAPIError()
        assert "error" in error.message.lower()

    def test_netro_api_error_status_code(self):
        """NetroAPIError should store status_code."""
        error = NetroAPIError("Server error", status_code=500)
        assert error.status_code == 500

    def test_netro_api_error_error_code(self):
        """NetroAPIError should store error_code."""
        error = NetroAPIError("Server error", error_code=1)
        assert error.error_code == 1

    def test_netro_api_error_all_attributes(self):
        """NetroAPIError should store all attributes together."""
        error = NetroAPIError("Server error", status_code=500, error_code=1)
        assert error.status_code == 500
        assert error.error_code == 1
        assert error.message == "Server error"

    def test_netro_connection_error_message(self):
        """NetroConnectionError should store message."""
        error = NetroConnectionError("Connection failed")
        assert str(error) == "Connection failed"
        assert error.message == "Connection failed"

    def test_netro_connection_error_original_error(self):
        """NetroConnectionError should store original_error."""
        original = ConnectionError("Network unreachable")
        error = NetroConnectionError("Connection failed", original_error=original)
        assert error.original_error == original

    def test_netro_timeout_error_message(self):
        """NetroTimeoutError should store message."""
        error = NetroTimeoutError("Request timed out")
        assert str(error) == "Request timed out"
        assert error.message == "Request timed out"

    def test_netro_timeout_error_timeout_seconds(self):
        """NetroTimeoutError should store timeout_seconds."""
        error = NetroTimeoutError("Timed out", timeout_seconds=5.0)
        assert error.timeout_seconds == 5.0

    def test_exception_hierarchy(self):
        """All custom exceptions should inherit from NetroError."""
        assert issubclass(ThrottleDelayError, NetroError)
        assert issubclass(NetroAPIError, NetroError)
        assert issubclass(NetroConnectionError, NetroError)
        assert issubclass(NetroTimeoutError, NetroError)

    def test_catch_all_netro_errors(self):
        """Should be able to catch all Netro exceptions with NetroError."""
        exceptions_to_test = [
            ThrottleDelayError("test"),
            NetroAPIError("test"),
            NetroConnectionError("test"),
            NetroTimeoutError("test"),
        ]
        for exc in exceptions_to_test:
            try:
                raise exc
            except NetroError:
                pass  # Expected
            except Exception:
                pytest.fail(f"{type(exc).__name__} was not caught by NetroError")


class TestUtils:
    """Tests for utils.py module."""

    def test_get_key_from_dict_existing_key(self):
        """get_key_from_dict should return value for existing key."""
        data = {"name": "test", "value": 42}
        assert get_key_from_dict("name", data) == "test"
        assert get_key_from_dict("value", data) == 42

    def test_get_key_from_dict_missing_key(self):
        """get_key_from_dict should return 'unavailable from API' for missing key."""
        data = {"name": "test"}
        assert get_key_from_dict("missing", data) == "unavailable from API"

    def test_get_key_from_dict_none_dict(self):
        """get_key_from_dict should return 'unknown error' for None dict."""
        assert get_key_from_dict("key", None) == "unknown error"

    def test_get_key_from_dict_with_default(self):
        """get_key_from_dict should use default when provided."""
        data = {"name": "test"}
        assert get_key_from_dict("missing", data, default="N/A") == "N/A"

    def test_get_key_from_dict_with_default_on_none(self):
        """get_key_from_dict should use default on None dict when provided."""
        assert get_key_from_dict("key", None, default="fallback") == "fallback"

    def test_get_key_from_dict_non_dict_string(self):
        """get_key_from_dict should handle string gracefully."""
        assert get_key_from_dict("key", "not a dict") == "unknown error"

    def test_get_key_from_dict_non_dict_int(self):
        """get_key_from_dict should handle int gracefully."""
        assert get_key_from_dict("key", 123) == "unknown error"

    def test_get_key_from_dict_non_dict_list(self):
        """get_key_from_dict should handle list gracefully."""
        assert get_key_from_dict("key", [1, 2, 3]) == "unknown error"

    def test_get_key_from_dict_empty_dict(self):
        """get_key_from_dict should handle empty dict."""
        assert get_key_from_dict("key", {}) == "unavailable from API"

    def test_get_key_from_dict_nested_value(self):
        """get_key_from_dict should return nested structures."""
        data = {"nested": {"a": 1, "b": 2}}
        result = get_key_from_dict("nested", data)
        assert result == {"a": 1, "b": 2}

    def test_get_key_from_dict_falsy_value(self):
        """get_key_from_dict should return falsy values correctly."""
        data = {"zero": 0, "empty": "", "false": False, "none": None}
        assert get_key_from_dict("zero", data) == 0
        assert get_key_from_dict("empty", data) == ""
        assert get_key_from_dict("false", data) is False
        assert get_key_from_dict("none", data) is None
