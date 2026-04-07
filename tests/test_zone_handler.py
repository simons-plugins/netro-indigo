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
