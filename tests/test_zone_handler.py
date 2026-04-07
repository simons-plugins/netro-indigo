"""Unit tests for ZoneHandler in device_handlers.py."""
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

SERVER_PLUGIN_DIR = (
    Path(__file__).parent.parent
    / "Netro Sprinklers.indigoPlugin"
    / "Contents"
    / "Server Plugin"
)
sys.path.insert(0, str(SERVER_PLUGIN_DIR))

from device_handlers import ZoneHandler


@pytest.fixture
def mock_logger():
    logger = Mock()
    logger.debug = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    return logger


@pytest.fixture
def zone_handler(mock_logger):
    return ZoneHandler(logger=mock_logger)


@pytest.fixture
def sample_zones():
    return [
        {"ith": 1, "name": "Lawn", "enabled": True, "smart": "SMART"},
        {"ith": 2, "name": "Garden", "enabled": True, "smart": "ASSISTANT"},
        {"ith": 3, "name": "Side Path", "enabled": False, "smart": "TIMER"},
    ]


class TestExtractZoneStates:
    def test_enabled_zone(self, zone_handler, sample_zones):
        states = zone_handler.extract_zone_states(sample_zones, zone_number=1)
        state_dict = {s["key"]: s["value"] for s in states}
        assert state_dict["enabled"] is True
        assert state_dict["smartMode"] == "SMART"

    def test_disabled_zone(self, zone_handler, sample_zones):
        states = zone_handler.extract_zone_states(sample_zones, zone_number=3)
        state_dict = {s["key"]: s["value"] for s in states}
        assert state_dict["enabled"] is False
        assert state_dict["smartMode"] == "TIMER"

    def test_missing_zone_returns_defaults(self, zone_handler, sample_zones):
        states = zone_handler.extract_zone_states(sample_zones, zone_number=99)
        state_dict = {s["key"]: s["value"] for s in states}
        assert state_dict["enabled"] is False
        assert state_dict["smartMode"] == "Unknown"

    def test_empty_zones_list(self, zone_handler):
        states = zone_handler.extract_zone_states([], zone_number=1)
        state_dict = {s["key"]: s["value"] for s in states}
        assert state_dict["enabled"] is False


@pytest.fixture
def sample_schedules_response():
    """Schedules response with multiple zones and statuses."""
    return {
        "data": {
            "schedules": [
                {
                    "id": 100, "zone": 1, "zone_name": "Lawn",
                    "start_time": 1700000000000, "end_time": 1700000900000,
                    "duration": 900, "source": "SMART", "status": "EXECUTING"
                },
                {
                    "id": 99, "zone": 1, "zone_name": "Lawn",
                    "start_time": 1699990000000, "end_time": 1699990600000,
                    "duration": 600, "source": "FIX", "status": "EXECUTED"
                },
                {
                    "id": 101, "zone": 2, "zone_name": "Garden",
                    "start_time": 1700001000000, "end_time": 1700001600000,
                    "duration": 600, "source": "SMART", "status": "VALID"
                },
                {
                    "id": 98, "zone": 2, "zone_name": "Garden",
                    "start_time": 1699980000000, "end_time": 1699980900000,
                    "duration": 900, "source": "MANUAL", "status": "CANCELLED"
                },
            ]
        }
    }


@pytest.fixture
def sample_v2_schedules_response():
    """V2 schedules with ISO 8601 timestamps."""
    return {
        "data": {
            "schedules": [
                {
                    "id": 200, "zone": 1,
                    "start_time": "2026-04-07T06:00:00",
                    "end_time": "2026-04-07T06:15:00",
                    "local_date": "2026-04-07",
                    "local_start_time": "06:00:00",
                    "local_end_time": "06:15:00",
                    "source": "SMART", "status": "EXECUTED"
                },
                {
                    "id": 201, "zone": 1,
                    "start_time": "2026-04-07T18:00:00",
                    "end_time": "2026-04-07T18:20:00",
                    "local_date": "2026-04-07",
                    "local_start_time": "18:00:00",
                    "local_end_time": "18:20:00",
                    "source": "FIX", "status": "VALID"
                },
            ]
        }
    }


class TestProcessZoneSchedules:
    def test_executing_zone(self, zone_handler, sample_schedules_response):
        states = zone_handler.process_zone_schedules(
            sample_schedules_response, zone_number=1
        )
        state_dict = {s["key"]: s["value"] for s in states}
        assert state_dict["isIrrigating"] is True

    def test_not_executing_zone(self, zone_handler, sample_schedules_response):
        states = zone_handler.process_zone_schedules(
            sample_schedules_response, zone_number=2
        )
        state_dict = {s["key"]: s["value"] for s in states}
        assert state_dict["isIrrigating"] is False

    def test_last_watering_executed(self, zone_handler, sample_schedules_response):
        states = zone_handler.process_zone_schedules(
            sample_schedules_response, zone_number=1
        )
        state_dict = {s["key"]: s["value"] for s in states}
        assert state_dict["lastWateringSource"] == "Fix"
        assert state_dict["lastWateringStatus"] == "Executed"

    def test_last_watering_cancelled(self, zone_handler, sample_schedules_response):
        states = zone_handler.process_zone_schedules(
            sample_schedules_response, zone_number=2
        )
        state_dict = {s["key"]: s["value"] for s in states}
        assert state_dict["lastWateringSource"] == "Manual"
        assert state_dict["lastWateringStatus"] == "Cancelled"

    def test_next_watering(self, zone_handler, sample_schedules_response):
        states = zone_handler.process_zone_schedules(
            sample_schedules_response, zone_number=2
        )
        state_dict = {s["key"]: s["value"] for s in states}
        assert state_dict["nextWateringSource"] == "Smart"

    def test_no_schedules_for_zone(self, zone_handler, sample_schedules_response):
        states = zone_handler.process_zone_schedules(
            sample_schedules_response, zone_number=99
        )
        state_dict = {s["key"]: s["value"] for s in states}
        assert state_dict["isIrrigating"] is False
        assert state_dict["lastWateringStart"] == ""
        assert state_dict["nextWateringStart"] == ""

    def test_empty_schedules(self, zone_handler):
        response = {"data": {"schedules": []}}
        states = zone_handler.process_zone_schedules(response, zone_number=1)
        state_dict = {s["key"]: s["value"] for s in states}
        assert state_dict["isIrrigating"] is False

    def test_v2_timestamps(self, zone_handler, sample_v2_schedules_response):
        states = zone_handler.process_zone_schedules(
            sample_v2_schedules_response, zone_number=1, api_version="2"
        )
        state_dict = {s["key"]: s["value"] for s in states}
        assert "2026-04-07" in state_dict["lastWateringStart"]
        assert "2026-04-07" in state_dict["nextWateringStart"]
        assert state_dict["lastWateringSource"] == "Smart"
        assert state_dict["nextWateringSource"] == "Fix"
