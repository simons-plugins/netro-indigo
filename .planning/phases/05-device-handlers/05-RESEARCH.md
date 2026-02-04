# Phase 5: Device Handlers - Research

**Researched:** 2026-02-02
**Domain:** Device state update extraction, handler pattern design, Indigo plugin architecture
**Confidence:** HIGH

## Summary

This research investigates the extraction of device update logic from the monolithic plugin.py (1635 lines) into dedicated handler classes (SprinklerHandler and WhispererHandler). The current codebase has all device state update logic embedded in the `_update_from_netro()` method (lines 170-452), which processes API responses and updates Indigo device states.

The research confirms that the standard approach for this refactoring is the **Handler Pattern** with state dictionaries. Handlers receive API data from the API client, transform it into Indigo-compatible state dictionaries, and return these dictionaries to the plugin coordinator for update. This pattern aligns with existing codebase conventions (validators return tuples, api_client returns parsed responses) and the user's locked decision for "full state replacement" on each update.

**Primary recommendation:** Use shared handler instances (one per device type) that receive API response data and return complete state dictionaries, with the plugin coordinator responsible for calling `dev.updateStatesOnServer()`.

## Standard Stack

This phase primarily involves code extraction and restructuring within the existing Python codebase. No new external libraries are required.

### Core
| Module | Version | Purpose | Why Standard |
|--------|---------|---------|--------------|
| device_handlers.py | new | Contains SprinklerHandler and WhispererHandler classes | Follows existing module extraction pattern (api_client.py, validators.py) |
| typing | Python 3.10+ | Type hints for state dictionaries | Already used throughout codebase |
| dataclasses | Python 3.10+ | For optional structured state results | Pattern used in validators.py (PrefsFieldSpec) |

### Supporting
| Module | Version | Purpose | When to Use |
|--------|---------|---------|-------------|
| utils.py | existing | get_key_from_dict helper | Safe dictionary access with fallback values |
| constants.py | existing | State key names, defaults | Centralized constants (extend as needed) |
| exceptions.py | existing | DeviceStateError (new) | Error handling for malformed API data |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Return state dict | Modify device directly | Dict return is more testable, matches validators pattern |
| Shared handlers | Per-device instances | Shared is simpler, handlers have no device-specific state |
| Class-based handlers | Functions | Classes allow shared setup methods, better organization |

**Installation:**
No new packages required - uses existing Python standard library and plugin modules.

## Architecture Patterns

### Recommended Project Structure
```
Server Plugin/
├── plugin.py              # Slim coordinator (~400 lines target)
├── api_client.py          # HTTP communication (existing)
├── validators.py          # Config validation (existing)
├── device_handlers.py     # NEW: SprinklerHandler, WhispererHandler (~260 lines)
├── constants.py           # Constants (existing)
├── exceptions.py          # Exceptions (extend with DeviceStateError)
└── utils.py               # Utilities (existing)
```

### Pattern 1: Handler with State Dictionary Return

**What:** Handler receives API response, returns list of state key-value dicts ready for `updateStatesOnServer()`.

**When to use:** For all device state updates from API polling.

**Example:**
```python
# Source: Codebase pattern from validators.py, api_client.py
from typing import List, Dict, Any, Optional, Tuple

class SprinklerHandler:
    """Handles sprinkler device state updates from API data."""

    def __init__(self, logger):
        """Initialize handler with logger.

        Args:
            logger: Plugin logger instance for error/warning logging
        """
        self.logger = logger

    def process_device_info(
        self,
        api_response: Dict[str, Any],
        serial: str
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """Transform device info API response to state updates.

        Args:
            api_response: Parsed JSON from api_client.get_device_info()
            serial: Device serial number for error context

        Returns:
            Tuple of (state_updates_list, is_online)
            - state_updates_list: List of {'key': str, 'value': Any, 'uiValue'?: str}
            - is_online: True if device status is ONLINE
        """
        try:
            device_data = api_response["data"]["device"]
            meta = api_response.get("meta", {})

            is_online = device_data.get("status") == "ONLINE"

            updates = [
                {"key": "id", "value": device_data.get("serial", serial)},
                {"key": "api_version", "value": device_data.get("version", 0)},
                {"key": "status", "value": device_data.get("status", "UNKNOWN")},
                {"key": "token_remaining", "value": meta.get("token_remaining", 0)},
                # ... more states
            ]

            return (updates, is_online)

        except (KeyError, TypeError) as exc:
            self.logger.error(f"Malformed device info for {serial}: {exc}")
            # Return minimal update marking device offline
            return ([{"key": "status", "value": "ERROR"}], False)
```

### Pattern 2: Coordinator Integration

**What:** Plugin.py calls handlers and applies state updates.

**When to use:** In `_update_from_netro()` and other polling methods.

**Example:**
```python
# Source: Existing plugin.py pattern
class Plugin(indigo.PluginBase):
    def __init__(self, ...):
        # ...
        self.sprinkler_handler = SprinklerHandler(self.logger)
        self.whisperer_handler = WhispererHandler(self.logger)

    def _update_from_netro(self):
        for dev in indigo.devices.iter("self"):
            if not dev.enabled:
                continue

            if dev.deviceTypeId == "sprinkler":
                self._update_sprinkler(dev)
            elif dev.deviceTypeId == "Whisperer":
                self._update_whisperer(dev)

    def _update_sprinkler(self, dev):
        """Update a single sprinkler device."""
        try:
            # Get data from API client
            response = self.api_client.get_device_info(dev.address)

            # Transform via handler
            states, is_online = self.sprinkler_handler.process_device_info(
                response, dev.address
            )

            # Apply to Indigo device
            if states:
                dev.updateStatesOnServer(states)

            # Set error state based on online status
            if is_online:
                dev.setErrorStateOnServer('')
            else:
                dev.setErrorStateOnServer('unavailable')

        except ThrottleDelayError:
            pass  # Already logged by api_client
        except requests.exceptions.RequestException:
            self.logger.exception(f"Network error updating {dev.name}")
            self._fireTrigger("personInfoCall")
```

### Pattern 3: Schedule and Moisture Sub-Handlers

**What:** Methods within handler for different API data types.

**When to use:** For related but separate API calls (schedules, moistures).

**Example:**
```python
# Source: Existing callMoisturesAPI pattern
class SprinklerHandler:
    # ...

    def process_schedules(
        self,
        api_response: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Transform schedules API response to state updates.

        Returns:
            Tuple of (state_updates, active_schedule_name)
        """
        updates = []
        active_name = None

        try:
            schedules = api_response["data"]["schedules"]

            # Find executing schedule
            current = next(
                (s for s in schedules if s["status"] == "EXECUTING"),
                None
            )

            if current:
                active_name = current["source"].title()
                updates.append({"key": "activeZone", "value": current["zone"]})
                updates.append({"key": "activeSchedule", "value": active_name})
            else:
                updates.append({"key": "activeSchedule", "value": "No active schedule"})
                updates.append({"key": "activeZone", "value": 0})

            # Find next valid schedule
            valid_schedules = [s for s in schedules if s["status"] == "VALID"]
            if valid_schedules:
                # Sort by start_time to get next
                next_sched = min(valid_schedules, key=lambda s: s.get("start_time", 0))
                updates.extend(self._format_next_schedule(next_sched))
            else:
                updates.extend(self._no_upcoming_schedule())

            return (updates, active_name)

        except (KeyError, TypeError) as exc:
            self.logger.error(f"Error parsing schedules: {exc}")
            return ([{"key": "activeSchedule", "value": "Error getting schedule"}], None)

    def process_moistures(
        self,
        api_response: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Transform moistures API response to state updates."""
        try:
            moistures = api_response["data"]["moistures"]

            if not moistures:
                return []

            # Sort by ID descending, get most recent date
            moistures.sort(key=lambda x: x.get('id', 0), reverse=True)
            max_date = moistures[0]['date']

            # Get all moistures from most recent date
            recent = [m for m in moistures if m['date'] == max_date]

            return [
                {"key": f"zone_{m['zone']}_moisture", "value": str(m['moisture'])}
                for m in recent
            ]

        except (KeyError, TypeError, IndexError) as exc:
            self.logger.error(f"Error parsing moistures: {exc}")
            return []
```

### Anti-Patterns to Avoid

- **Handler with Indigo imports:** Keep handlers pure Python for testability. Never import `indigo` in device_handlers.py.

- **Handler modifying device directly:** Handler receives API data, returns state dict. Plugin coordinator calls `updateStatesOnServer()`.

- **Handler holding device state:** Handlers should be stateless transforms. Don't cache device state in handler.

- **Multiple API calls in handler:** Handler only transforms data. API calls stay in plugin.py or a dedicated poller.

- **Logging in handler return values:** Log errors internally, don't include log messages in returned state dict.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Safe dict access | Custom try/except everywhere | `get_key_from_dict()` from utils.py | Already exists, handles missing keys gracefully |
| State update batching | Individual updateStateOnServer calls | `dev.updateStatesOnServer([...])` | More efficient, single server roundtrip |
| Timestamp parsing | Manual datetime parsing | Centralize in utils.py (existing pattern) | Consistency, single place to fix bugs |
| API response structure | Custom response wrappers | Dict access with validation | api_client already validates schema |

**Key insight:** The existing api_client already handles HTTP, throttling, and basic schema validation. Handlers only need to transform the validated response data into Indigo state format.

## Common Pitfalls

### Pitfall 1: Modifying indigo.Dict in handler

**What goes wrong:** Handlers receive `dev.states` (an indigo.Dict) and try to modify it, or return it directly.

**Why it happens:** indigo.Dict looks like a regular dict but has special behavior.

**How to avoid:** Always convert to plain dict at handler boundary: `dict(dev.states)`. Return plain dicts from handlers.

**Warning signs:** Type errors about indigo.Dict, state updates not persisting.

### Pitfall 2: Missing state keys cause device errors

**What goes wrong:** Handler returns state update list missing expected keys, causing stale display.

**Why it happens:** API response missing expected data, handler doesn't provide defaults.

**How to avoid:** User decision is "full state replacement" - handlers must return ALL state keys on each update, using sensible defaults for missing data.

**Warning signs:** Device states showing old values, inconsistent UI display.

### Pitfall 3: Offline detection vs API errors

**What goes wrong:** API network errors treated same as device offline status.

**Why it happens:** Both result in "can't get data" but mean different things.

**How to avoid:**
- API client errors -> preserve last known state, don't mark offline
- Device status="OFFLINE" in API response -> mark device unavailable
- Malformed API data -> log error, mark device offline per user decision

**Warning signs:** Devices flapping between online/offline during network hiccups.

### Pitfall 4: Handler logging with indigo logger

**What goes wrong:** Circular import when device_handlers.py imports from plugin that imports device_handlers.

**Why it happens:** Wanting to use self.logger from plugin.

**How to avoid:** Pass logger to handler constructor (same pattern as api_client.py uses callbacks).

**Warning signs:** ImportError on plugin load, circular import tracebacks.

### Pitfall 5: Testing handlers requires Indigo

**What goes wrong:** Tests can't run without Indigo runtime.

**Why it happens:** Handler imports indigo or depends on indigo.Dict.

**How to avoid:** Keep handlers pure Python. Test with plain dicts. No indigo imports in device_handlers.py.

**Warning signs:** Tests requiring Indigo mocks, ImportError in pytest.

## Code Examples

### Complete SprinklerHandler Class Structure

```python
# Source: Pattern from existing validators.py and api_client.py
"""Device handlers for transforming API responses to Indigo state updates.

Handlers are responsible for:
- Parsing API response structure
- Transforming data to Indigo state format
- Providing sensible defaults for missing data
- Logging errors for malformed responses

Handlers do NOT:
- Make API calls (plugin coordinator does this)
- Import indigo (pure Python for testability)
- Modify devices (return state dicts instead)
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from utils import get_key_from_dict


class SprinklerHandler:
    """Handles state transformation for sprinkler controller devices."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize with optional logger."""
        self.logger = logger or logging.getLogger(__name__)

    def process_device_info(
        self,
        api_response: Dict[str, Any],
        serial: str
    ) -> Tuple[List[Dict[str, Any]], bool, Dict[str, Any]]:
        """Process device info API response.

        Args:
            api_response: Response from api_client.get_device_info()
            serial: Device serial for logging context

        Returns:
            Tuple of:
            - List of state update dicts for updateStatesOnServer()
            - is_online: True if device reports ONLINE status
            - device_data: Raw device dict for zone processing
        """
        # Implementation
        pass

    def process_schedules(
        self,
        api_response: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Process schedules API response.

        Returns:
            Tuple of (state_updates, active_schedule_name_or_none)
        """
        pass

    def process_moistures(
        self,
        api_response: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Process moistures API response."""
        pass

    def extract_zone_info(
        self,
        device_data: Dict[str, Any],
        max_zone_runtime: int
    ) -> Tuple[str, List[str], List[Dict[str, Any]]]:
        """Extract zone information for pluginProps update.

        Returns:
            Tuple of (zone_names_csv, max_durations_list, zones_data_list)
        """
        pass


class WhispererHandler:
    """Handles state transformation for Whisperer sensor devices."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)

    def process_sensor_data(
        self,
        api_response: Dict[str, Any],
        serial: str
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """Process sensor data API response.

        Returns:
            Tuple of:
            - List of state update dicts for updateStatesOnServer()
            - has_readings: True if sensor has recent readings
        """
        pass
```

### Testing Pattern for Handlers

```python
# Source: Existing test_validators.py and test_api_client.py patterns
"""Tests for device_handlers.py module.

Tests verify handlers transform API data correctly without Indigo dependency.
"""
import pytest
from device_handlers import SprinklerHandler, WhispererHandler


class TestSprinklerHandler:
    """Tests for SprinklerHandler class."""

    @pytest.fixture
    def handler(self):
        """Create handler with mock logger."""
        from unittest.mock import Mock
        return SprinklerHandler(logger=Mock())

    def test_process_device_info_online(self, handler):
        """Online device returns correct states."""
        api_response = {
            "status": "OK",
            "data": {
                "device": {
                    "serial": "ABC123",
                    "status": "ONLINE",
                    "version": 1,
                    "name": "Test Device",
                    "zones": []
                }
            },
            "meta": {"token_remaining": 1500}
        }

        states, is_online, device_data = handler.process_device_info(
            api_response, "ABC123"
        )

        assert is_online is True
        assert any(s["key"] == "status" and s["value"] == "ONLINE" for s in states)

    def test_process_device_info_offline(self, handler):
        """Offline device returns is_online=False."""
        api_response = {
            "data": {"device": {"status": "OFFLINE", "zones": []}},
            "meta": {}
        }

        states, is_online, _ = handler.process_device_info(api_response, "ABC123")

        assert is_online is False

    def test_process_device_info_malformed(self, handler):
        """Malformed response logs error, returns error state."""
        api_response = {"garbage": "data"}

        states, is_online, _ = handler.process_device_info(api_response, "ABC123")

        assert is_online is False
        handler.logger.error.assert_called()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| All code in plugin.py | Extracted modules (api_client, validators, handlers) | Phase 3-5 | Testable, maintainable, ~400 line coordinator |
| Modify device in polling | Return state dicts from handlers | This phase | Pure Python handlers, no Indigo dependency in handlers |
| Per-update API calls | api_client with throttle management | Phase 3 | Centralized rate limit handling |

**Deprecated/outdated:**
- Single monolithic plugin.py: Being replaced by module extraction
- Direct device modification in polling: Replaced by handler pattern with state dict return

## Open Questions

1. **Zone state keys as dynamic or fixed?**
   - What we know: Devices.xml defines zone_1_moisture through zone_12_moisture as fixed states
   - What's unclear: Should handlers return all 12 zone states or only populated ones?
   - Recommendation: Return only zones that exist in API response. Indigo handles missing state keys gracefully.

2. **Props update timing**
   - What we know: Current code updates pluginProps (ZoneNames, NumZones) during each poll
   - What's unclear: Should props updates happen in handler or stay in coordinator?
   - Recommendation: Handler extracts zone info, coordinator calls replacePluginPropsOnServer(). This keeps Indigo interactions in coordinator.

3. **State image updates**
   - What we know: Whisperer updates state image based on onState (HumiditySensorOn vs HumiditySensor)
   - What's unclear: Should handler return image selector or should coordinator decide?
   - Recommendation: Coordinator handles state image selection. Handler only returns state values.

## Sources

### Primary (HIGH confidence)
- `/Users/simon/vsCodeProjects/Indigo/netro/Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py` - Current implementation (lines 170-564 for device update logic)
- `/Users/simon/vsCodeProjects/Indigo/netro/Netro Sprinklers.indigoPlugin/Contents/Server Plugin/api_client.py` - API client pattern with callback injection
- `/Users/simon/vsCodeProjects/Indigo/netro/Netro Sprinklers.indigoPlugin/Contents/Server Plugin/validators.py` - Pure function pattern with tuple returns
- `/Users/simon/vsCodeProjects/Indigo/Indigo-skill/docs/api/iom/devices.md` - Indigo device API reference
- `/Users/simon/vsCodeProjects/Indigo/Indigo-skill/docs/patterns/api-patterns.md` - updateStatesOnServer batch pattern

### Secondary (MEDIUM confidence)
- `/Users/simon/vsCodeProjects/Indigo/Indigo-skill/docs/concepts/devices.md` - Device lifecycle and state concepts
- Existing test patterns from test_validators.py and test_api_client.py

### Tertiary (LOW confidence)
- None - all patterns verified from codebase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Uses existing codebase patterns and modules
- Architecture: HIGH - Patterns verified from existing api_client.py and validators.py
- Pitfalls: HIGH - Derived from existing code analysis and Indigo documentation

**Research date:** 2026-02-02
**Valid until:** 2026-03-02 (30 days - stable Python patterns, no external dependencies)
