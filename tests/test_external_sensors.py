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
from types import SimpleNamespace
from unittest.mock import MagicMock

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


def _fake_zone(dev_id=500, name="Lawn", entries=None, zone_number=1, parent_id=100, enabled=True):
    props = {
        "zoneNumber": str(zone_number),
        "parentDeviceId": str(parent_id),
    }
    if entries is not None:
        props["externalSensorsJson"] = json.dumps(entries)
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


def _fake_sensor(dev_id, name="Sensor", states=None, enabled=True, type_id="thirdParty"):
    return SimpleNamespace(
        id=dev_id, name=name, deviceTypeId=type_id, enabled=enabled, states=states or {},
    )


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
        if getattr(base, "deviceUpdated", None) is None:
            pytest.skip("mock base has no deviceUpdated")
        mock_super = MagicMock()
        monkeypatch.setattr(base, "deviceUpdated", mock_super)

        plugin_with_api._external_sensor_index = {}
        orig = SimpleNamespace(id=999, states={})
        new = SimpleNamespace(id=999, states={})
        plugin_with_api.deviceUpdated(orig, new)

        assert mock_super.called
        assert mock_super.call_args.args[-2:] == (orig, new)


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
