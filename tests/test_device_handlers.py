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
            "id", "api_version", "status", "token_remaining", "time",
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

    def test_process_device_info_unicode_device_name(self, sprinkler_handler):
        """Device name with unicode characters is preserved."""
        response = {
            "status": "OK",
            "data": {
                "device": {
                    "serial": "ABC123",
                    "status": "ONLINE",
                    "version": 1,
                    "name": "Syst\u00e8me d'arrosage"  # French with accent
                }
            },
            "meta": {}
        }
        states, is_online, device_data = sprinkler_handler.process_device_info(response, "ABC123")

        name_state = next(s for s in states if s["key"] == "name")
        assert name_state["value"] == "Syst\u00e8me d'arrosage"

    def test_process_device_info_zones_key_missing(self, sprinkler_handler):
        """Missing zones key returns empty zones list."""
        response = {
            "status": "OK",
            "data": {"device": {"serial": "ABC123", "status": "ONLINE", "version": 1}},
            "meta": {}
        }
        states, is_online, device_data = sprinkler_handler.process_device_info(response, "ABC123")

        # Should handle gracefully - no zones key in device_data is OK
        assert is_online is True
        assert len(states) > 0  # Should still return device states

    def test_api_response_completely_empty(self, sprinkler_handler, mock_logger):
        """Completely empty response is handled gracefully."""
        response = {}
        states, is_online, device_data = sprinkler_handler.process_device_info(response, "ABC123")

        # Should log error and return error states
        assert is_online is False
        mock_logger.error.assert_called()

    # -------------------------------------------------------------------------
    # Malformed JSON Tests (TEST-04)
    # -------------------------------------------------------------------------

    def test_process_device_info_data_is_list(self, sprinkler_handler, mock_logger):
        """Data as list instead of dict returns error state."""
        response = {"status": "OK", "data": []}
        states, is_online, device_data = sprinkler_handler.process_device_info(response, "ABC123")

        assert is_online is False
        mock_logger.error.assert_called()

    def test_process_device_info_device_key_is_null(self, sprinkler_handler, mock_logger):
        """Device key with None value gracefully returns error state."""
        response = {"status": "OK", "data": {"device": None}}
        # None has no .get() method, so handler should catch AttributeError
        states, is_online, device_data = sprinkler_handler.process_device_info(response, "ABC123")

        assert is_online is False
        assert device_data == {}
        mock_logger.error.assert_called()


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

    # -------------------------------------------------------------------------
    # Malformed JSON Tests (TEST-04)
    # -------------------------------------------------------------------------

    def test_process_schedules_schedules_is_dict(self, sprinkler_handler):
        """Schedules as dict instead of list is treated as empty (no iteration)."""
        response = {"status": "OK", "data": {"schedules": {}}}
        states, active_name = sprinkler_handler.process_schedules(response)

        # Empty dict is falsy, so treated as no schedules
        active_schedule = next(s for s in states if s["key"] == "activeSchedule")
        assert active_schedule["value"] == "No active schedule"


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

    # -------------------------------------------------------------------------
    # Malformed JSON Tests (TEST-04)
    # -------------------------------------------------------------------------

    def test_process_moistures_moistures_is_string(self, sprinkler_handler, mock_logger):
        """Moistures as string instead of list gracefully returns empty list."""
        response = {"status": "OK", "data": {"moistures": "none"}}
        # String has no .sort() method, so handler should catch AttributeError
        states = sprinkler_handler.process_moistures(response)

        assert states == []
        mock_logger.error.assert_called()


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

    @pytest.mark.parametrize("zone_name", [
        "Garden \U0001f33b",           # Emoji (sunflower)
        "\u82b1\u56ed",                 # Chinese characters
        "\u062d\u062f\u064a\u0642\u0629",  # Arabic RTL
        "Zone\u003c\u0026\u003e",      # Mixed with HTML entities
        "\u00c9tage",                   # French accent
        "Jard\u00edn",                  # Spanish accent
    ])
    def test_extract_zone_info_unicode_names(self, sprinkler_handler, zone_name):
        """Zone names with unicode characters are preserved."""
        device_data = {"zones": [{"ith": 1, "name": zone_name, "enabled": True}]}
        zone_names, max_durations, zones_data = sprinkler_handler.extract_zone_info(device_data, 3600)

        assert zones_data[0]["name"] == zone_name
        assert zone_name in zone_names


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

    def test_process_sensor_data_unicode_in_timestamps(self, whisperer_handler):
        """Unicode characters in timestamp fields are handled without crash."""
        response = {
            "status": "OK",
            "data": {
                "sensor_data": [
                    {
                        "id": 1,
                        "moisture": 40.0,
                        "celsius": 20.0,
                        "sunlight": 50,
                        "time": "2026-02-01T12:00:00\u200b",  # Zero-width space
                        "local_date": "2026-02-01",
                        "local_time": "12:00:00",
                        "battery_level": 90
                    }
                ]
            },
            "meta": {}
        }
        states, has_readings = whisperer_handler.process_sensor_data(response, "SENSOR123")

        # Should not crash, should process time
        assert has_readings is True
        time_state = next(s for s in states if s["key"] == "readingTime")
        assert time_state is not None

    def test_process_sensor_data_meta_completely_missing(self, whisperer_handler):
        """Completely missing meta section uses defaults."""
        response = {
            "status": "OK",
            "data": {
                "sensor_data": [
                    {
                        "id": 1,
                        "moisture": 40.0,
                        "celsius": 20.0,
                        "sunlight": 50,
                        "time": "2026-02-01T12:00:00",
                        "local_date": "2026-02-01",
                        "local_time": "12:00:00",
                        "battery_level": 90
                    }
                ]
            }
        }
        states, has_readings = whisperer_handler.process_sensor_data(response, "SENSOR123")

        # Should use defaults, no crash
        assert has_readings is True
        token_state = next((s for s in states if s["key"] == "token_remaining"), None)
        assert token_state is not None
        assert token_state["value"] == 0  # Default

    # -------------------------------------------------------------------------
    # Whisperer Edge Case Tests (TEST-01)
    # -------------------------------------------------------------------------

    def test_process_sensor_data_keyerror_missing_data_key(self, whisperer_handler, mock_logger):
        """Missing 'data' key returns empty gracefully."""
        response = {"status": "OK", "meta": {"token_remaining": 1500}}
        states, has_readings = whisperer_handler.process_sensor_data(response, "SENSOR123")

        assert has_readings is False
        # Should not raise KeyError
        mock_logger.error.assert_called()

    def test_process_sensor_data_typeerror_data_is_string(self, whisperer_handler, mock_logger):
        """Data as string instead of dict gracefully returns empty result."""
        response = {"status": "OK", "data": "not a dict", "meta": {}}
        # String has no .get() method, so handler should catch AttributeError
        states, has_readings = whisperer_handler.process_sensor_data(response, "SENSOR123")

        assert has_readings is False
        assert states == []
        mock_logger.error.assert_called()

    def test_process_sensor_data_typeerror_sensor_data_is_dict(self, whisperer_handler, mock_logger):
        """Sensor_data as dict instead of list treats as empty."""
        response = {"status": "OK", "data": {"sensor_data": {}}, "meta": {}}
        states, has_readings = whisperer_handler.process_sensor_data(response, "SENSOR123")

        # Empty dict is falsy, so no readings
        assert has_readings is False
        mock_logger.info.assert_called()

    def test_process_sensor_data_null_moisture_value(self, whisperer_handler, mock_logger):
        """Moisture value of None causes TypeError in f-string formatting."""
        response = {
            "status": "OK",
            "data": {
                "sensor_data": [
                    {"id": 1, "moisture": None, "celsius": 20, "sunlight": 50,
                     "time": "2026-02-01T12:00:00", "local_date": "2026-02-01",
                     "local_time": "12:00:00", "battery_level": 90}
                ]
            },
            "meta": {}
        }
        states, has_readings = whisperer_handler.process_sensor_data(response, "SENSOR123")

        # f-string formatting "{moisture:.1f}" raises TypeError with None
        assert has_readings is False
        mock_logger.error.assert_called()

    def test_process_sensor_data_negative_moisture(self, whisperer_handler):
        """Negative moisture values are preserved (API quirk)."""
        response = {
            "status": "OK",
            "data": {
                "sensor_data": [
                    {"id": 1, "moisture": -10, "celsius": 20, "sunlight": 50,
                     "time": "2026-02-01T12:00:00", "local_date": "2026-02-01",
                     "local_time": "12:00:00", "battery_level": 90}
                ]
            },
            "meta": {}
        }
        states, has_readings = whisperer_handler.process_sensor_data(response, "SENSOR123")

        assert has_readings is True
        moisture = next(s for s in states if s["key"] == "soilMoisture")
        assert moisture["value"] == -10

    def test_process_sensor_data_null_celsius_value(self, whisperer_handler):
        """Celsius value of None is passed through (not replaced with default)."""
        response = {
            "status": "OK",
            "data": {
                "sensor_data": [
                    {"id": 1, "moisture": 42.5, "celsius": None, "sunlight": 50,
                     "time": "2026-02-01T12:00:00", "local_date": "2026-02-01",
                     "local_time": "12:00:00", "battery_level": 90}
                ]
            },
            "meta": {}
        }
        states, has_readings = whisperer_handler.process_sensor_data(response, "SENSOR123")

        assert has_readings is True
        temp = next(s for s in states if s["key"] == "temperature")
        # When key exists with None value, .get() returns None (not default)
        assert temp["value"] is None

    def test_process_sensor_data_null_battery_level(self, whisperer_handler):
        """Battery_level value of None is passed through (not replaced with default)."""
        response = {
            "status": "OK",
            "data": {
                "sensor_data": [
                    {"id": 1, "moisture": 42.5, "celsius": 20, "sunlight": 50,
                     "time": "2026-02-01T12:00:00", "local_date": "2026-02-01",
                     "local_time": "12:00:00", "battery_level": None}
                ]
            },
            "meta": {}
        }
        states, has_readings = whisperer_handler.process_sensor_data(response, "SENSOR123")

        assert has_readings is True
        battery = next(s for s in states if s["key"] == "batteryLevel")
        # When key exists with None value, .get() returns None (not default)
        assert battery["value"] is None

    def test_process_sensor_data_battery_zero(self, whisperer_handler):
        """Battery level of 0 is valid boundary value."""
        response = {
            "status": "OK",
            "data": {
                "sensor_data": [
                    {"id": 1, "moisture": 42.5, "celsius": 20, "sunlight": 50,
                     "time": "2026-02-01T12:00:00", "local_date": "2026-02-01",
                     "local_time": "12:00:00", "battery_level": 0}
                ]
            },
            "meta": {}
        }
        states, has_readings = whisperer_handler.process_sensor_data(response, "SENSOR123")

        assert has_readings is True
        battery = next(s for s in states if s["key"] == "batteryLevel")
        assert battery["value"] == 0

    def test_process_sensor_data_battery_100(self, whisperer_handler):
        """Battery level of 100 is valid boundary value."""
        response = {
            "status": "OK",
            "data": {
                "sensor_data": [
                    {"id": 1, "moisture": 42.5, "celsius": 20, "sunlight": 50,
                     "time": "2026-02-01T12:00:00", "local_date": "2026-02-01",
                     "local_time": "12:00:00", "battery_level": 100}
                ]
            },
            "meta": {}
        }
        states, has_readings = whisperer_handler.process_sensor_data(response, "SENSOR123")

        assert has_readings is True
        battery = next(s for s in states if s["key"] == "batteryLevel")
        assert battery["value"] == 100

    def test_process_sensor_data_very_large_reading_id(self, whisperer_handler):
        """Very large reading ID does not overflow."""
        response = {
            "status": "OK",
            "data": {
                "sensor_data": [
                    {"id": 2147483647, "moisture": 42.5, "celsius": 20, "sunlight": 50,
                     "time": "2026-02-01T12:00:00", "local_date": "2026-02-01",
                     "local_time": "12:00:00", "battery_level": 90}
                ]
            },
            "meta": {}
        }
        states, has_readings = whisperer_handler.process_sensor_data(response, "SENSOR123")

        assert has_readings is True
        reading_id = next(s for s in states if s["key"] == "readingID")
        assert reading_id["value"] == 2147483647

    def test_process_sensor_data_unicode_time_field(self, whisperer_handler):
        """Time with unicode characters is handled gracefully."""
        response = {
            "status": "OK",
            "data": {
                "sensor_data": [
                    {"id": 1, "moisture": 42.5, "celsius": 20, "sunlight": 50,
                     "time": "2026-02-01T12:00:00\u200b", "local_date": "2026-02-01",
                     "local_time": "12:00:00", "battery_level": 90}
                ]
            },
            "meta": {}
        }
        states, has_readings = whisperer_handler.process_sensor_data(response, "SENSOR123")

        assert has_readings is True
        reading_time = next(s for s in states if s["key"] == "readingTime")
        # Should preserve the unicode character
        assert "\u200b" in reading_time["value"]

    def test_process_sensor_data_missing_all_optional_fields(self, whisperer_handler):
        """Minimal valid reading with only id and moisture."""
        response = {
            "status": "OK",
            "data": {
                "sensor_data": [
                    {"id": 1, "moisture": 42.5}
                ]
            },
            "meta": {}
        }
        states, has_readings = whisperer_handler.process_sensor_data(response, "SENSOR123")

        assert has_readings is True
        # All missing fields should use defaults
        temp = next(s for s in states if s["key"] == "temperature")
        assert temp["value"] == 0
        sunlight = next(s for s in states if s["key"] == "sunlight")
        assert sunlight["value"] == 0
        battery = next(s for s in states if s["key"] == "batteryLevel")
        assert battery["value"] == 0

    def test_process_sensor_data_extra_unexpected_fields(self, whisperer_handler):
        """Extra unexpected fields are ignored gracefully."""
        response = {
            "status": "OK",
            "data": {
                "sensor_data": [
                    {
                        "id": 1, "moisture": 42.5, "celsius": 20, "sunlight": 50,
                        "time": "2026-02-01T12:00:00", "local_date": "2026-02-01",
                        "local_time": "12:00:00", "battery_level": 90,
                        "unknown_field": "should be ignored",
                        "another_unknown": 123
                    }
                ]
            },
            "meta": {}
        }
        states, has_readings = whisperer_handler.process_sensor_data(response, "SENSOR123")

        assert has_readings is True
        # Should process successfully despite extra fields
        moisture = next(s for s in states if s["key"] == "soilMoisture")
        assert moisture["value"] == 42.5

    def test_process_sensor_data_empty_serial_string(self, whisperer_handler):
        """Empty serial string does not crash."""
        response = {
            "status": "OK",
            "data": {
                "sensor_data": [
                    {"id": 1, "moisture": 42.5, "celsius": 20, "sunlight": 50,
                     "time": "2026-02-01T12:00:00", "local_date": "2026-02-01",
                     "local_time": "12:00:00", "battery_level": 90}
                ]
            },
            "meta": {}
        }
        states, has_readings = whisperer_handler.process_sensor_data(response, "")

        assert has_readings is True
        # Should process successfully with empty serial

    def test_process_sensor_data_serial_with_unicode(self, whisperer_handler):
        """Serial with unicode characters is handled."""
        response = {
            "status": "OK",
            "data": {
                "sensor_data": [
                    {"id": 1, "moisture": 42.5, "celsius": 20, "sunlight": 50,
                     "time": "2026-02-01T12:00:00", "local_date": "2026-02-01",
                     "local_time": "12:00:00", "battery_level": 90}
                ]
            },
            "meta": {}
        }
        states, has_readings = whisperer_handler.process_sensor_data(response, "SENSOR-\u2603")

        assert has_readings is True
        # Should process successfully with unicode in serial

    # -------------------------------------------------------------------------
    # Malformed JSON Tests (TEST-04)
    # -------------------------------------------------------------------------

    def test_process_sensor_data_sensor_data_is_int(self, whisperer_handler, mock_logger):
        """Sensor_data as int instead of list returns no readings."""
        response = {"status": "OK", "data": {"sensor_data": 0}}
        states, has_readings = whisperer_handler.process_sensor_data(response, "SENSOR123")

        # Int is falsy (0), so no readings
        assert has_readings is False
        mock_logger.info.assert_called()

    def test_process_sensor_data_missing_status_key(self, whisperer_handler):
        """Response missing status key is handled gracefully."""
        response = {"data": {"sensor_data": []}, "meta": {}}
        states, has_readings = whisperer_handler.process_sensor_data(response, "SENSOR123")

        # Should still process (status key not required for processing)
        assert has_readings is False


# =============================================================================
# TestHandlerThreadSafety
# =============================================================================

@pytest.mark.handlers
class TestHandlerThreadSafety:
    """Tests for handler exception safety when called from concurrent threads."""

    def test_sprinkler_handler_exception_does_not_propagate_on_keyerror(self, sprinkler_handler, mock_logger):
        """KeyError in process_device_info is caught and returns error state."""
        # Malformed response that would cause KeyError
        response = {"status": "OK"}  # Missing 'data' key

        # Should not raise, should return error states
        states, is_online, device_data = sprinkler_handler.process_device_info(response, "ABC123")

        assert is_online is False
        mock_logger.error.assert_called()
        # Should return error state, not crash
        assert len(states) > 0
        status_state = next((s for s in states if s["key"] == "status"), None)
        assert status_state is not None
        assert status_state["value"] == "ERROR"

    def test_whisperer_handler_exception_does_not_propagate(self, whisperer_handler, mock_logger):
        """Exceptions in process_sensor_data are caught and return error state."""
        # Malformed response that would cause exception
        response = {"status": "OK"}  # Missing 'data' key

        # Should not raise, should return empty with has_readings=False
        states, has_readings = whisperer_handler.process_sensor_data(response, "SENSOR123")

        assert has_readings is False
        # Should log error but not crash


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


# =============================================================================
# V2 Device Handler Tests
# =============================================================================

@pytest.mark.handlers
class TestSprinklerHandlerV2DeviceInfo:
    """Tests for V2 device info processing."""

    def test_watering_status_is_online(self, mock_logger, sample_v2_device_info):
        """V2 WATERING status should be treated as online."""
        handler = SprinklerHandler(logger=mock_logger)
        states, is_online, device_data = handler.process_device_info(
            sample_v2_device_info, "ABC123", api_version="2"
        )
        assert is_online is True

    def test_sleeping_status_is_offline(self, mock_logger):
        """V2 SLEEPING status should be treated as offline."""
        handler = SprinklerHandler(logger=mock_logger)
        response = {
            "status": "OK",
            "data": {
                "device": {
                    "serial": "ABC123", "status": "SLEEPING", "version": "2.0",
                    "name": "Test", "zones": []
                }
            },
            "meta": {"token_remaining": 1900, "token_reset": "2026-04-08T00:00:00"}
        }
        _, is_online, _ = handler.process_device_info(response, "ABC123", api_version="2")
        assert is_online is False

    def test_v2_version_stored_as_string(self, mock_logger, sample_v2_device_info):
        """V2 version field ('2.0') should be stored as string."""
        handler = SprinklerHandler(logger=mock_logger)
        states, _, _ = handler.process_device_info(
            sample_v2_device_info, "ABC123", api_version="2"
        )
        api_ver_state = next(s for s in states if s["key"] == "api_version")
        assert api_ver_state["value"] == "2.0"
        assert isinstance(api_ver_state["value"], str)

    def test_v2_sw_version_included(self, mock_logger, sample_v2_device_info):
        """V2 response with sw_version should include it in states."""
        handler = SprinklerHandler(logger=mock_logger)
        states, _, _ = handler.process_device_info(
            sample_v2_device_info, "ABC123", api_version="2"
        )
        sw_ver_state = next((s for s in states if s["key"] == "sw_version"), None)
        assert sw_ver_state is not None
        assert sw_ver_state["value"] == "3.1.0"

    def test_v1_no_sw_version(self, mock_logger, sample_v2_device_info):
        """V1 mode should not include sw_version even if present in response."""
        handler = SprinklerHandler(logger=mock_logger)
        states, _, _ = handler.process_device_info(
            sample_v2_device_info, "ABC123", api_version="1"
        )
        sw_ver_state = next((s for s in states if s["key"] == "sw_version"), None)
        assert sw_ver_state is None

    def test_v2_online_status_is_online(self, mock_logger):
        """V2 ONLINE status should be treated as online."""
        handler = SprinklerHandler(logger=mock_logger)
        response = {
            "status": "OK",
            "data": {
                "device": {
                    "serial": "ABC123", "status": "ONLINE", "version": "2.0",
                    "name": "Test", "zones": []
                }
            },
            "meta": {"token_remaining": 1900}
        }
        _, is_online, _ = handler.process_device_info(response, "ABC123", api_version="2")
        assert is_online is True


@pytest.mark.handlers
class TestSprinklerHandlerV2Schedules:
    """Tests for V2 schedule processing."""

    def test_v2_schedule_iso_timestamp_parsing(self, mock_logger, sample_v2_schedules):
        """V2 schedules with ISO 8601 timestamps should parse correctly."""
        handler = SprinklerHandler(logger=mock_logger)
        states, active_name = handler.process_schedules(
            sample_v2_schedules, api_version="2"
        )
        assert active_name is not None
        # Should find the EXECUTING schedule
        active_zone = next(s for s in states if s["key"] == "activeZone")
        assert active_zone["value"] == 1

    def test_v2_next_schedule_uses_local_time(self, mock_logger, sample_v2_schedules):
        """V2 next schedule should use local_start_time when available."""
        handler = SprinklerHandler(logger=mock_logger)
        states, _ = handler.process_schedules(sample_v2_schedules, api_version="2")
        next_time = next(s for s in states if s["key"] == "nextScheduleTime")
        assert "06:15:00" in next_time["value"]

    def test_v2_duration_calculated_from_start_end(self, mock_logger, sample_v2_schedules):
        """V2 duration should be calculated from start_time and end_time."""
        handler = SprinklerHandler(logger=mock_logger)
        states, _ = handler.process_schedules(sample_v2_schedules, api_version="2")
        duration = next(s for s in states if s["key"] == "nextScheduleDuration")
        assert duration["value"] == 15  # 06:15 to 06:30 = 15 minutes

    def test_v2_source_values(self, mock_logger, sample_v2_schedules):
        """V2 schedule source (SMART/FIX/MANUAL) should be title-cased."""
        handler = SprinklerHandler(logger=mock_logger)
        states, active_name = handler.process_schedules(
            sample_v2_schedules, api_version="2"
        )
        # Active schedule source is SMART
        assert active_name == "Smart"
        # Next schedule source is FIX
        next_source = next(s for s in states if s["key"] == "nextScheduleSource")
        assert next_source["value"] == "Fix"

    def test_v2_schedule_sort_key_iso_parsing(self, mock_logger):
        """V2 timestamp sort key should parse ISO 8601 correctly."""
        handler = SprinklerHandler(logger=mock_logger)
        result = handler._parse_schedule_sort_key("2026-04-07T06:00:00", api_version="2")
        assert result > 0
        assert isinstance(result, float)

    def test_v1_schedule_sort_key_ms_parsing(self, mock_logger):
        """V1 timestamp sort key should parse millisecond timestamp."""
        handler = SprinklerHandler(logger=mock_logger)
        result = handler._parse_schedule_sort_key("1740664800000", api_version="1")
        assert result == 1740664800000.0

    def test_v2_calc_duration_from_start_end(self, mock_logger):
        """_calc_v2_duration should calculate minutes from ISO times."""
        handler = SprinklerHandler(logger=mock_logger)
        schedule = {
            "start_time": "2026-04-07T06:00:00",
            "end_time": "2026-04-07T06:30:00"
        }
        assert handler._calc_v2_duration(schedule) == 30

    def test_v2_calc_duration_missing_end(self, mock_logger):
        """_calc_v2_duration returns 0 when end_time is missing."""
        handler = SprinklerHandler(logger=mock_logger)
        assert handler._calc_v2_duration({"start_time": "2026-04-07T06:00:00"}) == 0

    def test_v2_calc_duration_invalid_format(self, mock_logger):
        """_calc_v2_duration returns 0 for invalid timestamps."""
        handler = SprinklerHandler(logger=mock_logger)
        assert handler._calc_v2_duration({"start_time": "bad", "end_time": "data"}) == 0


@pytest.mark.handlers
class TestWhispererHandlerV2:
    """Tests for V2 Whisperer sensor processing."""

    def test_v2_sensor_data_processed(self, mock_logger, sample_v2_sensor_data):
        """V2 sensor data should be processed correctly."""
        handler = WhispererHandler(logger=mock_logger)
        states, has_readings = handler.process_sensor_data(
            sample_v2_sensor_data, "SENSOR123", api_version="2"
        )
        assert has_readings is True
        moisture = next(s for s in states if s["key"] == "soilMoisture")
        assert moisture["value"] == 45

    def test_v2_sensor_temperature(self, mock_logger, sample_v2_sensor_data):
        """V2 sensor should report celsius temperature."""
        handler = WhispererHandler(logger=mock_logger)
        states, _ = handler.process_sensor_data(
            sample_v2_sensor_data, "SENSOR123", api_version="2"
        )
        temp = next(s for s in states if s["key"] == "temperature")
        assert temp["value"] == 22.5

    def test_v2_sensor_v2_meta_fields(self, mock_logger, sample_v2_sensor_data):
        """V2 sensor should include v2 meta fields in states."""
        handler = WhispererHandler(logger=mock_logger)
        states, _ = handler.process_sensor_data(
            sample_v2_sensor_data, "SENSOR123", api_version="2"
        )
        token = next(s for s in states if s["key"] == "token_remaining")
        assert token["value"] == 1848


# =============================================================================
# V2 Event Processing Tests
# =============================================================================

@pytest.mark.handlers
class TestSprinklerHandlerV2Events:
    """Tests for V2 event processing."""

    def test_process_events_happy_path(self, mock_logger):
        """New events should be returned with updated highest ID."""
        handler = SprinklerHandler(logger=mock_logger)
        response = {
            "status": "OK",
            "data": {
                "events": [
                    {"id": 100, "event": 2, "time": "2026-04-07T08:00:00", "message": "online"},
                    {"id": 101, "event": 3, "time": "2026-04-07T08:15:00", "message": "schedule started"},
                ]
            }
        }
        new_events, highest_id = handler.process_events(response, last_event_id=0)
        assert len(new_events) == 2
        assert highest_id == 101

    def test_process_events_filters_old(self, mock_logger):
        """Events with ID <= last_event_id should be filtered out."""
        handler = SprinklerHandler(logger=mock_logger)
        response = {
            "status": "OK",
            "data": {
                "events": [
                    {"id": 100, "event": 2, "time": "2026-04-07T08:00:00", "message": "online"},
                    {"id": 101, "event": 3, "time": "2026-04-07T08:15:00", "message": "started"},
                    {"id": 102, "event": 4, "time": "2026-04-07T08:30:00", "message": "ended"},
                ]
            }
        }
        new_events, highest_id = handler.process_events(response, last_event_id=100)
        assert len(new_events) == 2
        assert new_events[0]["id"] == 101
        assert highest_id == 102

    def test_process_events_empty(self, mock_logger):
        """Empty events list should return empty with same last_event_id."""
        handler = SprinklerHandler(logger=mock_logger)
        response = {"status": "OK", "data": {"events": []}}
        new_events, highest_id = handler.process_events(response, last_event_id=50)
        assert len(new_events) == 0
        assert highest_id == 50

    def test_process_events_no_data(self, mock_logger):
        """Missing data key should return empty safely."""
        handler = SprinklerHandler(logger=mock_logger)
        response = {"status": "OK"}
        new_events, highest_id = handler.process_events(response, last_event_id=0)
        assert len(new_events) == 0
        assert highest_id == 0

    def test_process_events_malformed(self, mock_logger):
        """Malformed response should return empty and log error."""
        handler = SprinklerHandler(logger=mock_logger)
        response = {"status": "OK", "data": {"events": "not a list"}}
        new_events, highest_id = handler.process_events(response, last_event_id=0)
        assert len(new_events) == 0

    def test_process_events_first_run(self, mock_logger):
        """First run (last_event_id=0) should return all events."""
        handler = SprinklerHandler(logger=mock_logger)
        response = {
            "status": "OK",
            "data": {
                "events": [
                    {"id": 500, "event": 1, "time": "2026-04-07T10:00:00", "message": "offline"},
                ]
            }
        }
        new_events, highest_id = handler.process_events(response, last_event_id=0)
        assert len(new_events) == 1
        assert highest_id == 500

    def test_process_events_no_new(self, mock_logger):
        """When all events are old, should return empty list."""
        handler = SprinklerHandler(logger=mock_logger)
        response = {
            "status": "OK",
            "data": {
                "events": [
                    {"id": 50, "event": 2, "time": "2026-04-07T08:00:00", "message": "online"},
                ]
            }
        }
        new_events, highest_id = handler.process_events(response, last_event_id=50)
        assert len(new_events) == 0
        assert highest_id == 50
