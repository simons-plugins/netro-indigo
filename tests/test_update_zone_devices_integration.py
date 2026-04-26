"""Integration tests for Plugin._update_zone_devices moisture resolution.

These tests verify the call-site rewiring:
  - moistureForecast gets the /moistures.json value.
  - moisture gets the resolved value (Whisperer if fresh + paired, else forecast).
  - Source transitions are logged.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


FROZEN_NOW = datetime(2026, 4, 23, 12, 0, 0, tzinfo=timezone.utc)


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
    props = {
        "zoneNumber": str(zone_num),
        "linkedWhispererDeviceId": linked_id,
    }

    def _update_states(states):
        replaced_states.extend(states)

    def _replace_props(new_props):
        replaced_props.append(dict(new_props))
        # Simulate Indigo's real behavior: pluginProps reflects the server write.
        props.clear()
        props.update(new_props)

    dev = SimpleNamespace(
        id=1000 + zone_num,
        name=name,
        pluginProps=props,
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


def _whisperer(soil=24, hours_old=2, reading_id=1001):
    return SimpleNamespace(
        enabled=True,
        states={
            "soilMoisture": soil,
            "readingTime": (FROZEN_NOW - timedelta(hours=hours_old)).strftime(
                "%Y-%m-%dT%H:%M:%S"
            ),
            "readingID": reading_id,
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


def test_source_transition_logged_during_update(plugin_instance, mock_indigo):
    """Verify _update_zone_devices actually wires up the transition logger."""
    zone = _zone_dev(zone_num=1, linked_id="999")
    zone.pluginProps["lastMoistureSource"] = "whisperer"  # prior state
    mock_indigo._devices_by_id[999] = _whisperer(soil=24, hours_old=20)  # now stale
    plugin_instance._get_zone_devices = lambda parent_id: {1: zone}
    parent = SimpleNamespace(id=42, name="Sprite")

    with patch("utils._now_utc", return_value=FROZEN_NOW):
        plugin_instance._update_zone_devices(
            parent, _device_data(),
            schedule_response=None,
            moisture_response=_moistures_response(1, forecast_val=89),
            api_version="1",
        )

    assert plugin_instance.logger.warning.call_count >= 1
    # The transition should have been recorded.
    assert zone.pluginProps.get("lastMoistureSource") == "forecast-stale"
    # Pin the user-facing wording so a refactor of the warning message would fail loudly.
    warn_msgs = [c.args[0] for c in plugin_instance.logger.warning.call_args_list]
    assert any("stale" in m.lower() for m in warn_msgs), warn_msgs
    assert any("Netro forecast" in m for m in warn_msgs), warn_msgs


def test_empty_moistures_response_skips_forecast_write(plugin_instance, mock_indigo):
    """Empty data.moistures → moistureForecast not written (no fake 0%)."""
    zone = _zone_dev(zone_num=1, linked_id="")
    plugin_instance._get_zone_devices = lambda parent_id: {1: zone}
    parent = SimpleNamespace(id=42, name="Sprite")

    empty_response = {"status": "OK", "data": {"moistures": []}}

    plugin_instance._update_zone_devices(
        parent, _device_data(),
        schedule_response=None,
        moisture_response=empty_response,
        api_version="1",
    )

    keys = {s["key"]: s.get("value") for s in zone._replaced_states}
    assert "moistureForecast" not in keys
    assert "moisture" not in keys


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


def test_malformed_moisture_response_swallows_and_continues(plugin_instance, mock_indigo):
    """A malformed moisture_response triggers the inner except; other state writes survive."""
    zone = _zone_dev(zone_num=1, linked_id="")
    plugin_instance._get_zone_devices = lambda pid: {1: zone}
    parent = SimpleNamespace(id=42, name="Sprite")

    # data.moistures wrong shape → handler can return [] cleanly OR (worst case)
    # caller's loop hits AttributeError on entry.get(). Either way the inner
    # except in _update_zone_devices must catch it.
    bogus = {"status": "OK", "data": {"moistures": "not-a-list"}}

    plugin_instance._update_zone_devices(
        parent, _device_data(),
        schedule_response=None,
        moisture_response=bogus,
        api_version="1",
    )

    # Test reaches this line means no exception escaped to the outer per-zone try/except.
    keys = {s["key"] for s in zone._replaced_states}
    # moistureForecast not written (bogus moistures path):
    assert "moistureForecast" not in keys


def test_resolver_exception_falls_back_to_forecast(plugin_instance, mock_indigo, monkeypatch):
    """If _resolve_zone_moisture raises, the zone falls back to forecast and other states still write."""
    zone = _zone_dev(zone_num=1, linked_id="999")
    plugin_instance._get_zone_devices = lambda pid: {1: zone}
    parent = SimpleNamespace(id=42, name="Sprite")

    def _bad_resolver(*args, **kwargs):
        raise AttributeError("simulated IOM corruption")

    monkeypatch.setattr(plugin_instance, "_resolve_zone_moisture", _bad_resolver)

    plugin_instance._update_zone_devices(
        parent, _device_data(),
        schedule_response=None,
        moisture_response=_moistures_response(1, forecast_val=55),
        api_version="1",
    )

    keys = {s["key"]: s["value"] for s in zone._replaced_states}
    # Forecast still wrote (the resolver failed AFTER moistureForecast was added):
    assert keys.get("moistureForecast") == 55
    # Moisture wrote with forecast fallback (resolver returned (forecast_val, "forecast")):
    assert keys.get("moisture") == 55
    # Warning was emitted with the right context:
    msgs = [c.args[0] for c in plugin_instance.logger.warning.call_args_list]
    assert any("could not resolve moisture source" in m for m in msgs)
