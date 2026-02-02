"""Unit tests for device_handlers.py module.

Tests verify handlers transform API data correctly without Indigo dependency.
These tests do not require Indigo runtime and can run with pytest.
"""
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

# Add Server Plugin directory to path for imports
SERVER_PLUGIN_DIR = (
    Path(__file__).parent.parent
    / "Netro Sprinklers.indigoPlugin"
    / "Contents"
    / "Server Plugin"
)
sys.path.insert(0, str(SERVER_PLUGIN_DIR))

from device_handlers import SprinklerHandler, WhispererHandler


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_logger():
    """Create a mock logger for testing."""
    logger = Mock()
    logger.debug = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    return logger


@pytest.fixture
def sprinkler_handler(mock_logger):
    """Create a SprinklerHandler instance with mock logger."""
    return SprinklerHandler(logger=mock_logger)


@pytest.fixture
def whisperer_handler(mock_logger):
    """Create a WhispererHandler instance with mock logger."""
    return WhispererHandler(logger=mock_logger)


@pytest.fixture
def sample_device_info_response():
    """Sample response from api_client.get_device_info()."""
    return {
        "status": "OK",
        "data": {
            "device": {
                "serial": "ABC123456789",
                "status": "ONLINE",
                "version": 1,
                "name": "Front Yard Sprinkler",
                "macAddress": "00:11:22:33:44:55",
                "model": "Netro Sprite",
                "paused": False,
                "scheduleModeType": "SMART",
                "last_active": "2026-02-01T12:00:00",
                "zones": [
                    {"ith": 1, "name": "Lawn", "enabled": True, "maxRuntime": 1800},
                    {"ith": 2, "name": "Garden", "enabled": True, "maxRuntime": 1200},
                    {"ith": 3, "name": "Disabled Zone", "enabled": False, "maxRuntime": 900},
                ]
            }
        },
        "meta": {
            "token_remaining": 1500,
            "time": "2026-02-01T12:30:00",
            "token_reset": "2026-02-02T00:00:00"
        }
    }


@pytest.fixture
def sample_schedules_response():
    """Sample response from api_client.get_schedules()."""
    return {
        "status": "OK",
        "data": {
            "schedules": [
                {
                    "status": "EXECUTING",
                    "zone": 1,
                    "source": "AUTOMATIC",
                    "start_time": 1706814000000,
                    "duration": 1800,
                    "zone_name": "Lawn"
                },
                {
                    "status": "VALID",
                    "zone": 2,
                    "source": "SMART",
                    "start_time": 1706817600000,
                    "duration": 1200,
                    "zone_name": "Garden"
                },
                {
                    "status": "VALID",
                    "zone": 3,
                    "source": "MANUAL",
                    "start_time": 1706820000000,
                    "duration": 600,
                    "zone_name": "Patio"
                }
            ]
        },
        "meta": {}
    }


@pytest.fixture
def sample_moistures_response():
    """Sample response from api_client.get_moistures()."""
    return {
        "status": "OK",
        "data": {
            "moistures": [
                {"id": 100, "zone": 1, "moisture": 45.5, "date": "2026-02-01"},
                {"id": 99, "zone": 2, "moisture": 52.3, "date": "2026-02-01"},
                {"id": 98, "zone": 1, "moisture": 42.0, "date": "2026-01-31"},
            ]
        },
        "meta": {}
    }


@pytest.fixture
def sample_sensor_data_response():
    """Sample response from api_client.get_sensor_data()."""
    return {
        "status": "OK",
        "data": {
            "sensor_data": [
                {
                    "id": 500,
                    "moisture": 42.5,
                    "celsius": 22.3,
                    "sunlight": 85,
                    "time": "2026-02-01T12:00:00",
                    "local_date": "2026-02-01",
                    "local_time": "12:00:00",
                    "battery_level": 95
                },
                {
                    "id": 499,
                    "moisture": 40.0,
                    "celsius": 21.5,
                    "sunlight": 80,
                    "time": "2026-02-01T11:00:00",
                    "local_date": "2026-02-01",
                    "local_time": "11:00:00",
                    "battery_level": 95
                }
            ]
        },
        "meta": {
            "token_remaining": 1500,
            "time": "2026-02-01T12:30:00",
            "token_reset": "2026-02-02T00:00:00",
            "last_active": "2026-02-01T12:00:00"
        }
    }


# =============================================================================
# TestSprinklerHandlerDeviceInfo
# =============================================================================

@pytest.mark.handlers
class TestSprinklerHandlerDeviceInfo:
    """Tests for SprinklerHandler.process_device_info method."""

    def test_process_device_info_online_device(self, sprinkler_handler, sample_device_info_response):
        """Online device returns is_online=True."""
        states, is_online, device_data = sprinkler_handler.process_device_info(
            sample_device_info_response, "ABC123456789"
        )
        assert is_online is True
        assert len(states) > 0

    def test_process_device_info_offline_device(self, sprinkler_handler):
        """Offline device returns is_online=False."""
        response = {
            "status": "OK",
            "data": {"device": {"serial": "ABC123", "status": "OFFLINE", "version": 1}},
            "meta": {}
        }
        states, is_online, device_data = sprinkler_handler.process_device_info(response, "ABC123")
        assert is_online is False

    def test_process_device_info_extracts_all_fields(self, sprinkler_handler, sample_device_info_response):
        """All expected fields are extracted into states."""
        states, is_online, device_data = sprinkler_handler.process_device_info(
            sample_device_info_response, "ABC123456789"
        )

        state_keys = {s["key"] for s in states}
        expected_keys = {
            "id", "api_version", "address", "model", "paused",
            "scheduleModeType", "status", "token_remaining", "time",
            "last_active", "token_reset", "name"
        }
        assert expected_keys.issubset(state_keys)

    def test_process_device_info_missing_meta(self, sprinkler_handler):
        """Missing meta section uses defaults."""
        response = {
            "status": "OK",
            "data": {"device": {"serial": "ABC123", "status": "ONLINE", "version": 1}},
        }
        states, is_online, device_data = sprinkler_handler.process_device_info(response, "ABC123")

        # Should find token_remaining with default value
        token_state = next((s for s in states if s["key"] == "token_remaining"), None)
        assert token_state is not None
        assert token_state["value"] == 0

    def test_process_device_info_missing_device_data(self, sprinkler_handler, mock_logger):
        """Missing device data returns error states."""
        response = {"status": "OK", "data": {}}
        states, is_online, device_data = sprinkler_handler.process_device_info(response, "ABC123")

        assert is_online is False
        # Should log error
        mock_logger.error.assert_called()
        # Should return error state
        status_state = next((s for s in states if s["key"] == "status"), None)
        assert status_state is not None
        assert status_state["value"] == "ERROR"

    def test_process_device_info_malformed_response(self, sprinkler_handler, mock_logger):
        """Malformed response returns error states."""
        response = {"status": "OK"}  # Missing data entirely
        states, is_online, device_data = sprinkler_handler.process_device_info(response, "ABC123")

        assert is_online is False
        mock_logger.error.assert_called()

    def test_process_device_info_returns_device_data_for_zones(self, sprinkler_handler, sample_device_info_response):
        """Device data returned includes zones for further processing."""
        states, is_online, device_data = sprinkler_handler.process_device_info(
            sample_device_info_response, "ABC123456789"
        )
        assert "zones" in device_data
        assert len(device_data["zones"]) == 3

    def test_process_device_info_handles_none_values(self, sprinkler_handler):
        """None values in response are handled gracefully."""
        response = {
            "status": "OK",
            "data": {
                "device": {
                    "serial": "ABC123",
                    "status": "ONLINE",
                    "version": None,
                    "name": None,
                    "macAddress": None
                }
            },
            "meta": {"token_remaining": None}
        }
        states, is_online, device_data = sprinkler_handler.process_device_info(response, "ABC123")
        # Should not raise exception
        assert is_online is True

    def test_process_device_info_serial_from_response(self, sprinkler_handler, sample_device_info_response):
        """Serial is extracted from response, not passed argument."""
        states, is_online, device_data = sprinkler_handler.process_device_info(
            sample_device_info_response, "DIFFERENT_SERIAL"
        )
        id_state = next(s for s in states if s["key"] == "id")
        assert id_state["value"] == "ABC123456789"

    def test_process_device_info_uses_fallback_serial(self, sprinkler_handler):
        """When serial missing from response, uses passed serial."""
        response = {
            "status": "OK",
            "data": {"device": {"status": "ONLINE", "version": 1}},
            "meta": {}
        }
        states, is_online, device_data = sprinkler_handler.process_device_info(
            response, "FALLBACK_SERIAL"
        )
        id_state = next(s for s in states if s["key"] == "id")
        assert id_state["value"] == "FALLBACK_SERIAL"

    def test_process_device_info_status_values(self, sprinkler_handler, sample_device_info_response):
        """Status value is correctly extracted."""
        states, is_online, device_data = sprinkler_handler.process_device_info(
            sample_device_info_response, "ABC123"
        )
        status_state = next(s for s in states if s["key"] == "status")
        assert status_state["value"] == "ONLINE"

    def test_process_device_info_empty_zones(self, sprinkler_handler):
        """Device with no zones still works."""
        response = {
            "status": "OK",
            "data": {"device": {"serial": "ABC123", "status": "ONLINE", "version": 1, "zones": []}},
            "meta": {}
        }
        states, is_online, device_data = sprinkler_handler.process_device_info(response, "ABC123")
        assert is_online is True
        assert device_data.get("zones") == []


# =============================================================================
# TestSprinklerHandlerSchedules
# =============================================================================

@pytest.mark.handlers
class TestSprinklerHandlerSchedules:
    """Tests for SprinklerHandler.process_schedules method."""

    def test_process_schedules_executing_schedule(self, sprinkler_handler, sample_schedules_response):
        """Executing schedule is detected and returned."""
        states, active_name = sprinkler_handler.process_schedules(sample_schedules_response)

        active_schedule = next(s for s in states if s["key"] == "activeSchedule")
        active_zone = next(s for s in states if s["key"] == "activeZone")

        assert active_schedule["value"] == "Automatic"
        assert active_zone["value"] == 1
        assert active_name == "Automatic"

    def test_process_schedules_no_active_schedule(self, sprinkler_handler):
        """No executing schedule returns appropriate message."""
        response = {
            "status": "OK",
            "data": {
                "schedules": [
                    {"status": "VALID", "zone": 1, "source": "SMART", "start_time": 1706817600000}
                ]
            }
        }
        states, active_name = sprinkler_handler.process_schedules(response)

        active_schedule = next(s for s in states if s["key"] == "activeSchedule")
        active_zone = next(s for s in states if s["key"] == "activeZone")

        assert active_schedule["value"] == "No active schedule"
        assert active_zone["value"] == 0
        assert active_name is None

    def test_process_schedules_finds_next_valid_schedule(self, sprinkler_handler, sample_schedules_response):
        """Next VALID schedule with earliest start time is found."""
        states, active_name = sprinkler_handler.process_schedules(sample_schedules_response)

        next_zone = next(s for s in states if s["key"] == "nextScheduleZone")
        next_source = next(s for s in states if s["key"] == "nextScheduleSource")

        # Zone 2 has earlier start_time than Zone 3
        assert next_zone["value"] == "Garden"
        assert next_source["value"] == "Smart"

    def test_process_schedules_multiple_valid_selects_earliest(self, sprinkler_handler):
        """When multiple VALID schedules, selects one with earliest start_time."""
        response = {
            "status": "OK",
            "data": {
                "schedules": [
                    {"status": "VALID", "zone": 3, "source": "MANUAL", "start_time": 2000000000000, "zone_name": "Later"},
                    {"status": "VALID", "zone": 1, "source": "SMART", "start_time": 1000000000000, "zone_name": "Earlier"},
                ]
            }
        }
        states, active_name = sprinkler_handler.process_schedules(response)

        next_zone = next(s for s in states if s["key"] == "nextScheduleZone")
        assert next_zone["value"] == "Earlier"

    def test_process_schedules_timestamp_conversion(self, sprinkler_handler, sample_schedules_response):
        """Timestamp is converted to readable format."""
        states, active_name = sprinkler_handler.process_schedules(sample_schedules_response)

        next_time = next(s for s in states if s["key"] == "nextScheduleTime")
        # Should be formatted string, not raw timestamp
        assert "-" in next_time["value"]  # Date format like YYYY-MM-DD
        assert ":" in next_time["value"]  # Time format like HH:MM:SS

    def test_process_schedules_invalid_timestamp(self, sprinkler_handler):
        """Invalid timestamp is handled gracefully."""
        response = {
            "status": "OK",
            "data": {
                "schedules": [
                    {"status": "VALID", "zone": 1, "source": "SMART", "start_time": "not_a_number"}
                ]
            }
        }
        states, active_name = sprinkler_handler.process_schedules(response)

        next_time = next(s for s in states if s["key"] == "nextScheduleTime")
        assert next_time["value"] == "Invalid timestamp"

    def test_process_schedules_empty_schedules(self, sprinkler_handler):
        """Empty schedules list returns no upcoming schedule."""
        response = {"status": "OK", "data": {"schedules": []}}
        states, active_name = sprinkler_handler.process_schedules(response)

        next_time = next(s for s in states if s["key"] == "nextScheduleTime")
        assert next_time["value"] == "No upcoming schedule"

    def test_process_schedules_malformed_response(self, sprinkler_handler, mock_logger):
        """Malformed response returns error message."""
        response = {"status": "OK", "data": {}}
        states, active_name = sprinkler_handler.process_schedules(response)

        mock_logger.error.assert_called()
        active_schedule = next(s for s in states if s["key"] == "activeSchedule")
        assert "Error" in active_schedule["value"]

    def test_process_schedules_returns_active_name(self, sprinkler_handler, sample_schedules_response):
        """Active schedule name is returned for property update."""
        states, active_name = sprinkler_handler.process_schedules(sample_schedules_response)
        assert active_name == "Automatic"

    def test_process_schedules_string_start_time(self, sprinkler_handler):
        """String start_time is converted to float."""
        response = {
            "status": "OK",
            "data": {
                "schedules": [
                    {"status": "VALID", "zone": 1, "source": "SMART", "start_time": "1706817600000", "zone_name": "Test"}
                ]
            }
        }
        states, active_name = sprinkler_handler.process_schedules(response)

        next_time = next(s for s in states if s["key"] == "nextScheduleTime")
        # Should be parsed successfully
        assert "Invalid timestamp" not in next_time["value"]

    def test_process_schedules_duration_conversion(self, sprinkler_handler, sample_schedules_response):
        """Duration in seconds is converted to minutes."""
        states, active_name = sprinkler_handler.process_schedules(sample_schedules_response)

        next_duration = next(s for s in states if s["key"] == "nextScheduleDuration")
        # 1200 seconds = 20 minutes
        assert next_duration["value"] == 20


# =============================================================================
# TestSprinklerHandlerMoistures
# =============================================================================

@pytest.mark.handlers
class TestSprinklerHandlerMoistures:
    """Tests for SprinklerHandler.process_moistures method."""

    def test_process_moistures_returns_zone_states(self, sprinkler_handler, sample_moistures_response):
        """Moisture states are returned for each zone."""
        states = sprinkler_handler.process_moistures(sample_moistures_response)

        assert len(states) >= 1
        # Check state format
        for state in states:
            assert "key" in state
            assert "value" in state
            assert "zone_" in state["key"]
            assert "_moisture" in state["key"]

    def test_process_moistures_selects_most_recent_date(self, sprinkler_handler, sample_moistures_response):
        """Only most recent date's moistures are returned."""
        states = sprinkler_handler.process_moistures(sample_moistures_response)

        # Only zones from 2026-02-01 should be returned (id 100, 99)
        # Not from 2026-01-31 (id 98)
        zone_keys = [s["key"] for s in states]
        assert "zone_1_moisture" in zone_keys
        assert "zone_2_moisture" in zone_keys
        assert len(states) == 2  # Only 2 zones from most recent date

    def test_process_moistures_empty_list(self, sprinkler_handler, mock_logger):
        """Empty moistures list returns empty states."""
        response = {"status": "OK", "data": {"moistures": []}}
        states = sprinkler_handler.process_moistures(response)

        assert states == []
        mock_logger.debug.assert_called()

    def test_process_moistures_multiple_zones(self, sprinkler_handler, sample_moistures_response):
        """Multiple zones are all processed."""
        states = sprinkler_handler.process_moistures(sample_moistures_response)

        zone1 = next((s for s in states if s["key"] == "zone_1_moisture"), None)
        zone2 = next((s for s in states if s["key"] == "zone_2_moisture"), None)

        assert zone1 is not None
        assert zone2 is not None
        assert zone1["value"] == "45.5"
        assert zone2["value"] == "52.3"

    def test_process_moistures_malformed_response(self, sprinkler_handler, mock_logger):
        """Malformed response returns empty list."""
        response = {"status": "OK", "data": {}}
        states = sprinkler_handler.process_moistures(response)

        assert states == []
        mock_logger.error.assert_called()

    def test_process_moistures_sorts_by_id(self, sprinkler_handler):
        """Moistures are sorted by ID (descending) to find most recent."""
        response = {
            "status": "OK",
            "data": {
                "moistures": [
                    {"id": 50, "zone": 1, "moisture": 30.0, "date": "2026-01-01"},
                    {"id": 200, "zone": 1, "moisture": 45.0, "date": "2026-02-01"},
                    {"id": 100, "zone": 1, "moisture": 40.0, "date": "2026-01-15"},
                ]
            }
        }
        states = sprinkler_handler.process_moistures(response)

        # Only the date from highest ID should be used (2026-02-01)
        zone1 = next(s for s in states if s["key"] == "zone_1_moisture")
        assert zone1["value"] == "45.0"


# =============================================================================
# TestSprinklerHandlerZoneInfo
# =============================================================================

@pytest.mark.handlers
class TestSprinklerHandlerZoneInfo:
    """Tests for SprinklerHandler.extract_zone_info method."""

    def test_extract_zone_info_builds_zone_names(self, sprinkler_handler, sample_device_info_response):
        """Zone names are built as comma-separated string."""
        device_data = sample_device_info_response["data"]["device"]
        zone_names, max_durations, zones_data = sprinkler_handler.extract_zone_info(device_data, 3600)

        assert "Lawn" in zone_names
        assert "Garden" in zone_names
        assert "Disabled Zone" in zone_names

    def test_extract_zone_info_respects_max_runtime(self, sprinkler_handler, sample_device_info_response):
        """Max runtime from plugin is used for enabled zones."""
        device_data = sample_device_info_response["data"]["device"]
        zone_names, max_durations, zones_data = sprinkler_handler.extract_zone_info(device_data, 2400)

        # First two zones enabled, should have max_runtime = 2400
        assert max_durations[0] == "2400"
        assert max_durations[1] == "2400"

    def test_extract_zone_info_disabled_zones_zero_duration(self, sprinkler_handler, sample_device_info_response):
        """Disabled zones get duration of 0."""
        device_data = sample_device_info_response["data"]["device"]
        zone_names, max_durations, zones_data = sprinkler_handler.extract_zone_info(device_data, 3600)

        # Third zone is disabled
        assert max_durations[2] == "0"

    def test_extract_zone_info_sorts_by_ith(self, sprinkler_handler):
        """Zones are sorted by ith (zone number)."""
        device_data = {
            "zones": [
                {"ith": 3, "name": "Third", "enabled": True},
                {"ith": 1, "name": "First", "enabled": True},
                {"ith": 2, "name": "Second", "enabled": True},
            ]
        }
        zone_names, max_durations, zones_data = sprinkler_handler.extract_zone_info(device_data, 3600)

        assert zone_names == "First, Second, Third"
        assert zones_data[0]["name"] == "First"
        assert zones_data[1]["name"] == "Second"
        assert zones_data[2]["name"] == "Third"

    def test_extract_zone_info_builds_zones_data(self, sprinkler_handler, sample_device_info_response):
        """zones_data is built for dropdown lists."""
        device_data = sample_device_info_response["data"]["device"]
        zone_names, max_durations, zones_data = sprinkler_handler.extract_zone_info(device_data, 3600)

        assert len(zones_data) == 3
        assert zones_data[0]["id"] == 1
        assert zones_data[0]["name"] == "Lawn"
        assert zones_data[0]["enabled"] is True

    def test_extract_zone_info_empty_zones(self, sprinkler_handler):
        """Empty zones list returns empty results."""
        device_data = {"zones": []}
        zone_names, max_durations, zones_data = sprinkler_handler.extract_zone_info(device_data, 3600)

        assert zone_names == ""
        assert max_durations == []
        assert zones_data == []

    def test_extract_zone_info_missing_zones_key(self, sprinkler_handler, mock_logger):
        """Missing zones key is handled gracefully."""
        device_data = {}
        zone_names, max_durations, zones_data = sprinkler_handler.extract_zone_info(device_data, 3600)

        assert zone_names == ""
        assert max_durations == []
        assert zones_data == []


# =============================================================================
# TestWhispererHandler
# =============================================================================

@pytest.mark.handlers
class TestWhispererHandler:
    """Tests for WhispererHandler.process_sensor_data method."""

    def test_process_sensor_data_returns_all_states(self, whisperer_handler, sample_sensor_data_response):
        """All expected states are returned."""
        states, has_readings = whisperer_handler.process_sensor_data(
            sample_sensor_data_response, "SENSOR123"
        )

        state_keys = {s["key"] for s in states}
        expected_keys = {
            "sensorValue", "humidity", "soilMoisture", "temperature",
            "soilTemperature", "sunlight", "readingID", "readingTime",
            "readingLocalDate", "readingLocalTime", "id", "token_remaining",
            "token_reset", "api_last_active", "sensor_last_active", "time",
            "batteryLevel"
        }
        assert expected_keys.issubset(state_keys)

    def test_process_sensor_data_has_readings_true(self, whisperer_handler, sample_sensor_data_response):
        """has_readings is True when sensor data exists."""
        states, has_readings = whisperer_handler.process_sensor_data(
            sample_sensor_data_response, "SENSOR123"
        )
        assert has_readings is True

    def test_process_sensor_data_empty_readings(self, whisperer_handler, mock_logger):
        """Empty readings returns minimal meta-only update."""
        response = {
            "status": "OK",
            "data": {"sensor_data": []},
            "meta": {"token_remaining": 1500, "token_reset": "2026-02-02", "last_active": "2026-02-01", "time": "now"}
        }
        states, has_readings = whisperer_handler.process_sensor_data(response, "SENSOR123")

        assert has_readings is False
        mock_logger.info.assert_called()
        # Should still return meta states
        assert len(states) > 0

    def test_process_sensor_data_has_readings_false_when_empty(self, whisperer_handler):
        """has_readings is False when sensor_data is empty."""
        response = {"status": "OK", "data": {"sensor_data": []}, "meta": {}}
        states, has_readings = whisperer_handler.process_sensor_data(response, "SENSOR123")
        assert has_readings is False

    def test_process_sensor_data_includes_ui_value(self, whisperer_handler, sample_sensor_data_response):
        """sensorValue includes uiValue with formatted percentage."""
        states, has_readings = whisperer_handler.process_sensor_data(
            sample_sensor_data_response, "SENSOR123"
        )

        sensor_value = next(s for s in states if s["key"] == "sensorValue")
        assert "uiValue" in sensor_value
        assert "%" in sensor_value["uiValue"]

    def test_process_sensor_data_missing_field(self, whisperer_handler):
        """Missing field in reading uses default."""
        response = {
            "status": "OK",
            "data": {
                "sensor_data": [
                    {"id": 1, "moisture": 40.0}  # Missing many fields
                ]
            },
            "meta": {}
        }
        states, has_readings = whisperer_handler.process_sensor_data(response, "SENSOR123")

        # Should not raise, should use defaults
        assert has_readings is True
        temp_state = next((s for s in states if s["key"] == "temperature"), None)
        assert temp_state is not None
        assert temp_state["value"] == 0  # Default

    def test_process_sensor_data_malformed_response(self, whisperer_handler, mock_logger):
        """Malformed response returns empty list."""
        response = {"status": "OK", "data": {}}
        states, has_readings = whisperer_handler.process_sensor_data(response, "SENSOR123")

        # Empty data.sensor_data key should be handled
        assert has_readings is False

    def test_process_sensor_data_sorts_by_id(self, whisperer_handler):
        """Sensor readings are sorted by ID to get most recent."""
        response = {
            "status": "OK",
            "data": {
                "sensor_data": [
                    {"id": 100, "moisture": 30.0, "celsius": 20, "sunlight": 50, "time": "t1",
                     "local_date": "d1", "local_time": "lt1", "battery_level": 90},
                    {"id": 500, "moisture": 45.0, "celsius": 25, "sunlight": 85, "time": "t2",
                     "local_date": "d2", "local_time": "lt2", "battery_level": 95},
                ]
            },
            "meta": {}
        }
        states, has_readings = whisperer_handler.process_sensor_data(response, "SENSOR123")

        # Should use id=500 (highest)
        moisture = next(s for s in states if s["key"] == "soilMoisture")
        assert moisture["value"] == 45.0

    def test_process_sensor_data_meta_values(self, whisperer_handler, sample_sensor_data_response):
        """Meta values are correctly extracted."""
        states, has_readings = whisperer_handler.process_sensor_data(
            sample_sensor_data_response, "SENSOR123"
        )

        token_state = next(s for s in states if s["key"] == "token_remaining")
        assert token_state["value"] == 1500

    def test_process_sensor_data_battery_level(self, whisperer_handler, sample_sensor_data_response):
        """Battery level is extracted."""
        states, has_readings = whisperer_handler.process_sensor_data(
            sample_sensor_data_response, "SENSOR123"
        )

        battery = next(s for s in states if s["key"] == "batteryLevel")
        assert battery["value"] == 95


# =============================================================================
# TestHandlerInstantiation
# =============================================================================

@pytest.mark.handlers
class TestHandlerInstantiation:
    """Tests for handler class instantiation."""

    def test_sprinkler_handler_default_logger(self):
        """SprinklerHandler uses module logger when none provided."""
        handler = SprinklerHandler()
        assert handler.logger is not None

    def test_sprinkler_handler_custom_logger(self, mock_logger):
        """SprinklerHandler accepts custom logger."""
        handler = SprinklerHandler(logger=mock_logger)
        assert handler.logger is mock_logger

    def test_whisperer_handler_default_logger(self):
        """WhispererHandler uses module logger when none provided."""
        handler = WhispererHandler()
        assert handler.logger is not None

    def test_whisperer_handler_custom_logger(self, mock_logger):
        """WhispererHandler accepts custom logger."""
        handler = WhispererHandler(logger=mock_logger)
        assert handler.logger is mock_logger
