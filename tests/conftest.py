"""Pytest configuration and shared fixtures for Netro plugin tests."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest


# Fixture directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def mock_indigo():
    """Create a mock Indigo module."""
    mock = MagicMock()

    # Mock Indigo.Dict class
    mock.Dict = dict

    # Mock device types
    mock.kSprinklerAction = MagicMock()
    mock.kSprinklerAction.ZoneOn = 1
    mock.kSprinklerAction.ZoneOff = 2
    mock.kSprinklerAction.AllZonesOff = 3
    mock.kSprinklerAction.PreviousZone = 4
    mock.kSprinklerAction.NextZone = 5
    mock.kSprinklerAction.PauseZone = 6
    mock.kSprinklerAction.ResumeZone = 7

    # Mock logger
    mock_logger = MagicMock()
    mock.PluginBase = type('PluginBase', (), {
        'logger': mock_logger,
        '__init__': lambda self, *args, **kwargs: None
    })

    return mock


@pytest.fixture
def mock_plugin_prefs():
    """Create mock plugin preferences."""
    return {
        "accessToken": "test-serial-123",
        "pollingInterval": 5,
        "apiTimeout": 5,
        "maxZoneRunTime": 3600,
        "showDebugInfo": False
    }


@pytest.fixture
def mock_device():
    """Create a mock Indigo device."""
    device = MagicMock()
    device.id = 123456
    device.name = "Test Controller"
    device.address = "test-serial-123"
    device.deviceTypeId = "sprinkler"
    device.states = {
        "id": "device-uuid-12345",
        "serial": "test-serial-123",
        "status": "ONLINE",
        "activeZone": 0,
        "activeSchedule": "No active schedule"
    }
    device.pluginProps = {
        "address": "test-serial-123",
        "NumZones": 4,
        "ZoneNames": "Front Lawn, Back Lawn, Garden Beds, Side Yard",
        "MaxZoneDurations": "3600, 3600, 3600, 0",
        "zones": json.dumps([
            {"id": "zone-uuid-1", "name": "Front Lawn", "enabled": True},
            {"id": "zone-uuid-2", "name": "Back Lawn", "enabled": True},
            {"id": "zone-uuid-3", "name": "Garden Beds", "enabled": True}
        ])
    }

    # Mock methods
    device.updateStatesOnServer = MagicMock()
    device.replacePluginPropsOnServer = MagicMock()

    return device


@pytest.fixture
def mock_whisperer_device():
    """Create a mock Whisperer sensor device."""
    device = MagicMock()
    device.id = 123457
    device.name = "Test Sensor"
    device.address = "whisperer-serial-456"
    device.deviceTypeId = "Whisperer"
    device.states = {
        "id": "sensor-uuid-1",
        "serial": "whisperer-serial-456",
        "humidity": 65,
        "temperature": 72,
        "soilMoisture": 65,
        "sunlight": 50000
    }
    device.pluginProps = {
        "address": "whisperer-serial-456"
    }

    device.updateStatesOnServer = MagicMock()

    return device


@pytest.fixture
def load_fixture():
    """Factory fixture to load JSON fixtures."""
    def _load(filename):
        fixture_path = FIXTURES_DIR / filename
        if not fixture_path.exists():
            raise FileNotFoundError(f"Fixture not found: {fixture_path}")

        with open(fixture_path, 'r') as f:
            return json.load(f)

    return _load


@pytest.fixture
def mock_requests_get(mocker, load_fixture):
    """Mock requests.get with fixture responses."""
    def _mock_get(url, fixture_name="info_response.json", status_code=200):
        mock_response = Mock()
        mock_response.status_code = status_code
        mock_response.json.return_value = load_fixture(fixture_name)

        if status_code >= 400:
            mock_response.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
        else:
            mock_response.raise_for_status.return_value = None

        return mocker.patch('requests.get', return_value=mock_response)

    return _mock_get


@pytest.fixture
def mock_requests_post(mocker, load_fixture):
    """Mock requests.post with fixture responses."""
    def _mock_post(url, fixture_name=None, status_code=200):
        mock_response = Mock()
        mock_response.status_code = status_code

        if fixture_name:
            mock_response.json.return_value = load_fixture(fixture_name)
        else:
            # Default success response
            mock_response.json.return_value = {
                "status": "OK",
                "meta": {
                    "time": 1609459200000,
                    "token_remaining": 1850
                }
            }

        if status_code >= 400:
            mock_response.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
        else:
            mock_response.raise_for_status.return_value = None

        return mocker.patch('requests.post', return_value=mock_response)

    return _mock_post


@pytest.fixture
def plugin_action():
    """Create a mock plugin action."""
    action = MagicMock()
    action.props = {}
    return action


@pytest.fixture
def mock_plugin(mock_indigo, mock_plugin_prefs, mocker):
    """Create a mock plugin instance for testing.

    Note: This requires importing the actual plugin module,
    which may need sys.path adjustment in real tests.
    """
    # This is a placeholder - real implementation would import the plugin
    # and create an instance with mocked dependencies
    mock = MagicMock()
    mock.pluginPrefs = mock_plugin_prefs
    mock.serial_number = mock_plugin_prefs["accessToken"]
    mock.timeout = mock_plugin_prefs["apiTimeout"]
    mock.maxZoneRunTime = mock_plugin_prefs["maxZoneRunTime"]
    mock.debug = mock_plugin_prefs["showDebugInfo"]
    mock.throttle_next_call = None
    mock.logger = MagicMock()

    return mock
