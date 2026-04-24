"""Tests for Plugin._resolve_zone_moisture."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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
    plugin = Plugin.__new__(Plugin)
    plugin.logger = MagicMock()
    return plugin


def _fake_whisperer(enabled=True, soil=30, reading_time="2026-04-23T10:00:00", reading_id=1001):
    return SimpleNamespace(
        enabled=enabled,
        states={
            "soilMoisture": soil,
            "readingTime": reading_time,
            "readingID": reading_id,
        },
    )


def _fake_zone(linked_id="", name="Test Zone"):
    return SimpleNamespace(
        name=name,
        pluginProps={"linkedWhispererDeviceId": linked_id},
    )


FROZEN_NOW = datetime(2026, 4, 23, 12, 0, 0, tzinfo=timezone.utc)


# --- Unpaired paths ---

def test_unpaired_returns_forecast(plugin_instance):
    zone = _fake_zone(linked_id="")
    val, src = plugin_instance._resolve_zone_moisture(zone, forecast_val=55)
    assert (val, src) == (55, "forecast")


def test_unpaired_forecast_none(plugin_instance):
    zone = _fake_zone(linked_id="")
    val, src = plugin_instance._resolve_zone_moisture(zone, forecast_val=None)
    assert (val, src) == (None, "forecast")


# --- Paired, fresh ---

def test_paired_fresh_returns_whisperer(plugin_instance, mock_indigo):
    whisperer = _fake_whisperer(
        soil=24,
        reading_time=(FROZEN_NOW - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S"),
    )
    mock_indigo._devices_by_id[999] = whisperer
    zone = _fake_zone(linked_id="999")
    with patch("utils._now_utc", return_value=FROZEN_NOW):
        val, src = plugin_instance._resolve_zone_moisture(zone, forecast_val=89)
    assert (val, src) == (24, "whisperer")


# --- Paired, stale ---

def test_paired_stale_returns_forecast(plugin_instance, mock_indigo):
    whisperer = _fake_whisperer(
        soil=24,
        reading_time=(FROZEN_NOW - timedelta(hours=20)).strftime("%Y-%m-%dT%H:%M:%S"),
    )
    mock_indigo._devices_by_id[999] = whisperer
    zone = _fake_zone(linked_id="999")
    with patch("utils._now_utc", return_value=FROZEN_NOW):
        val, src = plugin_instance._resolve_zone_moisture(zone, forecast_val=89)
    assert (val, src) == (89, "forecast-stale")


def test_paired_stale_forecast_also_none(plugin_instance, mock_indigo):
    whisperer = _fake_whisperer(
        soil=24,
        reading_time=(FROZEN_NOW - timedelta(hours=20)).strftime("%Y-%m-%dT%H:%M:%S"),
    )
    mock_indigo._devices_by_id[999] = whisperer
    zone = _fake_zone(linked_id="999")
    with patch("utils._now_utc", return_value=FROZEN_NOW):
        val, src = plugin_instance._resolve_zone_moisture(zone, forecast_val=None)
    assert (val, src) == (None, "forecast-stale")


# --- Paired, Whisperer missing ---

def test_paired_device_deleted(plugin_instance, mock_indigo):
    zone = _fake_zone(linked_id="999")  # 999 not in _devices_by_id
    val, src = plugin_instance._resolve_zone_moisture(zone, forecast_val=89)
    assert (val, src) == (89, "forecast-missing-device")


def test_paired_invalid_id(plugin_instance):
    zone = _fake_zone(linked_id="not-an-int")
    val, src = plugin_instance._resolve_zone_moisture(zone, forecast_val=89)
    assert (val, src) == (89, "forecast-missing-device")


# --- Paired, Whisperer disabled ---

def test_paired_device_disabled(plugin_instance, mock_indigo):
    whisperer = _fake_whisperer(enabled=False, soil=24)
    mock_indigo._devices_by_id[999] = whisperer
    zone = _fake_zone(linked_id="999")
    val, src = plugin_instance._resolve_zone_moisture(zone, forecast_val=89)
    assert (val, src) == (89, "forecast-disabled-device")


# --- Paired, unparseable time ---

def test_paired_unparseable_reading_time(plugin_instance, mock_indigo):
    whisperer = _fake_whisperer(reading_time="unknown")
    mock_indigo._devices_by_id[999] = whisperer
    zone = _fake_zone(linked_id="999")
    val, src = plugin_instance._resolve_zone_moisture(zone, forecast_val=89)
    assert (val, src) == (89, "forecast-unparseable-time")


# --- Paired, no soilMoisture state ---

def test_paired_no_soil_state(plugin_instance, mock_indigo):
    whisperer = SimpleNamespace(
        enabled=True,
        states={"readingTime": "2026-04-23T10:00:00", "readingID": 1001},  # soilMoisture missing
    )
    mock_indigo._devices_by_id[999] = whisperer
    zone = _fake_zone(linked_id="999")
    with patch("utils._now_utc", return_value=FROZEN_NOW):
        val, src = plugin_instance._resolve_zone_moisture(zone, forecast_val=89)
    assert (val, src) == (89, "forecast-missing-reading")


# --- Paired, v1 epoch-millis readingTime ---

def test_paired_fresh_v1_epoch_millis(plugin_instance, mock_indigo):
    """v1 API stores readingTime as an epoch-millis int — resolver should honour it."""
    two_hours_ago_ms = int((FROZEN_NOW - timedelta(hours=2)).timestamp() * 1000)
    whisperer = _fake_whisperer(soil=28, reading_time=two_hours_ago_ms)
    mock_indigo._devices_by_id[999] = whisperer
    zone = _fake_zone(linked_id="999")
    with patch("utils._now_utc", return_value=FROZEN_NOW):
        val, src = plugin_instance._resolve_zone_moisture(zone, forecast_val=89)
    assert (val, src) == (28, "whisperer")


# --- Paired, non-numeric soilMoisture (defensive) ---

def test_paired_non_numeric_soil_treated_as_missing_reading(plugin_instance, mock_indigo):
    """Non-numeric soilMoisture (should never happen in practice) falls back safely."""
    whisperer = SimpleNamespace(
        enabled=True,
        states={
            "soilMoisture": "unknown",
            "readingTime": "2026-04-23T10:00:00",
            "readingID": 1001,
        },
    )
    mock_indigo._devices_by_id[999] = whisperer
    zone = _fake_zone(linked_id="999")
    with patch("utils._now_utc", return_value=FROZEN_NOW):
        val, src = plugin_instance._resolve_zone_moisture(zone, forecast_val=89)
    assert (val, src) == (89, "forecast-missing-reading")


# --- Paired, readingID == 0 (sensor uninitialised) ---

def test_paired_reading_id_zero_is_missing_reading(plugin_instance, mock_indigo):
    """readingID == 0 (Indigo Integer-state default) → sensor hasn't reported yet."""
    fresh = (FROZEN_NOW - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
    whisperer = _fake_whisperer(soil=24, reading_time=fresh, reading_id=0)
    mock_indigo._devices_by_id[999] = whisperer
    zone = _fake_zone(linked_id="999")
    with patch("utils._now_utc", return_value=FROZEN_NOW):
        val, src = plugin_instance._resolve_zone_moisture(zone, forecast_val=89)
    assert (val, src) == (89, "forecast-missing-reading")


# --- Paired, real soil=0 reading ---

def test_paired_soil_integer_zero_with_valid_reading(plugin_instance, mock_indigo):
    """soil=0 with readingID>0 and fresh time IS a valid sensor report (bone-dry)."""
    fresh = (FROZEN_NOW - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
    whisperer = _fake_whisperer(soil=0, reading_time=fresh, reading_id=1001)
    mock_indigo._devices_by_id[999] = whisperer
    zone = _fake_zone(linked_id="999")
    with patch("utils._now_utc", return_value=FROZEN_NOW):
        val, src = plugin_instance._resolve_zone_moisture(zone, forecast_val=89)
    assert (val, src) == (0, "whisperer")


# --- Boundary: WHISPERER_STALENESS_HOURS is strict > (not >=) ---

@pytest.mark.parametrize("hours_old,expected_source", [
    (11.9, "whisperer"),
    (12.0, "whisperer"),  # boundary is > not >=
    (12.1, "forecast-stale"),
])
def test_staleness_threshold_boundary(plugin_instance, mock_indigo, hours_old, expected_source):
    whisperer = _fake_whisperer(
        soil=24,
        reading_time=(FROZEN_NOW - timedelta(hours=hours_old)).strftime("%Y-%m-%dT%H:%M:%S"),
    )
    mock_indigo._devices_by_id[999] = whisperer
    zone = _fake_zone(linked_id="999")
    with patch("utils._now_utc", return_value=FROZEN_NOW):
        _, src = plugin_instance._resolve_zone_moisture(zone, forecast_val=89)
    assert src == expected_source
