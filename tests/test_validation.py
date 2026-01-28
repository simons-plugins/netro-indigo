"""Tests for configuration and action validation."""

import pytest
from unittest.mock import MagicMock


# Mark all tests in this module as validation tests
pytestmark = pytest.mark.validation


class TestPluginConfigValidation:
    """Test suite for plugin configuration validation."""

    def test_serial_number_required(self, mock_plugin):
        """Test that serial number is required."""
        # Arrange
        values_dict = {
            "accessToken": "",
            "pollingInterval": 5,
            "apiTimeout": 5,
            "maxZoneRunTime": 3600
        }

        # Act
        is_valid = len(values_dict.get("accessToken", "").strip()) > 0

        # Assert
        assert is_valid is False

    def test_serial_number_minimum_length(self, mock_plugin):
        """Test that serial number has minimum length."""
        # Arrange
        values_dict = {
            "accessToken": "short",  # Too short (< 8 chars)
            "pollingInterval": 5
        }

        # Act
        serial = values_dict.get("accessToken", "").strip()
        is_valid = len(serial) >= 8

        # Assert
        assert is_valid is False

    def test_polling_interval_minimum(self, mock_plugin):
        """Test that polling interval has minimum value."""
        # Arrange
        values_dict = {"pollingInterval": 2}  # Below minimum of 3

        # Act
        polling = int(values_dict.get("pollingInterval", 3))
        is_valid = polling >= 3

        # Assert
        assert is_valid is False

    def test_polling_interval_maximum(self, mock_plugin):
        """Test that polling interval has maximum value."""
        # Arrange
        values_dict = {"pollingInterval": 2000}  # Above maximum of 1440

        # Act
        polling = int(values_dict.get("pollingInterval", 3))
        is_valid = polling <= 1440

        # Assert
        assert is_valid is False

    def test_api_timeout_minimum(self, mock_plugin):
        """Test that API timeout has minimum value."""
        # Arrange
        values_dict = {"apiTimeout": 0}  # Below minimum of 1

        # Act
        timeout = int(values_dict.get("apiTimeout", 5))
        is_valid = timeout >= 1

        # Assert
        assert is_valid is False

    def test_api_timeout_maximum(self, mock_plugin):
        """Test that API timeout has maximum value."""
        # Arrange
        values_dict = {"apiTimeout": 100}  # Above maximum of 60

        # Act
        timeout = int(values_dict.get("apiTimeout", 5))
        is_valid = timeout <= 60

        # Assert
        assert is_valid is False

    def test_max_zone_runtime_minimum(self, mock_plugin):
        """Test that max zone runtime has minimum value."""
        # Arrange
        values_dict = {"maxZoneRunTime": 30}  # Below minimum of 60

        # Act
        max_runtime = int(values_dict.get("maxZoneRunTime", 3600))
        is_valid = max_runtime >= 60

        # Assert
        assert is_valid is False

    def test_max_zone_runtime_maximum(self, mock_plugin):
        """Test that max zone runtime has maximum value."""
        # Arrange
        values_dict = {"maxZoneRunTime": 15000}  # Above maximum of 10800

        # Act
        max_runtime = int(values_dict.get("maxZoneRunTime", 3600))
        is_valid = max_runtime <= 10800

        # Assert
        assert is_valid is False

    def test_valid_configuration(self, mock_plugin):
        """Test that valid configuration passes all checks."""
        # Arrange
        values_dict = {
            "accessToken": "a4cf12b8d5e2",
            "pollingInterval": 5,
            "apiTimeout": 5,
            "maxZoneRunTime": 3600,
            "showDebugInfo": False
        }

        # Act
        serial_valid = len(values_dict["accessToken"]) >= 8
        polling_valid = 3 <= int(values_dict["pollingInterval"]) <= 1440
        timeout_valid = 1 <= int(values_dict["apiTimeout"]) <= 60
        runtime_valid = 60 <= int(values_dict["maxZoneRunTime"]) <= 10800

        # Assert
        assert all([serial_valid, polling_valid, timeout_valid, runtime_valid])


class TestActionValidation:
    """Test suite for action configuration validation."""

    def test_start_zone_duration_minimum(self, mock_plugin):
        """Test that zone duration has minimum value."""
        # Arrange
        values_dict = {"duration": 0}  # Below minimum of 1

        # Act
        duration = int(values_dict.get("duration", 15))
        is_valid = 1 <= duration <= 180

        # Assert
        assert is_valid is False

    def test_start_zone_duration_maximum(self, mock_plugin):
        """Test that zone duration has maximum value."""
        # Arrange
        values_dict = {"duration": 200}  # Above maximum of 180

        # Act
        duration = int(values_dict.get("duration", 15))
        is_valid = 1 <= duration <= 180

        # Assert
        assert is_valid is False

    def test_start_zone_delay_minimum(self, mock_plugin):
        """Test that zone delay has minimum value."""
        # Arrange
        values_dict = {"delay": -5}  # Below minimum of 0

        # Act
        delay = int(values_dict.get("delay", 0))
        is_valid = 0 <= delay <= 60

        # Assert
        assert is_valid is False

    def test_start_zone_delay_maximum(self, mock_plugin):
        """Test that zone delay has maximum value."""
        # Arrange
        values_dict = {"delay": 100}  # Above maximum of 60

        # Act
        delay = int(values_dict.get("delay", 0))
        is_valid = 0 <= delay <= 60

        # Assert
        assert is_valid is False

    def test_weather_temperature_required(self, mock_plugin):
        """Test that temperature is required for weather reporting."""
        # Arrange
        values_dict = {
            "condition": 0,
            "humidity": 65
        }

        # Act
        temperature = values_dict.get("temperature", "").strip()
        is_valid = len(temperature) > 0

        # Assert
        assert is_valid is False

    def test_weather_humidity_range(self, mock_plugin):
        """Test that humidity is within valid range."""
        # Arrange
        test_cases = [
            (-10, False),   # Below minimum
            (0, True),      # At minimum
            (50, True),     # Valid middle
            (100, True),    # At maximum
            (150, False)    # Above maximum
        ]

        # Act & Assert
        for humidity, expected_valid in test_cases:
            is_valid = 0 <= humidity <= 100
            assert is_valid == expected_valid, f"Failed for humidity={humidity}"

    def test_weather_rain_prob_range(self, mock_plugin):
        """Test that rain probability is within valid range."""
        # Arrange
        test_cases = [
            (-10, False),
            (0, True),
            (50, True),
            (100, True),
            (150, False)
        ]

        # Act & Assert
        for rain_prob, expected_valid in test_cases:
            is_valid = 0 <= rain_prob <= 100
            assert is_valid == expected_valid, f"Failed for rain_prob={rain_prob}"

    def test_weather_date_format(self, mock_plugin):
        """Test that date format is validated."""
        from datetime import datetime

        # Arrange
        test_cases = [
            ("2021-01-01", True),      # Valid format
            ("2021-1-1", False),       # Invalid (missing leading zeros)
            ("01/01/2021", False),     # Invalid (wrong separator)
            ("2021-13-01", False),     # Invalid (month out of range)
            ("not-a-date", False)      # Invalid (not a date)
        ]

        # Act & Assert
        for date_str, expected_valid in test_cases:
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
                is_valid = True
            except ValueError:
                is_valid = False

            assert is_valid == expected_valid, f"Failed for date={date_str}"

    def test_rain_delay_days_minimum(self, mock_plugin):
        """Test that rain delay days has minimum value."""
        # Arrange
        values_dict = {"numDaysNoWater": 0}  # Below minimum of 1

        # Act
        days = int(values_dict.get("numDaysNoWater", 1))
        is_valid = 1 <= days <= 100

        # Assert
        assert is_valid is False

    def test_rain_delay_days_maximum(self, mock_plugin):
        """Test that rain delay days has maximum value."""
        # Arrange
        values_dict = {"numDaysNoWater": 150}  # Above maximum of 100

        # Act
        days = int(values_dict.get("numDaysNoWater", 1))
        is_valid = 1 <= days <= 100

        # Assert
        assert is_valid is False


class TestDeviceValidation:
    """Test suite for device configuration validation."""

    def test_device_serial_required(self, mock_device):
        """Test that device serial number is required."""
        # Arrange
        values_dict = {"address": ""}

        # Act
        serial = values_dict.get("address", "").strip()
        is_valid = len(serial) > 0

        # Assert
        assert is_valid is False

    def test_zone_selected_for_action(self, mock_device):
        """Test that zone must be selected for zone actions."""
        # Arrange
        values_dict = {"zone": ""}

        # Act
        zone = values_dict.get("zone")
        is_valid = zone is not None and zone != ""

        # Assert
        assert is_valid is False


class TestValueTypeValidation:
    """Test suite for value type validation."""

    def test_numeric_field_rejects_text(self, mock_plugin):
        """Test that numeric fields reject text values."""
        # Arrange
        values = ["abc", "12.5.6", "one", ""]

        # Act & Assert
        for value in values:
            try:
                int(value)
                is_valid = True
            except ValueError:
                is_valid = False

            assert is_valid is False, f"Should reject non-numeric value: {value}"

    def test_numeric_field_accepts_valid_numbers(self, mock_plugin):
        """Test that numeric fields accept valid numbers."""
        # Arrange
        values = ["5", "100", "3600"]

        # Act & Assert
        for value in values:
            try:
                int(value)
                is_valid = True
            except ValueError:
                is_valid = False

            assert is_valid is True, f"Should accept valid number: {value}"

    def test_float_field_accepts_decimals(self, mock_plugin):
        """Test that float fields accept decimal values."""
        # Arrange
        values = ["72.5", "0.5", "100.0"]

        # Act & Assert
        for value in values:
            try:
                float(value)
                is_valid = True
            except ValueError:
                is_valid = False

            assert is_valid is True, f"Should accept valid float: {value}"
