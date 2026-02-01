# Python Refactoring Patterns for Monolithic Code

**Project:** Netro Sprinklers Indigo Plugin
**Researched:** 2026-02-01
**Overall Confidence:** HIGH (Python patterns well-established; Indigo-specific patterns from SDK examples)

## Executive Summary

This research addresses splitting a 1635-line monolithic `plugin.py` into focused modules while maintaining Indigo plugin compatibility. The recommended approach extracts four modules (`api_client.py`, `validators.py`, `utils.py`, `device_handlers.py`) while keeping the Plugin class thin as an orchestrator.

Key finding: Indigo SDK examples use single-file patterns, but this is convenience not requirement. The `Server Plugin/` directory can contain multiple `.py` files that import each other. Python 3.10+ features (structural pattern matching, improved type hints, union operators) make the refactored code cleaner.

## Recommended Module Structure

**Confidence:** HIGH (Python module patterns are well-established)

### Target Directory Layout

```
Netro Sprinklers.indigoPlugin/Contents/Server Plugin/
|-- plugin.py              # Main Plugin class (thin orchestrator, ~400 lines)
|-- api_client.py          # API communication layer (~200 lines)
|-- validators.py          # Input validation functions (~150 lines)
|-- utils.py               # Utility functions and helpers (~100 lines)
|-- device_handlers.py     # Device update logic (~300 lines)
|-- constants.py           # Configuration constants (~50 lines)
|-- exceptions.py          # Custom exceptions (~30 lines)
|-- Devices.xml            # (unchanged)
|-- Actions.xml            # (unchanged)
|-- Events.xml             # (unchanged)
|-- PluginConfig.xml       # (unchanged)
|-- MenuItems.xml          # (unchanged)
|-- requirements.txt       # (unchanged)
```

### Module Responsibilities

| Module | Responsibility | Dependencies | Size Estimate |
|--------|---------------|--------------|---------------|
| `plugin.py` | Plugin lifecycle, Indigo callbacks, orchestration | All others | ~400 lines |
| `api_client.py` | HTTP requests, rate limiting, error handling | `exceptions.py`, `constants.py` | ~200 lines |
| `validators.py` | Config validation, action parameter validation | `constants.py` | ~150 lines |
| `utils.py` | Timestamp parsing, dict helpers, data transforms | None | ~100 lines |
| `device_handlers.py` | Device state updates, API response processing | `api_client.py`, `utils.py` | ~300 lines |
| `constants.py` | API URLs, timeouts, limits, event sets | None | ~50 lines |
| `exceptions.py` | ThrottleDelayError and future custom exceptions | None | ~30 lines |

### Why This Structure

**Separation of Concerns:**
- API communication isolated from business logic
- Validation separate from execution
- Utilities reusable across modules
- Plugin class focuses on Indigo integration

**Testability:**
- Each module can be unit tested in isolation
- API client mocked without touching validation
- Validators tested without HTTP
- Device handlers tested with mock API responses

**Maintainability:**
- Find code by responsibility, not by scrolling
- Changes to API don't ripple to validation
- New features go in appropriate module
- Code review scope clearer

## Refactoring Patterns

### Pattern 1: Extract Class to Module

**Confidence:** HIGH (standard Python pattern)

**Before (monolithic):**
```python
# plugin.py (1635 lines)
class Plugin(indigo.PluginBase):
    def _make_api_call(self, url, method="get", data=None):
        # 140 lines of API logic
        ...

    def _update_from_netro(self):
        # 260 lines of device update logic
        ...

    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        # 40 lines of validation
        ...
```

**After (modular):**
```python
# api_client.py
class NetroAPIClient:
    """Handles all HTTP communication with Netro API."""

    def __init__(self, logger, timeout: int = 5):
        self.logger = logger
        self.timeout = timeout
        self.throttle_next_call: datetime | None = None
        self._displayed_connection_error = False

    def call(self, url: str, method: str = "get", data: dict | None = None) -> dict:
        """Make API call with throttle checking and error handling."""
        ...

# validators.py
def validate_device_config(values_dict: dict, type_id: str) -> tuple[bool, dict, dict]:
    """Validate device configuration values."""
    ...

def validate_action_config(values_dict: dict, type_id: str) -> tuple[bool, dict, dict]:
    """Validate action configuration values."""
    ...

# plugin.py
from api_client import NetroAPIClient
from validators import validate_device_config, validate_action_config

class Plugin(indigo.PluginBase):
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        super().__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
        self.api = NetroAPIClient(self.logger, int(pluginPrefs.get("apiTimeout", 5)))

    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        return validate_device_config(valuesDict, typeId)
```

### Pattern 2: Extract Functions to Utilities Module

**Confidence:** HIGH (standard Python pattern)

**Before (scattered helpers):**
```python
# plugin.py - helpers mixed with class
def convert_timestamp(timestamp):
    """Convert Unix timestamp (milliseconds) to local timezone datetime."""
    from_zone = tz.tzutc()
    to_zone = tz.tzlocal()
    time_utc = datetime.utcfromtimestamp(timestamp / 1000)
    time_utc_gmt = time_utc.replace(tzinfo=from_zone)
    return time_utc_gmt.astimezone(to_zone)

def get_key_from_dict(a_key, a_dict):
    """Safely get value from dictionary."""
    try:
        return a_dict[a_key]
    except KeyError:
        return "unavailable from API"
    except Exception:
        return "unknown error"
```

**After (utils module):**
```python
# utils.py
from datetime import datetime
from dateutil import tz
from typing import Any

def parse_timestamp(timestamp: int | float | str) -> datetime:
    """Convert Unix timestamp (milliseconds) to local timezone datetime.

    Handles both string and numeric timestamp formats from API.

    Args:
        timestamp: Unix timestamp in milliseconds (int, float, or numeric string)

    Returns:
        datetime in local timezone

    Raises:
        ValueError: If timestamp cannot be parsed
    """
    # Handle string timestamps from API
    if isinstance(timestamp, str):
        timestamp = float(timestamp)

    from_zone = tz.tzutc()
    to_zone = tz.tzlocal()
    time_utc = datetime.utcfromtimestamp(timestamp / 1000)
    time_utc_gmt = time_utc.replace(tzinfo=from_zone)
    return time_utc_gmt.astimezone(to_zone)

def safe_get(dictionary: dict, key: str, default: Any = "unavailable from API") -> Any:
    """Safely get value from dictionary with fallback.

    Args:
        dictionary: Dict to retrieve from
        key: Key to look up
        default: Value to return if key missing

    Returns:
        Value at key or default
    """
    return dictionary.get(key, default)

def parse_int_safely(value: Any, default: int = 0, logger=None) -> int:
    """Parse integer from various types with fallback.

    Args:
        value: Value to parse (int, str, float, or None)
        default: Fallback if parsing fails
        logger: Optional logger for debug messages

    Returns:
        Parsed integer or default
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        if logger:
            logger.debug(f"Could not parse '{value}' as int, using default {default}")
        return default
```

### Pattern 3: Constants Module

**Confidence:** HIGH (standard Python pattern)

**Before (scattered at top of file):**
```python
# plugin.py lines 49-88
NETRO_API_VERSION = "1"
NETRO_MAX_ZONE_DURATION = 10800
DEFAULT_API_CALL_TIMEOUT = 5
MINIMUM_POLLING_INTERVAL = 3
...
API_BASE_URL = "http://api.netrohome.com/npa/v{apiVersion}/"
API_URL = API_BASE_URL.format(apiVersion=NETRO_API_VERSION)
DEVICE_INFO_URL = API_URL + "info.json"
...
ALL_OPERATIONAL_ERROR_EVENTS = {"startZoneFailed", "stopFailed", ...}
```

**After (constants module):**
```python
# constants.py
"""Constants for Netro Sprinklers plugin."""

# API Configuration
NETRO_API_VERSION = "1"
DEFAULT_API_CALL_TIMEOUT = 5  # seconds
MINIMUM_POLLING_INTERVAL = 3  # minutes
THROTTLE_LIMIT_TIMER = 61  # minutes
FORECAST_UPDATE_INTERVAL = 60  # minutes

# Zone Limits
MAX_ZONE_DURATION = 10800  # seconds (3 hours)
MIN_ZONE_DURATION = 60  # seconds (1 minute)

# API URLs
API_BASE_URL = f"http://api.netrohome.com/npa/v{NETRO_API_VERSION}/"

class Endpoints:
    """API endpoint paths."""
    INFO = API_BASE_URL + "info.json"
    SCHEDULES = API_BASE_URL + "schedules.json"
    MOISTURES = API_BASE_URL + "moistures.json"
    SENSOR_DATA = API_BASE_URL + "sensor_data.json"
    WATER = API_BASE_URL + "water.json"
    STOP_WATER = API_BASE_URL + "stop_water.json"
    SET_STATUS = API_BASE_URL + "set_status.json"
    NO_WATER = API_BASE_URL + "no_water.json"
    REPORT_WEATHER = API_BASE_URL + "report_weather.json"
    ZONE_START = API_BASE_URL + "zone/start"

# Error Event Sets
OPERATIONAL_ERROR_EVENTS = frozenset({
    "startZoneFailed",
    "stopFailed",
    "setStandbyFailed",
})

COMM_ERROR_EVENTS = frozenset({
    "personCall",
    "personInfoCall",
    "getScheduleCall",
    "forecastCall",
})

# Validation Limits
class Limits:
    """Validation limits for user input."""
    POLLING_MIN = 3
    POLLING_MAX = 1440
    TIMEOUT_MIN = 1
    TIMEOUT_MAX = 60
    ZONE_DURATION_MIN = 1
    ZONE_DURATION_MAX = 180
    DELAY_MIN = 0
    DELAY_MAX = 60
```

### Pattern 4: Extract Custom Exceptions

**Confidence:** HIGH (Python best practice)

**Before (exception in main file):**
```python
# plugin.py line 91
class ThrottleDelayError(Exception):
    """Raised when API calls are throttled due to rate limit violations."""
    pass
```

**After (exceptions module):**
```python
# exceptions.py
"""Custom exceptions for Netro Sprinklers plugin."""

class NetroError(Exception):
    """Base exception for Netro plugin errors."""
    pass

class ThrottleDelayError(NetroError):
    """Raised when API calls are throttled due to rate limit violations.

    The Netro API allows 2000 calls per day. When the limit is exceeded,
    the API returns HTTP 400 with error code 3. This exception is raised
    to prevent further API calls until the throttle period expires.

    Attributes:
        retry_after: datetime when calls can resume
        message: Human-readable error message
    """

    def __init__(self, message: str, retry_after: datetime | None = None):
        super().__init__(message)
        self.retry_after = retry_after
        self.message = message

class InvalidSerialError(NetroError):
    """Raised when an invalid serial number is provided."""
    pass

class APIConnectionError(NetroError):
    """Raised when unable to connect to Netro API."""
    pass
```

### Pattern 5: Device Handler Extraction

**Confidence:** MEDIUM (Indigo-specific, but logical)

**Before (all device logic in one method):**
```python
# plugin.py _update_from_netro() - 260 lines handling both sprinkler and Whisperer
def _update_from_netro(self):
    for dev in indigo.devices.iter(filter="self"):
        if dev.deviceTypeId == "sprinkler":
            # 200 lines of sprinkler update logic
            ...
        if dev.deviceTypeId == "Whisperer":
            # 30 lines of sensor update logic
            ...
```

**After (device handlers module):**
```python
# device_handlers.py
"""Device-specific update handlers."""
from typing import Protocol
from api_client import NetroAPIClient
from utils import parse_timestamp, safe_get, parse_int_safely
from constants import Endpoints

class DeviceHandler(Protocol):
    """Protocol for device update handlers."""
    def update(self, dev, api: NetroAPIClient) -> list[dict]:
        """Update device states from API.

        Returns:
            List of state update dicts [{"key": ..., "value": ...}]
        """
        ...

class SprinklerHandler:
    """Handles sprinkler controller state updates."""

    def __init__(self, logger):
        self.logger = logger

    def update(self, dev, api: NetroAPIClient) -> list[dict]:
        """Fetch and process sprinkler data from API."""
        serial = dev.address
        updates = []

        # Fetch device info
        info = api.call(f"{Endpoints.INFO}?key={serial}")
        updates.extend(self._process_device_info(info))

        # Fetch schedules
        schedules = api.call(f"{Endpoints.SCHEDULES}?key={serial}")
        updates.extend(self._process_schedules(schedules))

        # Fetch moisture data
        moistures = api.call(f"{Endpoints.MOISTURES}?key={serial}")
        updates.extend(self._process_moistures(moistures))

        return updates

    def _process_device_info(self, info: dict) -> list[dict]:
        """Extract device info states."""
        device = info["data"]["device"]
        meta = info["meta"]

        return [
            {"key": "id", "value": device.get("serial", "")},
            {"key": "api_version", "value": device.get("version", "")},
            {"key": "status", "value": device.get("status", "UNKNOWN")},
            {"key": "token_remaining", "value": meta.get("token_remaining", 0)},
            {"key": "token_reset", "value": meta.get("token_reset", "")},
            # ... more states
        ]

    def _process_schedules(self, data: dict) -> list[dict]:
        """Extract schedule states."""
        schedules = data.get("data", {}).get("schedules", [])
        # Find active and next schedules...
        ...

    def _process_moistures(self, data: dict) -> list[dict]:
        """Extract moisture states per zone."""
        moistures = data.get("data", {}).get("moistures", [])
        if not moistures:
            return []
        # Process moistures...
        ...

class WhispererHandler:
    """Handles Whisperer sensor state updates."""

    def __init__(self, logger):
        self.logger = logger

    def update(self, dev, api: NetroAPIClient) -> list[dict]:
        """Fetch and process sensor data from API."""
        serial = dev.address

        sensor_data = api.call(f"{Endpoints.SENSOR_DATA}?key={serial}")
        return self._process_sensor_data(sensor_data)

    def _process_sensor_data(self, data: dict) -> list[dict]:
        """Extract sensor readings."""
        readings = data.get("data", {}).get("sensor_data", [])
        if not readings:
            self.logger.warning("No sensor data available from API")
            return []

        # Sort by ID to get most recent
        readings.sort(key=lambda x: x.get("id", 0), reverse=True)
        latest = readings[0]

        return [
            {"key": "sensorValue", "value": latest.get("moisture", 0)},
            {"key": "temperature", "value": latest.get("celsius", 0)},
            {"key": "sunlight", "value": latest.get("sunlight", 0)},
            {"key": "batteryLevel", "value": latest.get("battery_level", 0)},
            # ... more states
        ]
```

## Import Strategy

**Confidence:** HIGH (Python import mechanics well-documented)

### Relative vs Absolute Imports

For Indigo plugins, use **relative imports within the package**:

```python
# plugin.py
from .api_client import NetroAPIClient
from .validators import validate_device_config
from .utils import parse_timestamp
from .constants import Endpoints, Limits
from .exceptions import ThrottleDelayError
```

However, Indigo's plugin loader may not support package semantics. In that case, use **direct imports** (all files in same directory):

```python
# plugin.py (if relative imports fail)
from api_client import NetroAPIClient
from validators import validate_device_config
from utils import parse_timestamp
from constants import Endpoints, Limits
from exceptions import ThrottleDelayError
```

### Handling Circular Imports

**Problem:** Plugin needs API client; API client needs exceptions from plugin.

**Solution:** Extract shared dependencies to separate modules:

```
exceptions.py  <- No dependencies (base)
constants.py   <- No dependencies (base)
utils.py       <- May depend on constants
api_client.py  <- Depends on exceptions, constants
validators.py  <- Depends on constants
device_handlers.py <- Depends on api_client, utils, constants
plugin.py      <- Depends on all above
```

This creates a clear dependency graph with no cycles.

## Exception Handling Refactoring

**Confidence:** HIGH (Python best practices)

### Replace Bare Exceptions

**Before (anti-pattern):**
```python
try:
    self._update_from_netro()
except (Exception,):
    pass  # Silent failure
```

**After (specific exceptions):**
```python
try:
    self._update_from_netro()
except ThrottleDelayError as e:
    self.logger.warning(f"Update skipped due to throttle: {e}")
except requests.exceptions.Timeout:
    self.logger.debug("API request timed out, will retry next cycle")
except requests.exceptions.ConnectionError:
    self.logger.debug("Connection failed, will retry next cycle")
except Exception as e:
    self.logger.error(f"Unexpected error during update: {type(e).__name__}: {e}")
    self.logger.debug(f"Traceback:\n{traceback.format_exc()}")
```

### Exception Hierarchy for This Plugin

```python
# exceptions.py
class NetroError(Exception):
    """Base for all Netro plugin exceptions."""
    pass

class ThrottleDelayError(NetroError):
    """Rate limit exceeded."""
    pass

class InvalidSerialError(NetroError):
    """Bad serial number."""
    pass

class APIResponseError(NetroError):
    """Unexpected API response format."""
    pass

# Usage in code:
try:
    result = api.call(url)
except ThrottleDelayError:
    # Handle rate limiting
except requests.exceptions.RequestException as e:
    # Handle all requests library errors
except NetroError as e:
    # Handle other Netro-specific errors
except Exception as e:
    # Unexpected errors - log and continue
```

## Python 3.10+ Specific Patterns

**Confidence:** HIGH (language features documented in official docs)

### Structural Pattern Matching (match/case)

**Use Case:** Device type dispatch

```python
# Python 3.10+ pattern matching
def get_handler(device_type_id: str) -> DeviceHandler:
    match device_type_id:
        case "sprinkler":
            return SprinklerHandler(self.logger)
        case "Whisperer":
            return WhispererHandler(self.logger)
        case _:
            raise ValueError(f"Unknown device type: {device_type_id}")
```

### Union Type Syntax (|)

**Use Case:** Type hints for optional/union types

```python
# Python 3.10+ union syntax (instead of Optional[X] or Union[X, Y])
def parse_timestamp(timestamp: int | float | str) -> datetime:
    ...

def call(self, url: str, data: dict | None = None) -> dict | bool:
    ...

# Class attribute with union
class NetroAPIClient:
    throttle_next_call: datetime | None = None
```

### ParamSpec and TypeVarTuple (typing)

**Use Case:** Preserving callback signatures when wrapping

```python
from typing import ParamSpec, TypeVar, Callable

P = ParamSpec('P')
R = TypeVar('R')

def with_throttle_check(func: Callable[P, R]) -> Callable[P, R]:
    """Decorator that checks throttle before calling function."""
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        if self.throttle_next_call and datetime.now() < self.throttle_next_call:
            raise ThrottleDelayError(f"Throttled until {self.throttle_next_call}")
        return func(*args, **kwargs)
    return wrapper
```

### Improved Error Messages (Python 3.10+)

Python 3.10+ provides better error messages automatically. Leverage this by:
- Raising specific exceptions with context
- Using f-strings in exception messages
- Including relevant state in error messages

```python
raise ValueError(
    f"Invalid zone {zone_id}: expected 1-{max_zones}, "
    f"enabled zones are {enabled_zones}"
)
```

## Refactoring Steps (Ordered)

**Confidence:** MEDIUM (approach is sound; exact order may vary based on testing needs)

### Phase 1: Extract Foundation (No Logic Changes)

1. **Create `constants.py`** - Move all constants from plugin.py
   - No behavior change, just relocation
   - Update imports in plugin.py
   - Run tests to verify nothing broke

2. **Create `exceptions.py`** - Move ThrottleDelayError
   - Add base NetroError class
   - Update imports in plugin.py
   - Run tests

3. **Create `utils.py`** - Move helper functions
   - `convert_timestamp()` -> `parse_timestamp()`
   - `get_key_from_dict()` -> `safe_get()`
   - Add type hints
   - Update imports in plugin.py
   - Run tests

**Checkpoint:** All tests pass, plugin.py imports from 3 new modules

### Phase 2: Extract API Layer

4. **Create `api_client.py`** - Extract API communication
   - Move `_make_api_call()` method to `NetroAPIClient` class
   - Move throttle state management
   - Move HTTP error handling
   - Plugin keeps thin wrapper or uses client directly
   - Run tests (may need to update mocks)

**Checkpoint:** API calls go through api_client.py

### Phase 3: Extract Validation

5. **Create `validators.py`** - Extract validation functions
   - `validate_device_config()` from `validateDeviceConfigUi()`
   - `validate_action_config()` from `validateActionConfigUi()`
   - `validate_prefs_config()` from `validatePrefsConfigUi()`
   - Plugin callbacks become thin wrappers
   - Run tests

**Checkpoint:** Validation logic in validators.py

### Phase 4: Extract Device Handlers

6. **Create `device_handlers.py`** - Extract device update logic
   - Move `_update_from_netro()` guts to handlers
   - Create `SprinklerHandler` and `WhispererHandler`
   - Plugin orchestrates, handlers do work
   - Run tests

**Checkpoint:** Device logic in device_handlers.py, plugin.py is thin orchestrator

### Phase 5: Clean Up Plugin Class

7. **Simplify `plugin.py`**
   - Remove extracted code (should be imports now)
   - Add type hints to remaining methods
   - Update docstrings
   - Target: ~400 lines
   - Run full test suite

8. **Update tests**
   - Adjust imports for new module structure
   - Add unit tests for individual modules
   - Verify coverage maintained

## Test Migration Strategy

**Confidence:** HIGH (pytest patterns well-established)

### Current Test Structure
```
tests/
|-- conftest.py          # Fixtures
|-- test_api_client.py   # API tests (17 tests)
|-- test_validation.py   # Validation tests (24 tests)
|-- test_actions.py      # Action tests (23 tests)
```

### After Refactoring
```
tests/
|-- conftest.py              # Shared fixtures
|-- test_api_client.py       # Tests for api_client.py module
|-- test_validators.py       # Tests for validators.py module
|-- test_utils.py            # Tests for utils.py module
|-- test_device_handlers.py  # Tests for device_handlers.py module
|-- test_plugin_integration.py  # Integration tests for plugin.py
|-- fixtures/                # Mock API responses
```

### Import Updates in Tests

```python
# Before
from plugin import Plugin, ThrottleDelayError

# After
from plugin import Plugin
from api_client import NetroAPIClient
from validators import validate_device_config
from exceptions import ThrottleDelayError
from utils import parse_timestamp
```

### Mocking Strategy

```python
# Test API client in isolation
def test_api_call_success(mocker):
    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "OK"}
    mocker.patch("requests.get", return_value=mock_response)

    client = NetroAPIClient(logger=mocker.MagicMock())
    result = client.call("http://api.example.com/test")

    assert result["status"] == "OK"

# Test device handler with mocked API client
def test_sprinkler_handler_update(mocker):
    mock_api = mocker.MagicMock(spec=NetroAPIClient)
    mock_api.call.return_value = {"data": {"device": {...}}}

    handler = SprinklerHandler(logger=mocker.MagicMock())
    updates = handler.update(mock_device, mock_api)

    assert any(u["key"] == "status" for u in updates)
```

## Common Pitfalls and Prevention

**Confidence:** HIGH (based on common refactoring mistakes)

### Pitfall 1: Breaking Indigo Plugin Loading

**Risk:** Indigo may not find Plugin class after refactoring
**Prevention:**
- Keep `plugin.py` as main file with `class Plugin(indigo.PluginBase)`
- Test plugin loading in Indigo after each phase
- Don't rename plugin.py

### Pitfall 2: Import Errors at Runtime

**Risk:** Circular imports or missing modules
**Prevention:**
- Draw dependency graph before refactoring
- Keep dependencies flowing one direction
- Test imports in isolation: `python3 -c "from api_client import NetroAPIClient"`

### Pitfall 3: Losing Logger Access

**Risk:** Extracted modules can't log properly
**Prevention:**
- Pass logger to module constructors/functions
- Don't use global logger
- Example: `NetroAPIClient(logger=self.logger)`

### Pitfall 4: Test Breakage

**Risk:** Tests break due to changed imports/structure
**Prevention:**
- Run tests after each extraction step
- Update mocks to match new structure
- Maintain same test coverage

### Pitfall 5: State Management Split

**Risk:** State (like throttle_next_call) split across modules
**Prevention:**
- Keep related state together (throttle in API client)
- Pass state explicitly, don't rely on shared globals
- Document state ownership clearly

## Backward Compatibility

**Confidence:** MEDIUM (depends on external usage)

### Breaking Changes (Acceptable per PROJECT.md)

- Internal method signatures may change
- Import paths change (internal only)
- Error message text may change

### Preserving External Interface

- Plugin class name unchanged: `Plugin(indigo.PluginBase)`
- Indigo callback signatures unchanged
- Device state keys unchanged
- Action/Event XML IDs unchanged

### Migration for Tests

Tests need updates but follow predictable patterns:
```python
# Old import
from plugin import Plugin

# New imports
from plugin import Plugin
from api_client import NetroAPIClient
from exceptions import ThrottleDelayError
```

## Quality Metrics

### Before Refactoring
| Metric | Current | Target |
|--------|---------|--------|
| Lines in plugin.py | 1635 | ~400 |
| Pylint score | 6.5/10 | 8.0+ |
| Test coverage | 70% | 75%+ |
| Cyclomatic complexity | High | Medium |

### After Refactoring
| Module | Target Lines | Target Pylint |
|--------|-------------|---------------|
| plugin.py | ~400 | 8.5+ |
| api_client.py | ~200 | 9.0+ |
| validators.py | ~150 | 9.0+ |
| utils.py | ~100 | 9.0+ |
| device_handlers.py | ~300 | 8.5+ |
| constants.py | ~50 | 10.0 |
| exceptions.py | ~30 | 10.0 |

## Sources and Confidence Assessment

| Area | Confidence | Basis |
|------|------------|-------|
| Python module patterns | HIGH | Language documentation, widespread adoption |
| Exception hierarchy | HIGH | Python best practices |
| Python 3.10+ features | HIGH | Official Python docs |
| Indigo plugin structure | HIGH | SDK examples examined |
| Multi-file Indigo plugins | MEDIUM | Logical inference (SDK uses single-file for simplicity, not requirement) |
| Specific line counts | LOW | Estimates based on current code analysis |
| Test migration | MEDIUM | Standard pytest patterns |

---

*Research completed: 2026-02-01*
*Primary sources: Python documentation, Indigo SDK examples, project codebase analysis*
