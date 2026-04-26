"""Tests for Plugin._log_moisture_source_transition."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def plugin_instance(mock_indigo_base):
    from plugin import Plugin  # noqa: WPS433
    plugin = Plugin.__new__(Plugin)
    plugin.logger = MagicMock()
    return plugin


_NEXT_ZONE_ID = [9000]


def _zone(last_source=None, name="Test Zone"):
    """A fake zone with a mutable pluginProps dict and a replacePluginPropsOnServer stub."""
    props = {}
    if last_source is not None:
        props["lastMoistureSource"] = last_source
    replaced = []

    def _replace(new_props):
        replaced.append(dict(new_props))
        # Simulate Indigo's real behavior: pluginProps reflects the server write.
        props.clear()
        props.update(new_props)

    # Each fake zone gets a unique id so the in-memory transition cache can key on it.
    _NEXT_ZONE_ID[0] += 1
    return SimpleNamespace(
        id=_NEXT_ZONE_ID[0],
        name=name,
        pluginProps=props,
        replacePluginPropsOnServer=_replace,
        _replaced=replaced,
    )


def test_no_log_when_source_unchanged(plugin_instance):
    zone = _zone(last_source="whisperer")
    plugin_instance._log_moisture_source_transition(zone, "whisperer")
    plugin_instance.logger.warning.assert_not_called()
    plugin_instance.logger.info.assert_not_called()
    # pluginProps still reflect the (unchanged) value.
    assert zone.pluginProps.get("lastMoistureSource") == "whisperer"
    # Repeated calls with same source must not hit replacePluginPropsOnServer.
    assert zone._replaced == []


def test_no_log_when_cold_start_whisperer(plugin_instance):
    """Paired zone, first poll with no prior lastMoistureSource → silent."""
    zone = _zone(last_source=None)
    plugin_instance._log_moisture_source_transition(zone, "whisperer")
    plugin_instance.logger.warning.assert_not_called()
    plugin_instance.logger.info.assert_not_called()
    assert zone.pluginProps["lastMoistureSource"] == "whisperer"


def test_log_info_on_forecast_to_whisperer(plugin_instance):
    zone = _zone(last_source="forecast")
    plugin_instance._log_moisture_source_transition(zone, "whisperer")
    plugin_instance.logger.info.assert_called_once()
    assert "Whisperer reading" in plugin_instance.logger.info.call_args[0][0]
    assert zone.pluginProps["lastMoistureSource"] == "whisperer"


def test_log_warning_on_whisperer_to_stale(plugin_instance):
    zone = _zone(last_source="whisperer")
    plugin_instance._log_moisture_source_transition(zone, "forecast-stale")
    plugin_instance.logger.warning.assert_called_once()
    msg = plugin_instance.logger.warning.call_args[0][0]
    assert "stale" in msg.lower()
    assert "forecast" in msg.lower()


def test_log_info_on_stale_to_whisperer(plugin_instance):
    zone = _zone(last_source="forecast-stale")
    plugin_instance._log_moisture_source_transition(zone, "whisperer")
    plugin_instance.logger.info.assert_called_once()
    assert "recovered" in plugin_instance.logger.info.call_args[0][0].lower()


def test_log_warning_on_missing_device(plugin_instance):
    zone = _zone(last_source="whisperer")
    plugin_instance._log_moisture_source_transition(zone, "forecast-missing-device")
    plugin_instance.logger.warning.assert_called_once()
    assert "no longer" in plugin_instance.logger.warning.call_args[0][0].lower()


def test_log_warning_on_disabled_device(plugin_instance):
    zone = _zone(last_source="whisperer")
    plugin_instance._log_moisture_source_transition(zone, "forecast-disabled-device")
    plugin_instance.logger.warning.assert_called_once()
    assert "disabled" in plugin_instance.logger.warning.call_args[0][0].lower()


def test_no_log_when_cold_start_forecast(plugin_instance):
    """Fresh install, first-ever poll on an unpaired zone → silent (no transition)."""
    zone = _zone(last_source=None)
    plugin_instance._log_moisture_source_transition(zone, "forecast")
    plugin_instance.logger.warning.assert_not_called()
    plugin_instance.logger.info.assert_not_called()
    assert zone.pluginProps["lastMoistureSource"] == "forecast"


def test_repeated_warning_suppressed(plugin_instance):
    """Same stale source across two polls logs only once."""
    zone = _zone(last_source="whisperer")
    plugin_instance._log_moisture_source_transition(zone, "forecast-stale")
    plugin_instance._log_moisture_source_transition(zone, "forecast-stale")
    assert plugin_instance.logger.warning.call_count == 1


def test_log_warning_on_missing_reading(plugin_instance):
    """Paired, but Whisperer has no reading yet (readingID==0) → warning."""
    zone = _zone(last_source="whisperer")
    plugin_instance._log_moisture_source_transition(zone, "forecast-missing-reading")
    plugin_instance.logger.warning.assert_called_once()
    assert "no reading yet" in plugin_instance.logger.warning.call_args[0][0].lower()


def test_log_warning_on_unparseable_time(plugin_instance):
    """Paired, but readingTime can't be parsed → warning."""
    zone = _zone(last_source="whisperer")
    plugin_instance._log_moisture_source_transition(zone, "forecast-unparseable-time")
    plugin_instance.logger.warning.assert_called_once()
    assert "unparseable" in plugin_instance.logger.warning.call_args[0][0].lower()


def test_log_warning_on_invalid_reading(plugin_instance):
    """Paired, but soilMoisture is non-numeric → distinct warning from missing-reading."""
    zone = _zone(last_source="whisperer")
    plugin_instance._log_moisture_source_transition(zone, "forecast-invalid-reading")
    plugin_instance.logger.warning.assert_called_once()
    assert "non-numeric soil value" in plugin_instance.logger.warning.call_args[0][0].lower()


def test_replace_props_failure_logs_warning_not_raises(plugin_instance):
    """If replacePluginPropsOnServer raises, logger.warning is called and no exception escapes."""
    zone = _zone(last_source="whisperer")

    def _failing_replace(new_props):
        raise RuntimeError("IOM hiccup")

    zone.replacePluginPropsOnServer = _failing_replace
    # Should not raise.
    plugin_instance._log_moisture_source_transition(zone, "forecast-stale")
    # The stale transition warning AND the persistence-failure warning should both have fired.
    assert plugin_instance.logger.warning.call_count >= 1
    # Verify at least one warning mentions persistence failure.
    messages = [call.args[0] for call in plugin_instance.logger.warning.call_args_list]
    assert any("could not persist moisture source" in m for m in messages)


def test_repeated_transition_with_persist_failure_logs_once(plugin_instance):
    """When replacePluginPropsOnServer keeps failing, the transition log fires only once.

    Pre-fix: every poll re-logged the same transition because pluginProps never updated.
    Post-fix: in-memory cache prevents the spam while IOM is broken.
    """
    zone = _zone(last_source="whisperer")
    # Give the zone an id so the in-memory cache can key on it.
    zone.id = 1234
    zone.replacePluginPropsOnServer = lambda new_props: (_ for _ in ()).throw(RuntimeError("IOM"))

    # First call: transition logs the stale warning + the persist-failure warning.
    plugin_instance._log_moisture_source_transition(zone, "forecast-stale")

    # Second and third calls with the SAME source must not re-log the transition.
    plugin_instance._log_moisture_source_transition(zone, "forecast-stale")
    plugin_instance._log_moisture_source_transition(zone, "forecast-stale")

    # Persistence still fails on every call, but the *transition* warning fires only once.
    transition_msgs = [
        c.args[0] for c in plugin_instance.logger.warning.call_args_list
        if "stale" in c.args[0].lower() and "Netro forecast" in c.args[0]
    ]
    assert len(transition_msgs) == 1, transition_msgs
