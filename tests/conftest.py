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
