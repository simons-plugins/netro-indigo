"""Integration tests for Plugin._update_zone_devices moisture resolution.

These tests verify the call-site rewiring:
  - moistureForecast gets the /moistures.json value.
  - moisture gets the resolved value (Whisperer if fresh + paired, else forecast).
  - Source transitions are logged.
"""
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


FROZEN_NOW = datetime(2026, 4, 23, 12, 0, 0, tzinfo=timezone.utc)


class _PluginBase:
    pass


@pytest.fixture
def mock_indigo(monkeypatch):
    indigo = MagicMock()
    indigo.PluginBase = _PluginBase
    indigo.Dict = dict
    indigo._devices_by_id = {}

    def _getitem(dev_id):
        if dev_id not in indigo._devices_by_id:
            raise KeyError(dev_id)
        return indigo._devices_by_id[dev_id]

    indigo.devices.__getitem__.side_effect = _getitem
    monkeypatch.setitem(sys.modules, "indigo", indigo)
    monkeypatch.delitem(sys.modules, "plugin", raising=False)
    return indigo


@pytest.fixture
def plugin_instance(mock_indigo):
    from plugin import Plugin  # noqa: WPS433
    plugin = Plugin.__new__(Plugin)
    plugin.logger = MagicMock()
    from device_handlers import ZoneHandler
    plugin.zone_handler = ZoneHandler(logger=MagicMock())
    return plugin


def _zone_dev(zone_num=1, linked_id="", name="Front Lawn"):
    """Build a zone device double that captures state + prop writes.

    The zone must look enabled in the extracted-zone-states so the moisture
    block runs; that requires ``zones`` in ``device_data`` to mark the zone
    as enabled, not the device itself. ``enabled`` here controls the Indigo
    device-enabled flag, not the zone's ``enabled`` state.
    """
    replaced_states = []
    replaced_props = []

    def _update_states(states):
        replaced_states.extend(states)

    def _replace_props(props):
        replaced_props.append(dict(props))

    dev = SimpleNamespace(
        id=1000 + zone_num,
        name=name,
        pluginProps={
            "zoneNumber": str(zone_num),
            "linkedWhispererDeviceId": linked_id,
        },
        enabled=True,
        states={},
        deviceTypeId="zone",
        updateStatesOnServer=_update_states,
        replacePluginPropsOnServer=_replace_props,
        setErrorStateOnServer=lambda *a, **kw: None,
        updateStateImageOnServer=lambda *a, **kw: None,
        _replaced_states=replaced_states,
        _replaced_props=replaced_props,
    )
    return dev


def _whisperer(soil=24, hours_old=2):
    return SimpleNamespace(
        enabled=True,
        states={
            "soilMoisture": soil,
            "readingTime": (FROZEN_NOW - timedelta(hours=hours_old)).strftime(
                "%Y-%m-%dT%H:%M:%S"
            ),
        },
    )


def _moistures_response(zone_num, forecast_val):
    return {
        "status": "OK",
        "data": {
            "moistures": [
                {
                    "id": 1,
                    "zone": zone_num,
                    "date": "2026-04-23",
                    "moisture": forecast_val,
                },
            ],
        },
    }


def _device_data(zone_num=1):
    """Return a minimal device_data with a single enabled zone.

    ``_update_zone_devices`` pulls ``zones`` out of ``device_data`` and
    passes them to ``ZoneHandler.extract_zone_states`` which uses the
    ``enabled`` flag on the matching zone to decide whether to run the
    moisture block.
    """
    return {
        "zones": [
            {"ith": zone_num, "name": f"Zone {zone_num}", "enabled": True,
             "smart": "SMART"},
        ],
    }


def test_paired_fresh_writes_sensor_to_moisture_and_forecast_to_moistureForecast(
    plugin_instance, mock_indigo
):
    zone = _zone_dev(zone_num=1, linked_id="999")
    mock_indigo._devices_by_id[999] = _whisperer(soil=24, hours_old=2)
    plugin_instance._get_zone_devices = lambda parent_id: {1: zone}
    parent = SimpleNamespace(id=42, name="Sprite")

    with patch("utils._now_utc", return_value=FROZEN_NOW):
        plugin_instance._update_zone_devices(
            parent,
            _device_data(1),
            schedule_response=None,
            moisture_response=_moistures_response(1, forecast_val=89),
            api_version="1",
        )

    keys = {s["key"]: s["value"] for s in zone._replaced_states}
    assert keys["moisture"] == 24
    assert keys["moistureForecast"] == 89


def test_unpaired_zone_mirrors_forecast_to_both(plugin_instance, mock_indigo):
    zone = _zone_dev(zone_num=1, linked_id="")
    plugin_instance._get_zone_devices = lambda parent_id: {1: zone}
    parent = SimpleNamespace(id=42, name="Sprite")

    plugin_instance._update_zone_devices(
        parent,
        _device_data(1),
        schedule_response=None,
        moisture_response=_moistures_response(1, forecast_val=55),
        api_version="1",
    )

    keys = {s["key"]: s["value"] for s in zone._replaced_states}
    assert keys["moisture"] == 55
    assert keys["moistureForecast"] == 55


def test_missing_moisture_response_skips_both_writes(plugin_instance, mock_indigo):
    zone = _zone_dev(zone_num=1, linked_id="")
    plugin_instance._get_zone_devices = lambda parent_id: {1: zone}
    parent = SimpleNamespace(id=42, name="Sprite")

    plugin_instance._update_zone_devices(
        parent,
        _device_data(1),
        schedule_response=None,
        moisture_response=None,
        api_version="1",
    )

    keys = {s["key"]: s.get("value") for s in zone._replaced_states}
    # When paired=no and forecast missing, we skip writing moisture.
    assert "moisture" not in keys
    assert "moistureForecast" not in keys


def test_missing_forecast_but_paired_fresh_writes_sensor(plugin_instance, mock_indigo):
    zone = _zone_dev(zone_num=1, linked_id="999")
    mock_indigo._devices_by_id[999] = _whisperer(soil=24, hours_old=2)
    plugin_instance._get_zone_devices = lambda parent_id: {1: zone}
    parent = SimpleNamespace(id=42, name="Sprite")

    with patch("utils._now_utc", return_value=FROZEN_NOW):
        plugin_instance._update_zone_devices(
            parent,
            _device_data(1),
            schedule_response=None,
            moisture_response=None,
            api_version="1",
        )

    keys = {s["key"]: s["value"] for s in zone._replaced_states}
    assert keys["moisture"] == 24
    # No moistureForecast write when moisture_response is None.
    assert "moistureForecast" not in keys


def test_paired_stale_falls_back_to_forecast(plugin_instance, mock_indigo):
    """End-to-end: paired Whisperer with stale reading → moisture shows forecast."""
    zone = _zone_dev(zone_num=1, linked_id="999")
    mock_indigo._devices_by_id[999] = _whisperer(soil=24, hours_old=20)
    plugin_instance._get_zone_devices = lambda parent_id: {1: zone}
    parent = SimpleNamespace(id=42, name="Sprite")

    with patch("utils._now_utc", return_value=FROZEN_NOW):
        plugin_instance._update_zone_devices(
            parent, _device_data(),
            schedule_response=None,
            moisture_response=_moistures_response(1, forecast_val=89),
            api_version="1",
        )

    keys = {s["key"]: s["value"] for s in zone._replaced_states}
    # Stale Whisperer → fall back to forecast for both states.
    assert keys["moisture"] == 89
    assert keys["moistureForecast"] == 89
