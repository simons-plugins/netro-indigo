# Per-Zone Child Devices Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add per-zone child devices to the Netro plugin so each zone gets its own Indigo device with moisture, schedule, and irrigation states.

**Architecture:** New `zone` custom device type in Devices.xml, auto-created by the parent controller during polling. A new `ZoneHandler` class in `device_handlers.py` transforms existing API responses into per-zone states. Variable subscription auto-links moisture variable writes to the `set_moisture` API.

**Tech Stack:** Python 3.10+, Indigo Plugin SDK, pytest

**Issue:** simons-plugins/netro-indigo#37
**Design:** `docs/plans/2026-04-07-zone-devices-design.md`
**Branch:** `feat/zone-devices`

---

### Task 1: ZoneHandler — extract_zone_states

Extracts `enabled` and `smartMode` from the device info zones array for a single zone.

**Files:**
- Create: `tests/test_zone_handler.py`
- Modify: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/device_handlers.py`

**Step 1: Write the failing test**

In `tests/test_zone_handler.py`:

```python
"""Unit tests for ZoneHandler in device_handlers.py."""
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

SERVER_PLUGIN_DIR = (
    Path(__file__).parent.parent
    / "Netro Sprinklers.indigoPlugin"
    / "Contents"
    / "Server Plugin"
)
sys.path.insert(0, str(SERVER_PLUGIN_DIR))

from device_handlers import ZoneHandler


@pytest.fixture
def mock_logger():
    logger = Mock()
    logger.debug = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    return logger


@pytest.fixture
def zone_handler(mock_logger):
    return ZoneHandler(logger=mock_logger)


@pytest.fixture
def sample_zones():
    return [
        {"ith": 1, "name": "Lawn", "enabled": True, "smart": "SMART"},
        {"ith": 2, "name": "Garden", "enabled": True, "smart": "ASSISTANT"},
        {"ith": 3, "name": "Side Path", "enabled": False, "smart": "TIMER"},
    ]


class TestExtractZoneStates:
    def test_enabled_zone(self, zone_handler, sample_zones):
        states = zone_handler.extract_zone_states(sample_zones, zone_number=1)
        state_dict = {s["key"]: s["value"] for s in states}
        assert state_dict["enabled"] is True
        assert state_dict["smartMode"] == "SMART"

    def test_disabled_zone(self, zone_handler, sample_zones):
        states = zone_handler.extract_zone_states(sample_zones, zone_number=3)
        state_dict = {s["key"]: s["value"] for s in states}
        assert state_dict["enabled"] is False
        assert state_dict["smartMode"] == "TIMER"

    def test_missing_zone_returns_defaults(self, zone_handler, sample_zones):
        states = zone_handler.extract_zone_states(sample_zones, zone_number=99)
        state_dict = {s["key"]: s["value"] for s in states}
        assert state_dict["enabled"] is False
        assert state_dict["smartMode"] == "Unknown"

    def test_empty_zones_list(self, zone_handler):
        states = zone_handler.extract_zone_states([], zone_number=1)
        state_dict = {s["key"]: s["value"] for s in states}
        assert state_dict["enabled"] is False
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/simon/vsCodeProjects/Indigo/netro && python3 -m pytest tests/test_zone_handler.py -v`
Expected: ImportError — `ZoneHandler` not found

**Step 3: Write minimal implementation**

In `device_handlers.py`, add after the `WhispererHandler` class (after line 584):

```python
class ZoneHandler:
    """Handles state transformation for individual zone devices.

    Transforms Netro API responses into per-zone Indigo state updates.
    All data comes from the parent controller's API calls — no extra
    API requests needed.

    Attributes:
        logger: Logger instance for error/debug output
    """

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)

    def extract_zone_states(self, zones, zone_number):
        """Extract enabled and smartMode for a single zone from info data.

        Args:
            zones: List of zone dicts from device_data["zones"]
            zone_number: Zone ith number (1-based)

        Returns:
            List of state update dicts for updateStatesOnServer()
        """
        for zone in zones:
            if zone.get("ith") == zone_number:
                return [
                    {"key": "enabled", "value": zone.get("enabled", False)},
                    {"key": "smartMode", "value": zone.get("smart", "Unknown")},
                ]
        return [
            {"key": "enabled", "value": False},
            {"key": "smartMode", "value": "Unknown"},
        ]
```

Also add `ZoneHandler` to `__all__` at line 36:

```python
__all__ = ["SprinklerHandler", "WhispererHandler", "ZoneHandler"]
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/simon/vsCodeProjects/Indigo/netro && python3 -m pytest tests/test_zone_handler.py -v`
Expected: 4 PASSED

**Step 5: Commit**

```bash
git add tests/test_zone_handler.py "Netro Sprinklers.indigoPlugin/Contents/Server Plugin/device_handlers.py"
git commit -m "feat: add ZoneHandler.extract_zone_states (#37)"
```

---

### Task 2: ZoneHandler — process_zone_schedules

Filters the schedules response to extract per-zone last/next/active watering states.

**Files:**
- Modify: `tests/test_zone_handler.py`
- Modify: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/device_handlers.py`

**Step 1: Write the failing tests**

Add to `tests/test_zone_handler.py`:

```python
@pytest.fixture
def sample_schedules_response():
    """Schedules response with multiple zones and statuses."""
    return {
        "data": {
            "schedules": [
                {
                    "id": 100, "zone": 1, "zone_name": "Lawn",
                    "start_time": 1700000000000, "end_time": 1700000900000,
                    "duration": 900, "source": "SMART", "status": "EXECUTING"
                },
                {
                    "id": 99, "zone": 1, "zone_name": "Lawn",
                    "start_time": 1699990000000, "end_time": 1699990600000,
                    "duration": 600, "source": "FIX", "status": "EXECUTED"
                },
                {
                    "id": 101, "zone": 2, "zone_name": "Garden",
                    "start_time": 1700001000000, "end_time": 1700001600000,
                    "duration": 600, "source": "SMART", "status": "VALID"
                },
                {
                    "id": 98, "zone": 2, "zone_name": "Garden",
                    "start_time": 1699980000000, "end_time": 1699980900000,
                    "duration": 900, "source": "MANUAL", "status": "CANCELLED"
                },
            ]
        }
    }


@pytest.fixture
def sample_v2_schedules_response():
    """V2 schedules with ISO 8601 timestamps."""
    return {
        "data": {
            "schedules": [
                {
                    "id": 200, "zone": 1,
                    "start_time": "2026-04-07T06:00:00",
                    "end_time": "2026-04-07T06:15:00",
                    "local_date": "2026-04-07",
                    "local_start_time": "06:00:00",
                    "local_end_time": "06:15:00",
                    "source": "SMART", "status": "EXECUTED"
                },
                {
                    "id": 201, "zone": 1,
                    "start_time": "2026-04-07T18:00:00",
                    "end_time": "2026-04-07T18:20:00",
                    "local_date": "2026-04-07",
                    "local_start_time": "18:00:00",
                    "local_end_time": "18:20:00",
                    "source": "FIX", "status": "VALID"
                },
            ]
        }
    }


class TestProcessZoneSchedules:
    def test_executing_zone(self, zone_handler, sample_schedules_response):
        states = zone_handler.process_zone_schedules(
            sample_schedules_response, zone_number=1
        )
        state_dict = {s["key"]: s["value"] for s in states}
        assert state_dict["isIrrigating"] is True

    def test_not_executing_zone(self, zone_handler, sample_schedules_response):
        states = zone_handler.process_zone_schedules(
            sample_schedules_response, zone_number=2
        )
        state_dict = {s["key"]: s["value"] for s in states}
        assert state_dict["isIrrigating"] is False

    def test_last_watering_executed(self, zone_handler, sample_schedules_response):
        states = zone_handler.process_zone_schedules(
            sample_schedules_response, zone_number=1
        )
        state_dict = {s["key"]: s["value"] for s in states}
        assert state_dict["lastWateringSource"] == "Fix"
        assert state_dict["lastWateringStatus"] == "Executed"

    def test_last_watering_cancelled(self, zone_handler, sample_schedules_response):
        states = zone_handler.process_zone_schedules(
            sample_schedules_response, zone_number=2
        )
        state_dict = {s["key"]: s["value"] for s in states}
        assert state_dict["lastWateringSource"] == "Manual"
        assert state_dict["lastWateringStatus"] == "Cancelled"

    def test_next_watering(self, zone_handler, sample_schedules_response):
        states = zone_handler.process_zone_schedules(
            sample_schedules_response, zone_number=2
        )
        state_dict = {s["key"]: s["value"] for s in states}
        assert state_dict["nextWateringSource"] == "Smart"

    def test_no_schedules_for_zone(self, zone_handler, sample_schedules_response):
        states = zone_handler.process_zone_schedules(
            sample_schedules_response, zone_number=99
        )
        state_dict = {s["key"]: s["value"] for s in states}
        assert state_dict["isIrrigating"] is False
        assert state_dict["lastWateringStart"] == ""
        assert state_dict["nextWateringStart"] == ""

    def test_empty_schedules(self, zone_handler):
        response = {"data": {"schedules": []}}
        states = zone_handler.process_zone_schedules(response, zone_number=1)
        state_dict = {s["key"]: s["value"] for s in states}
        assert state_dict["isIrrigating"] is False

    def test_v2_timestamps(self, zone_handler, sample_v2_schedules_response):
        states = zone_handler.process_zone_schedules(
            sample_v2_schedules_response, zone_number=1, api_version="2"
        )
        state_dict = {s["key"]: s["value"] for s in states}
        assert "2026-04-07" in state_dict["lastWateringStart"]
        assert "2026-04-07" in state_dict["nextWateringStart"]
        assert state_dict["lastWateringSource"] == "Smart"
        assert state_dict["nextWateringSource"] == "Fix"
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/simon/vsCodeProjects/Indigo/netro && python3 -m pytest tests/test_zone_handler.py::TestProcessZoneSchedules -v`
Expected: AttributeError — `process_zone_schedules` not found

**Step 3: Write implementation**

Add to `ZoneHandler` in `device_handlers.py`:

```python
    def process_zone_schedules(self, api_response, zone_number, api_version="1"):
        """Process schedules response for a single zone.

        Extracts isIrrigating, last watering, and next watering states
        for the given zone number.

        Args:
            api_response: Response from api_client.get_schedules()
            zone_number: Zone ith number (1-based)
            api_version: API version ("1" or "2")

        Returns:
            List of state update dicts for updateStatesOnServer()
        """
        is_irrigating = False
        last_schedule = None
        next_schedule = None
        next_start_sort = None

        try:
            schedules = api_response["data"]["schedules"]
            zone_schedules = [s for s in schedules if s.get("zone") == zone_number]

            for sch in zone_schedules:
                status = sch.get("status", "")
                if status == "EXECUTING":
                    is_irrigating = True
                elif status in ("EXECUTED", "CANCELLED"):
                    # Most recent past schedule (highest ID)
                    if last_schedule is None or sch.get("id", 0) > last_schedule.get("id", 0):
                        last_schedule = sch
                elif status == "VALID":
                    sort_key = SprinklerHandler._parse_schedule_sort_key(
                        sch.get("start_time", 0), api_version
                    )
                    if next_start_sort is None or sort_key < next_start_sort:
                        next_start_sort = sort_key
                        next_schedule = sch

        except (KeyError, TypeError) as exc:
            self.logger.error(f"Error parsing zone schedules: {exc}")

        states = [{"key": "isIrrigating", "value": is_irrigating}]
        states.extend(self._format_last_watering(last_schedule, api_version))
        states.extend(self._format_next_watering(next_schedule, api_version))
        return states

    def _format_last_watering(self, schedule, api_version="1"):
        """Format last watering states from a schedule dict."""
        if not schedule:
            return [
                {"key": "lastWateringStart", "value": ""},
                {"key": "lastWateringEnd", "value": ""},
                {"key": "lastWateringSource", "value": ""},
                {"key": "lastWateringStatus", "value": ""},
            ]
        return [
            {"key": "lastWateringStart", "value": self._format_timestamp(schedule.get("start_time"), api_version)},
            {"key": "lastWateringEnd", "value": self._format_timestamp(schedule.get("end_time"), api_version)},
            {"key": "lastWateringSource", "value": schedule.get("source", "Unknown").title()},
            {"key": "lastWateringStatus", "value": schedule.get("status", "Unknown").title()},
        ]

    def _format_next_watering(self, schedule, api_version="1"):
        """Format next watering states from a schedule dict."""
        if not schedule:
            return [
                {"key": "nextWateringStart", "value": ""},
                {"key": "nextWateringEnd", "value": ""},
                {"key": "nextWateringSource", "value": ""},
            ]
        return [
            {"key": "nextWateringStart", "value": self._format_timestamp(schedule.get("start_time"), api_version)},
            {"key": "nextWateringEnd", "value": self._format_timestamp(schedule.get("end_time"), api_version)},
            {"key": "nextWateringSource", "value": schedule.get("source", "Unknown").title()},
        ]

    @staticmethod
    def _format_timestamp(raw_value, api_version="1"):
        """Format a timestamp for display.

        Args:
            raw_value: ms timestamp (v1) or ISO 8601 string (v2)
            api_version: "1" or "2"

        Returns:
            Formatted datetime string, or "" if unparseable
        """
        if not raw_value:
            return ""
        try:
            if api_version == "2":
                dt = datetime.fromisoformat(str(raw_value))
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            else:
                ms = float(raw_value) if isinstance(raw_value, str) else float(raw_value)
                dt = datetime.fromtimestamp(ms / 1000.0)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError, OSError):
            return ""
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/simon/vsCodeProjects/Indigo/netro && python3 -m pytest tests/test_zone_handler.py -v`
Expected: All PASSED

**Step 5: Commit**

```bash
git add tests/test_zone_handler.py "Netro Sprinklers.indigoPlugin/Contents/Server Plugin/device_handlers.py"
git commit -m "feat: add ZoneHandler.process_zone_schedules (#37)"
```

---

### Task 3: ZoneHandler — process_zone_moisture

Extracts the moisture value for a single zone from the moistures response.

**Files:**
- Modify: `tests/test_zone_handler.py`
- Modify: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/device_handlers.py`

**Step 1: Write the failing tests**

Add to `tests/test_zone_handler.py`:

```python
@pytest.fixture
def sample_moistures_response():
    return {
        "data": {
            "moistures": [
                {"id": 50, "zone": 1, "moisture": 65, "date": "2026-04-07"},
                {"id": 51, "zone": 2, "moisture": 42, "date": "2026-04-07"},
                {"id": 40, "zone": 1, "moisture": 55, "date": "2026-04-06"},
            ]
        }
    }


class TestProcessZoneMoisture:
    def test_zone_moisture(self, zone_handler, sample_moistures_response):
        states = zone_handler.process_zone_moisture(
            sample_moistures_response, zone_number=1
        )
        state_dict = {s["key"]: s["value"] for s in states}
        assert state_dict["moisture"] == 65

    def test_zone_moisture_latest_date(self, zone_handler, sample_moistures_response):
        """Should return most recent date's reading, not older ones."""
        states = zone_handler.process_zone_moisture(
            sample_moistures_response, zone_number=1
        )
        state_dict = {s["key"]: s["value"] for s in states}
        assert state_dict["moisture"] == 65  # from 2026-04-07, not 55 from 04-06

    def test_zone_not_found(self, zone_handler, sample_moistures_response):
        states = zone_handler.process_zone_moisture(
            sample_moistures_response, zone_number=99
        )
        state_dict = {s["key"]: s["value"] for s in states}
        assert state_dict["moisture"] == 0

    def test_empty_moistures(self, zone_handler):
        response = {"data": {"moistures": []}}
        states = zone_handler.process_zone_moisture(response, zone_number=1)
        state_dict = {s["key"]: s["value"] for s in states}
        assert state_dict["moisture"] == 0
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/simon/vsCodeProjects/Indigo/netro && python3 -m pytest tests/test_zone_handler.py::TestProcessZoneMoisture -v`
Expected: AttributeError — `process_zone_moisture` not found

**Step 3: Write implementation**

Add to `ZoneHandler` in `device_handlers.py`:

```python
    def process_zone_moisture(self, api_response, zone_number):
        """Extract moisture for a single zone from moistures response.

        Uses the most recent date's reading for the zone.

        Args:
            api_response: Response from api_client.get_moistures()
            zone_number: Zone ith number (1-based)

        Returns:
            List with single moisture state update dict
        """
        try:
            moistures = api_response["data"]["moistures"]
            if not moistures:
                return [{"key": "moisture", "value": 0}]

            # Sort by ID descending to get most recent first
            moistures_sorted = sorted(moistures, key=lambda x: x.get("id", 0), reverse=True)
            max_date = moistures_sorted[0].get("date")

            # Find this zone's reading on the most recent date
            for m in moistures_sorted:
                if m.get("zone") == zone_number and m.get("date") == max_date:
                    return [{"key": "moisture", "value": m.get("moisture", 0)}]

            return [{"key": "moisture", "value": 0}]

        except (KeyError, TypeError, IndexError) as exc:
            self.logger.error(f"Error parsing zone moisture: {exc}")
            return [{"key": "moisture", "value": 0}]
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/simon/vsCodeProjects/Indigo/netro && python3 -m pytest tests/test_zone_handler.py -v`
Expected: All PASSED

**Step 5: Commit**

```bash
git add tests/test_zone_handler.py "Netro Sprinklers.indigoPlugin/Contents/Server Plugin/device_handlers.py"
git commit -m "feat: add ZoneHandler.process_zone_moisture (#37)"
```

---

### Task 4: Devices.xml — add zone device type, remove controller moisture states

**Files:**
- Modify: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/Devices.xml`

**Step 1: Remove the 12 `zone_N_moisture` states**

In `Devices.xml`, delete lines 152-212 (the `<State id="zone_1_moisture">` through `<State id="zone_12_moisture">` blocks).

**Step 2: Add the zone device type**

After the closing `</Device>` tag of the Whisperer device (line ~337 after deletions), add:

```xml
    <Device type="custom" id="zone">
        <Name>Netro Zone</Name>
        <ConfigUI>
            <Field id="parentDeviceId" type="textfield" hidden="true">
                <Label/>
            </Field>
            <Field id="zoneNumber" type="textfield" hidden="true">
                <Label/>
            </Field>
        </ConfigUI>
        <States>
            <State id="moisture">
                <ValueType>Integer</ValueType>
                <TriggerLabel>Moisture Level (%)</TriggerLabel>
                <ControlPageLabel>Moisture Level (%)</ControlPageLabel>
            </State>
            <State id="enabled">
                <ValueType>Boolean</ValueType>
                <TriggerLabel>Zone Enabled</TriggerLabel>
                <ControlPageLabel>Zone Enabled</ControlPageLabel>
            </State>
            <State id="smartMode">
                <ValueType>String</ValueType>
                <TriggerLabel>Smart Mode</TriggerLabel>
                <ControlPageLabel>Smart Mode</ControlPageLabel>
            </State>
            <State id="isIrrigating">
                <ValueType>Boolean</ValueType>
                <TriggerLabel>Currently Irrigating</TriggerLabel>
                <ControlPageLabel>Currently Irrigating</ControlPageLabel>
            </State>
            <State id="lastWateringStart">
                <ValueType>String</ValueType>
                <TriggerLabel>Last Watering Start</TriggerLabel>
                <ControlPageLabel>Last Watering Start</ControlPageLabel>
            </State>
            <State id="lastWateringEnd">
                <ValueType>String</ValueType>
                <TriggerLabel>Last Watering End</TriggerLabel>
                <ControlPageLabel>Last Watering End</ControlPageLabel>
            </State>
            <State id="lastWateringSource">
                <ValueType>String</ValueType>
                <TriggerLabel>Last Watering Source</TriggerLabel>
                <ControlPageLabel>Last Watering Source</ControlPageLabel>
            </State>
            <State id="lastWateringStatus">
                <ValueType>String</ValueType>
                <TriggerLabel>Last Watering Status</TriggerLabel>
                <ControlPageLabel>Last Watering Status</ControlPageLabel>
            </State>
            <State id="nextWateringStart">
                <ValueType>String</ValueType>
                <TriggerLabel>Next Watering Start</TriggerLabel>
                <ControlPageLabel>Next Watering Start</ControlPageLabel>
            </State>
            <State id="nextWateringEnd">
                <ValueType>String</ValueType>
                <TriggerLabel>Next Watering End</TriggerLabel>
                <ControlPageLabel>Next Watering End</ControlPageLabel>
            </State>
            <State id="nextWateringSource">
                <ValueType>String</ValueType>
                <TriggerLabel>Next Watering Source</TriggerLabel>
                <ControlPageLabel>Next Watering Source</ControlPageLabel>
            </State>
        </States>
        <UiDisplayStateId>moisture</UiDisplayStateId>
    </Device>
```

**Step 3: Commit**

```bash
git add "Netro Sprinklers.indigoPlugin/Contents/Server Plugin/Devices.xml"
git commit -m "feat: add zone device type, remove controller moisture states (#37)"
```

---

### Task 5: Actions.xml — add setZoneMoisture action

**Files:**
- Modify: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/Actions.xml`

**Step 1: Add the zone moisture action**

Before the closing `</Actions>` tag, add:

```xml
    <Action id="setZoneMoisture" deviceFilter="self.zone" uiPath="DeviceActions">
        <Name>Set Zone Moisture Override</Name>
        <CallbackMethod>setZoneMoisture</CallbackMethod>
        <ConfigUI>
            <Field type="label" id="zone_moisture_warning_label" fontColor="orange">
                <Label>Warning: Overriding moisture levels affects Netro's smart scheduling. Use with caution.</Label>
            </Field>
            <Field type="textfield" id="moisture" defaultValue="50">
                <Label>Moisture Level (%):</Label>
            </Field>
            <Field type="label" id="zone_moisture_label" alignWithControl="true" fontSize="small" fontColor="darkgray">
                <Label>Moisture percentage (0-100). This overrides Netro's calculated moisture for this zone.</Label>
            </Field>
        </ConfigUI>
    </Action>
```

**Step 2: Commit**

```bash
git add "Netro Sprinklers.indigoPlugin/Contents/Server Plugin/Actions.xml"
git commit -m "feat: add setZoneMoisture action for zone devices (#37)"
```

---

### Task 6: plugin.py — zone auto-creation and state updates

This is the core integration task. Adds zone device auto-creation during the controller poll cycle, and populates zone states from existing API responses.

**Files:**
- Modify: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py`

**Step 1: Import ZoneHandler**

At `plugin.py:64`, change:

```python
from device_handlers import SprinklerHandler, WhispererHandler
```

to:

```python
from device_handlers import SprinklerHandler, WhispererHandler, ZoneHandler
```

**Step 2: Initialize ZoneHandler in `__init__`**

After `plugin.py:131` (`self.whisperer_handler = WhispererHandler(self.logger)`), add:

```python
        self.zone_handler = ZoneHandler(self.logger)
```

**Step 3: Add `_get_zone_devices` helper**

After the `_get_device_auth` method (after line 335), add:

```python
    def _get_zone_devices(self, parent_dev_id):
        """Get all zone devices belonging to a parent controller.

        Args:
            parent_dev_id: Indigo device ID of the parent controller

        Returns:
            Dict mapping zone number (int) to Indigo device
        """
        zone_devs = {}
        for dev in indigo.devices.iter(filter="self.zone"):
            if dev.pluginProps.get("parentDeviceId") == str(parent_dev_id):
                zone_num = int(dev.pluginProps.get("zoneNumber", 0))
                if zone_num > 0:
                    zone_devs[zone_num] = dev
        return zone_devs

    def _ensure_zone_devices(self, parent_dev, zones_data):
        """Create or update zone devices for a parent controller.

        Auto-creates zone devices for zones returned by the API.
        Updates device names if the zone was renamed in Netro.

        Args:
            parent_dev: Indigo sprinkler controller device
            zones_data: List of zone dicts from extract_zone_info
                        (each has "id", "name", "enabled")
        """
        existing = self._get_zone_devices(parent_dev.id)

        for zone in zones_data:
            zone_num = zone["id"]
            zone_name = zone.get("name", f"Zone {zone_num}")
            expected_name = f"{parent_dev.name} - {zone_name}"

            if zone_num in existing:
                # Update name if zone was renamed
                zone_dev = existing[zone_num]
                if zone_dev.name != expected_name:
                    self.logger.info(
                        f"Zone renamed: '{zone_dev.name}' -> '{expected_name}'"
                    )
                    zone_dev.name = expected_name
                    zone_dev.replaceOnServer()
            else:
                # Create new zone device
                try:
                    props = {
                        "parentDeviceId": str(parent_dev.id),
                        "zoneNumber": str(zone_num),
                    }
                    new_dev = indigo.device.create(
                        protocol=indigo.kProtocol.Plugin,
                        deviceTypeId="zone",
                        name=expected_name,
                        props=props,
                    )
                    new_dev.model = "Netro Zone"
                    new_dev.subModel = zone_name
                    new_dev.replaceOnServer()
                    self.logger.info(
                        f"Created zone device '{expected_name}' "
                        f"(zone {zone_num} on '{parent_dev.name}')"
                    )
                except Exception as exc:
                    self.logger.error(
                        f"Could not create zone device for zone {zone_num} "
                        f"on '{parent_dev.name}': {exc}"
                    )
```

**Step 4: Add `_update_zone_devices` method**

After `_ensure_zone_devices`, add:

```python
    def _update_zone_devices(self, parent_dev, device_data, schedule_response, moisture_response, api_version):
        """Update all zone devices for a parent controller.

        Args:
            parent_dev: Indigo sprinkler controller device
            device_data: Raw device dict from info API (contains zones array)
            schedule_response: Raw schedules API response (or None)
            moisture_response: Raw moistures API response (or None)
            api_version: "1" or "2"
        """
        zone_devs = self._get_zone_devices(parent_dev.id)
        zones = device_data.get("zones", [])

        for zone_dev in zone_devs.values():
            zone_num = int(zone_dev.pluginProps.get("zoneNumber", 0))
            if zone_num == 0:
                continue

            states = []

            # Zone info states (enabled, smartMode)
            states.extend(self.zone_handler.extract_zone_states(zones, zone_num))

            # Schedule states (isIrrigating, last/next watering)
            if schedule_response:
                states.extend(
                    self.zone_handler.process_zone_schedules(
                        schedule_response, zone_num, api_version=api_version
                    )
                )

            # Moisture state
            if moisture_response:
                states.extend(
                    self.zone_handler.process_zone_moisture(moisture_response, zone_num)
                )

            if states:
                zone_dev.updateStatesOnServer(states)
```

**Step 5: Integrate into `_update_sprinkler_device`**

In `_update_sprinkler_device` (around line 366), the method currently calls info, schedules, moistures, then updates zone variables. We need to:

1. Store the schedule and moisture responses
2. Call `_ensure_zone_devices` after zone info extraction
3. Call `_update_zone_devices` with all responses

Modify `_update_sprinkler_device` to store responses and add zone device calls. After the moisture try/except block (around line 437) and before `_ensure_zone_variables`, add:

```python
            # Auto-create and update zone devices
            self._ensure_zone_devices(dev, zones_data)
            self._update_zone_devices(
                dev, device_data,
                schedule_response=schedule_dict if 'schedule_dict' in dir() else None,
                moisture_response=moisture_dict if 'moisture_dict' in dir() else None,
                api_version=api_version,
            )
```

**Important**: The `schedule_dict` and `moisture_dict` variables need to be initialized to `None` before their try/except blocks so they're available later. Add at the start of the try block (after line 372):

```python
            schedule_dict = None
            moisture_dict = None
```

Then update the schedule try block to assign:

```python
            try:
                schedule_dict = self.api_client.get_schedules(key, api_version=api_version)
                schedule_states, active_schedule_name = self.sprinkler_handler.process_schedules(
                    schedule_dict, api_version=api_version
                )
```

And the moisture try block:

```python
            try:
                moisture_dict = self.api_client.get_moistures(key, api_version=api_version)
                moisture_states = self.sprinkler_handler.process_moistures(
```

**Step 6: Remove controller moisture state updates**

The existing `process_moistures` call on the controller updates `zone_N_moisture` states which we've removed from Devices.xml. Remove the controller moisture state update (the `dev.updateStatesOnServer(moisture_states)` call around line 435) but keep the `moisture_dict` fetch since zone devices need it. Change:

```python
            try:
                moisture_dict = self.api_client.get_moistures(key, api_version=api_version)
                moisture_states = self.sprinkler_handler.process_moistures(
                    moisture_dict, api_version=api_version
                )
                if moisture_states:
                    dev.updateStatesOnServer(moisture_states)
```

to:

```python
            try:
                moisture_dict = self.api_client.get_moistures(key, api_version=api_version)
```

**Step 7: Run existing tests to check nothing is broken**

Run: `cd /Users/simon/vsCodeProjects/Indigo/netro && python3 -m pytest tests/ -v`
Expected: All PASSED (zone handler tests + existing tests)

**Step 8: Commit**

```bash
git add "Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py"
git commit -m "feat: auto-create zone devices and populate states during poll (#37)"
```

---

### Task 7: plugin.py — setZoneMoisture action callback

**Files:**
- Modify: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py`

**Step 1: Add the action callback**

After the existing `setMoisture` method (after line 1102), add:

```python
    def setZoneMoisture(self, pluginAction, dev):
        """Override moisture for this zone device.

        Looks up the parent controller's auth credentials and calls
        set_moisture API for this zone.

        Args:
            pluginAction: Action parameters containing moisture value
            dev: Zone device
        """
        try:
            zone_num = int(dev.pluginProps.get("zoneNumber", 0))
            parent_id = int(dev.pluginProps.get("parentDeviceId", 0))
            parent_dev = indigo.devices[parent_id]

            moisture_raw = self.substitute(pluginAction.props.get("moisture", ""))
            try:
                moisture = int(float(moisture_raw))
            except (ValueError, TypeError):
                self.logger.error(
                    f"Moisture value '{moisture_raw}' is not a valid number"
                )
                return

            if moisture < 0 or moisture > 100:
                self.logger.error(f"Moisture value {moisture} is out of range (0-100)")
                return

            key, api_version = self._get_device_auth(parent_dev)
            response = self.api_client.set_moisture(key, zone_num, moisture, api_version=api_version)
            if response.get("status") == "OK":
                self.logger.info(f"Moisture for '{dev.name}' set to {moisture}%")
                dev.updateStateOnServer("moisture", moisture)
            else:
                self.logger.error(f"Error setting moisture for '{dev.name}': {response.get('status')}")
        except KeyError:
            self.logger.error(
                f"Parent controller (ID {dev.pluginProps.get('parentDeviceId')}) "
                f"not found for zone '{dev.name}'"
            )
        except Exception:
            self.logger.error(f"Could not set moisture for '{dev.name}'")
            self.logger.debug(f"API error: \n{traceback.format_exc(10)}")
```

**Step 2: Commit**

```bash
git add "Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py"
git commit -m "feat: add setZoneMoisture action callback (#37)"
```

---

### Task 8: plugin.py — variable subscription auto-link

Subscribe to variable changes and auto-call `set_moisture` API when a zone moisture variable is updated.

**Files:**
- Modify: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py`

**Step 1: Add variable subscription in `startup()`**

In `plugin.py:586` (the `startup` method), add after the existing logging:

```python
        # Subscribe to variable changes for zone moisture auto-link
        indigo.variables.subscribeToChanges()
```

**Step 2: Add `variableUpdated` callback**

After the `triggerStopProcessing` method (after line 911), add:

```python
    def variableUpdated(self, origVar, newVar):
        """Called when any subscribed variable changes.

        Checks if the variable is a zone moisture variable. If so,
        calls set_moisture API for the corresponding zone.

        Args:
            origVar: Variable before change
            newVar: Variable after change
        """
        # Only act on value changes
        if origVar.value == newVar.value:
            return

        # Search all sprinkler devices for a zone variable mapping that matches
        for dev in indigo.devices.iter(filter="self.sprinkler"):
            mapping_json = dev.pluginProps.get("zoneVariableMap", "{}")
            try:
                zone_var_map = json.loads(mapping_json)
            except (json.JSONDecodeError, TypeError):
                continue

            for zone_num, var_info in zone_var_map.items():
                if str(var_info.get("var_id")) == str(newVar.id):
                    # Found the matching zone — call set_moisture
                    try:
                        moisture = int(float(newVar.value))
                    except (ValueError, TypeError):
                        self.logger.warning(
                            f"Zone moisture variable '{newVar.name}' has "
                            f"non-numeric value '{newVar.value}', ignoring"
                        )
                        return

                    if moisture < 0 or moisture > 100:
                        self.logger.warning(
                            f"Zone moisture variable '{newVar.name}' value "
                            f"{moisture} out of range (0-100), ignoring"
                        )
                        return

                    key, api_version = self._get_device_auth(dev)
                    try:
                        response = self.api_client.set_moisture(
                            key, int(zone_num), moisture, api_version=api_version
                        )
                        if response.get("status") == "OK":
                            self.logger.info(
                                f"Auto-set moisture for zone {zone_num} on "
                                f"'{dev.name}' to {moisture}% "
                                f"(from variable '{newVar.name}')"
                            )
                            # Update the zone device state too
                            zone_devs = self._get_zone_devices(dev.id)
                            if int(zone_num) in zone_devs:
                                zone_devs[int(zone_num)].updateStateOnServer(
                                    "moisture", moisture
                                )
                        else:
                            self.logger.error(
                                f"Error auto-setting moisture for zone {zone_num}: "
                                f"{response.get('status')}"
                            )
                    except Exception:
                        self.logger.error(
                            f"API error auto-setting moisture for zone {zone_num}"
                        )
                        self.logger.debug(f"API error: \n{traceback.format_exc(10)}")
                    return  # Found match, stop searching
```

**Step 3: Commit**

```bash
git add "Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py"
git commit -m "feat: auto-link zone moisture variables to set_moisture API (#37)"
```

---

### Task 9: Validators — add zone device validation

**Files:**
- Modify: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/validators.py`
- Modify: `tests/test_validators.py`

**Step 1: Update `validate_device_config` to handle zone type**

In `validators.py`, the `validate_device_config` function validates by `typeId`. Add a case for `"zone"` that accepts the config as-is (hidden fields, nothing to validate from user input):

Find the `validate_device_config` function and add an early return for zone devices:

```python
    if type_id == "zone":
        return (True, values, {})
```

**Step 2: Add a test**

In `tests/test_validators.py`, add:

```python
def test_zone_device_config_always_valid():
    is_valid, sanitized, errors = validate_device_config(
        {"parentDeviceId": "123", "zoneNumber": "1"}, "zone"
    )
    assert is_valid is True
    assert errors == {}
```

**Step 3: Run tests**

Run: `cd /Users/simon/vsCodeProjects/Indigo/netro && python3 -m pytest tests/test_validators.py -v`
Expected: All PASSED

**Step 4: Commit**

```bash
git add "Netro Sprinklers.indigoPlugin/Contents/Server Plugin/validators.py" tests/test_validators.py
git commit -m "feat: add zone device type validation (#37)"
```

---

### Task 10: Version bump and final verification

**Files:**
- Modify: `Netro Sprinklers.indigoPlugin/Contents/Info.plist`

**Step 1: Bump version**

In `Info.plist`, change `PluginVersion` from `2026.0.1` to `2026.1.0` (minor bump for feature addition).

**Step 2: Run full test suite**

Run: `cd /Users/simon/vsCodeProjects/Indigo/netro && python3 -m pytest tests/ -v`
Expected: All PASSED

**Step 3: Commit**

```bash
git add "Netro Sprinklers.indigoPlugin/Contents/Info.plist"
git commit -m "chore: bump version to 2026.1.0 for zone devices feature (#37)"
```

**Step 4: Push and create PR**

```bash
git push -u origin feat/zone-devices
```

Create PR referencing issue #37 with summary of changes.
