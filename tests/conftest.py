"""Shared pytest fixtures for all test modules.

This module provides common test fixtures that are automatically
discovered and made available to all test files via pytest's conftest.py
mechanism.
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


# =============================================================================
# Shared Fixtures
# =============================================================================

@pytest.fixture
def mock_logger():
    """Create a mock logger for testing.

    Provides a Mock object with all standard logging methods:
    debug, info, warning, error, exception.

    This fixture is used across all test modules to avoid duplicating
    logger setup code.
    """
    logger = Mock()
    logger.debug = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    logger.exception = Mock()
    return logger


@pytest.fixture
def sample_api_response():
    """Create a base successful API response structure.

    Returns a dict with typical Netro API response structure:
    - status: "OK"
    - data: {} (empty dict, tests can populate)
    - meta: token_remaining and token_reset fields

    Tests can modify the returned dict as needed for specific scenarios.
    """
    return {
        "status": "OK",
        "data": {},
        "meta": {
            "token_remaining": 1900,
            "token_reset": "2026-02-02T00:00:00"
        }
    }


@pytest.fixture
def mock_prefs():
    """Create mock prefs getter/setter for testing.

    Returns a 3-tuple:
    - prefs_getter: callable that returns prefs dict
    - prefs_setter: callable(key, value) that stores in prefs dict
    - prefs_data: the underlying dict (for direct inspection/modification)

    This fixture is primarily used by api_client tests that need to
    verify preference persistence behavior.
    """
    prefs_data = {}

    def prefs_getter():
        return prefs_data

    def prefs_setter(key, value):
        prefs_data[key] = value

    return prefs_getter, prefs_setter, prefs_data


# =============================================================================
# V2 API Fixtures
# =============================================================================

@pytest.fixture
def sample_api_v2_response():
    """Create a base successful API v2 response structure.

    V2 meta includes additional fields: tid, version, token_limit.
    Timestamps are ISO 8601 strings.
    """
    return {
        "status": "OK",
        "data": {},
        "meta": {
            "time": "2026-04-07T14:30:00",
            "tid": "txn-12345",
            "version": "2.0",
            "token_limit": 2000,
            "token_remaining": 1900,
            "token_reset": "2026-04-08T00:00:00",
            "last_active": "2026-04-07T14:25:00"
        }
    }


@pytest.fixture
def sample_v2_device_info():
    """Sample v2 device info response with expanded fields."""
    return {
        "status": "OK",
        "data": {
            "device": {
                "serial": "ABC123456789",
                "status": "WATERING",
                "version": "2.0",
                "sw_version": "3.1.0",
                "name": "Front Yard Sprinkler",
                "macAddress": "00:11:22:33:44:55",
                "model": "Netro Sprite",
                "paused": False,
                "scheduleModeType": "SMART",
                "last_active": "2026-04-07T12:00:00",
                "battery_level": 0.85,
                "zone_num": 3,
                "zones": [
                    {"ith": 1, "name": "Lawn", "enabled": True, "smart": "SMART"},
                    {"ith": 2, "name": "Garden", "enabled": True, "smart": "ASSISTANT"},
                    {"ith": 3, "name": "Disabled Zone", "enabled": False, "smart": "TIMER"}
                ]
            }
        },
        "meta": {
            "time": "2026-04-07T14:30:00",
            "tid": "txn-99999",
            "version": "2.0",
            "token_limit": 2000,
            "token_remaining": 1850,
            "token_reset": "2026-04-08T00:00:00",
            "last_active": "2026-04-07T14:25:00"
        }
    }


@pytest.fixture
def sample_v2_schedules():
    """Sample v2 schedules response with ISO 8601 timestamps."""
    return {
        "status": "OK",
        "data": {
            "schedules": [
                {
                    "id": 100,
                    "zone": 1,
                    "start_time": "2026-04-07T06:00:00",
                    "end_time": "2026-04-07T06:15:00",
                    "local_date": "2026-04-07",
                    "local_start_time": "06:00:00",
                    "local_end_time": "06:15:00",
                    "source": "SMART",
                    "status": "EXECUTING"
                },
                {
                    "id": 101,
                    "zone": 2,
                    "start_time": "2026-04-07T06:15:00",
                    "end_time": "2026-04-07T06:30:00",
                    "local_date": "2026-04-07",
                    "local_start_time": "06:15:00",
                    "local_end_time": "06:30:00",
                    "source": "FIX",
                    "status": "VALID"
                }
            ]
        },
        "meta": {
            "time": "2026-04-07T14:30:00",
            "tid": "txn-sched",
            "version": "2.0",
            "token_limit": 2000,
            "token_remaining": 1849,
            "token_reset": "2026-04-08T00:00:00"
        }
    }


@pytest.fixture
def sample_v2_sensor_data():
    """Sample v2 sensor data response with ISO 8601 timestamps."""
    return {
        "status": "OK",
        "data": {
            "sensor_data": [
                {
                    "id": 5001,
                    "time": "2026-04-07T10:00:00",
                    "local_date": "2026-04-07",
                    "local_time": "10:00:00",
                    "moisture": 45,
                    "sunlight": 1.2,
                    "celsius": 22.5,
                    "fahrenheit": 72.5,
                    "battery_level": 85
                }
            ]
        },
        "meta": {
            "time": "2026-04-07T14:30:00",
            "tid": "txn-sensor",
            "version": "2.0",
            "token_limit": 2000,
            "token_remaining": 1848,
            "token_reset": "2026-04-08T00:00:00",
            "last_active": "2026-04-07T10:00:00"
        }
    }
