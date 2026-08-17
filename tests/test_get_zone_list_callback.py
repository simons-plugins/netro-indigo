"""Tests for Plugin.getZoneList ConfigUI callback (startZoneWithDelay action).

Found during the external-sensor sentinel sweep: both of getZoneList's
placeholder options used an empty-string value, which Indigo rejects
("UI dynamic list function returned illegal ID string"). Sentinels now use
"-1", matching the getWhispererDevices/getExternalSensorDevices/
getExternalSensorStates fix.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_indigo(mock_indigo_base):
    """Extend the shared mock_indigo_base with a `_devices_by_id` lookup."""
    indigo = mock_indigo_base
    indigo._devices_by_id = {}

    def _getitem(dev_id):
        if dev_id not in indigo._devices_by_id:
            raise KeyError(dev_id)
        return indigo._devices_by_id[dev_id]

    indigo.devices.__getitem__.side_effect = _getitem
    return indigo


@pytest.fixture
def plugin_instance(mock_indigo):
    from plugin import Plugin  # noqa: WPS433
    plugin = Plugin.__new__(Plugin)  # skip __init__
    plugin.logger = MagicMock()
    return plugin


def test_no_zones_configured_returns_sentinel(mock_indigo, plugin_instance):
    mock_indigo._devices_by_id[100] = SimpleNamespace(pluginProps={})
    result = plugin_instance.getZoneList(targetId=100)
    assert result == [("-1", "No zones configured - update device first")]


def test_error_loading_zones_returns_sentinel(mock_indigo, plugin_instance):
    result = plugin_instance.getZoneList(targetId=999)  # not registered -> KeyError
    assert result == [("-1", "Error loading zones")]


def test_disabled_zones_excluded_leaves_only_sentinel(mock_indigo, plugin_instance):
    import json
    zones_json = json.dumps([{"id": "1", "name": "Front Lawn", "enabled": False}])
    mock_indigo._devices_by_id[100] = SimpleNamespace(pluginProps={"zones": zones_json})
    result = plugin_instance.getZoneList(targetId=100)
    assert result == [("-1", "No zones configured - update device first")]


def test_enabled_zone_returned_alongside_no_sentinel(mock_indigo, plugin_instance):
    import json
    zones_json = json.dumps([{"id": "1", "name": "Front Lawn", "enabled": True}])
    mock_indigo._devices_by_id[100] = SimpleNamespace(pluginProps={"zones": zones_json})
    result = plugin_instance.getZoneList(targetId=100)
    assert result == [("1", "Front Lawn")]
    assert all(value != "" for value, _label in result)
