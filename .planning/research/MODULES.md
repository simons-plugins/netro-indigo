# Module Organization Research

**Project:** Netro Sprinklers Indigo Plugin Refactoring
**Research Focus:** How to organize an Indigo plugin into multiple modules
**Researched:** 2026-02-01
**Overall Confidence:** HIGH

## Executive Summary

Indigo plugins fully support multi-file Python organization. The main `plugin.py` must contain the `Plugin(indigo.PluginBase)` class (Indigo's entry point), but all other code can be factored into separate modules. The UK-Trains plugin in this repository demonstrates a production pattern with 8 Python modules totaling ~40k lines refactored from a monolithic structure.

**Key finding:** There are no technical barriers to modularization. Indigo loads `plugin.py` as the entry point and standard Python imports work normally from there. The Plugin class delegates to helper modules via imports.

## Recommended Module Structure

Based on analysis of the UK-Trains plugin pattern and the current Netro plugin architecture, here is the recommended structure:

```
Netro Sprinklers.indigoPlugin/
  Contents/
    Server Plugin/
      plugin.py           # Plugin class + lifecycle (slim coordinator)
      api_client.py       # Netro API HTTP communication
      validators.py       # Configuration validation functions
      utils.py            # Utility functions (timestamps, helpers)
      constants.py        # Constants, enums, configuration defaults
      actions.py          # Custom action handlers (optional - see notes)
      exceptions.py       # Custom exception classes
```

### Module Responsibilities

| Module | Lines (Est.) | Responsibility | Dependencies |
|--------|-------------|----------------|--------------|
| `plugin.py` | ~400 | Plugin class, lifecycle methods, device callbacks, trigger dispatch | All modules |
| `api_client.py` | ~250 | HTTP communication, throttle management, error classification | `constants.py`, `exceptions.py` |
| `validators.py` | ~200 | All `validate*ConfigUi()` functions | `constants.py` |
| `utils.py` | ~100 | Timestamp conversion, dict helpers, shared utilities | `constants.py` |
| `constants.py` | ~80 | API URLs, defaults, enums (ThrottleDelayError could move here) | None |
| `exceptions.py` | ~30 | Custom exceptions (ThrottleDelayError) | None |
| `actions.py` | ~300 | Custom action implementations (optional extraction) | `api_client.py` |

**Total:** ~1360 lines (down from 1635 due to reduced duplication)

### Why This Structure

1. **Single Responsibility:** Each module has one clear purpose
2. **Testability:** `api_client.py` and `validators.py` can be unit tested independently
3. **Import Simplicity:** No circular dependencies (linear dependency chain)
4. **Indigo Compatibility:** Plugin class remains in `plugin.py` as required

## Import Patterns

### Pattern 1: Direct Module Import (Recommended)

From `plugin.py`:

```python
# At top of plugin.py
from api_client import NetroAPIClient
from validators import (
    validate_prefs_config,
    validate_device_config,
    validate_action_config,
    validate_event_config
)
from utils import convert_timestamp, get_key_from_dict
from constants import (
    API_BASE_URL,
    MINIMUM_POLLING_INTERVAL,
    NETRO_MAX_ZONE_DURATION,
    ThrottleDelayError  # or from exceptions if separate
)
```

From `api_client.py`:

```python
from constants import (
    API_BASE_URL,
    DEFAULT_API_CALL_TIMEOUT,
    THROTTLE_LIMIT_TIMER
)
from exceptions import ThrottleDelayError
```

### Pattern 2: Module-Level Import with Aliases

```python
import api_client
import validators
import utils
import constants as const

# Usage
client = api_client.NetroAPIClient(...)
const.MINIMUM_POLLING_INTERVAL
```

### Pattern 3: UK-Trains Style (Flat Functions)

The UK-Trains plugin imports functions directly rather than classes:

```python
# In plugin.py
from darwin_api import darwin_api_retry, _fetch_station_board, nationalRailLogin
from device_manager import _clear_device_states, _update_train_device_states
from config import PluginConfig, PluginPaths, RuntimeConfig
```

This works well when modules contain standalone functions rather than classes.

## Dependency Graph

```
plugin.py
    |
    +-- api_client.py
    |       |
    |       +-- constants.py
    |       +-- exceptions.py
    |
    +-- validators.py
    |       |
    |       +-- constants.py
    |
    +-- utils.py
    |       |
    |       +-- constants.py
    |
    +-- constants.py (no dependencies)
    |
    +-- exceptions.py (no dependencies)
```

**Key principle:** Modules at the bottom of the graph have no internal dependencies. Modules higher up depend only on modules below them. This prevents circular imports.

## Implementation Details

### api_client.py

This module encapsulates all HTTP communication with the Netro API.

```python
"""Netro API client for HTTP communication.

Handles authentication, rate limiting, and error classification.
"""
import json
import traceback
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import requests

from constants import (
    API_BASE_URL,
    DEFAULT_API_CALL_TIMEOUT,
    THROTTLE_LIMIT_TIMER,
    DEVICE_INFO_URL,
    DEVICE_SCHEDULES_URL,
    DEVICE_MOISTURES_URL,
    DEVICE_SENSOR_DATA_URL,
    DEVICE_WATER_URL,
    DEVICE_STOP_WATER_URL,
    DEVICE_SET_STATUS_URL,
    DEVICE_NO_WATER_URL,
    DEVICE_REPORT_WEATHER_URL,
)
from exceptions import ThrottleDelayError


class NetroAPIClient:
    """HTTP client for Netro Public API with throttle management."""

    def __init__(self, timeout: int = DEFAULT_API_CALL_TIMEOUT, logger=None):
        """Initialize API client.

        Args:
            timeout: Request timeout in seconds
            logger: Logger instance for debug output
        """
        self.timeout = timeout
        self.logger = logger
        self.throttle_next_call: Optional[datetime] = None
        self._displayed_connection_error = False
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def make_request(
        self,
        url: str,
        method: str = "get",
        data: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Make API request with error handling and throttle enforcement.

        Args:
            url: Full URL to call
            method: HTTP method (get, post, put)
            data: Optional data dict for POST/PUT requests

        Returns:
            JSON response data or True for 204 responses

        Raises:
            ThrottleDelayError: If API calls are throttled
            requests.exceptions.HTTPError: On HTTP errors
            requests.exceptions.ConnectionError: On connection failures
        """
        # Implementation from current _make_api_call()
        ...

    def get_device_info(self, serial: str) -> Dict[str, Any]:
        """Get device information from Netro API."""
        return self.make_request(f"{DEVICE_INFO_URL}?key={serial}")

    def get_schedules(self, serial: str) -> Dict[str, Any]:
        """Get device schedules from Netro API."""
        return self.make_request(f"{DEVICE_SCHEDULES_URL}?key={serial}")

    def get_moistures(self, serial: str) -> Dict[str, Any]:
        """Get moisture levels from Netro API."""
        return self.make_request(f"{DEVICE_MOISTURES_URL}?key={serial}")

    def get_sensor_data(self, serial: str) -> Dict[str, Any]:
        """Get Whisperer sensor data from Netro API."""
        return self.make_request(f"{DEVICE_SENSOR_DATA_URL}?key={serial}")

    def start_watering(
        self,
        serial: str,
        zones: list,
        delay: int = 0,
        start_time: Optional[int] = None
    ) -> Dict[str, Any]:
        """Start watering with optional delay."""
        data = {"key": serial, "zones": zones}
        if delay > 0:
            data["delay"] = delay
        if start_time:
            data["start_time"] = start_time
        return self.make_request(DEVICE_WATER_URL, method="post", data=data)

    def stop_watering(self, serial: str) -> Dict[str, Any]:
        """Stop all zones."""
        return self.make_request(
            DEVICE_STOP_WATER_URL,
            method="post",
            data={"key": serial}
        )

    def set_status(self, serial: str, status: int) -> Dict[str, Any]:
        """Set device status (0=standby, 1=online)."""
        return self.make_request(
            DEVICE_SET_STATUS_URL,
            method="post",
            data={"key": serial, "status": status}
        )

    def set_no_water(self, serial: str, days: int) -> Dict[str, Any]:
        """Set rain delay for N days."""
        return self.make_request(
            DEVICE_NO_WATER_URL,
            method="post",
            data={"key": serial, "days": days}
        )

    def report_weather(self, serial: str, weather_data: Dict[str, Any]) -> Dict[str, Any]:
        """Report local weather to Netro."""
        data = {"key": serial, **weather_data}
        return self.make_request(DEVICE_REPORT_WEATHER_URL, method="post", data=data)

    @property
    def is_throttled(self) -> bool:
        """Check if API calls are currently throttled."""
        if not self.throttle_next_call:
            return False
        if datetime.now() >= self.throttle_next_call:
            self.throttle_next_call = None
            return False
        return True

    @property
    def throttle_expires(self) -> Optional[datetime]:
        """Get throttle expiration time if throttled."""
        return self.throttle_next_call if self.is_throttled else None
```

### validators.py

Extract all validation logic into standalone functions:

```python
"""Configuration validation for Netro Sprinklers plugin.

All validate*ConfigUi() functions extracted for testability.
"""
from typing import Tuple, Dict, Any
from datetime import datetime

import indigo

from constants import MINIMUM_POLLING_INTERVAL


def validate_prefs_config(values_dict: Dict[str, Any]) -> Tuple[bool, Dict, Dict]:
    """Validate plugin configuration before saving.

    Args:
        values_dict: Configuration values from UI

    Returns:
        Tuple of (is_valid, values_dict, errors_dict)
    """
    errors_dict = indigo.Dict()

    # Validate polling interval
    try:
        polling = int(values_dict.get("pollingInterval", 3))
        if polling < MINIMUM_POLLING_INTERVAL:
            errors_dict["pollingInterval"] = (
                f"Polling interval must be at least {MINIMUM_POLLING_INTERVAL} "
                "minutes to avoid API rate limits"
            )
        elif polling > 1440:
            errors_dict["pollingInterval"] = (
                "Polling interval cannot exceed 1440 minutes (24 hours)"
            )
    except (ValueError, TypeError):
        errors_dict["pollingInterval"] = "Polling interval must be a valid number"

    # Validate API timeout
    try:
        timeout = int(values_dict.get("apiTimeout", 5))
        if timeout < 1:
            errors_dict["apiTimeout"] = "Timeout must be at least 1 second"
        elif timeout > 60:
            errors_dict["apiTimeout"] = "Timeout cannot exceed 60 seconds"
    except (ValueError, TypeError):
        errors_dict["apiTimeout"] = "Timeout must be a valid number"

    # Validate max zone runtime
    try:
        max_runtime = int(values_dict.get("maxZoneRunTime", 3600))
        if max_runtime < 60:
            errors_dict["maxZoneRunTime"] = (
                "Max runtime must be at least 60 seconds (1 minute)"
            )
        elif max_runtime > 10800:
            errors_dict["maxZoneRunTime"] = (
                "Max runtime cannot exceed 10800 seconds (3 hours)"
            )
    except (ValueError, TypeError):
        errors_dict["maxZoneRunTime"] = "Max runtime must be a valid number"

    if len(errors_dict):
        return False, values_dict, errors_dict
    return True, values_dict, errors_dict


def validate_device_config(
    values_dict: Dict[str, Any],
    type_id: str,
    dev_id: int
) -> Tuple[bool, Dict, Dict]:
    """Validate device configuration before saving.

    Args:
        values_dict: Device configuration values from UI
        type_id: Device type ID
        dev_id: Device ID

    Returns:
        Tuple of (is_valid, values_dict, errors_dict)
    """
    errors_dict = indigo.Dict()

    if type_id == "sprinkler":
        serial = values_dict.get("address", "").strip()
        if not serial:
            errors_dict["address"] = "Serial number is required for Netro controller"
        elif len(serial) < 8:
            errors_dict["address"] = (
                "Serial number appears too short (should be 12 hex characters)"
            )

    if type_id == "Whisperer":
        serial = values_dict.get("address", "").strip()
        if not serial:
            errors_dict["address"] = "Serial number is required for Whisperer sensor"
        elif len(serial) < 8:
            errors_dict["address"] = "Serial number appears too short"

        # Set sensor capabilities
        values_dict["SupportsBatteryLevel"] = True
        values_dict["NumTemperatureInputs"] = 1
        values_dict["NumHumidityInputs"] = 1
        values_dict["SupportsTemperatureReporting"] = True

    if len(errors_dict):
        return False, values_dict, errors_dict
    return True, values_dict, errors_dict


def validate_action_config(
    values_dict: Dict[str, Any],
    type_id: str,
    dev_id: int
) -> Tuple[bool, Dict, Dict]:
    """Validate action configuration before saving.

    Args:
        values_dict: Action configuration values
        type_id: Action type ID
        dev_id: Device ID

    Returns:
        Tuple of (is_valid, values_dict, errors_dict)
    """
    errors_dict = indigo.Dict()

    if type_id == "startZoneWithDelay":
        # Validate duration
        try:
            duration = int(values_dict.get("duration", 15))
            if duration < 1 or duration > 180:
                errors_dict["duration"] = "Duration must be between 1 and 180 minutes"
        except (ValueError, TypeError):
            errors_dict["duration"] = "Duration must be a valid number"

        # Validate delay
        try:
            delay = int(values_dict.get("delay", 0))
            if delay < 0 or delay > 60:
                errors_dict["delay"] = "Delay must be between 0 and 60 minutes"
        except (ValueError, TypeError):
            errors_dict["delay"] = "Delay must be a valid number"

        # Validate start_time if provided
        start_time = values_dict.get("start_time", "").strip()
        if start_time:
            try:
                int(start_time)
            except ValueError:
                errors_dict["start_time"] = (
                    "Start time must be a valid Unix timestamp (integer)"
                )

        # Validate zone selected
        if not values_dict.get("zone"):
            errors_dict["zone"] = "You must select a zone"

    elif type_id == "reportWeather":
        # Validate required temperature
        temperature = values_dict.get("temperature", "").strip()
        if not temperature:
            errors_dict["temperature"] = "Current temperature is required"
        else:
            try:
                float(temperature)
            except ValueError:
                errors_dict["temperature"] = "Temperature must be a valid number"

        # Validate optional numeric fields
        weather_fields = [
            ("t_max", "Max temperature", -50, 150),
            ("t_min", "Min temperature", -50, 150),
            ("humidity", "Humidity", 0, 100),
            ("rain", "Rainfall", 0, 100),
            ("rain_prob", "Rain probability", 0, 100),
            ("wind_speed", "Wind speed", 0, 200),
            ("pressure", "Pressure", 20, 35)
        ]
        for field, label, min_val, max_val in weather_fields:
            value = values_dict.get(field, "").strip()
            if value:
                try:
                    num_value = float(value)
                    if num_value < min_val or num_value > max_val:
                        errors_dict[field] = f"{label} must be between {min_val} and {max_val}"
                except ValueError:
                    errors_dict[field] = f"{label} must be a valid number"

        # Validate date format
        date_str = values_dict.get("date", "").strip()
        if date_str:
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                errors_dict["date"] = "Date must be in YYYY-MM-DD format"

    if len(errors_dict):
        return False, values_dict, errors_dict
    return True, values_dict, errors_dict


def validate_event_config(
    values_dict: Dict[str, Any],
    type_id: str,
    dev_id: int
) -> Tuple[bool, Dict, Dict]:
    """Validate event/trigger configuration before saving.

    Args:
        values_dict: Event configuration values from UI
        type_id: Event type ID
        dev_id: Device ID

    Returns:
        Tuple of (is_valid, values_dict, errors_dict)
    """
    errors_dict = indigo.Dict()

    if type_id == "sprinklerError":
        if values_dict.get("serial", "") == "":
            errors_dict["serial"] = "You must select a Netro Sprinkler device."

    if len(errors_dict):
        return False, values_dict, errors_dict
    return True, values_dict, errors_dict
```

### utils.py

Extract standalone utility functions:

```python
"""Utility functions for Netro Sprinklers plugin."""
from datetime import datetime
from typing import Any

from dateutil import tz


def convert_timestamp(timestamp: int) -> datetime:
    """Convert Unix timestamp (milliseconds) to local timezone datetime.

    Args:
        timestamp: Unix timestamp in milliseconds

    Returns:
        datetime: Timestamp converted to local timezone
    """
    from_zone = tz.tzutc()
    to_zone = tz.tzlocal()
    time_utc = datetime.utcfromtimestamp(timestamp / 1000)
    time_utc_gmt = time_utc.replace(tzinfo=from_zone)
    return time_utc_gmt.astimezone(to_zone)


def get_key_from_dict(key: str, data: dict) -> Any:
    """Safely get value from dictionary with graceful error handling.

    Args:
        key: Dictionary key to retrieve
        data: Dictionary to search

    Returns:
        Value if key exists, otherwise "unavailable from API" or "unknown error"
    """
    try:
        return data[key]
    except KeyError:
        return "unavailable from API"
    except Exception:
        return "unknown error"


def parse_timestamp_flexible(raw_value: Any) -> float:
    """Parse timestamp that may be string or numeric.

    Handles Netro API quirk where timestamps come as strings sometimes.

    Args:
        raw_value: Timestamp value (string or numeric)

    Returns:
        Timestamp as float
    """
    if isinstance(raw_value, str):
        return float(raw_value)
    return float(raw_value) if raw_value else 0.0
```

### constants.py

Centralize all constants:

```python
"""Constants and configuration defaults for Netro Sprinklers plugin."""

# API Configuration
NETRO_API_VERSION = "1"
API_BASE_URL = f"http://api.netrohome.com/npa/v{NETRO_API_VERSION}/"

# API Endpoints
DEVICE_INFO_URL = API_BASE_URL + "info.json"
DEVICE_SCHEDULES_URL = API_BASE_URL + "schedules.json"
DEVICE_MOISTURES_URL = API_BASE_URL + "moistures.json"
DEVICE_SENSOR_DATA_URL = API_BASE_URL + "sensor_data.json"
DEVICE_WATER_URL = API_BASE_URL + "water.json"
DEVICE_STOP_WATER_URL = API_BASE_URL + "stop_water.json"
DEVICE_SET_STATUS_URL = API_BASE_URL + "set_status.json"
DEVICE_NO_WATER_URL = API_BASE_URL + "no_water.json"
DEVICE_REPORT_WEATHER_URL = API_BASE_URL + "report_weather.json"
ZONE_START_URL = API_BASE_URL + "zone/start"

# Rate Limiting
NETRO_DAILY_API_LIMIT = 2000
THROTTLE_LIMIT_TIMER = 61  # minutes to wait after rate limit

# Polling Configuration
MINIMUM_POLLING_INTERVAL = 3  # minutes
DEFAULT_WEATHER_UPDATE_INTERVAL = 10  # minutes
FORECAST_UPDATE_INTERVAL = 60  # minutes

# Request Configuration
DEFAULT_API_CALL_TIMEOUT = 5  # seconds
NETRO_MAX_ZONE_DURATION = 10800  # 3 hours in seconds

# Error Event Types
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

### exceptions.py

Custom exceptions:

```python
"""Custom exceptions for Netro Sprinklers plugin."""


class ThrottleDelayError(Exception):
    """Raised when API calls are throttled due to rate limit violations.

    The Netro API allows 2000 calls per day. When the limit is exceeded,
    the API returns HTTP 400 with error code 3. This exception is raised
    to prevent further API calls until the throttle period expires.
    """
    pass
```

## Plugin Class Integration

After extraction, `plugin.py` becomes a slim coordinator:

```python
"""Netro Smart Sprinkler Controller Plugin for Indigo.

This plugin integrates Netro smart irrigation controllers with Indigo.
"""
import indigo

from api_client import NetroAPIClient
from validators import (
    validate_prefs_config,
    validate_device_config,
    validate_action_config,
    validate_event_config
)
from utils import convert_timestamp, get_key_from_dict, parse_timestamp_flexible
from constants import (
    MINIMUM_POLLING_INTERVAL,
    NETRO_MAX_ZONE_DURATION,
    ALL_OPERATIONAL_ERROR_EVENTS,
    ALL_COMM_ERROR_EVENTS,
)
from exceptions import ThrottleDelayError


class Plugin(indigo.PluginBase):
    """Main plugin class for Netro Sprinkler Controller integration."""

    def __init__(self, plugin_id, plugin_display_name, plugin_version, plugin_prefs):
        super().__init__(plugin_id, plugin_display_name, plugin_version, plugin_prefs)

        # Configuration
        self.debug = plugin_prefs.get("showDebugInfo", False)
        self.polling_interval = int(plugin_prefs.get("pollingInterval", MINIMUM_POLLING_INTERVAL))
        self.max_zone_run_time = int(plugin_prefs.get("maxZoneRunTime", NETRO_MAX_ZONE_DURATION))

        # API client
        timeout = int(plugin_prefs.get("apiTimeout", 5))
        self.api_client = NetroAPIClient(timeout=timeout, logger=self.logger)

        # State
        self.trigger_dict = {}
        self.person = {}
        self.netro_devices = []

    # Lifecycle methods delegate to modules where appropriate

    def validatePrefsConfigUi(self, values_dict):
        return validate_prefs_config(values_dict)

    def validateDeviceConfigUi(self, values_dict, type_id, dev_id):
        return validate_device_config(values_dict, type_id, dev_id)

    def validateActionConfigUi(self, values_dict, type_id, dev_id):
        return validate_action_config(values_dict, type_id, dev_id)

    def validateEventConfigUi(self, values_dict, type_id, dev_id):
        return validate_event_config(values_dict, type_id, dev_id)

    # ... rest of Plugin class with action handlers using self.api_client
```

## Build Order

Extract modules in this order to maintain working plugin at each step:

### Phase 1: Foundation (No Plugin Changes Yet)

1. **`constants.py`** - Extract all constants from top of plugin.py
   - No changes to plugin.py needed yet
   - Can be tested by importing

2. **`exceptions.py`** - Extract ThrottleDelayError
   - No changes to plugin.py needed yet

### Phase 2: Utilities (Low Risk)

3. **`utils.py`** - Extract helper functions
   - Functions: `convert_timestamp()`, `get_key_from_dict()`
   - Update plugin.py imports
   - Test: Import utils and verify functions work

### Phase 3: Validators (Isolated)

4. **`validators.py`** - Extract all validation functions
   - Functions: All `validate*ConfigUi()` implementations
   - Update plugin.py to call validators module
   - Test: Plugin still validates configuration correctly

### Phase 4: API Client (Critical Path)

5. **`api_client.py`** - Extract API communication
   - Class: `NetroAPIClient` with all HTTP methods
   - Move throttle logic into client
   - Update plugin.py to use `self.api_client`
   - Test: All API calls still work, throttle detection works

### Phase 5: Actions (Optional)

6. **`actions.py`** - Extract custom action handlers (optional)
   - Only if actions are large enough to warrant extraction
   - May keep in plugin.py for simpler architecture

## Testing Strategy

### Unit Tests by Module

Each extracted module should have corresponding tests:

```
tests/
  test_api_client.py      # Existing + expanded
  test_validators.py      # Existing + expanded
  test_utils.py           # New
  test_constants.py       # New (simple import tests)
```

### Integration Tests

After each extraction phase:

1. Copy plugin to Indigo plugins folder
2. Reload plugin
3. Verify device communication works
4. Verify actions execute correctly
5. Verify triggers fire correctly

### Regression Testing

- Run existing 64 tests after each phase
- All tests should continue to pass
- Add new tests for extracted modules

## Pitfalls to Avoid

### Circular Import Prevention

**Problem:** Module A imports from Module B, Module B imports from Module A.

**Solution:** Use the dependency hierarchy above. Lower modules never import from higher modules. If needed, pass dependencies as constructor arguments rather than importing.

```python
# BAD: Circular import
# api_client.py
from plugin import Plugin  # Circular!

# GOOD: Pass logger as argument
# api_client.py
class NetroAPIClient:
    def __init__(self, logger=None):
        self.logger = logger
```

### Logger Access

**Problem:** Extracted modules need to log but don't have access to `self.logger`.

**Solution:** Pass logger as constructor argument or use module-level logger.

```python
# Option 1: Pass logger (preferred)
class NetroAPIClient:
    def __init__(self, timeout: int, logger=None):
        self.logger = logger or logging.getLogger(__name__)

# Option 2: Module-level logger (simpler but less flexible)
import logging
logger = logging.getLogger("Plugin.NetroAPI")
```

### Indigo Module Import

**Problem:** `indigo` module is only available at runtime.

**Solution:** Guard imports with try/except or use TYPE_CHECKING.

```python
# validators.py
try:
    import indigo
except ImportError:
    # For testing outside Indigo environment
    class MockIndigo:
        @staticmethod
        def Dict():
            return dict()
    indigo = MockIndigo()
```

### State Sharing

**Problem:** Extracted modules need access to plugin state.

**Solution:** Pass state via method arguments or use instance composition.

```python
# Plugin owns state, passes to client methods
response = self.api_client.get_device_info(dev.address)

# NOT: Client maintains its own copy of device addresses
```

## Verification Checklist

Before considering modularization complete:

- [ ] All 64 existing tests pass
- [ ] Plugin loads without import errors
- [ ] Device communication works (poll updates states)
- [ ] All actions execute correctly (zone on/off, standby, rain delay)
- [ ] Throttle detection and recovery works
- [ ] Triggers fire on errors
- [ ] Configuration validation works
- [ ] Debug logging works throughout
- [ ] No circular imports
- [ ] Each module has focused responsibility
- [ ] New module tests added (utils, constants)

## Sources

### HIGH Confidence (Verified)

- **UK-Trains Plugin** (local codebase): Production multi-file Indigo plugin with 8 Python modules demonstrating the pattern
  - `/Users/simon/vsCodeProjects/Indigo/UK-Trains/UKTrains.indigoPlugin/Contents/Server Plugin/`
  - Modules: `plugin.py`, `darwin_api.py`, `config.py`, `constants.py`, `device_manager.py`, `image_generator.py`, `text_formatter.py`

- **Indigo SDK CLAUDE.md** (local documentation): Official SDK structure showing `[additional .py modules]` as supported
  - `/Users/simon/vsCodeProjects/Indigo/Indigo-skill/reference/SDK-CLAUDE.md`

- **Netro Plugin Source** (local codebase): Current architecture being refactored
  - `/Users/simon/vsCodeProjects/Indigo/netro/Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py`

### MEDIUM Confidence (Official Documentation Pattern)

- **Indigo Plugin Structure**: Standard Python module import works from `plugin.py`
  - Source: SDK examples showing imports of bundled packages (jinja2, dicttoxml)
  - Example HTTP Responder plugin imports: `import jinja2`, `import dicttoxml`

---

*Research completed: 2026-02-01*
*Confidence: HIGH - Based on working production example (UK-Trains) and Indigo SDK documentation*
