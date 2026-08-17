"""Tests for the external soil sensor -> zone moisture push feature.

Covers:
- Plugin._normalize_external_reading
- Plugin._compute_external_average
- Plugin.deviceUpdated (external sensor branch)
- Plugin._push_external_moisture duplicate-push suppression
- Plugin._rebuild_external_sensor_index
- Zone ConfigUI callbacks (getExternalSensorDevices/States, addExternalSensor,
  getConfiguredExternalSensors, removeExternalSensors)
- validators.validate_device_config zone externalSensorsJson validation
"""
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from validators import validate_device_config


# =============================================================================
# Shared fixtures / helpers
# =============================================================================

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


@pytest.fixture
def plugin_with_api(plugin_instance):
    plugin_instance.api_client = MagicMock()
    plugin_instance.api_client.set_moisture.return_value = {"status": "OK"}
    plugin_instance._last_pushed_external_moisture = {}
    return plugin_instance


def _fake_zone(
    dev_id=500, name="Lawn", entries=None, zone_number=1, parent_id=100, enabled=True,
    aggregation=None, max_age_days=None,
):
    props = {
        "zoneNumber": str(zone_number),
        "parentDeviceId": str(parent_id),
    }
    if entries is not None:
        props["externalSensorsJson"] = json.dumps(entries)
    if aggregation is not None:
        props["externalAggregation"] = aggregation
    if max_age_days is not None:
        props["externalMaxAgeDays"] = str(max_age_days)
    dev = SimpleNamespace(
        id=dev_id,
        name=name,
        deviceTypeId="zone",
        enabled=enabled,
        pluginProps=props,
        states={},
    )
    dev.updateStateOnServer = MagicMock()
    return dev


_UNSET = object()


def _fake_sensor(dev_id, name="Sensor", states=None, enabled=True, type_id="thirdParty", last_changed=_UNSET):
    sensor = SimpleNamespace(
        id=dev_id, name=name, deviceTypeId=type_id, enabled=enabled, states=states or {},
    )
    # Only set `lastChanged` when the caller asks for it, so tests that don't
    # care about staleness exercise the "attribute missing" (treat-as-fresh) path.
    if last_changed is not _UNSET:
        sensor.lastChanged = last_changed
    return sensor


# =============================================================================
# _normalize_external_reading
# =============================================================================

class TestNormalizeExternalReading:
    @pytest.mark.parametrize("raw,scale,expected", [
        (47, "percent", 47),
        (47.0, "percent", 47),
        ("47", "percent", 47),
        ("47 %", "percent", 47),
        ("47%", "percent", 47),
        (0.42, "fraction", 42),
        (1.0, "fraction", 100),
        ("abc", "percent", None),
        (-5, "percent", None),
        (150, "percent", None),
        (1.5, "fraction", None),
        (0.0, "fraction", 0),
        ("0.42", "fraction", 42),
        (0, "percent", 0),
        (100, "percent", 100),
        (True, "percent", None),
        (False, "percent", None),
    ])
    def test_normalize(self, plugin_instance, raw, scale, expected):
        assert plugin_instance._normalize_external_reading(raw, scale) == expected

    def test_normalize_none_rejected(self, plugin_instance):
        assert plugin_instance._normalize_external_reading(None, "percent") is None


# =============================================================================
# _compute_external_average
# =============================================================================

class TestComputeExternalAverage:
    def test_two_sensors_averaged(self, plugin_instance, mock_indigo):
        mock_indigo._devices_by_id[1] = _fake_sensor(1, states={"moisture": 40})
        mock_indigo._devices_by_id[2] = _fake_sensor(2, states={"moisture": 60})
        zone = _fake_zone(entries=[
            {"dev_id": 1, "state_id": "moisture", "scale": "percent"},
            {"dev_id": 2, "state_id": "moisture", "scale": "percent"},
        ])
        assert plugin_instance._compute_external_average(zone) == (50, 2, 2)

    def test_missing_device_skipped(self, plugin_instance, mock_indigo):
        mock_indigo._devices_by_id[1] = _fake_sensor(1, states={"moisture": 40})
        zone = _fake_zone(entries=[
            {"dev_id": 1, "state_id": "moisture", "scale": "percent"},
            {"dev_id": 2, "state_id": "moisture", "scale": "percent"},  # not in _devices_by_id
        ])
        assert plugin_instance._compute_external_average(zone) == (40, 1, 2)

    def test_disabled_device_skipped(self, plugin_instance, mock_indigo):
        mock_indigo._devices_by_id[1] = _fake_sensor(1, states={"moisture": 40})
        mock_indigo._devices_by_id[2] = _fake_sensor(2, states={"moisture": 80}, enabled=False)
        zone = _fake_zone(entries=[
            {"dev_id": 1, "state_id": "moisture", "scale": "percent"},
            {"dev_id": 2, "state_id": "moisture", "scale": "percent"},
        ])
        assert plugin_instance._compute_external_average(zone) == (40, 1, 2)

    def test_unreadable_state_skipped(self, plugin_instance, mock_indigo):
        mock_indigo._devices_by_id[1] = _fake_sensor(1, states={"other": 40})
        zone = _fake_zone(entries=[{"dev_id": 1, "state_id": "moisture", "scale": "percent"}])
        assert plugin_instance._compute_external_average(zone) == (None, 0, 1)

    def test_all_unusable_returns_none_with_total(self, plugin_instance, mock_indigo):
        zone = _fake_zone(entries=[
            {"dev_id": 1, "state_id": "moisture", "scale": "percent"},
            {"dev_id": 2, "state_id": "moisture", "scale": "percent"},
        ])
        assert plugin_instance._compute_external_average(zone) == (None, 0, 2)

    def test_single_sensor_works(self, plugin_instance, mock_indigo):
        mock_indigo._devices_by_id[1] = _fake_sensor(1, states={"moisture": 55})
        zone = _fake_zone(entries=[{"dev_id": 1, "state_id": "moisture", "scale": "percent"}])
        assert plugin_instance._compute_external_average(zone) == (55, 1, 1)

    def test_no_entries_configured(self, plugin_instance, mock_indigo):
        zone = _fake_zone(entries=[])
        assert plugin_instance._compute_external_average(zone) == (None, 0, 0)


# =============================================================================
# _compute_external_average — aggregation method
# =============================================================================

class TestComputeExternalAverageAggregation:
    def _three_sensor_zone(self, mock_indigo, aggregation=None):
        mock_indigo._devices_by_id[1] = _fake_sensor(1, states={"moisture": 20})
        mock_indigo._devices_by_id[2] = _fake_sensor(2, states={"moisture": 50})
        mock_indigo._devices_by_id[3] = _fake_sensor(3, states={"moisture": 90})
        return _fake_zone(
            entries=[
                {"dev_id": 1, "state_id": "moisture", "scale": "percent"},
                {"dev_id": 2, "state_id": "moisture", "scale": "percent"},
                {"dev_id": 3, "state_id": "moisture", "scale": "percent"},
            ],
            aggregation=aggregation,
        )

    def test_minimum_aggregation(self, plugin_instance, mock_indigo):
        zone = self._three_sensor_zone(mock_indigo, aggregation="minimum")
        assert plugin_instance._compute_external_average(zone) == (20, 3, 3)

    def test_maximum_aggregation(self, plugin_instance, mock_indigo):
        zone = self._three_sensor_zone(mock_indigo, aggregation="maximum")
        assert plugin_instance._compute_external_average(zone) == (90, 3, 3)

    def test_unknown_aggregation_falls_back_to_average(self, plugin_instance, mock_indigo):
        zone = self._three_sensor_zone(mock_indigo, aggregation="bogus")
        assert plugin_instance._compute_external_average(zone) == (53, 3, 3)  # round(160/3)

    def test_default_aggregation_is_average(self, plugin_instance, mock_indigo):
        """externalAggregation absent from pluginProps -> average, same as before."""
        zone = self._three_sensor_zone(mock_indigo, aggregation=None)
        assert plugin_instance._compute_external_average(zone) == (53, 3, 3)


# =============================================================================
# _compute_external_average — max reading age (staleness)
# =============================================================================

class TestComputeExternalAverageMaxAge:
    def test_stale_sensor_excluded_fresh_sensor_kept(self, plugin_instance, mock_indigo):
        now = datetime.now()
        stale = _fake_sensor(1, states={"moisture": 20}, last_changed=now - timedelta(days=10))
        fresh = _fake_sensor(2, states={"moisture": 60}, last_changed=now - timedelta(hours=1))
        mock_indigo._devices_by_id[1] = stale
        mock_indigo._devices_by_id[2] = fresh
        zone = _fake_zone(
            entries=[
                {"dev_id": 1, "state_id": "moisture", "scale": "percent"},
                {"dev_id": 2, "state_id": "moisture", "scale": "percent"},
            ],
            max_age_days=3,
        )
        assert plugin_instance._compute_external_average(zone) == (60, 1, 2)
        plugin_instance.logger.debug.assert_called()

    def test_empty_max_age_no_exclusion(self, plugin_instance, mock_indigo):
        now = datetime.now()
        stale = _fake_sensor(1, states={"moisture": 20}, last_changed=now - timedelta(days=999))
        mock_indigo._devices_by_id[1] = stale
        zone = _fake_zone(entries=[{"dev_id": 1, "state_id": "moisture", "scale": "percent"}])
        assert plugin_instance._compute_external_average(zone) == (20, 1, 1)

    def test_zero_max_age_means_no_limit(self, plugin_instance, mock_indigo):
        now = datetime.now()
        stale = _fake_sensor(1, states={"moisture": 20}, last_changed=now - timedelta(days=999))
        mock_indigo._devices_by_id[1] = stale
        zone = _fake_zone(
            entries=[{"dev_id": 1, "state_id": "moisture", "scale": "percent"}],
            max_age_days=0,
        )
        assert plugin_instance._compute_external_average(zone) == (20, 1, 1)

    def test_missing_last_changed_treated_fresh(self, plugin_instance, mock_indigo):
        """SimpleNamespace without a `lastChanged` attribute at all -> AttributeError -> fresh."""
        sensor = _fake_sensor(1, states={"moisture": 20})  # no last_changed kwarg
        mock_indigo._devices_by_id[1] = sensor
        zone = _fake_zone(
            entries=[{"dev_id": 1, "state_id": "moisture", "scale": "percent"}],
            max_age_days=1,
        )
        assert plugin_instance._compute_external_average(zone) == (20, 1, 1)

    def test_none_last_changed_treated_fresh(self, plugin_instance, mock_indigo):
        sensor = _fake_sensor(1, states={"moisture": 20}, last_changed=None)
        mock_indigo._devices_by_id[1] = sensor
        zone = _fake_zone(
            entries=[{"dev_id": 1, "state_id": "moisture", "scale": "percent"}],
            max_age_days=1,
        )
        assert plugin_instance._compute_external_average(zone) == (20, 1, 1)

    def test_all_sensors_stale_returns_none_with_total(self, plugin_instance, mock_indigo):
        now = datetime.now()
        mock_indigo._devices_by_id[1] = _fake_sensor(
            1, states={"moisture": 20}, last_changed=now - timedelta(days=10)
        )
        zone = _fake_zone(
            entries=[{"dev_id": 1, "state_id": "moisture", "scale": "percent"}],
            max_age_days=3,
        )
        assert plugin_instance._compute_external_average(zone) == (None, 0, 1)

    def test_all_sensors_stale_triggers_unusable_warning(self, plugin_with_api, mock_indigo):
        now = datetime.now()
        mock_indigo._devices_by_id[1] = _fake_sensor(
            1, states={"moisture": 20}, last_changed=now - timedelta(days=10)
        )
        zone = _fake_zone(
            entries=[{"dev_id": 1, "state_id": "moisture", "scale": "percent"}],
            max_age_days=3,
        )
        plugin_with_api._push_external_moisture(zone)
        plugin_with_api.api_client.set_moisture.assert_not_called()
        plugin_with_api.logger.warning.assert_called_once()


# =============================================================================
# deviceUpdated
# =============================================================================

class TestDeviceUpdated:
    def test_changed_state_pushes_average(self, plugin_with_api, mock_indigo):
        sensor_id, zone_id, parent_id = 1, 500, 100
        parent = SimpleNamespace(pluginProps={"apiKey": ""}, address="SERIAL123")
        mock_indigo._devices_by_id[parent_id] = parent
        zone = _fake_zone(
            dev_id=zone_id,
            entries=[{"dev_id": sensor_id, "state_id": "moisture", "scale": "percent"}],
            parent_id=parent_id,
        )
        mock_indigo._devices_by_id[zone_id] = zone
        mock_indigo._devices_by_id[sensor_id] = _fake_sensor(sensor_id, states={"moisture": 60})
        plugin_with_api._external_sensor_index = {sensor_id: {zone_id}}

        orig = SimpleNamespace(id=sensor_id, states={"moisture": 40})
        new = SimpleNamespace(id=sensor_id, states={"moisture": 60})
        plugin_with_api.deviceUpdated(orig, new)

        plugin_with_api.api_client.set_moisture.assert_called_once_with(
            "SERIAL123", 1, 60, api_version="1"
        )
        zone.updateStateOnServer.assert_called_once_with("moisture", 60, uiValue="60%")

    def test_unchanged_state_does_not_push(self, plugin_with_api, mock_indigo):
        sensor_id, zone_id = 1, 500
        zone = _fake_zone(
            dev_id=zone_id,
            entries=[{"dev_id": sensor_id, "state_id": "moisture", "scale": "percent"}],
        )
        mock_indigo._devices_by_id[zone_id] = zone
        plugin_with_api._external_sensor_index = {sensor_id: {zone_id}}

        orig = SimpleNamespace(id=sensor_id, states={"moisture": 40})
        new = SimpleNamespace(id=sensor_id, states={"moisture": 40})
        plugin_with_api.deviceUpdated(orig, new)

        plugin_with_api.api_client.set_moisture.assert_not_called()

    def test_device_not_in_index_does_not_push(self, plugin_with_api, mock_indigo):
        plugin_with_api._external_sensor_index = {}
        orig = SimpleNamespace(id=999, states={"moisture": 40})
        new = SimpleNamespace(id=999, states={"moisture": 60})
        plugin_with_api.deviceUpdated(orig, new)
        plugin_with_api.api_client.set_moisture.assert_not_called()

    def test_super_deviceupdated_is_called(self, plugin_with_api, mock_indigo, monkeypatch):
        """super().deviceUpdated() must be invoked — it's mandatory per Indigo docs."""
        base = mock_indigo.PluginBase
        mock_super = MagicMock()
        monkeypatch.setattr(base, "deviceUpdated", mock_super)

        plugin_with_api._external_sensor_index = {}
        orig = SimpleNamespace(id=999, states={})
        new = SimpleNamespace(id=999, states={})
        plugin_with_api.deviceUpdated(orig, new)

        assert mock_super.called
        assert mock_super.call_args.args[-2:] == (orig, new)

    def test_first_report_state_missing_in_orig_pushes(self, plugin_with_api, mock_indigo):
        """State key absent from origDev.states (first-ever report) still counts as a change."""
        sensor_id, zone_id, parent_id = 1, 500, 100
        parent = SimpleNamespace(pluginProps={"apiKey": ""}, address="SERIAL123")
        mock_indigo._devices_by_id[parent_id] = parent
        zone = _fake_zone(
            dev_id=zone_id,
            entries=[{"dev_id": sensor_id, "state_id": "moisture", "scale": "percent"}],
            parent_id=parent_id,
        )
        mock_indigo._devices_by_id[zone_id] = zone
        mock_indigo._devices_by_id[sensor_id] = _fake_sensor(sensor_id, states={"moisture": 65})
        plugin_with_api._external_sensor_index = {sensor_id: {zone_id}}

        orig = SimpleNamespace(id=sensor_id, states={})
        new = SimpleNamespace(id=sensor_id, states={"moisture": 65})
        plugin_with_api.deviceUpdated(orig, new)

        plugin_with_api.api_client.set_moisture.assert_called_once_with(
            "SERIAL123", 1, 65, api_version="1"
        )

    def test_multi_zone_fanout(self, plugin_with_api, mock_indigo):
        """One sensor linked to two zones pushes to both."""
        sensor_id, zone_a_id, zone_b_id, parent_id = 1, 500, 501, 100
        parent = SimpleNamespace(pluginProps={"apiKey": ""}, address="SERIAL123")
        mock_indigo._devices_by_id[parent_id] = parent
        zone_a = _fake_zone(
            dev_id=zone_a_id,
            entries=[{"dev_id": sensor_id, "state_id": "moisture", "scale": "percent"}],
            parent_id=parent_id,
            zone_number=1,
        )
        zone_b = _fake_zone(
            dev_id=zone_b_id,
            entries=[{"dev_id": sensor_id, "state_id": "moisture", "scale": "percent"}],
            parent_id=parent_id,
            zone_number=2,
        )
        mock_indigo._devices_by_id[zone_a_id] = zone_a
        mock_indigo._devices_by_id[zone_b_id] = zone_b
        mock_indigo._devices_by_id[sensor_id] = _fake_sensor(sensor_id, states={"moisture": 60})
        plugin_with_api._external_sensor_index = {sensor_id: {zone_a_id, zone_b_id}}

        orig = SimpleNamespace(id=sensor_id, states={"moisture": 40})
        new = SimpleNamespace(id=sensor_id, states={"moisture": 60})
        plugin_with_api.deviceUpdated(orig, new)

        assert plugin_with_api.api_client.set_moisture.call_count == 2
        zone_a.updateStateOnServer.assert_called_once_with("moisture", 60, uiValue="60%")
        zone_b.updateStateOnServer.assert_called_once_with("moisture", 60, uiValue="60%")


# =============================================================================
# Duplicate-push suppression
# =============================================================================

class TestPushExternalMoistureDuplicateSuppression:
    def test_same_average_twice_only_one_api_call(self, plugin_with_api, mock_indigo):
        sensor_id, zone_id, parent_id = 1, 500, 100
        parent = SimpleNamespace(pluginProps={"apiKey": ""}, address="SERIAL123")
        mock_indigo._devices_by_id[parent_id] = parent
        zone = _fake_zone(
            dev_id=zone_id,
            entries=[{"dev_id": sensor_id, "state_id": "moisture", "scale": "percent"}],
            parent_id=parent_id,
        )
        mock_indigo._devices_by_id[zone_id] = zone
        mock_indigo._devices_by_id[sensor_id] = _fake_sensor(sensor_id, states={"moisture": 50})

        plugin_with_api._push_external_moisture(zone)
        plugin_with_api._push_external_moisture(zone)

        plugin_with_api.api_client.set_moisture.assert_called_once()

    def test_no_usable_sensors_does_not_call_api(self, plugin_with_api, mock_indigo):
        zone = _fake_zone(dev_id=500, entries=[{"dev_id": 1, "state_id": "moisture", "scale": "percent"}])
        plugin_with_api._push_external_moisture(zone)
        plugin_with_api.api_client.set_moisture.assert_not_called()


# =============================================================================
# _push_external_moisture — error handling
# =============================================================================

class TestPushExternalMoistureErrorHandling:
    def test_non_ok_response_not_recorded_then_subsequent_ok_succeeds(self, plugin_with_api, mock_indigo):
        sensor_id, zone_id, parent_id = 1, 500, 100
        parent = SimpleNamespace(pluginProps={"apiKey": ""}, address="SERIAL123")
        mock_indigo._devices_by_id[parent_id] = parent
        zone = _fake_zone(
            dev_id=zone_id,
            entries=[{"dev_id": sensor_id, "state_id": "moisture", "scale": "percent"}],
            parent_id=parent_id,
        )
        mock_indigo._devices_by_id[zone_id] = zone
        mock_indigo._devices_by_id[sensor_id] = _fake_sensor(sensor_id, states={"moisture": 50})
        plugin_with_api.api_client.set_moisture.return_value = {"status": "ERROR"}

        plugin_with_api._push_external_moisture(zone)

        assert zone_id not in plugin_with_api._last_pushed_external_moisture
        zone.updateStateOnServer.assert_not_called()
        plugin_with_api.logger.error.assert_called_once()

        plugin_with_api.api_client.set_moisture.return_value = {"status": "OK"}
        plugin_with_api._push_external_moisture(zone)

        assert plugin_with_api._last_pushed_external_moisture[zone_id] == 50
        zone.updateStateOnServer.assert_called_once_with("moisture", 50, uiValue="50%")

    def test_set_moisture_raises_no_exception_escapes(self, plugin_with_api, mock_indigo):
        sensor_id, zone_id, parent_id = 1, 500, 100
        parent = SimpleNamespace(pluginProps={"apiKey": ""}, address="SERIAL123")
        mock_indigo._devices_by_id[parent_id] = parent
        zone = _fake_zone(
            dev_id=zone_id,
            entries=[{"dev_id": sensor_id, "state_id": "moisture", "scale": "percent"}],
            parent_id=parent_id,
        )
        mock_indigo._devices_by_id[zone_id] = zone
        mock_indigo._devices_by_id[sensor_id] = _fake_sensor(sensor_id, states={"moisture": 50})
        plugin_with_api.api_client.set_moisture.side_effect = RuntimeError("boom")

        plugin_with_api._push_external_moisture(zone)  # must not raise

        assert zone_id not in plugin_with_api._last_pushed_external_moisture
        plugin_with_api.logger.error.assert_called_once()


# =============================================================================
# _push_external_moisture / _rebuild_external_sensor_index — disabled zones
# =============================================================================

class TestDisabledZoneHandling:
    def test_push_external_moisture_skips_disabled_zone(self, plugin_with_api, mock_indigo):
        zone = _fake_zone(
            dev_id=500,
            entries=[{"dev_id": 1, "state_id": "moisture", "scale": "percent"}],
            enabled=False,
        )
        plugin_with_api._push_external_moisture(zone)
        plugin_with_api.api_client.set_moisture.assert_not_called()

    def test_rebuild_excludes_disabled_zone(self, mock_indigo, plugin_instance):
        zone = _fake_zone(
            dev_id=500,
            entries=[{"dev_id": 1, "state_id": "moisture", "scale": "percent"}],
            enabled=False,
        )
        mock_indigo.devices.iter = MagicMock(return_value=iter([zone]))
        plugin_instance._rebuild_external_sensor_index()
        assert plugin_instance._external_sensor_index == {}


# =============================================================================
# Unusable-readings warning (one-shot, re-arms after a successful push)
# =============================================================================

class TestUnusableReadingsWarning:
    def test_warns_once_then_rearms_after_success(self, plugin_with_api, mock_indigo):
        zone = _fake_zone(dev_id=500, entries=[{"dev_id": 1, "state_id": "moisture", "scale": "percent"}])

        # Sensor 1 not registered yet -> unusable. Two consecutive pushes must
        # only log the warning once.
        plugin_with_api._push_external_moisture(zone)
        plugin_with_api._push_external_moisture(zone)
        assert plugin_with_api.logger.warning.call_count == 1

        # Sensor becomes usable -> push succeeds, discarding the warned id.
        mock_indigo._devices_by_id[1] = _fake_sensor(1, states={"moisture": 55})
        mock_indigo._devices_by_id[100] = SimpleNamespace(
            pluginProps={"apiKey": ""}, address="SERIAL123"
        )
        plugin_with_api._push_external_moisture(zone)
        assert plugin_with_api.logger.warning.call_count == 1

        # Sensor goes unusable again -> the warning re-arms and fires again.
        del mock_indigo._devices_by_id[1]
        plugin_with_api._push_external_moisture(zone)
        assert plugin_with_api.logger.warning.call_count == 2


# =============================================================================
# _rebuild_external_sensor_index
# =============================================================================

class TestRebuildExternalSensorIndex:
    def test_builds_correct_mapping(self, mock_indigo, plugin_instance):
        zones = [
            _fake_zone(dev_id=500, entries=[
                {"dev_id": 1, "state_id": "moisture", "scale": "percent"},
                {"dev_id": 2, "state_id": "humidity", "scale": "percent"},
            ]),
            _fake_zone(dev_id=501, entries=[
                {"dev_id": 1, "state_id": "moisture", "scale": "percent"},
            ]),
        ]
        mock_indigo.devices.iter = MagicMock(return_value=iter(zones))
        plugin_instance._rebuild_external_sensor_index()
        assert plugin_instance._external_sensor_index == {1: {500, 501}, 2: {500}}

    def test_ignores_non_zone_devices(self, mock_indigo, plugin_instance):
        sprite = SimpleNamespace(
            id=1, name="Sprite", deviceTypeId="sprinkler", pluginProps={}, states={},
        )
        zone = _fake_zone(dev_id=500, entries=[{"dev_id": 9, "state_id": "moisture", "scale": "percent"}])
        mock_indigo.devices.iter = MagicMock(return_value=iter([sprite, zone]))
        plugin_instance._rebuild_external_sensor_index()
        assert plugin_instance._external_sensor_index == {9: {500}}

    def test_no_entries_produces_empty_index(self, mock_indigo, plugin_instance):
        zone = _fake_zone(dev_id=500, entries=[])
        mock_indigo.devices.iter = MagicMock(return_value=iter([zone]))
        plugin_instance._rebuild_external_sensor_index()
        assert plugin_instance._external_sensor_index == {}

    def test_tolerates_corrupt_json_with_warning(self, mock_indigo, plugin_instance):
        bad_zone = _fake_zone(dev_id=502, entries=[])
        bad_zone.pluginProps["externalSensorsJson"] = "{not valid json"
        mock_indigo.devices.iter = MagicMock(return_value=iter([bad_zone]))
        plugin_instance._rebuild_external_sensor_index()
        assert plugin_instance._external_sensor_index == {}
        plugin_instance.logger.warning.assert_called_once()


# =============================================================================
# deviceStartComm
# =============================================================================

class TestDeviceStartComm:
    def test_zone_rebuilds_index_pops_cache_and_pushes(self, plugin_with_api, mock_indigo):
        sensor_id, zone_id, parent_id = 1, 500, 100
        parent = SimpleNamespace(pluginProps={"apiKey": ""}, address="SERIAL123")
        mock_indigo._devices_by_id[parent_id] = parent
        zone = _fake_zone(
            dev_id=zone_id,
            entries=[{"dev_id": sensor_id, "state_id": "moisture", "scale": "percent"}],
            parent_id=parent_id,
        )
        mock_indigo._devices_by_id[zone_id] = zone
        mock_indigo._devices_by_id[sensor_id] = _fake_sensor(sensor_id, states={"moisture": 70})
        mock_indigo.devices.iter = MagicMock(return_value=iter([zone]))
        plugin_with_api._last_pushed_external_moisture[zone_id] = 999  # stale cache entry

        plugin_with_api.deviceStartComm(zone)

        assert plugin_with_api._external_sensor_index == {sensor_id: {zone_id}}
        plugin_with_api.api_client.set_moisture.assert_called_once_with(
            "SERIAL123", 1, 70, api_version="1"
        )
        assert plugin_with_api._last_pushed_external_moisture[zone_id] == 70

    def test_zone_without_sensors_does_not_push(self, plugin_with_api, mock_indigo):
        zone = _fake_zone(dev_id=500, entries=[])
        mock_indigo.devices.iter = MagicMock(return_value=iter([zone]))
        plugin_with_api.deviceStartComm(zone)
        plugin_with_api.api_client.set_moisture.assert_not_called()

    def test_disabled_zone_does_not_push(self, plugin_with_api, mock_indigo):
        sensor_id, zone_id, parent_id = 1, 500, 100
        zone = _fake_zone(
            dev_id=zone_id,
            entries=[{"dev_id": sensor_id, "state_id": "moisture", "scale": "percent"}],
            parent_id=parent_id,
            enabled=False,
        )
        mock_indigo.devices.iter = MagicMock(return_value=iter([zone]))
        plugin_with_api.deviceStartComm(zone)
        plugin_with_api.api_client.set_moisture.assert_not_called()

    def test_non_zone_device_does_nothing(self, plugin_with_api, mock_indigo):
        sprinkler = SimpleNamespace(id=1, deviceTypeId="sprinkler", pluginProps={}, enabled=True)
        plugin_with_api.deviceStartComm(sprinkler)
        plugin_with_api.api_client.set_moisture.assert_not_called()
        mock_indigo.devices.iter.assert_not_called()


# =============================================================================
# didDeviceCommPropertyChange
# =============================================================================

class TestDidDeviceCommPropertyChange:
    def test_zone_with_changed_external_sensors_json_returns_true(self, plugin_instance):
        orig = SimpleNamespace(deviceTypeId="zone", pluginProps={"externalSensorsJson": "[]"}, states={})
        new = SimpleNamespace(
            deviceTypeId="zone",
            pluginProps={"externalSensorsJson": '[{"dev_id": 1}]'},
            states={},
        )
        assert plugin_instance.didDeviceCommPropertyChange(orig, new) is True

    def test_zone_with_unchanged_external_sensors_json_returns_false(self, plugin_instance):
        same = '[{"dev_id": 1}]'
        orig = SimpleNamespace(deviceTypeId="zone", pluginProps={"externalSensorsJson": same}, states={})
        new = SimpleNamespace(deviceTypeId="zone", pluginProps={"externalSensorsJson": same}, states={})
        assert plugin_instance.didDeviceCommPropertyChange(orig, new) is False

    def test_non_zone_id_changed_returns_true(self, plugin_instance):
        orig = SimpleNamespace(deviceTypeId="sprinkler", pluginProps={}, states={"id": "A"})
        new = SimpleNamespace(deviceTypeId="sprinkler", pluginProps={}, states={"id": "B"})
        assert plugin_instance.didDeviceCommPropertyChange(orig, new) is True

    def test_non_zone_id_unchanged_returns_false(self, plugin_instance):
        orig = SimpleNamespace(deviceTypeId="sprinkler", pluginProps={}, states={"id": "A"})
        new = SimpleNamespace(deviceTypeId="sprinkler", pluginProps={}, states={"id": "A"})
        assert plugin_instance.didDeviceCommPropertyChange(orig, new) is False


# =============================================================================
# ConfigUI callbacks
# =============================================================================

class TestGetExternalSensorDevices:
    def test_excludes_own_devices_and_sorts(self, mock_indigo, plugin_instance):
        own_zone = _fake_zone(dev_id=500, entries=[])
        others = [
            _fake_sensor(1, name="Zebra Sensor"),
            _fake_sensor(2, name="apple Sensor"),
        ]
        mock_indigo.devices.iter = MagicMock(return_value=iter([own_zone]))
        mock_indigo.devices.__iter__ = MagicMock(return_value=iter([own_zone] + others))

        result = plugin_instance.getExternalSensorDevices()

        assert result[0] == ("", "(Select a sensor device)")
        assert result[1:] == [("2", "apple Sensor"), ("1", "Zebra Sensor")]


class TestGetExternalSensorStates:
    def test_no_device_selected_returns_sentinel(self, mock_indigo, plugin_instance):
        result = plugin_instance.getExternalSensorStates(valuesDict={})
        assert result == [("", "(Select a device first)")]

    def test_invalid_device_id_returns_sentinel(self, mock_indigo, plugin_instance):
        result = plugin_instance.getExternalSensorStates(valuesDict={"externalSensorDevice": "999"})
        assert result == [("", "(Select a device first)")]

    def test_priority_states_sort_first(self, mock_indigo, plugin_instance):
        sensor = _fake_sensor(1, states={"batteryLevel": 90, "soilMoisture": 45, "humidity": 33})
        mock_indigo._devices_by_id[1] = sensor
        result = plugin_instance.getExternalSensorStates(valuesDict={"externalSensorDevice": "1"})
        ids = [r[0] for r in result]
        assert ids == ["humidity", "soilMoisture", "batteryLevel"]
        assert result[0] == ("humidity", "humidity (current: 33)")


class TestAddExternalSensor:
    def test_no_selection_logs_warning_and_returns_unchanged(self, plugin_instance):
        values = {"externalSensorDevice": "", "externalSensorState": ""}
        result = plugin_instance.addExternalSensor(dict(values), "zone", 500)
        assert result["externalSensorDevice"] == ""
        plugin_instance.logger.warning.assert_called_once()

    def test_adds_entry(self, plugin_instance):
        values = {
            "externalSensorDevice": "42",
            "externalSensorState": "soilMoisture",
            "externalSensorScale": "percent",
            "externalSensorsJson": "[]",
        }
        result = plugin_instance.addExternalSensor(values, "zone", 500)
        entries = json.loads(result["externalSensorsJson"])
        assert entries == [{"dev_id": 42, "state_id": "soilMoisture", "scale": "percent"}]
        assert result["externalSensorDevice"] == ""
        assert result["externalSensorState"] == ""

    def test_dedupes_existing_entry(self, plugin_instance):
        existing = json.dumps([{"dev_id": 42, "state_id": "soilMoisture", "scale": "percent"}])
        values = {
            "externalSensorDevice": "42",
            "externalSensorState": "soilMoisture",
            "externalSensorScale": "percent",
            "externalSensorsJson": existing,
        }
        result = plugin_instance.addExternalSensor(values, "zone", 500)
        entries = json.loads(result["externalSensorsJson"])
        assert len(entries) == 1
        plugin_instance.logger.warning.assert_called_once()


class TestGetConfiguredExternalSensors:
    def test_formats_entries(self, mock_indigo, plugin_instance):
        mock_indigo._devices_by_id[42] = _fake_sensor(42, name="Garden Sensor")
        values = {"externalSensorsJson": json.dumps(
            [{"dev_id": 42, "state_id": "soilMoisture", "scale": "percent"}]
        )}
        result = plugin_instance.getConfiguredExternalSensors(valuesDict=values)
        assert result == [("42:soilMoisture", "Garden Sensor → soilMoisture (percent)")]

    def test_missing_device_shows_placeholder(self, mock_indigo, plugin_instance):
        values = {"externalSensorsJson": json.dumps(
            [{"dev_id": 99, "state_id": "soilMoisture", "scale": "percent"}]
        )}
        result = plugin_instance.getConfiguredExternalSensors(valuesDict=values)
        assert result == [("99:soilMoisture", "(missing device 99) → soilMoisture (percent)")]


class TestRemoveExternalSensors:
    def test_removes_selected_entries(self, plugin_instance):
        entries = [
            {"dev_id": 1, "state_id": "moisture", "scale": "percent"},
            {"dev_id": 2, "state_id": "humidity", "scale": "percent"},
        ]
        values = {
            "externalSensorsJson": json.dumps(entries),
            "externalSensorsList": ["1:moisture"],
        }
        result = plugin_instance.removeExternalSensors(values, "zone", 500)
        remaining = json.loads(result["externalSensorsJson"])
        assert remaining == [{"dev_id": 2, "state_id": "humidity", "scale": "percent"}]

    def test_no_selection_returns_unchanged(self, plugin_instance):
        entries = [{"dev_id": 1, "state_id": "moisture", "scale": "percent"}]
        values = {"externalSensorsJson": json.dumps(entries), "externalSensorsList": []}
        result = plugin_instance.removeExternalSensors(values, "zone", 500)
        assert json.loads(result["externalSensorsJson"]) == entries

    def test_single_string_selection_removes_entry(self, plugin_instance):
        """Indigo delivers a single-item list selection as a bare string, not a list."""
        entries = [
            {"dev_id": 1, "state_id": "moisture", "scale": "percent"},
            {"dev_id": 2, "state_id": "humidity", "scale": "percent"},
        ]
        values = {
            "externalSensorsJson": json.dumps(entries),
            "externalSensorsList": "1:moisture",
        }
        result = plugin_instance.removeExternalSensors(values, "zone", 500)
        remaining = json.loads(result["externalSensorsJson"])
        assert remaining == [{"dev_id": 2, "state_id": "humidity", "scale": "percent"}]

    def test_empty_string_selection_no_change(self, plugin_instance):
        entries = [{"dev_id": 1, "state_id": "moisture", "scale": "percent"}]
        values = {"externalSensorsJson": json.dumps(entries), "externalSensorsList": ""}
        result = plugin_instance.removeExternalSensors(values, "zone", 500)
        assert json.loads(result["externalSensorsJson"]) == entries


class TestExternalSensorsRoundTrip:
    def test_add_list_remove_round_trip(self, mock_indigo, plugin_instance):
        mock_indigo._devices_by_id[42] = _fake_sensor(42, name="Garden Sensor")
        values = {
            "externalSensorDevice": "42",
            "externalSensorState": "soilMoisture",
            "externalSensorScale": "percent",
            "externalSensorsJson": "[]",
        }

        values = plugin_instance.addExternalSensor(values, "zone", 500)

        listed = plugin_instance.getConfiguredExternalSensors(valuesDict=values)
        assert listed == [("42:soilMoisture", "Garden Sensor → soilMoisture (percent)")]

        values["externalSensorsList"] = ["42:soilMoisture"]
        values = plugin_instance.removeExternalSensors(values, "zone", 500)
        assert json.loads(values["externalSensorsJson"]) == []


# =============================================================================
# validators.validate_device_config — zone externalSensorsJson
# =============================================================================

class TestValidateZoneExternalSensors:
    def test_absent_json_passes(self):
        is_valid, _, errors = validate_device_config({}, "zone")
        assert is_valid
        assert errors == {}

    def test_empty_string_json_passes(self):
        is_valid, _, errors = validate_device_config({"externalSensorsJson": ""}, "zone")
        assert is_valid
        assert errors == {}

    def test_valid_json_passes(self):
        values = {"externalSensorsJson": json.dumps(
            [{"dev_id": 1, "state_id": "moisture", "scale": "percent"}]
        )}
        is_valid, sanitized, errors = validate_device_config(values, "zone")
        assert is_valid
        assert errors == {}
        assert sanitized["externalSensorsJson"] == values["externalSensorsJson"]

    def test_corrupt_json_rejected(self):
        is_valid, _, errors = validate_device_config({"externalSensorsJson": "{not valid"}, "zone")
        assert not is_valid
        assert "externalSensorsJson" in errors
        assert "corrupt" in errors["externalSensorsJson"].lower()

    def test_wrong_shape_rejected(self):
        values = {"externalSensorsJson": json.dumps([{"dev_id": 1}])}  # missing state_id/scale
        is_valid, _, errors = validate_device_config(values, "zone")
        assert not is_valid
        assert "externalSensorsJson" in errors

    def test_non_list_json_rejected(self):
        values = {"externalSensorsJson": json.dumps({"dev_id": 1})}
        is_valid, _, errors = validate_device_config(values, "zone")
        assert not is_valid
        assert "externalSensorsJson" in errors

    def test_non_int_dev_id_rejected(self):
        values = {"externalSensorsJson": json.dumps(
            [{"dev_id": "abc", "state_id": "moisture", "scale": "percent"}]
        )}
        is_valid, _, errors = validate_device_config(values, "zone")
        assert not is_valid
        assert "externalSensorsJson" in errors

    def test_bool_dev_id_rejected(self):
        values = {"externalSensorsJson": json.dumps(
            [{"dev_id": True, "state_id": "moisture", "scale": "percent"}]
        )}
        is_valid, _, errors = validate_device_config(values, "zone")
        assert not is_valid
        assert "externalSensorsJson" in errors

    def test_bad_scale_rejected(self):
        values = {"externalSensorsJson": json.dumps(
            [{"dev_id": 1, "state_id": "moisture", "scale": "bogus"}]
        )}
        is_valid, _, errors = validate_device_config(values, "zone")
        assert not is_valid
        assert "externalSensorsJson" in errors

    def test_empty_state_id_rejected(self):
        values = {"externalSensorsJson": json.dumps(
            [{"dev_id": 1, "state_id": "", "scale": "percent"}]
        )}
        is_valid, _, errors = validate_device_config(values, "zone")
        assert not is_valid
        assert "externalSensorsJson" in errors

    def test_string_dev_id_accepted(self):
        values = {"externalSensorsJson": json.dumps(
            [{"dev_id": "1", "state_id": "moisture", "scale": "fraction"}]
        )}
        is_valid, _, errors = validate_device_config(values, "zone")
        assert is_valid
        assert errors == {}


class TestValidateZoneExternalMaxAgeDays:
    def test_numeric_string_accepted(self):
        is_valid, _, errors = validate_device_config({"externalMaxAgeDays": "7"}, "zone")
        assert is_valid
        assert errors == {}

    def test_empty_string_accepted(self):
        is_valid, _, errors = validate_device_config({"externalMaxAgeDays": ""}, "zone")
        assert is_valid
        assert errors == {}

    def test_absent_accepted(self):
        is_valid, _, errors = validate_device_config({}, "zone")
        assert is_valid
        assert errors == {}

    def test_non_numeric_rejected(self):
        is_valid, _, errors = validate_device_config({"externalMaxAgeDays": "abc"}, "zone")
        assert not is_valid
        assert "externalMaxAgeDays" in errors

    def test_negative_rejected(self):
        is_valid, _, errors = validate_device_config({"externalMaxAgeDays": "-1"}, "zone")
        assert not is_valid
        assert "externalMaxAgeDays" in errors

    def test_zero_accepted(self):
        """0 is a valid number (treated as "no limit" at runtime)."""
        is_valid, _, errors = validate_device_config({"externalMaxAgeDays": "0"}, "zone")
        assert is_valid
        assert errors == {}


# =============================================================================
# _resolve_zone_moisture — external branch (highest precedence)
# =============================================================================

class TestResolveZoneMoistureExternalBranch:
    def test_usable_external_average_takes_precedence_over_whisperer(self, plugin_instance, mock_indigo):
        sensor_id, whisperer_id = 1, 999
        mock_indigo._devices_by_id[sensor_id] = _fake_sensor(sensor_id, states={"moisture": 80})
        mock_indigo._devices_by_id[whisperer_id] = SimpleNamespace(
            enabled=True,
            states={"soilMoisture": 20, "readingTime": "2026-04-23T10:00:00", "readingID": 1},
        )
        zone = SimpleNamespace(
            name="Lawn",
            pluginProps={
                "linkedWhispererDeviceId": str(whisperer_id),
                "externalSensorsJson": json.dumps(
                    [{"dev_id": sensor_id, "state_id": "moisture", "scale": "percent"}]
                ),
            },
        )
        val, src = plugin_instance._resolve_zone_moisture(zone, forecast_val=50)
        assert (val, src) == (80, "external")

    def test_unusable_external_falls_through_to_whisperer(self, plugin_instance, mock_indigo):
        whisperer_id = 999
        mock_indigo._devices_by_id[whisperer_id] = SimpleNamespace(
            enabled=True,
            states={"soilMoisture": 20, "readingTime": "2026-04-23T10:00:00", "readingID": 1},
        )
        zone = SimpleNamespace(
            name="Lawn",
            pluginProps={
                "linkedWhispererDeviceId": str(whisperer_id),
                # sensor id 1 is not registered -> unusable -> avg is None
                "externalSensorsJson": json.dumps(
                    [{"dev_id": 1, "state_id": "moisture", "scale": "percent"}]
                ),
            },
        )
        frozen_now = datetime(2026, 4, 23, 12, 0, 0, tzinfo=timezone.utc)
        with patch("utils._now_utc", return_value=frozen_now):
            val, src = plugin_instance._resolve_zone_moisture(zone, forecast_val=50)
        assert (val, src) == (20, "whisperer")

    def test_zone_without_external_sensors_behaves_as_before(self, plugin_instance):
        zone = SimpleNamespace(name="Lawn", pluginProps={"linkedWhispererDeviceId": ""})
        val, src = plugin_instance._resolve_zone_moisture(zone, forecast_val=77)
        assert (val, src) == (77, "forecast")

    def test_respects_minimum_aggregation(self, plugin_instance, mock_indigo):
        """The external branch flows through _compute_external_average, so the
        zone's configured aggregation method is honoured, not just plain average."""
        mock_indigo._devices_by_id[1] = _fake_sensor(1, states={"moisture": 20})
        mock_indigo._devices_by_id[2] = _fake_sensor(2, states={"moisture": 80})
        zone = SimpleNamespace(
            name="Lawn",
            pluginProps={
                "linkedWhispererDeviceId": "",
                "externalAggregation": "minimum",
                "externalSensorsJson": json.dumps([
                    {"dev_id": 1, "state_id": "moisture", "scale": "percent"},
                    {"dev_id": 2, "state_id": "moisture", "scale": "percent"},
                ]),
            },
        )
        val, src = plugin_instance._resolve_zone_moisture(zone, forecast_val=50)
        assert (val, src) == (20, "external")

    def test_empty_list_external_sensors_json_falls_through(self, plugin_instance):
        """externalSensorsJson == "[]" is non-empty as a string but has 0 entries -> unusable."""
        zone = SimpleNamespace(
            name="Lawn",
            pluginProps={"linkedWhispererDeviceId": "", "externalSensorsJson": "[]"},
        )
        val, src = plugin_instance._resolve_zone_moisture(zone, forecast_val=77)
        assert (val, src) == (77, "forecast")
