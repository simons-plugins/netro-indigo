# Whisperer ↔ Zone Pairing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add per-zone Whisperer pairing so zone `moisture` reflects the actual sensor reading when a paired Whisperer is fresh (≤12h old), with graceful fallback to Netro's `/moistures.json` forecast.

**Architecture:** Single writer — the zone update loop pulls the paired Whisperer's current state from Indigo's device DB, checks age, and resolves whether `moisture` comes from the sensor or the forecast. The forecast always lands in a new `moistureForecast` state. The Whisperer update loop is unchanged.

**Tech Stack:** Python 3.10+, Indigo Plugin SDK (v3/v4), pytest + pytest-cov, pylint. Tests run against mocked `indigo.*` objects.

**Design doc:** `docs/plans/2026-04-23-whisperer-zone-pairing-design.md` (issue #54)

**Branch:** `feat/whisperer-zone-pairing` (already created off `origin/main`).

**Reference files (cross-cutting):**
- Plugin module: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py`
- Device definitions: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/Devices.xml`
- Constants: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/constants.py`
- Utils: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/utils.py`
- Handlers: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/device_handlers.py`
- Info.plist: `Netro Sprinklers.indigoPlugin/Contents/Info.plist`
- Tests conftest: `tests/conftest.py`
- Existing handler tests: `tests/test_device_handlers.py`

**Conventions:**
- 120-char lines (enforced by pylint in `pyproject.toml`).
- Write failing test → minimal implementation → pass → commit, per task.
- **No squash merges.** Commit each task separately.
- Version bump happens at the end (single commit, minor bump: user-visible feature).
- Use `date -u` for any timestamps you reference in commit messages — don't guess.

**Test command (shared):** `pytest tests/ -v` from the repo root. Use `-k` to narrow to a specific test during iteration. Full suite must stay green at every commit point.

**Python interpreter:** use the project's interpreter (honored by pytest). If you need a direct invocation, `python3 -m pytest ...` is fine — the plugin runs on Python 3.10+.

---

## Task 1: Add staleness constant

**Files:**
- Modify: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/constants.py`

**Step 1: Write the failing test**

Create `tests/test_constants_whisperer.py`:

```python
"""Tests for Whisperer-specific constants."""
import constants


def test_whisperer_staleness_hours_defined():
    """WHISPERER_STALENESS_HOURS should be defined as a positive integer."""
    assert hasattr(constants, "WHISPERER_STALENESS_HOURS")
    assert isinstance(constants.WHISPERER_STALENESS_HOURS, int)
    assert constants.WHISPERER_STALENESS_HOURS > 0


def test_whisperer_staleness_hours_value():
    """WHISPERER_STALENESS_HOURS should be 12 hours (2-12 missed readings at 1-6h cadence)."""
    assert constants.WHISPERER_STALENESS_HOURS == 12
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_constants_whisperer.py -v`
Expected: FAIL — `AttributeError: module 'constants' has no attribute 'WHISPERER_STALENESS_HOURS'`.

**Step 3: Write minimal implementation**

Append to `constants.py` (at end of "Default Values" section, after `TOKEN_WARNING_THRESHOLD`):

```python
WHISPERER_STALENESS_HOURS: Final[int] = 12
"""Maximum age (hours) for a Whisperer reading to be considered fresh.

Whisperers report every 1-6 hours depending on battery level. 12h = 2-12
missed readings — tolerates brief API outages but catches a dead battery
within a day. When a paired Whisperer reading is older than this, the
zone falls back to Netro's /moistures.json forecast.
"""
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_constants_whisperer.py -v`
Expected: PASS (2 tests).

Also run the full suite to confirm no regression: `pytest tests/ -v`
Expected: all existing tests still pass.

**Step 5: Commit**

```bash
git add "Netro Sprinklers.indigoPlugin/Contents/Server Plugin/constants.py" tests/test_constants_whisperer.py
git commit -m "feat(netro): add WHISPERER_STALENESS_HOURS constant (#54)"
```

---

## Task 2: Add reading-age parse utility

**Context:** Whisperer's `readingTime` state holds the raw `time` field from the API. V1 = epoch millis (e.g. `1234567890000`). V2 = ISO-8601 string (e.g. `"2026-04-07T10:00:00"`). Helper must accept either and return age-in-hours as float, `None` on unparseable input.

**Files:**
- Modify: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/utils.py`
- Create: `tests/test_reading_age.py`

**Step 1: Write the failing test**

Create `tests/test_reading_age.py`:

```python
"""Tests for parse_reading_age_hours utility."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

import utils


class TestParseReadingAgeHours:
    """Test utils.parse_reading_age_hours across supported input formats."""

    @pytest.fixture
    def fixed_now(self):
        """Anchor "now" to a known UTC datetime for deterministic age math."""
        return datetime(2026, 4, 23, 12, 0, 0, tzinfo=timezone.utc)

    def test_v2_iso_string_fresh(self, fixed_now):
        """ISO-8601 string 3h old → ~3.0 hours."""
        three_hours_ago = (fixed_now - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S")
        with patch("utils._now_utc", return_value=fixed_now):
            age = utils.parse_reading_age_hours(three_hours_ago)
        assert age is not None
        assert 2.9 <= age <= 3.1

    def test_v2_iso_string_with_timezone(self, fixed_now):
        """ISO-8601 string with Z suffix should be treated as UTC."""
        three_hours_ago = (fixed_now - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        with patch("utils._now_utc", return_value=fixed_now):
            age = utils.parse_reading_age_hours(three_hours_ago)
        assert age is not None
        assert 2.9 <= age <= 3.1

    def test_v1_epoch_millis_fresh(self, fixed_now):
        """V1 epoch millis 3h old → ~3.0 hours."""
        epoch_ms = int((fixed_now - timedelta(hours=3)).timestamp() * 1000)
        with patch("utils._now_utc", return_value=fixed_now):
            age = utils.parse_reading_age_hours(epoch_ms)
        assert age is not None
        assert 2.9 <= age <= 3.1

    def test_v1_epoch_millis_as_string(self, fixed_now):
        """Epoch millis passed as a string should still parse."""
        epoch_ms_str = str(int((fixed_now - timedelta(hours=3)).timestamp() * 1000))
        with patch("utils._now_utc", return_value=fixed_now):
            age = utils.parse_reading_age_hours(epoch_ms_str)
        assert age is not None
        assert 2.9 <= age <= 3.1

    def test_stale_reading(self, fixed_now):
        """24h-old reading → 24.0 hours (above threshold)."""
        one_day_ago = (fixed_now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")
        with patch("utils._now_utc", return_value=fixed_now):
            age = utils.parse_reading_age_hours(one_day_ago)
        assert age is not None
        assert 23.9 <= age <= 24.1

    def test_unparseable_string_returns_none(self):
        """Garbage input returns None, does not raise."""
        assert utils.parse_reading_age_hours("not-a-timestamp") is None
        assert utils.parse_reading_age_hours("unknown") is None

    def test_empty_string_returns_none(self):
        """Empty string returns None."""
        assert utils.parse_reading_age_hours("") is None

    def test_none_input_returns_none(self):
        """None input returns None."""
        assert utils.parse_reading_age_hours(None) is None

    def test_negative_age_clamped_to_zero(self, fixed_now):
        """Future timestamp (clock skew) returns 0.0, never negative."""
        future = (fixed_now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
        with patch("utils._now_utc", return_value=fixed_now):
            age = utils.parse_reading_age_hours(future)
        assert age == 0.0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_reading_age.py -v`
Expected: FAIL — `AttributeError: module 'utils' has no attribute 'parse_reading_age_hours'`.

**Step 3: Write minimal implementation**

Add to `utils.py` (new section at end, above `get_key_from_dict`):

```python
from datetime import datetime, timezone
from typing import Optional, Union


def _now_utc() -> datetime:
    """Return current time as a timezone-aware UTC datetime.

    Indirected through a module-level function so tests can patch it
    deterministically without depending on freezegun or similar.
    """
    return datetime.now(tz=timezone.utc)


def parse_reading_age_hours(
    reading_time: Union[str, int, float, None]
) -> Optional[float]:
    """Compute age (hours) of a Whisperer reading timestamp.

    Accepts both API v1 and v2 timestamp formats emitted by
    ``WhispererHandler.process_sensor_data``:

    - **V1 (epoch millis)**: e.g. ``1234567890000`` (int or numeric string)
    - **V2 (ISO 8601)**: e.g. ``"2026-04-07T10:00:00"`` or ``"...Z"``

    Args:
        reading_time: Value from the Whisperer ``readingTime`` state.

    Returns:
        Age in hours (non-negative float) if parseable, ``None`` otherwise.
        Returns ``0.0`` when the reading is in the future (clock skew).

    Note:
        V2 ISO strings without an explicit timezone are assumed to be UTC.
        Netro's ``time`` field is the sensor's UTC timestamp; ``local_time``
        is the pre-formatted local variant. We intentionally use the UTC
        form for age math to avoid DST/tz drift.
    """
    if reading_time is None or reading_time == "":
        return None

    now = _now_utc()

    # Try ISO 8601 first (covers v2 and any pre-formatted strings).
    if isinstance(reading_time, str):
        candidate = reading_time.rstrip("Z").strip()
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            parsed = None
        else:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            delta = (now - parsed).total_seconds() / 3600.0
            return max(0.0, delta)

        # Fall through: maybe it's a stringified epoch millis.
        try:
            reading_time = int(candidate)
        except (TypeError, ValueError):
            return None

    # Epoch millis (int or float from numeric-string fallthrough above).
    if isinstance(reading_time, (int, float)):
        try:
            seconds = float(reading_time) / 1000.0
            parsed = datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
        delta = (now - parsed).total_seconds() / 3600.0
        return max(0.0, delta)

    return None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_reading_age.py -v`
Expected: PASS (9 tests).

Full suite: `pytest tests/ -v`
Expected: all existing tests still pass.

**Step 5: Commit**

```bash
git add "Netro Sprinklers.indigoPlugin/Contents/Server Plugin/utils.py" tests/test_reading_age.py
git commit -m "feat(netro): add parse_reading_age_hours for v1 epoch + v2 ISO (#54)"
```

---

## Task 3: Add `moistureForecast` state to Devices.xml

**Files:**
- Modify: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/Devices.xml`

**Note:** `Devices.xml` is not unit-testable in isolation (it's consumed by the Indigo server at runtime). Rely on the XML validity check and downstream plugin tests for coverage.

**Step 1: Verify current XML is valid, then edit**

Run: `python3 -c "import xml.etree.ElementTree as ET; ET.parse('Netro Sprinklers.indigoPlugin/Contents/Server Plugin/Devices.xml'); print('OK')"`
Expected: `OK`.

**Step 2: Add the new state**

In `Devices.xml`, inside `<Device type="custom" id="zone">` → `<States>`, immediately after the existing `<State id="moisture">` block (around line 312), insert:

```xml
            <State id="moistureForecast">
                <ValueType>Integer</ValueType>
                <TriggerLabel>Moisture Forecast (%)</TriggerLabel>
                <ControlPageLabel>Moisture Forecast (%)</ControlPageLabel>
            </State>
```

(Keep `<UiDisplayStateId>moisture</UiDisplayStateId>` unchanged at the bottom of the zone device block.)

**Step 3: Verify XML still parses**

Run: `python3 -c "import xml.etree.ElementTree as ET; t = ET.parse('Netro Sprinklers.indigoPlugin/Contents/Server Plugin/Devices.xml'); zone = [d for d in t.findall('.//Device') if d.get('id') == 'zone'][0]; states = [s.get('id') for s in zone.findall('.//State')]; print('moisture' in states and 'moistureForecast' in states)"`
Expected: `True`.

**Step 4: Commit**

```bash
git add "Netro Sprinklers.indigoPlugin/Contents/Server Plugin/Devices.xml"
git commit -m "feat(netro): add moistureForecast state to zone device (#54)"
```

---

## Task 4: Add zone-device ConfigUI for Whisperer pairing (XML only)

**Files:**
- Modify: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/Devices.xml`

**Step 1: Add ConfigUI fields**

In `Devices.xml`, inside `<Device type="custom" id="zone">` → `<ConfigUI>`, append **after** the existing hidden `zoneNumber` field (around line 305):

```xml
        <Field id="sep_sensor" type="separator"/>
        <Field id="sensorLabel" type="label">
            <Label>Soil Moisture Source</Label>
        </Field>
        <Field id="linkedWhispererDeviceId" type="menu" defaultValue="">
            <Label>Paired Whisperer:</Label>
            <List class="self" method="getWhispererDevices" dynamicReload="true"/>
        </Field>
        <Field id="sensorHelp" type="label" fontSize="small" fontColor="darkgray" alignWithControl="true">
            <Label>When paired, the zone's moisture state mirrors the Whisperer's soil reading (if fresh within 12 hours). Otherwise, it shows Netro's daily forecast. The forecast is always available separately as the "Moisture Forecast" state.</Label>
        </Field>
```

**Step 2: Verify XML still parses and the callback reference is present**

Run: `python3 -c "import xml.etree.ElementTree as ET; t = ET.parse('Netro Sprinklers.indigoPlugin/Contents/Server Plugin/Devices.xml'); zone = [d for d in t.findall('.//Device') if d.get('id') == 'zone'][0]; fields = [f.get('id') for f in zone.findall('.//ConfigUI/Field')]; print('linkedWhispererDeviceId' in fields)"`
Expected: `True`.

**Step 3: Commit**

```bash
git add "Netro Sprinklers.indigoPlugin/Contents/Server Plugin/Devices.xml"
git commit -m "feat(netro): add Whisperer pairing dropdown to zone ConfigUI (#54)"
```

---

## Task 5: Implement `getWhispererDevices` callback

**Context:** Indigo calls this when the zone ConfigUI dropdown is opened. Returns a list of `(value, label)` tuples. First entry is the "unpaired" sentinel (empty string value).

**Files:**
- Modify: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py`
- Create: `tests/test_whisperer_pairing_callback.py`

**Step 1: Write the failing test**

Create `tests/test_whisperer_pairing_callback.py`:

```python
"""Tests for Plugin.getWhispererDevices ConfigUI callback."""
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_indigo(monkeypatch):
    """Install a minimal `indigo` module into sys.modules for plugin import."""
    indigo = MagicMock()
    indigo.devices.iter = MagicMock(return_value=iter([]))
    monkeypatch.setitem(sys.modules, "indigo", indigo)
    return indigo


def _fake_device(dev_id, name, type_id="Whisperer"):
    return SimpleNamespace(id=dev_id, name=name, deviceTypeId=type_id)


def test_returns_unpaired_sentinel_when_no_whisperers(mock_indigo):
    """With zero Whisperers installed, returns only the unpaired option."""
    mock_indigo.devices.iter.return_value = iter([])
    # Import after mock is installed.
    from plugin import Plugin  # noqa: WPS433
    plugin = Plugin.__new__(Plugin)  # skip __init__
    result = plugin.getWhispererDevices()
    assert result[0] == ("", "(Unpaired — use Netro forecast)")
    assert len(result) == 1


def test_returns_whisperers_sorted_by_name(mock_indigo):
    """Whisperers are appended, sorted case-insensitively by name."""
    devs = [
        _fake_device(101, "Zebra"),
        _fake_device(102, "apple"),
        _fake_device(103, "Mango"),
        _fake_device(104, "Sprite 8-zone", type_id="Sprite"),  # not Whisperer
    ]
    mock_indigo.devices.iter.return_value = iter(devs)
    from plugin import Plugin  # noqa: WPS433
    plugin = Plugin.__new__(Plugin)
    result = plugin.getWhispererDevices()
    assert result[0] == ("", "(Unpaired — use Netro forecast)")
    assert result[1:] == [("102", "apple"), ("103", "Mango"), ("101", "Zebra")]


def test_ignores_non_whisperer_devices(mock_indigo):
    """Sprite/Pixie/Spark controllers and zones are excluded."""
    devs = [
        _fake_device(1, "Sprite 8", type_id="Sprite"),
        _fake_device(2, "Pixie 12", type_id="Pixie"),
        _fake_device(3, "Zone A", type_id="zone"),
        _fake_device(4, "Garden Whisperer", type_id="Whisperer"),
    ]
    mock_indigo.devices.iter.return_value = iter(devs)
    from plugin import Plugin  # noqa: WPS433
    plugin = Plugin.__new__(Plugin)
    result = plugin.getWhispererDevices()
    whisperer_ids = [r[0] for r in result[1:]]
    assert whisperer_ids == ["4"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_whisperer_pairing_callback.py -v`
Expected: FAIL — `AttributeError: 'Plugin' object has no attribute 'getWhispererDevices'`.

**Step 3: Write minimal implementation**

In `plugin.py`, add the method to the `Plugin` class. Place it near other ConfigUI callbacks — search for an existing `def ...(self, filter="", valuesDict=None, typeId="", targetId=0)` signature to find the right neighbourhood; if none exists, place it immediately before `def _update_zone_devices` (around the helper-methods section):

```python
def getWhispererDevices(self, filter="", valuesDict=None, typeId="", targetId=0):
    """Populate the `linkedWhispererDeviceId` dropdown on zone ConfigUI.

    Returns a list of (value, label) tuples:
      - First entry: ("", "(Unpaired — use Netro forecast)") sentinel.
      - Remaining entries: this plugin's Whisperer devices, sorted
        case-insensitively by name. Value is the Indigo device ID as a
        string; label is the device name.

    Called by Indigo when the ConfigUI is opened / reloaded.
    """
    options = [("", "(Unpaired — use Netro forecast)")]
    whisperers = sorted(
        (d for d in indigo.devices.iter(filter="self")
         if d.deviceTypeId == "Whisperer"),
        key=lambda d: d.name.lower(),
    )
    options.extend((str(d.id), d.name) for d in whisperers)
    return options
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_whisperer_pairing_callback.py -v`
Expected: PASS (3 tests).

Full suite: `pytest tests/ -v`
Expected: green.

**Step 5: Commit**

```bash
git add "Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py" tests/test_whisperer_pairing_callback.py
git commit -m "feat(netro): add getWhispererDevices ConfigUI callback (#54)"
```

---

## Task 6: Implement `_resolve_zone_moisture` helper

**Context:** Pure-ish function — takes a zone device and a forecast value, returns `(resolved_value, source_tag)`. No logging here (that's task 7). No state writes here (call site does that in task 8).

Source tags:
- `"forecast"` — unpaired.
- `"whisperer"` — paired, fresh reading.
- `"forecast-stale"` — paired, reading too old (> 12h) or no reading.
- `"forecast-missing-device"` — paired id no longer resolves.
- `"forecast-disabled-device"` — paired device exists but is disabled.

**Files:**
- Modify: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py`
- Create: `tests/test_zone_moisture_resolution.py`

**Step 1: Write the failing test**

Create `tests/test_zone_moisture_resolution.py`:

```python
"""Tests for Plugin._resolve_zone_moisture."""
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_indigo(monkeypatch):
    indigo = MagicMock()
    # `indigo.devices[id]` lookup; tests install a side_effect dict.
    indigo._devices_by_id = {}

    def _getitem(dev_id):
        if dev_id not in indigo._devices_by_id:
            raise KeyError(dev_id)
        return indigo._devices_by_id[dev_id]

    indigo.devices.__getitem__.side_effect = _getitem
    monkeypatch.setitem(sys.modules, "indigo", indigo)
    return indigo


@pytest.fixture
def plugin_instance(mock_indigo):
    from plugin import Plugin  # noqa: WPS433
    return Plugin.__new__(Plugin)


def _fake_whisperer(enabled=True, soil=30, reading_time="2026-04-23T10:00:00"):
    return SimpleNamespace(
        enabled=enabled,
        states={"soilMoisture": soil, "readingTime": reading_time},
    )


def _fake_zone(linked_id=""):
    return SimpleNamespace(pluginProps={"linkedWhispererDeviceId": linked_id})


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
    assert (val, src) == (89, "forecast-stale")


# --- Paired, no soilMoisture state ---

def test_paired_no_soil_state(plugin_instance, mock_indigo):
    whisperer = SimpleNamespace(
        enabled=True,
        states={"readingTime": "2026-04-23T10:00:00"},  # soilMoisture missing
    )
    mock_indigo._devices_by_id[999] = whisperer
    zone = _fake_zone(linked_id="999")
    with patch("utils._now_utc", return_value=FROZEN_NOW):
        val, src = plugin_instance._resolve_zone_moisture(zone, forecast_val=89)
    assert (val, src) == (89, "forecast-stale")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_zone_moisture_resolution.py -v`
Expected: FAIL — `AttributeError: 'Plugin' object has no attribute '_resolve_zone_moisture'`.

**Step 3: Write minimal implementation**

In `plugin.py`, add the method to the `Plugin` class, immediately after `getWhispererDevices`:

```python
def _resolve_zone_moisture(self, zone_dev, forecast_val):
    """Resolve the "moisture" state value for a zone device.

    Pure function (no state writes, no logging). Returns a
    ``(value, source_tag)`` pair where source_tag is one of:

    - ``"forecast"``: zone has no paired Whisperer; returns forecast_val.
    - ``"whisperer"``: paired Whisperer exists, is enabled, has a fresh
      (≤ WHISPERER_STALENESS_HOURS old) ``soilMoisture`` reading.
    - ``"forecast-stale"``: paired but reading is missing, too old, or
      ``readingTime`` is unparseable.
    - ``"forecast-missing-device"``: paired device id does not resolve
      to an Indigo device (deleted or invalid id).
    - ``"forecast-disabled-device"``: paired device exists but is
      disabled in Indigo.

    ``value`` may be ``None`` if forecast_val is None and no Whisperer
    value is available; the caller should skip writing ``moisture`` in
    that case.
    """
    from constants import WHISPERER_STALENESS_HOURS  # noqa: WPS433
    from utils import parse_reading_age_hours  # noqa: WPS433

    linked_id = zone_dev.pluginProps.get("linkedWhispererDeviceId", "")
    if not linked_id:
        return forecast_val, "forecast"

    try:
        whisperer = indigo.devices[int(linked_id)]
    except (KeyError, ValueError):
        return forecast_val, "forecast-missing-device"

    if not whisperer.enabled:
        return forecast_val, "forecast-disabled-device"

    soil = whisperer.states.get("soilMoisture")
    reading_time = whisperer.states.get("readingTime", "")
    age_hours = parse_reading_age_hours(reading_time)
    if soil is None or age_hours is None or age_hours > WHISPERER_STALENESS_HOURS:
        return forecast_val, "forecast-stale"

    return int(soil), "whisperer"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_zone_moisture_resolution.py -v`
Expected: PASS (10 tests).

Full suite: `pytest tests/ -v`
Expected: green.

**Step 5: Commit**

```bash
git add "Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py" tests/test_zone_moisture_resolution.py
git commit -m "feat(netro): add _resolve_zone_moisture helper (#54)"
```

---

## Task 7: Implement `_log_moisture_source_transition`

**Context:** Transition-aware logger — writes the zone's `lastMoistureSource` into `pluginProps` so we only log when the source category changes. Prevents log spam on steady-state operation.

Logging rules (triggered on transition only):
- `"forecast"` → `"whisperer"`: info ("paired Whisperer reading active").
- `"whisperer"` → `"forecast-stale"`: warning ("Whisperer reading stale, falling back to forecast").
- `"forecast-stale"` → `"whisperer"`: info ("Whisperer reading recovered").
- Any → `"forecast-missing-device"`: warning ("paired Whisperer device no longer exists").
- Any → `"forecast-disabled-device"`: warning ("paired Whisperer device is disabled").
- All other transitions: silent (e.g. `forecast` → `forecast-stale` shouldn't happen, but if it does, silent is safe).

**Files:**
- Modify: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py`
- Create: `tests/test_moisture_source_logging.py`

**Step 1: Write the failing test**

Create `tests/test_moisture_source_logging.py`:

```python
"""Tests for Plugin._log_moisture_source_transition."""
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_indigo(monkeypatch):
    indigo = MagicMock()
    monkeypatch.setitem(sys.modules, "indigo", indigo)
    return indigo


@pytest.fixture
def plugin_instance(mock_indigo):
    from plugin import Plugin  # noqa: WPS433
    plugin = Plugin.__new__(Plugin)
    plugin.logger = MagicMock()
    return plugin


def _zone(last_source=None, name="Test Zone"):
    """A fake zone with a mutable pluginProps dict and a replacePluginPropsOnServer stub."""
    props = {}
    if last_source is not None:
        props["lastMoistureSource"] = last_source
    replaced = []

    def _replace(new_props):
        replaced.append(dict(new_props))

    return SimpleNamespace(
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_moisture_source_logging.py -v`
Expected: FAIL on all tests — method not defined.

**Step 3: Write minimal implementation**

In `plugin.py`, add immediately after `_resolve_zone_moisture`:

```python
def _log_moisture_source_transition(self, zone_dev, new_source):
    """Log a transition between moisture-source categories for a zone.

    Persists the current source in ``zone_dev.pluginProps['lastMoistureSource']``
    and only emits a log line when the category changes, to avoid spam.
    The first-ever call on a fresh install is silent (no prior state).

    Args:
        zone_dev: Indigo zone device.
        new_source: One of the source tags returned by
            ``_resolve_zone_moisture``.
    """
    prev = zone_dev.pluginProps.get("lastMoistureSource")
    if prev == new_source:
        return

    transition = (prev, new_source)
    if prev is not None:
        if transition == ("forecast", "whisperer") or transition == ("forecast-stale", "whisperer"):
            if prev == "forecast-stale":
                self.logger.info(
                    f"Zone '{zone_dev.name}': Whisperer reading recovered — "
                    f"moisture now tracking paired sensor."
                )
            else:
                self.logger.info(
                    f"Zone '{zone_dev.name}': paired Whisperer reading active — "
                    f"moisture now tracking sensor."
                )
        elif new_source == "forecast-stale":
            self.logger.warning(
                f"Zone '{zone_dev.name}': paired Whisperer reading stale "
                f"(>12h old) — falling back to Netro forecast."
            )
        elif new_source == "forecast-missing-device":
            self.logger.warning(
                f"Zone '{zone_dev.name}': paired Whisperer device no longer "
                f"exists — falling back to Netro forecast."
            )
        elif new_source == "forecast-disabled-device":
            self.logger.warning(
                f"Zone '{zone_dev.name}': paired Whisperer device is disabled "
                f"— falling back to Netro forecast."
            )

    # Persist the new source so the next poll can detect the next transition.
    new_props = dict(zone_dev.pluginProps)
    new_props["lastMoistureSource"] = new_source
    zone_dev.pluginProps = new_props  # keep test-side dict in sync
    zone_dev.replacePluginPropsOnServer(new_props)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_moisture_source_logging.py -v`
Expected: PASS (8 tests).

Full suite: `pytest tests/ -v`
Expected: green.

**Step 5: Commit**

```bash
git add "Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py" tests/test_moisture_source_logging.py
git commit -m "feat(netro): add transition-aware moisture source logging (#54)"
```

---

## Task 8: Wire resolver + logger into `_update_zone_devices`

**Context:** Now patch the existing zone-update loop to:
1. Rename the key emitted by `process_zone_moisture` from `"moisture"` to `"moistureForecast"`.
2. Call `_resolve_zone_moisture` to decide the `"moisture"` value.
3. Call `_log_moisture_source_transition`.

**Files:**
- Modify: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py` (in `_update_zone_devices` around line 690, specifically the `if moisture_response:` block near line 726).
- Create: `tests/test_update_zone_devices_integration.py`

**Step 1: Read the current implementation**

First, open `plugin.py` and locate `_update_zone_devices`. Find the block that processes `moisture_response` (grep: `process_zone_moisture`). It currently emits states keyed `"moisture"` directly from `ZoneHandler.process_zone_moisture`. Note the exact surrounding code so your edit matches context.

**Step 2: Write the failing integration test**

Create `tests/test_update_zone_devices_integration.py`:

```python
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


@pytest.fixture
def mock_indigo(monkeypatch):
    indigo = MagicMock()
    indigo._devices_by_id = {}
    indigo.devices.__getitem__.side_effect = lambda k: indigo._devices_by_id[k]
    monkeypatch.setitem(sys.modules, "indigo", indigo)
    return indigo


@pytest.fixture
def plugin_instance(mock_indigo):
    from plugin import Plugin  # noqa: WPS433
    plugin = Plugin.__new__(Plugin)
    plugin.logger = MagicMock()
    # ZoneHandler is instantiated in __init__; bypass it by attaching a stub.
    from device_handlers import ZoneHandler
    plugin.zone_handler = ZoneHandler(logger=MagicMock())
    return plugin


def _zone_dev(zone_num=1, linked_id="", name="Front Lawn"):
    replaced_states = []
    replaced_props = []

    def _update_states(states):
        replaced_states.extend(states)

    def _replace_props(props):
        replaced_props.append(dict(props))

    dev = SimpleNamespace(
        name=name,
        pluginProps={"zoneNumber": str(zone_num), "linkedWhispererDeviceId": linked_id},
        enabled=True,
        states={},
        updateStatesOnServer=_update_states,
        replacePluginPropsOnServer=_replace_props,
        _replaced_states=replaced_states,
        _replaced_props=replaced_props,
    )
    return dev


def _whisperer(soil=24, hours_old=2):
    return SimpleNamespace(
        enabled=True,
        states={
            "soilMoisture": soil,
            "readingTime": (FROZEN_NOW - timedelta(hours=hours_old)).strftime("%Y-%m-%dT%H:%M:%S"),
        },
    )


def _moistures_response(zone_num, forecast_val):
    return {
        "status": "OK",
        "data": {
            "moistures": [
                {"id": 1, "zone": zone_num, "date": "2026-04-23", "moisture": forecast_val},
            ],
        },
    }


def _device_data():
    return {"zones": []}  # minimum shape; _update_zone_devices iterates zone_devs, not zones


def test_paired_fresh_writes_sensor_to_moisture_and_forecast_to_moistureForecast(
    plugin_instance, mock_indigo
):
    zone = _zone_dev(zone_num=1, linked_id="999")
    mock_indigo._devices_by_id[999] = _whisperer(soil=24, hours_old=2)
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
    assert keys["moisture"] == 24
    assert keys["moistureForecast"] == 89


def test_unpaired_zone_mirrors_forecast_to_both(plugin_instance, mock_indigo):
    zone = _zone_dev(zone_num=1, linked_id="")
    plugin_instance._get_zone_devices = lambda parent_id: {1: zone}
    parent = SimpleNamespace(id=42, name="Sprite")

    plugin_instance._update_zone_devices(
        parent, _device_data(),
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
        parent, _device_data(),
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
            parent, _device_data(),
            schedule_response=None,
            moisture_response=None,
            api_version="1",
        )

    keys = {s["key"]: s["value"] for s in zone._replaced_states}
    assert keys["moisture"] == 24
    # No moistureForecast write when moisture_response is None.
    assert "moistureForecast" not in keys
```

**Step 3: Run test to verify it fails**

Run: `pytest tests/test_update_zone_devices_integration.py -v`
Expected: FAIL on `test_paired_fresh_...` (moisture still 89 or moistureForecast missing) — precise failure depends on current state of the code but tests will not pass.

**Step 4: Modify `_update_zone_devices`**

Locate the block in `_update_zone_devices` that currently looks roughly like:

```python
if moisture_response:
    try:
        states.extend(
            self.zone_handler.process_zone_moisture(moisture_response, zone_num)
        )
    except Exception:
        ...
```

Replace with:

```python
forecast_val = None
if moisture_response:
    try:
        forecast_states = self.zone_handler.process_zone_moisture(
            moisture_response, zone_num
        )
        for entry in forecast_states:
            if entry.get("key") == "moisture":
                entry["key"] = "moistureForecast"
                forecast_val = entry.get("value")
        states.extend(forecast_states)
    except Exception:
        self.logger.exception(
            f"Error processing moisture for zone {zone_num} on '{zone_dev.name}'"
        )

moisture_val, source = self._resolve_zone_moisture(zone_dev, forecast_val)
if moisture_val is not None:
    states.append({"key": "moisture", "value": moisture_val,
                   "uiValue": f"{moisture_val}%"})
self._log_moisture_source_transition(zone_dev, source)
```

**Important:** if the existing block has a different surrounding context (e.g. a wider try/except), preserve its error-handling shape — only adjust the key rename and inject the resolver call. Read the surrounding ~15 lines before editing.

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_update_zone_devices_integration.py -v`
Expected: PASS (4 tests).

Full suite: `pytest tests/ -v`
Expected: green. If any existing `_update_zone_devices` or `ZoneHandler.process_zone_moisture` test starts failing, it likely asserted on the old `"moisture"` key. Update those assertions to expect `"moistureForecast"` on the zone-update side. `ZoneHandler.process_zone_moisture` itself still returns `"moisture"` — don't modify the handler or its direct tests.

**Step 6: Commit**

```bash
git add "Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py" tests/test_update_zone_devices_integration.py
git commit -m "feat(netro): resolve zone moisture source in update loop (#54)"
```

---

## Task 9: Update API_NOTES.md §6

**Files:**
- Modify: `docs/API_NOTES.md`

**Step 1: Find §6**

Run: `grep -n "^#.*6\|^##.*6\|moisture" docs/API_NOTES.md | head -20`

Locate the section that discusses `/moistures.json` staleness (should mention "12–24 hours" based on the issue text).

**Step 2: Rewrite the section**

Replace the old "can be 12-24 hours old" framing with:

```markdown
## §6 · `/moistures.json` — predictions, not sensor readings

`/moistures.json` returns Netro's **smart-model daily prediction** for each
zone, *not* a sampled sensor value. The model assumes full saturation
immediately after irrigation, then decays based on local weather inputs.
For a zone with **no** paired Whisperer, this is the best signal
available. For a zone **with** a paired Whisperer (pairing done in the
Netro mobile app), Netro's app overlays the Whisperer's reading on the
zone tile, but **the `/moistures.json` response itself continues to
return the prediction** — the public API does not expose the app-side
overlay.

This means the plugin's zone `moisture` state will diverge from a
paired Whisperer's actual reading whenever the model and reality
disagree. Observed example: same zone, same moment — `/moistures.json`
= 89%, paired Whisperer = 24%.

**Plugin behavior:**

- The zone `moistureForecast` state always holds the raw
  `/moistures.json` value.
- The zone `moisture` state resolves to: the paired Whisperer's current
  `soilMoisture` if the pairing is configured on the zone device and
  the reading is less than 12 hours old, else `moistureForecast`.
- Pairing is plugin-side (zone ConfigUI → "Paired Whisperer" dropdown),
  independent of any Netro-side pairing. Both can coexist; they don't
  interact.

**Open empirical question:** whether `/moistures.json` continues to
produce sane predictions when a Whisperer is paired on Netro's side but
has stopped reporting (dead battery, unplugged). The issue-#54
investigation showed `/moistures.json` returning a saturation-based
prediction even with a working paired Whisperer, suggesting the
prediction is independent of Whisperer reporting state. Recommend
dogfooding with a disconnected Whisperer for a week before relying on
the fallback in production.
```

(Adjust heading level to match the surrounding file.)

**Step 3: Commit**

```bash
git add docs/API_NOTES.md
git commit -m "docs(netro): clarify /moistures.json is prediction + pairing notes (#54)"
```

---

## Task 10: Update README

**Files:**
- Modify: `README.md` (root of repo)

**Step 1: Find the Whisperer section**

Run: `grep -n -i "whisperer" README.md | head -5`

**Step 2: Add a short note**

Under or near the existing Whisperer section, add:

```markdown
### Pairing a Whisperer to a Zone

Each zone device has a **Paired Whisperer** dropdown in its config UI.
When paired and the Whisperer has reported within the last 12 hours,
the zone's `moisture` state mirrors the Whisperer's `soilMoisture`
reading (the actual measured value). Otherwise the zone falls back to
Netro's daily forecast.

The `/moistures.json` forecast is always visible separately on the
`moistureForecast` state — useful for comparing model predictions to
the sensor's ground truth, and for tuning schedules. See
[`docs/API_NOTES.md`](docs/API_NOTES.md) §6 for details.
```

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs(netro): document Whisperer-zone pairing in README (#54)"
```

---

## Task 11: Final verification + version bump

**Step 1: Run the full suite one more time**

Run: `pytest tests/ -v --tb=short`
Expected: all tests pass. Confirm the new tests are all included:

- `tests/test_constants_whisperer.py`
- `tests/test_reading_age.py`
- `tests/test_whisperer_pairing_callback.py`
- `tests/test_zone_moisture_resolution.py`
- `tests/test_moisture_source_logging.py`
- `tests/test_update_zone_devices_integration.py`

**Step 2: Run pylint on changed modules**

Run:
```
pylint "Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py" \
       "Netro Sprinklers.indigoPlugin/Contents/Server Plugin/utils.py" \
       "Netro Sprinklers.indigoPlugin/Contents/Server Plugin/constants.py"
```
Expected: no new issues introduced. (Match the existing baseline score — don't regress.)

**Step 3: Bump `PluginVersion` in Info.plist**

Run: `grep -A1 "PluginVersion" "Netro Sprinklers.indigoPlugin/Contents/Info.plist"` to read current version.

Compute new version: the workspace convention is `YYYY.R.P` where R increments for user-visible features. This change adds new ConfigUI + new state → **minor bump** (R+1, P=0).

Edit `Info.plist` to change the existing `<string>X.Y.Z</string>` immediately after `<key>PluginVersion</key>` to the new value. Verify the file still parses:

Run: `plutil -lint "Netro Sprinklers.indigoPlugin/Contents/Info.plist"`
Expected: `OK`.

**Step 4: Commit the bump**

```bash
git add "Netro Sprinklers.indigoPlugin/Contents/Info.plist"
git commit -m "chore(netro): bump PluginVersion for Whisperer-zone pairing (#54)"
```

**Step 5: Push the branch**

```bash
git push -u origin feat/whisperer-zone-pairing
```

Expected: remote accepts the branch. Do **not** open the PR from this plan — the user will create the PR (per workspace feedback rule: wait for explicit go-ahead before merging or opening PRs is user-driven via the `/ship` or `gh pr create` workflow).

---

## Post-implementation checklist (do NOT run as tasks — user confirms)

- [ ] All 11 tasks complete on `feat/whisperer-zone-pairing`.
- [ ] `pytest tests/ -v` green.
- [ ] `pylint` on changed modules: no new issues.
- [ ] `Info.plist` version bumped (minor: R+1, P=0).
- [ ] Branch pushed to `origin/feat/whisperer-zone-pairing`.
- [ ] User opens PR referencing #54; CI (`version-check` + tests) green.
- [ ] User dogfoods the fallback behavior with a physically disconnected
      Whisperer for ~1 week before merge (validates the open empirical
      question from the design doc §"Netro-side pairing").

## Not in scope for this plan

- Bulk-pairing action or UI.
- Auto-pairing heuristic.
- Changes to Netro `set_moisture` action, `ZoneHandler.process_zone_moisture`
  internals, or Whisperer update loop.
- Integration tests against the live Netro API (local testing documented
  separately in `docs/LOCAL_TESTING.md`).
