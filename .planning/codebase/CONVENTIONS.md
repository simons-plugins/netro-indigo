# Coding Conventions

**Analysis Date:** 2026-02-01

## Naming Patterns

**Files:**
- Single file `plugin.py` in `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/`
- XML configuration files with PascalCase names: `Devices.xml`, `Actions.xml`, `Events.xml`, `PluginConfig.xml`, `MenuItems.xml`
- Documentation files: `NETRO_API.md`, `API_NOTES.md`, `TESTING.md`, `TROUBLESHOOTING.md`

**Functions:**
- Module-level helper functions use `snake_case`: `convert_timestamp()`, `get_key_from_dict()`
- Class methods use `snake_case`: `_make_api_call()`, `_update_from_netro()`, `actionControlSprinkler()`
- Private methods (internal to class) prefixed with single underscore: `_make_api_call()`, `_get_device_dict()`, `_fireTrigger()`
- Public callback methods follow Indigo conventions: `validateDeviceConfigUi()`, `deviceStartComm()`, `triggerStartProcessing()`

**Variables:**
- Instance attributes use `camelCase`: `serialNo`, `pollingInterval`, `throttle_next_call`, `triggerDict`
- Local variables use `snake_case`: `reply_dict`, `update_list`, `current_schedule_dict`, `sensorReadings`
- Constants use `UPPER_SNAKE_CASE`: `NETRO_API_VERSION`, `MINIMUM_POLLING_INTERVAL`, `DEFAULT_API_CALL_TIMEOUT`, `THROTTLE_LIMIT_TIMER`

**Types:**
- Custom exceptions use PascalCase: `ThrottleDelayError`
- Class names use PascalCase: `Plugin` (inherits `indigo.PluginBase`)
- Device type IDs use lowercase with underscores in XML, referenced as strings: `"sprinkler"`, `"Whisperer"`

## Code Style

**Formatting:**
- PEP 8 compliant with some exceptions for Indigo API conventions
- Line length up to 120 characters (noted in pylint command)
- 4-space indentation
- Blank lines: Two between top-level definitions, one between method definitions

**Linting:**
- Pylint used for static analysis (target score: 8.0, current: ~6.5/10)
- Pylint disable directives placed inline for specific methods:
  ```python
  # pylint: disable=too-many-lines
  # pylint: disable=invalid-name
  # pylint: disable=too-many-branches,too-many-statements
  # pylint: disable=unused-argument
  ```
- File-level disable at top: `# pylint: disable=too-many-lines`
- Method-level disables immediately before method definition

## Import Organization

**Order:**
1. Standard library imports (`json`, `copy`, `traceback`, `datetime`)
2. Third-party library imports (`requests`, `dateutil`)
3. Indigo SDK imports (`indigo`)

**Pattern observed:**
```python
import json
import copy
import traceback
from operator import itemgetter
from datetime import datetime, timedelta, date

import indigo
import requests
from dateutil import tz
```

**Path Aliases:**
Not used in this codebase. All imports are fully qualified.

## Error Handling

**Patterns:**
- Broad `try/except` blocks with specific exception types handled differently
- Custom exception: `ThrottleDelayError` for rate limit violations
- Defensive exception handling with graceful fallbacks

**API Error Pattern** (`_make_api_call()` at `plugin.py:195-334`):
```python
try:
    # Attempt request
    r = requests.get(url, headers=self.headers, timeout=self.timeout)
except requests.exceptions.ConnectionError as exc:
    # Handle with flag to avoid duplicate logging
    if not self._displayed_connection_error:
        self.logger.error("Connection failed...")
        self._displayed_connection_error = True
    raise exc
except requests.exceptions.HTTPError as exc:
    # Specific handling for Netro error codes
    error_data = exc.response.json()
    if error_data.get("status") == "ERROR":
        # Process error codes 1 (invalid key), 3 (rate limit)
    raise exc
except ThrottleDelayError:
    raise  # Re-raise after logging in _make_api_call
except Exception as exc:
    self.logger.error(f"Connection failed: {exc.__class__.__name__}")
    self.logger.debug(f"Full traceback:\n{traceback.format_exc(10)}")
    raise exc
```

**Defensive Parsing Pattern:**
```python
try:
    value = int(some_value)
except (ValueError, TypeError):
    value = default_value
    self.logger.debug("Invalid value, using default")
```

**Silent Loop Exception Pattern** (`runConcurrentThread()` at `plugin.py:810-829`):
```python
while True:
    try:
        self._update_from_netro()
    except (Exception,):
        # Swallow all exceptions to prevent thread exit
        # Detailed logging happens in _update_from_netro()
        pass
    self.sleep(self.pollingInterval * 60)
```

## Logging

**Framework:** Indigo's built-in `self.logger` (inherits from `indigo.PluginBase`)

**Patterns:**
- `self.logger.debug()` - Detailed operation logs, API calls, data structures
- `self.logger.info()` - Normal operation (plugin start, status changes, successful actions)
- `self.logger.warning()` - Warnings (API tokens low, unusual conditions)
- `self.logger.error()` - Errors (API failures, invalid config, failed actions)
- Special method: `self.logger.threaddebug()` - Debug in callback context

**Usage examples:**
```python
self.logger.debug(f"API call: {request_method.upper()} {url}")
self.logger.info(f"Polling interval updated to {self.pollingInterval} minutes")
self.logger.warning(f"api tokens low: {tokens_remaining} of 2000 remaining")
self.logger.error("Connection to Netro API server failed")
self.logger.debug(f"traceback:\n{traceback.format_exc(10)}")
self.logger.threaddebug("validateDeviceConfigUi")
```

**Error suppression pattern:**
```python
if not self._displayed_connection_error:
    self.logger.error("Connection failed. Will retry silently.")
    self._displayed_connection_error = True
```

## Comments

**When to Comment:**
- Complex business logic (e.g., timestamp parsing, zone data transformation)
- Non-obvious API behavior (e.g., "API returns timestamps as string numbers")
- Important warnings or caveats
- Section dividers for large methods

**Examples:**
```python
# Check if we're in a throttle period
if self.throttle_next_call and datetime.now() < self.throttle_next_call:
    raise ThrottleDelayError(...)

# Handle start_time as either string or number
start_time_raw = sch_dict.get("start_time", 0)
try:
    start_time = (float(start_time_raw) if isinstance(start_time_raw, str)
                  else start_time_raw)
except (ValueError, TypeError):
    start_time = 0
```

**Docstring Format:** Google-style docstrings with triple quotes

```python
def convert_timestamp(timestamp):
    """Convert Unix timestamp (milliseconds) to local timezone datetime.

    Args:
        timestamp: Unix timestamp in milliseconds

    Returns:
        datetime: Timestamp converted to local timezone
    """
```

**JSDoc/Type Hints:**
- Method docstrings required for all public and private methods
- Args, Returns, Raises sections consistently used
- No Python type hints (project uses Python 3.10+ but opts for docstring-only documentation)
- Exception documentation in Raises section when applicable

## Function Design

**Size:**
- Most methods range 15-100 lines
- Large update method `_update_from_netro()` is 260 lines (marked with `pylint: disable=too-many-branches,too-many-statements`)
- Typically broken into logical sections with comment dividers

**Parameters:**
- Device callbacks use standard Indigo signatures: `(self, dev)`, `(self, action, dev)`, `(self, valuesDict, typeId, devId)`
- Optional parameters provided with defaults: `def _make_api_call(self, url, request_method="get", data=None)`
- Dictionary parameters (valuesDict) extensively used for configuration passing

**Return Values:**
- Most methods return None or single value
- Validation methods return tuple: `(bool, dict, dict)` - `(is_valid, valuesDict, errorsDict)`
- Configuration lists return tuples: `[(id, name), ...]`
- API methods return JSON dict or True (for 204 No Content responses)

## Module Design

**Exports:**
- Single class `Plugin` exported implicitly (main entry point for Indigo)
- Module-level functions: `convert_timestamp()`, `get_key_from_dict()`
- All other implementation is in `Plugin` class

**Barrel Files:**
- Not used. Single monolithic file approach: `plugin.py` (1600+ lines)

**Class Structure:**
- Single `Plugin` class inheriting `indigo.PluginBase`
- Organized by functional group with comment section dividers:
  - Internal helper methods
  - Lifecycle methods (startup, shutdown, concurrent thread)
  - Dialog list callbacks
  - Validation callbacks
  - Device callbacks
  - Event callbacks
  - Action callbacks
  - Menu callbacks

**Organization sections:**
```python
########################################
# Internal helper methods
########################################

########################################
# startup, concurrent thread, and shutdown methods
########################################

########################################
# Dialog list callbacks
########################################
```

## API Constants

**Convention:** All API endpoints and configuration defined at module top (`plugin.py:49-73`):
```python
NETRO_API_VERSION = "1"
NETRO_MAX_ZONE_DURATION = 10800
DEFAULT_API_CALL_TIMEOUT = 5
MINIMUM_POLLING_INTERVAL = 3
THROTTLE_LIMIT_TIMER = 61

API_BASE_URL = "http://api.netrohome.com/npa/v{apiVersion}/"
API_URL = API_BASE_URL.format(apiVersion=NETRO_API_VERSION)

DEVICE_INFO_URL = API_URL + "info.json"
DEVICE_SCHEDULES_URL = API_URL + "schedules.json"
# ... etc
```

**Error Event Sets:**
```python
ALL_OPERATIONAL_ERROR_EVENTS = {
    "startZoneFailed",
    "stopFailed",
    "setStandbyFailed",
}

ALL_COMM_ERROR_EVENTS = {
    "personCall",
    "personInfoCall",
    "getScheduleCall",
    "forecastCall",
}
```

## Indigo API Conventions

**Device State Updates:**
```python
# Build list of updates, then apply atomically
update_list = [
    {"key": "status", "value": reply_dict_device["status"]},
    {"key": "activeZone", "value": current_schedule_dict["zone"]},
]
dev.updateStatesOnServer(update_list)

# Or single state update
dev.updateStateOnServer("activeZone", action.zoneIndex)
```

**Device Properties (static config):**
```python
props = copy.deepcopy(dev.pluginProps)
props["NumZones"] = len(zones)
props["ZoneNames"] = zone_names_string
dev.replacePluginPropsOnServer(props)
```

**Indigo Collections:**
- `indigo.devices` - Device collection
- Filter by plugin: `indigo.devices.iter(filter="self")`
- Lookup by ID: `indigo.devices[device_id]`

---

*Convention analysis: 2026-02-01*
