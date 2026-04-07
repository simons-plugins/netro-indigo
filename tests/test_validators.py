"""Unit tests for validators.py module.

Tests verify all validation functions work correctly in isolation.
These tests do not require Indigo runtime and can run with pytest.
"""
import sys
from pathlib import Path

import pytest

# Add Server Plugin directory to path for imports
SERVER_PLUGIN_DIR = (
    Path(__file__).parent.parent
    / "Netro Sprinklers.indigoPlugin"
    / "Contents"
    / "Server Plugin"
)
sys.path.insert(0, str(SERVER_PLUGIN_DIR))

from validators import (
    validate_device_config,
    validate_action_config,
    validate_event_config,
    validate_prefs_config,
)


class TestDeviceConfigValidation:
    """Tests for validate_device_config function."""

    def test_sprinkler_valid_serial(self):
        """Valid 12-char serial passes."""
        values = {"address": "0123456789AB"}
        is_valid, sanitized, errors = validate_device_config(values, "sprinkler")
        assert is_valid is True
        assert sanitized["address"] == "0123456789AB"
        assert errors == {}

    def test_sprinkler_empty_serial(self):
        """Empty serial returns error with key 'address'."""
        values = {"address": ""}
        is_valid, sanitized, errors = validate_device_config(values, "sprinkler")
        assert is_valid is False
        assert "address" in errors
        assert "required" in errors["address"].lower()

    def test_sprinkler_missing_serial(self):
        """Missing serial key returns error."""
        values = {}
        is_valid, sanitized, errors = validate_device_config(values, "sprinkler")
        assert is_valid is False
        assert "address" in errors

    def test_sprinkler_short_serial(self):
        """Serial < 8 chars returns error."""
        values = {"address": "ABC"}
        is_valid, sanitized, errors = validate_device_config(values, "sprinkler")
        assert is_valid is False
        assert "address" in errors
        assert "too short" in errors["address"].lower()

    def test_sprinkler_serial_whitespace_stripped(self):
        """Whitespace trimmed from serial."""
        values = {"address": "  0123456789AB  "}
        is_valid, sanitized, errors = validate_device_config(values, "sprinkler")
        assert is_valid is True
        assert sanitized["address"] == "0123456789AB"

    def test_whisperer_valid_serial(self):
        """Valid serial passes for Whisperer."""
        values = {"address": "ABCDEFGH1234"}
        is_valid, sanitized, errors = validate_device_config(values, "Whisperer")
        assert is_valid is True
        assert sanitized["address"] == "ABCDEFGH1234"
        assert errors == {}

    def test_whisperer_empty_serial(self):
        """Empty serial returns error for Whisperer."""
        values = {"address": ""}
        is_valid, sanitized, errors = validate_device_config(values, "Whisperer")
        assert is_valid is False
        assert "address" in errors

    def test_whisperer_short_serial(self):
        """Short serial returns error for Whisperer."""
        values = {"address": "ABC"}
        is_valid, sanitized, errors = validate_device_config(values, "Whisperer")
        assert is_valid is False
        assert "address" in errors
        assert "too short" in errors["address"].lower()

    def test_whisperer_sets_capabilities(self):
        """Whisperer sets SupportsBatteryLevel, NumTemperatureInputs, etc."""
        values = {"address": "ABCDEFGH1234"}
        is_valid, sanitized, errors = validate_device_config(values, "Whisperer")
        assert is_valid is True
        assert sanitized["SupportsBatteryLevel"] is True
        assert sanitized["NumTemperatureInputs"] == 1
        assert sanitized["NumHumidityInputs"] == 1
        assert sanitized["SupportsTemperatureReporting"] is True

    def test_whisperer_sets_capabilities_even_on_error(self):
        """Whisperer sets capabilities even when serial validation fails."""
        values = {"address": ""}
        is_valid, sanitized, errors = validate_device_config(values, "Whisperer")
        assert is_valid is False
        # Capabilities should still be set
        assert sanitized["SupportsBatteryLevel"] is True
        assert sanitized["NumTemperatureInputs"] == 1

    def test_unknown_type_passes(self):
        """Unknown type_id doesn't error (passes through)."""
        values = {"address": "anything"}
        is_valid, sanitized, errors = validate_device_config(values, "unknownType")
        assert is_valid is True
        assert errors == {}


class TestActionConfigValidation:
    """Tests for validate_action_config function."""

    # startZoneWithDelay tests
    def test_start_zone_valid(self):
        """Valid duration/delay/zone passes."""
        values = {"duration": "15", "delay": "5", "zone": "zone1"}
        is_valid, sanitized, errors = validate_action_config(
            values, "startZoneWithDelay"
        )
        assert is_valid is True
        assert sanitized["duration"] == 15
        assert sanitized["delay"] == 5
        assert errors == {}

    def test_start_zone_default_values(self):
        """Missing duration/delay use defaults."""
        values = {"zone": "zone1"}
        is_valid, sanitized, errors = validate_action_config(
            values, "startZoneWithDelay"
        )
        assert is_valid is True
        assert sanitized["duration"] == 15
        assert sanitized["delay"] == 0

    def test_start_zone_invalid_duration_low(self):
        """Duration < 1 errors."""
        values = {"duration": "0", "delay": "0", "zone": "zone1"}
        is_valid, sanitized, errors = validate_action_config(
            values, "startZoneWithDelay"
        )
        assert is_valid is False
        assert "duration" in errors
        assert "between" in errors["duration"].lower()

    def test_start_zone_invalid_duration_high(self):
        """Duration > 180 errors."""
        values = {"duration": "200", "delay": "0", "zone": "zone1"}
        is_valid, sanitized, errors = validate_action_config(
            values, "startZoneWithDelay"
        )
        assert is_valid is False
        assert "duration" in errors

    def test_start_zone_invalid_duration_non_numeric(self):
        """Non-numeric duration errors."""
        values = {"duration": "abc", "delay": "0", "zone": "zone1"}
        is_valid, sanitized, errors = validate_action_config(
            values, "startZoneWithDelay"
        )
        assert is_valid is False
        assert "duration" in errors
        assert "valid number" in errors["duration"].lower()

    def test_start_zone_invalid_delay_negative(self):
        """Delay < 0 errors."""
        values = {"duration": "15", "delay": "-1", "zone": "zone1"}
        is_valid, sanitized, errors = validate_action_config(
            values, "startZoneWithDelay"
        )
        assert is_valid is False
        assert "delay" in errors

    def test_start_zone_invalid_delay_high(self):
        """Delay > 60 errors."""
        values = {"duration": "15", "delay": "100", "zone": "zone1"}
        is_valid, sanitized, errors = validate_action_config(
            values, "startZoneWithDelay"
        )
        assert is_valid is False
        assert "delay" in errors

    def test_start_zone_missing_zone(self):
        """Empty zone errors."""
        values = {"duration": "15", "delay": "0", "zone": ""}
        is_valid, sanitized, errors = validate_action_config(
            values, "startZoneWithDelay"
        )
        assert is_valid is False
        assert "zone" in errors
        assert "select" in errors["zone"].lower()

    def test_start_zone_missing_zone_key(self):
        """Missing zone key errors."""
        values = {"duration": "15", "delay": "0"}
        is_valid, sanitized, errors = validate_action_config(
            values, "startZoneWithDelay"
        )
        assert is_valid is False
        assert "zone" in errors

    def test_start_zone_valid_start_time(self):
        """Valid start_time (Unix timestamp) passes."""
        values = {"duration": "15", "delay": "0", "zone": "zone1", "start_time": "1706814000"}
        is_valid, sanitized, errors = validate_action_config(
            values, "startZoneWithDelay"
        )
        assert is_valid is True
        assert sanitized["start_time"] == 1706814000

    def test_start_zone_invalid_start_time(self):
        """Non-integer start_time errors."""
        values = {"duration": "15", "delay": "0", "zone": "zone1", "start_time": "notanumber"}
        is_valid, sanitized, errors = validate_action_config(
            values, "startZoneWithDelay"
        )
        assert is_valid is False
        assert "start_time" in errors
        assert "timestamp" in errors["start_time"].lower()

    def test_start_zone_empty_start_time_valid(self):
        """Empty start_time is valid (optional field)."""
        values = {"duration": "15", "delay": "0", "zone": "zone1", "start_time": ""}
        is_valid, sanitized, errors = validate_action_config(
            values, "startZoneWithDelay"
        )
        assert is_valid is True

    # reportWeather tests
    def test_report_weather_valid(self):
        """Valid temperature passes."""
        values = {"temperature": "72.5"}
        is_valid, sanitized, errors = validate_action_config(values, "reportWeather")
        assert is_valid is True
        assert sanitized["temperature"] == 72.5
        assert errors == {}

    def test_report_weather_missing_temperature(self):
        """Missing temperature errors."""
        values = {}
        is_valid, sanitized, errors = validate_action_config(values, "reportWeather")
        assert is_valid is False
        assert "temperature" in errors
        assert "required" in errors["temperature"].lower()

    def test_report_weather_empty_temperature(self):
        """Empty temperature errors."""
        values = {"temperature": ""}
        is_valid, sanitized, errors = validate_action_config(values, "reportWeather")
        assert is_valid is False
        assert "temperature" in errors

    def test_report_weather_invalid_temperature(self):
        """Non-numeric temperature errors."""
        values = {"temperature": "hot"}
        is_valid, sanitized, errors = validate_action_config(values, "reportWeather")
        assert is_valid is False
        assert "temperature" in errors
        assert "valid number" in errors["temperature"].lower()

    def test_report_weather_optional_fields_valid(self):
        """Optional fields within range pass."""
        values = {
            "temperature": "72",
            "t_max": "85",
            "t_min": "55",
            "humidity": "60",
            "rain": "0.5",
            "rain_prob": "25",
            "wind_speed": "10",
            "pressure": "30",
        }
        is_valid, sanitized, errors = validate_action_config(values, "reportWeather")
        assert is_valid is True
        assert sanitized["t_max"] == 85.0
        assert sanitized["t_min"] == 55.0
        assert sanitized["humidity"] == 60.0
        assert errors == {}

    def test_report_weather_optional_fields_out_of_range(self):
        """Out of range optional fields error."""
        values = {
            "temperature": "72",
            "humidity": "150",  # Out of range (0-100)
        }
        is_valid, sanitized, errors = validate_action_config(values, "reportWeather")
        assert is_valid is False
        assert "humidity" in errors
        assert "between" in errors["humidity"].lower()

    def test_report_weather_optional_fields_empty_valid(self):
        """Empty optional fields are valid."""
        values = {
            "temperature": "72",
            "t_max": "",
            "humidity": "",
        }
        is_valid, sanitized, errors = validate_action_config(values, "reportWeather")
        assert is_valid is True

    def test_report_weather_invalid_date(self):
        """Invalid date format errors."""
        values = {"temperature": "72", "date": "01/15/2024"}
        is_valid, sanitized, errors = validate_action_config(values, "reportWeather")
        assert is_valid is False
        assert "date" in errors
        assert "YYYY-MM-DD" in errors["date"]

    def test_report_weather_valid_date(self):
        """Valid YYYY-MM-DD passes."""
        values = {"temperature": "72", "date": "2024-01-15"}
        is_valid, sanitized, errors = validate_action_config(values, "reportWeather")
        assert is_valid is True
        assert sanitized["date"] == "2024-01-15"

    def test_unknown_action_type_passes(self):
        """Unknown action type_id passes through."""
        values = {"anything": "value"}
        is_valid, sanitized, errors = validate_action_config(values, "unknownAction")
        assert is_valid is True
        assert errors == {}

    # setMoisture tests
    def test_set_moisture_valid(self):
        """Valid zone and moisture passes."""
        values = {"zone": "3", "moisture": "75"}
        is_valid, sanitized, errors = validate_action_config(values, "setMoisture")
        assert is_valid is True
        assert sanitized["zone"] == 3
        assert sanitized["moisture"] == 75
        assert errors == {}

    def test_set_moisture_boundary_zero(self):
        """Moisture 0 is valid."""
        values = {"zone": "1", "moisture": "0"}
        is_valid, sanitized, errors = validate_action_config(values, "setMoisture")
        assert is_valid is True
        assert sanitized["moisture"] == 0

    def test_set_moisture_boundary_hundred(self):
        """Moisture 100 is valid."""
        values = {"zone": "1", "moisture": "100"}
        is_valid, sanitized, errors = validate_action_config(values, "setMoisture")
        assert is_valid is True
        assert sanitized["moisture"] == 100

    def test_set_moisture_over_hundred(self):
        """Moisture over 100 errors."""
        values = {"zone": "1", "moisture": "101"}
        is_valid, sanitized, errors = validate_action_config(values, "setMoisture")
        assert is_valid is False
        assert "moisture" in errors

    def test_set_moisture_negative(self):
        """Negative moisture errors."""
        values = {"zone": "1", "moisture": "-5"}
        is_valid, sanitized, errors = validate_action_config(values, "setMoisture")
        assert is_valid is False
        assert "moisture" in errors

    def test_set_moisture_non_numeric(self):
        """Non-numeric moisture errors."""
        values = {"zone": "1", "moisture": "wet"}
        is_valid, sanitized, errors = validate_action_config(values, "setMoisture")
        assert is_valid is False
        assert "moisture" in errors

    def test_set_moisture_empty_moisture(self):
        """Empty moisture errors."""
        values = {"zone": "1", "moisture": ""}
        is_valid, sanitized, errors = validate_action_config(values, "setMoisture")
        assert is_valid is False
        assert "moisture" in errors

    def test_set_moisture_missing_zone(self):
        """Missing zone errors."""
        values = {"moisture": "50"}
        is_valid, sanitized, errors = validate_action_config(values, "setMoisture")
        assert is_valid is False
        assert "zone" in errors

    def test_set_moisture_invalid_zone(self):
        """Non-numeric zone errors."""
        values = {"zone": "abc", "moisture": "50"}
        is_valid, sanitized, errors = validate_action_config(values, "setMoisture")
        assert is_valid is False
        assert "zone" in errors


class TestEventConfigValidation:
    """Tests for validate_event_config function."""

    def test_sprinkler_error_valid(self):
        """Non-empty serial passes."""
        values = {"serial": "0123456789AB"}
        is_valid, sanitized, errors = validate_event_config(values, "sprinklerError")
        assert is_valid is True
        assert errors == {}

    def test_sprinkler_error_empty_serial(self):
        """Empty serial errors."""
        values = {"serial": ""}
        is_valid, sanitized, errors = validate_event_config(values, "sprinklerError")
        assert is_valid is False
        assert "serial" in errors
        assert "select" in errors["serial"].lower()

    def test_sprinkler_error_missing_serial(self):
        """Missing serial key errors."""
        values = {}
        is_valid, sanitized, errors = validate_event_config(values, "sprinklerError")
        assert is_valid is False
        assert "serial" in errors

    def test_unknown_event_type_passes(self):
        """Unknown type_id passes through."""
        values = {"anything": "value"}
        is_valid, sanitized, errors = validate_event_config(values, "unknownEvent")
        assert is_valid is True
        assert errors == {}


class TestPrefsConfigValidation:
    """Tests for validate_prefs_config function."""

    def test_valid_prefs(self):
        """All valid values pass."""
        values = {
            "pollingInterval": "10",
            "apiTimeout": "30",
            "maxZoneRunTime": "3600",
        }
        is_valid, sanitized, errors = validate_prefs_config(values)
        assert is_valid is True
        assert sanitized["pollingInterval"] == 10
        assert sanitized["apiTimeout"] == 30
        assert sanitized["maxZoneRunTime"] == 3600
        assert errors == {}

    def test_valid_prefs_defaults(self):
        """Missing values use defaults."""
        values = {}
        is_valid, sanitized, errors = validate_prefs_config(values)
        assert is_valid is True
        assert sanitized["pollingInterval"] == 3
        assert sanitized["apiTimeout"] == 5
        assert sanitized["maxZoneRunTime"] == 3600

    def test_polling_interval_too_low(self):
        """< 3 minutes errors."""
        values = {"pollingInterval": "1"}
        is_valid, sanitized, errors = validate_prefs_config(values)
        assert is_valid is False
        assert "pollingInterval" in errors
        assert "at least" in errors["pollingInterval"].lower()

    def test_polling_interval_too_high(self):
        """> 1440 minutes errors."""
        values = {"pollingInterval": "2000"}
        is_valid, sanitized, errors = validate_prefs_config(values)
        assert is_valid is False
        assert "pollingInterval" in errors
        assert "exceed" in errors["pollingInterval"].lower()

    def test_polling_interval_non_numeric(self):
        """Non-numeric errors."""
        values = {"pollingInterval": "fast"}
        is_valid, sanitized, errors = validate_prefs_config(values)
        assert is_valid is False
        assert "pollingInterval" in errors
        assert "valid number" in errors["pollingInterval"].lower()

    def test_api_timeout_too_low(self):
        """< 1 second errors."""
        values = {"apiTimeout": "0"}
        is_valid, sanitized, errors = validate_prefs_config(values)
        assert is_valid is False
        assert "apiTimeout" in errors

    def test_api_timeout_too_high(self):
        """> 60 seconds errors."""
        values = {"apiTimeout": "120"}
        is_valid, sanitized, errors = validate_prefs_config(values)
        assert is_valid is False
        assert "apiTimeout" in errors

    def test_max_runtime_too_low(self):
        """< 60 seconds errors."""
        values = {"maxZoneRunTime": "30"}
        is_valid, sanitized, errors = validate_prefs_config(values)
        assert is_valid is False
        assert "maxZoneRunTime" in errors

    def test_max_runtime_too_high(self):
        """> 10800 seconds errors."""
        values = {"maxZoneRunTime": "50000"}
        is_valid, sanitized, errors = validate_prefs_config(values)
        assert is_valid is False
        assert "maxZoneRunTime" in errors


class TestEdgeCases:
    """Tests for edge cases across all validators."""

    def test_empty_dict_device(self):
        """Empty dict for device config with sprinkler type."""
        values = {}
        is_valid, sanitized, errors = validate_device_config(values, "sprinkler")
        assert is_valid is False
        # Should handle gracefully, not crash

    def test_empty_dict_action(self):
        """Empty dict for action config with startZoneWithDelay type."""
        values = {}
        is_valid, sanitized, errors = validate_action_config(
            values, "startZoneWithDelay"
        )
        assert is_valid is False
        assert "zone" in errors  # zone is required

    def test_empty_dict_event(self):
        """Empty dict for event config with sprinklerError type."""
        values = {}
        is_valid, sanitized, errors = validate_event_config(values, "sprinklerError")
        assert is_valid is False

    def test_empty_dict_prefs(self):
        """Empty dict for prefs config uses defaults."""
        values = {}
        is_valid, sanitized, errors = validate_prefs_config(values)
        assert is_valid is True
        # Defaults should be applied

    def test_string_numbers_converted(self):
        """String '15' converted to int correctly."""
        values = {"duration": "15", "delay": "5", "zone": "zone1"}
        is_valid, sanitized, errors = validate_action_config(
            values, "startZoneWithDelay"
        )
        assert is_valid is True
        assert isinstance(sanitized["duration"], int)
        assert sanitized["duration"] == 15

    def test_whitespace_in_numbers(self):
        """' 15 ' handled correctly."""
        values = {"duration": " 15 ", "delay": " 5 ", "zone": "zone1"}
        is_valid, sanitized, errors = validate_action_config(
            values, "startZoneWithDelay"
        )
        # Integer parsing should handle whitespace
        assert is_valid is True
        assert sanitized["duration"] == 15

    def test_returns_sanitized_values(self):
        """Sanitized values are returned correctly."""
        values = {"address": "  SERIAL123456  "}
        is_valid, sanitized, errors = validate_device_config(values, "sprinkler")
        assert is_valid is True
        # Sanitized should have stripped value
        assert sanitized["address"] == "SERIAL123456"
        # Original dict key should be in sanitized
        assert "address" in sanitized

    def test_integer_values_accepted(self):
        """Integer values (not strings) are accepted."""
        values = {"duration": 15, "delay": 5, "zone": "zone1"}
        is_valid, sanitized, errors = validate_action_config(
            values, "startZoneWithDelay"
        )
        assert is_valid is True
        assert sanitized["duration"] == 15

    def test_none_values_handled(self):
        """None values are handled gracefully."""
        values = {"address": None}
        is_valid, sanitized, errors = validate_device_config(values, "sprinkler")
        assert is_valid is False
        assert "address" in errors

    def test_float_string_for_integer_field(self):
        """Float string '15.5' for integer field."""
        values = {"duration": "15.5", "delay": "0", "zone": "zone1"}
        is_valid, sanitized, errors = validate_action_config(
            values, "startZoneWithDelay"
        )
        # Integer conversion of '15.5' should fail
        assert is_valid is False
        assert "duration" in errors

    def test_boundary_values_duration(self):
        """Boundary values for duration (1 and 180) are valid."""
        # Min boundary
        values = {"duration": "1", "delay": "0", "zone": "zone1"}
        is_valid, _, _ = validate_action_config(values, "startZoneWithDelay")
        assert is_valid is True

        # Max boundary
        values = {"duration": "180", "delay": "0", "zone": "zone1"}
        is_valid, _, _ = validate_action_config(values, "startZoneWithDelay")
        assert is_valid is True

    def test_boundary_values_polling(self):
        """Boundary values for polling interval (3 and 1440) are valid."""
        # Min boundary
        values = {"pollingInterval": "3"}
        is_valid, _, _ = validate_prefs_config(values)
        assert is_valid is True

        # Max boundary
        values = {"pollingInterval": "1440"}
        is_valid, _, _ = validate_prefs_config(values)
        assert is_valid is True
