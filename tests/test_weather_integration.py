"""Unit tests for Tomorrow.io weather integration.

Tests cover:
- Metric-to-US unit conversion (utils.py)
- Plugin prefs validation for Tomorrow.io fields (validators.py)
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

from utils import (
    convert_weather_metric_to_us,
    convert_weather_us_to_metric,
    celsius_to_fahrenheit,
    mm_to_inches,
    ms_to_mph,
    hpa_to_inhg,
)
from validators import validate_prefs_config


# =============================================================================
# TestMetricToUSConversion
# =============================================================================

@pytest.mark.weather
class TestMetricToUSConversion:
    """Tests for metric-to-US unit conversion functions."""

    def test_celsius_to_fahrenheit_freezing(self):
        """0C = 32F."""
        assert celsius_to_fahrenheit(0) == 32

    def test_celsius_to_fahrenheit_boiling(self):
        """100C = 212F."""
        assert celsius_to_fahrenheit(100) == 212

    def test_celsius_to_fahrenheit_negative(self):
        """-40C = -40F."""
        assert celsius_to_fahrenheit(-40) == -40

    def test_mm_to_inches(self):
        """25.4mm = 1 inch."""
        assert abs(mm_to_inches(25.4) - 1.0) < 0.001

    def test_ms_to_mph(self):
        """1 m/s ~ 2.237 mph."""
        assert abs(ms_to_mph(1.0) - 2.237) < 0.01

    def test_hpa_to_inhg(self):
        """1013.25 hPa ~ 29.92 inHg."""
        assert abs(hpa_to_inhg(1013.25) - 29.92) < 0.01

    def test_convert_full_weather_dict(self):
        """Full weather dict converts all fields correctly."""
        metric = {
            "condition": 2,
            "date": "2026-04-09",
            "t": 22.5,
            "t_max": 28.0,
            "t_min": 15.0,
            "humidity": 65,
            "rain": 2.5,
            "rain_prob": 80,
            "wind_speed": 5.2,
            "pressure": 1013.25,
        }
        us = convert_weather_metric_to_us(metric)

        # Temperature conversions
        assert us["t"] == 72.5
        assert us["t_max"] == 82.4
        assert us["t_min"] == 59.0

        # Rain: 2.5mm -> ~0.10 inches
        assert abs(us["rain"] - 0.10) < 0.01

        # Wind: 5.2 m/s -> ~11.6 mph
        assert abs(us["wind_speed"] - 11.6) < 0.1

        # Pressure: 1013.25 hPa -> ~29.92 inHg
        assert abs(us["pressure"] - 29.92) < 0.01

        # Non-converted fields stay the same
        assert us["condition"] == 2
        assert us["date"] == "2026-04-09"
        assert us["humidity"] == 65
        assert us["rain_prob"] == 80

    def test_convert_preserves_original(self):
        """Conversion returns a new dict, doesn't modify original."""
        metric = {"t": 20.0, "rain": 5.0}
        us = convert_weather_metric_to_us(metric)
        assert metric["t"] == 20.0  # Original unchanged
        assert us["t"] != 20.0  # Converted is different

    def test_convert_handles_missing_fields(self):
        """Missing optional fields don't cause errors."""
        metric = {"condition": 0, "date": "2026-04-09", "t": 20.0}
        us = convert_weather_metric_to_us(metric)
        assert us["t"] == 68.0
        assert "rain" not in us
        assert "wind_speed" not in us
        assert "pressure" not in us

    def test_convert_handles_none_values(self):
        """None values in optional fields are preserved."""
        metric = {"t": 20.0, "rain": None, "wind_speed": None, "pressure": None}
        us = convert_weather_metric_to_us(metric)
        assert us["t"] == 68.0
        assert us["rain"] is None
        assert us["wind_speed"] is None
        assert us["pressure"] is None


# =============================================================================
# TestPrefsValidationTomorrow
# =============================================================================

@pytest.mark.weather
class TestPrefsValidationTomorrow:
    """Tests for Tomorrow.io plugin prefs validation."""

    def test_valid_prefs_with_tomorrow_enabled(self):
        """Valid prefs with Tomorrow.io enabled passes validation."""
        values = {
            "pollingInterval": "5",
            "apiTimeout": "5",
            "maxZoneRunTime": "3600",
            "weatherUpdateInterval": "30",
            "tomorrowEnabled": True,
            "tomorrowApiKey": "my-tomorrow-api-key-12345678",
            "tomorrowLocation": "42.3478,-71.0466",
        }
        is_valid, sanitized, errors = validate_prefs_config(values)
        assert is_valid is True
        assert len(errors) == 0
        assert sanitized["tomorrowApiKey"] == "my-tomorrow-api-key-12345678"
        assert sanitized["tomorrowLocation"] == "42.3478,-71.0466"

    def test_valid_prefs_with_tomorrow_disabled(self):
        """Valid prefs with Tomorrow.io disabled - no API key needed."""
        values = {
            "pollingInterval": "5",
            "apiTimeout": "5",
            "maxZoneRunTime": "3600",
            "weatherUpdateInterval": "30",
            "tomorrowEnabled": False,
            "tomorrowApiKey": "",
            "tomorrowLocation": "",
        }
        is_valid, sanitized, errors = validate_prefs_config(values)
        assert is_valid is True
        assert len(errors) == 0

    def test_tomorrow_enabled_missing_api_key(self):
        """Enabled without API key fails validation."""
        values = {
            "pollingInterval": "5",
            "apiTimeout": "5",
            "maxZoneRunTime": "3600",
            "weatherUpdateInterval": "30",
            "tomorrowEnabled": True,
            "tomorrowApiKey": "",
            "tomorrowLocation": "42.3478,-71.0466",
        }
        is_valid, sanitized, errors = validate_prefs_config(values)
        assert is_valid is False
        assert "tomorrowApiKey" in errors

    def test_tomorrow_enabled_missing_location(self):
        """Enabled without location fails validation."""
        values = {
            "pollingInterval": "5",
            "apiTimeout": "5",
            "maxZoneRunTime": "3600",
            "weatherUpdateInterval": "30",
            "tomorrowEnabled": True,
            "tomorrowApiKey": "my-tomorrow-api-key-12345678",
            "tomorrowLocation": "",
        }
        is_valid, sanitized, errors = validate_prefs_config(values)
        assert is_valid is False
        assert "tomorrowLocation" in errors

    def test_weather_update_interval_too_low(self):
        """Weather interval below minimum fails validation."""
        values = {
            "pollingInterval": "5",
            "apiTimeout": "5",
            "maxZoneRunTime": "3600",
            "weatherUpdateInterval": "5",
            "tomorrowEnabled": False,
        }
        is_valid, sanitized, errors = validate_prefs_config(values)
        assert is_valid is False
        assert "weatherUpdateInterval" in errors

    def test_weather_update_interval_default(self):
        """Missing weather interval uses default (30 min)."""
        values = {
            "pollingInterval": "5",
            "apiTimeout": "5",
            "maxZoneRunTime": "3600",
        }
        is_valid, sanitized, errors = validate_prefs_config(values)
        assert is_valid is True
        assert sanitized["weatherUpdateInterval"] == 30

    def test_tomorrow_api_key_whitespace_stripped(self):
        """API key whitespace is stripped."""
        values = {
            "pollingInterval": "5",
            "apiTimeout": "5",
            "maxZoneRunTime": "3600",
            "weatherUpdateInterval": "30",
            "tomorrowEnabled": True,
            "tomorrowApiKey": "  my-api-key-12345678  ",
            "tomorrowLocation": "  42.3478,-71.0466  ",
        }
        is_valid, sanitized, errors = validate_prefs_config(values)
        assert is_valid is True
        assert sanitized["tomorrowApiKey"] == "my-api-key-12345678"
        assert sanitized["tomorrowLocation"] == "42.3478,-71.0466"


# =============================================================================
# TestDewPointConversion
# =============================================================================

@pytest.mark.weather
class TestDewPointConversion:
    """Tests for t_dew conversion in weather data."""

    def test_t_dew_converted_metric_to_us(self):
        """t_dew should be converted from Celsius to Fahrenheit."""
        weather = {"condition": 1, "t": 20.0, "t_dew": 10.0}
        result = convert_weather_metric_to_us(weather)
        assert result["t_dew"] == 50.0  # 10°C = 50°F

    def test_t_dew_converted_us_to_metric(self):
        """t_dew should be converted from Fahrenheit to Celsius."""
        weather = {"condition": 1, "t": 68.0, "t_dew": 50.0}
        result = convert_weather_us_to_metric(weather)
        assert result["t_dew"] == 10.0  # 50°F = 10°C

    def test_missing_t_dew_unaffected(self):
        """Dict without t_dew should be unchanged."""
        weather = {"condition": 1, "t": 20.0, "humidity": 60}
        result = convert_weather_metric_to_us(weather)
        assert "t_dew" not in result
        assert result["humidity"] == 60
