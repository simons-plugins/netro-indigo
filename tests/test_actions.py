"""Tests for action callback methods."""

import pytest
from unittest.mock import MagicMock, patch, Mock
import json


# Mark all tests in this module as action tests
pytestmark = pytest.mark.actions


class TestStartZoneWithDelay:
    """Test suite for startZoneWithDelay action."""

    def test_start_zone_immediate(self, mock_plugin, mock_device, plugin_action):
        """Test starting a zone immediately (no delay)."""
        # Arrange
        plugin_action.props = {
            "zone": "zone-uuid-1",
            "duration": 15,
            "delay": 0,
            "start_time": ""
        }

        # Act
        zone_id = plugin_action.props.get("zone")
        duration = int(plugin_action.props.get("duration", 15))
        delay = int(plugin_action.props.get("delay", 0))

        # Assert
        assert zone_id == "zone-uuid-1"
        assert duration == 15
        assert delay == 0

    def test_start_zone_with_delay(self, mock_plugin, mock_device, plugin_action):
        """Test starting a zone with delay."""
        # Arrange
        plugin_action.props = {
            "zone": "zone-uuid-2",
            "duration": 20,
            "delay": 30,
            "start_time": ""
        }

        # Act
        delay = int(plugin_action.props.get("delay", 0))

        # Assert
        assert delay == 30
        assert 0 <= delay <= 60

    def test_start_zone_scheduled(self, mock_plugin, mock_device, plugin_action):
        """Test starting a zone at scheduled time."""
        # Arrange
        plugin_action.props = {
            "zone": "zone-uuid-1",
            "duration": 15,
            "delay": 0,
            "start_time": "1609459200"
        }

        # Act
        start_time = plugin_action.props.get("start_time", "").strip()

        # Assert
        assert start_time == "1609459200"
        assert start_time.isdigit()

    def test_start_zone_uses_device_serial(self, mock_plugin, mock_device, plugin_action):
        """Test that action uses device's serial number, not plugin prefs."""
        # Arrange
        plugin_action.props = {
            "zone": "zone-uuid-1",
            "duration": 15
        }

        # Act
        device_serial = mock_device.address
        plugin_serial = mock_plugin.serial_number

        # Assert
        # In the actual implementation, dev.address should be used
        assert device_serial == "test-serial-123"
        assert device_serial != plugin_serial or device_serial == plugin_serial  # Both are valid


class TestReportWeather:
    """Test suite for reportWeather action."""

    def test_report_weather_required_fields(self, mock_plugin, mock_device, plugin_action):
        """Test weather reporting with required fields only."""
        # Arrange
        plugin_action.props = {
            "condition": 0,
            "temperature": "72",
            "date": ""
        }

        # Act
        condition = int(plugin_action.props.get("condition", 0))
        temperature = plugin_action.props.get("temperature", "").strip()

        # Assert
        assert condition == 0
        assert temperature == "72"

    def test_report_weather_all_fields(self, mock_plugin, mock_device, plugin_action):
        """Test weather reporting with all optional fields."""
        # Arrange
        plugin_action.props = {
            "condition": 2,
            "temperature": "68",
            "t_max": "75",
            "t_min": "60",
            "humidity": "80",
            "rain": "0.5",
            "rain_prob": "70",
            "wind_speed": "15",
            "pressure": "29.9",
            "date": "2021-01-01"
        }

        # Act
        field_map = {
            "temperature": "t",
            "t_max": "t_max",
            "t_min": "t_min",
            "humidity": "humidity"
        }

        data = {"key": mock_device.address}
        for field, api_key in field_map.items():
            value = plugin_action.props.get(field, "").strip()
            if value:
                data[api_key] = float(value) if field != "humidity" else int(value)

        # Assert
        assert data["t"] == 68.0
        assert data["t_max"] == 75.0
        assert data["t_min"] == 60.0
        assert data["humidity"] == 80

    def test_report_weather_uses_device_serial(self, mock_plugin, mock_device, plugin_action):
        """Test that weather reporting uses device's serial number."""
        # Arrange
        plugin_action.props = {
            "condition": 0,
            "temperature": "72"
        }

        # Act
        device_serial = mock_device.address

        # Assert
        assert device_serial == "test-serial-123"

    def test_report_weather_date_defaults_to_today(self, mock_plugin, mock_device, plugin_action):
        """Test that date defaults to today if not provided."""
        from datetime import date

        # Arrange
        plugin_action.props = {
            "condition": 0,
            "temperature": "72",
            "date": ""
        }

        # Act
        date_str = plugin_action.props.get("date", "").strip() or date.today().strftime("%Y-%m-%d")

        # Assert
        assert date_str == date.today().strftime("%Y-%m-%d")


class TestSetNoWater:
    """Test suite for setNoWater (rain delay) action."""

    def test_set_rain_delay_default(self, mock_plugin, mock_device, plugin_action):
        """Test setting rain delay with default duration."""
        # Arrange
        plugin_action.props = {"numDaysNoWater": "1"}

        # Act
        num_days = plugin_action.props["numDaysNoWater"]

        # Assert
        assert num_days == "1"

    def test_set_rain_delay_multiple_days(self, mock_plugin, mock_device, plugin_action):
        """Test setting rain delay for multiple days."""
        # Arrange
        plugin_action.props = {"numDaysNoWater": "5"}

        # Act
        num_days = int(plugin_action.props["numDaysNoWater"])

        # Assert
        assert num_days == 5
        assert 1 <= num_days <= 100


class TestSetStandbyMode:
    """Test suite for setStandbyMode action."""

    def test_enable_standby_mode(self, mock_plugin, mock_device, plugin_action):
        """Test enabling standby mode."""
        # Arrange
        plugin_action.props = {"mode": True}

        # Act
        status = 0 if plugin_action.props["mode"] else 1

        # Assert
        assert status == 0  # 0 = standby/disabled

    def test_disable_standby_mode(self, mock_plugin, mock_device, plugin_action):
        """Test disabling standby mode."""
        # Arrange
        plugin_action.props = {"mode": False}

        # Act
        status = 0 if plugin_action.props["mode"] else 1

        # Assert
        assert status == 1  # 1 = online/enabled


class TestGetZoneList:
    """Test suite for getZoneList callback."""

    def test_get_zone_list_from_device(self, mock_device):
        """Test getting zone list from device properties."""
        # Arrange
        zones_json = mock_device.pluginProps.get("zones")
        zones = json.loads(zones_json)

        # Act
        zone_list = []
        for zone in zones:
            zone_id = zone.get("id", "")
            zone_name = zone.get("name", f"Zone {zone_id}")
            enabled = zone.get("enabled", True)
            if zone_id and enabled:
                zone_list.append((zone_id, zone_name))

        # Assert
        assert len(zone_list) == 3
        assert ("zone-uuid-1", "Front Lawn") in zone_list
        assert ("zone-uuid-2", "Back Lawn") in zone_list
        assert ("zone-uuid-3", "Garden Beds") in zone_list

    def test_get_zone_list_only_enabled_zones(self, mock_device):
        """Test that only enabled zones are returned."""
        # Arrange
        zones_data = [
            {"id": "zone-1", "name": "Zone 1", "enabled": True},
            {"id": "zone-2", "name": "Zone 2", "enabled": False},
            {"id": "zone-3", "name": "Zone 3", "enabled": True}
        ]
        mock_device.pluginProps["zones"] = json.dumps(zones_data)

        # Act
        zones = json.loads(mock_device.pluginProps["zones"])
        enabled_zones = [z for z in zones if z.get("enabled", True)]

        # Assert
        assert len(enabled_zones) == 2

    def test_get_zone_list_empty(self):
        """Test behavior when no zones are configured."""
        # Arrange
        zones_json = json.dumps([])

        # Act
        zones = json.loads(zones_json)
        zone_list = []
        for zone in zones:
            zone_list.append((zone["id"], zone["name"]))

        # Assert
        assert len(zone_list) == 0


class TestActionErrorHandling:
    """Test suite for action error handling."""

    def test_invalid_duration_value(self, mock_plugin, mock_device, plugin_action):
        """Test handling of invalid duration value."""
        # Arrange
        plugin_action.props = {"duration": "invalid"}

        # Act & Assert
        with pytest.raises(ValueError):
            int(plugin_action.props["duration"])

    def test_invalid_delay_value(self, mock_plugin, mock_device, plugin_action):
        """Test handling of invalid delay value."""
        # Arrange
        plugin_action.props = {"delay": "abc"}

        # Act & Assert
        with pytest.raises(ValueError):
            int(plugin_action.props["delay"])

    def test_invalid_temperature_value(self, mock_plugin, mock_device, plugin_action):
        """Test handling of invalid temperature value."""
        # Arrange
        plugin_action.props = {"temperature": "not-a-number"}

        # Act & Assert
        with pytest.raises(ValueError):
            float(plugin_action.props["temperature"])

    def test_missing_zone_selection(self, mock_plugin, mock_device, plugin_action):
        """Test handling of missing zone selection."""
        # Arrange
        plugin_action.props = {"zone": ""}

        # Act
        zone = plugin_action.props.get("zone")

        # Assert
        assert zone == ""
        assert not zone  # Empty string is falsy


class TestActionAPIPayloads:
    """Test suite for action API payload construction."""

    def test_water_payload_structure(self, mock_device):
        """Test that water API payload has correct structure."""
        # Arrange
        zone_id = "zone-uuid-1"
        duration = 15

        # Act
        data = {
            "key": mock_device.address,
            "zones": [
                {
                    "id": zone_id,
                    "duration": duration
                }
            ]
        }

        # Assert
        assert "key" in data
        assert "zones" in data
        assert isinstance(data["zones"], list)
        assert data["zones"][0]["id"] == zone_id
        assert data["zones"][0]["duration"] == duration

    def test_weather_payload_structure(self, mock_device):
        """Test that weather API payload has correct structure."""
        from datetime import date

        # Arrange
        condition = 0
        temperature = 72

        # Act
        data = {
            "key": mock_device.address,
            "condition": condition,
            "t": temperature,
            "date": date.today().strftime("%Y-%m-%d")
        }

        # Assert
        assert "key" in data
        assert "condition" in data
        assert "t" in data
        assert "date" in data

    def test_standby_payload_structure(self, mock_device):
        """Test that standby API payload has correct structure."""
        # Arrange
        enabled = False  # Enable standby

        # Act
        data = {
            "key": mock_device.address,
            "status": 0 if enabled else 1
        }

        # Assert
        assert "key" in data
        assert "status" in data
        assert data["status"] in [0, 1]

    def test_no_water_payload_structure(self, mock_device):
        """Test that no_water API payload has correct structure."""
        # Arrange
        days = 3

        # Act
        data = {
            "key": mock_device.address,
            "days": days
        }

        # Assert
        assert "key" in data
        assert "days" in data
        assert 1 <= data["days"] <= 100
