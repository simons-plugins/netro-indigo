---
phase: 03-api-client
plan: 01
status: complete
completed: 2026-02-01

subsystem: api-communication
tags: [http-client, throttling, rate-limiting, state-persistence]

dependency_graph:
  requires: [02-base-modules]
  provides: [netro-api-client, throttle-management]
  affects: [05-device-handlers, plugin-integration]

tech_stack:
  added: []
  patterns: [callback-injection, proactive-throttling, state-persistence]

key_files:
  created:
    - "Netro Sprinklers.indigoPlugin/Contents/Server Plugin/api_client.py"
  modified:
    - "Netro Sprinklers.indigoPlugin/Contents/Server Plugin/constants.py"

decisions:
  - id: 03-01-a
    decision: "Use callback injection for logger and prefs to avoid circular imports"
    rationale: "api_client.py cannot import indigo directly; callbacks allow plugin to provide dependencies"
  - id: 03-01-b
    decision: "Re-export TOKEN_PAUSE_THRESHOLD and TOKEN_WARNING_THRESHOLD from api_client"
    rationale: "Convenient access for callers without importing from both modules"
  - id: 03-01-c
    decision: "Accept too-many-branches warning in make_request method"
    rationale: "Comprehensive error handling requires multiple branches; code is readable"

metrics:
  duration: "3 min"
  tasks: 3
  commits: 3
  lines_added: 605
---

# Phase 03 Plan 01: API Client Summary

HTTP client with throttle management for Netro API communication.

## One-Liner

NetroAPIClient class with proactive token tracking, persistent throttle state, and callback-based prefs access for Indigo independence.

## What Was Built

### api_client.py (599 lines)

Complete HTTP client encapsulating all Netro API communication:

**Core Features:**
- `make_request()` method with throttle enforcement and error handling
- Token budget tracking from response metadata (`token_remaining`, `token_reset`)
- Proactive polling pause when tokens below 100 (`should_pause_polling` property)
- Warning logging when tokens below 200

**State Persistence:**
- `_save_throttle_state()` serializes to JSON via prefs callback
- `_restore_throttle_state()` restores on init, respects expired throttles
- Survives plugin restarts without losing rate limit status

**Schema Validation:**
- `_validate_response_schema()` logs warnings for missing keys
- Debug logs additional unexpected keys
- Never raises exceptions (warning-only)

**Convenience Methods:**
- `get_device_info()`, `get_schedules()`, `get_moistures()`
- `get_sensor_data()`, `start_watering()`, `stop_watering()`
- `set_device_status()`, `set_no_water()`, `report_weather()`

### constants.py Updates

Added two threshold constants:
- `TOKEN_PAUSE_THRESHOLD = 100` - Triggers `should_pause_polling`
- `TOKEN_WARNING_THRESHOLD = 200` - Triggers warning logs

## Key Implementation Details

**Callback Injection Pattern:**
```python
def __init__(
    self,
    timeout: int = DEFAULT_API_TIMEOUT_SECONDS,
    logger: Optional[logging.Logger] = None,
    prefs_getter: Optional[Callable[[], Dict[str, Any]]] = None,
    prefs_setter: Optional[Callable[[str, Any], None]] = None
) -> None:
```

**Plugin Integration (future):**
```python
self.api_client = NetroAPIClient(
    logger=self.logger,
    prefs_getter=lambda: self.pluginPrefs,
    prefs_setter=lambda k, v: self.pluginPrefs.__setitem__(k, v)
)
```

## Commits

| Hash | Type | Description |
|------|------|-------------|
| af0a8a5 | feat | Add throttle threshold constants |
| 6bee720 | feat | Create NetroAPIClient with throttle management |
| 5df8635 | style | Fix logging f-string interpolation warnings |

## Decisions Made

1. **Callback injection for Indigo independence** - api_client.py receives logger and prefs callbacks rather than importing indigo directly, enabling unit testing and avoiding circular imports

2. **Re-export threshold constants** - TOKEN_PAUSE_THRESHOLD and TOKEN_WARNING_THRESHOLD are re-exported from api_client.py via `__all__` for convenient access

3. **Accept too-many-branches warning** - The `make_request()` method has 14 branches (vs 12 limit) due to comprehensive error handling; readability is maintained

## Deviations from Plan

**1. [Rule 2 - Missing Critical] Added List import**
- **Found during:** Task 2
- **Issue:** `start_watering()` method needs `List` type hint for zones parameter
- **Fix:** Added `List` to imports from typing
- **Files modified:** api_client.py

No other deviations - plan executed as written.

## Verification Results

```
Imports: OK
Properties: is_throttled, throttle_expires, token_remaining, should_pause_polling
Methods: 15/15 present
Pylint: 9.94/10
Circular imports: None
```

## Test Coverage

No unit tests added in this plan. Testing strategy:
- `api_client.py` designed for testability with callback injection
- Can mock prefs_getter/prefs_setter for state tests
- Can mock requests for HTTP tests
- Future: Unit tests in Phase 6 or separate test plan

## Next Phase Readiness

**Ready for integration:**
- Plugin.py can create NetroAPIClient instance
- Replace inline `_make_api_call()` with client methods
- Throttle state automatically persisted

**Dependencies met:**
- constants.py provides all needed values
- exceptions.py provides ThrottleDelayError, NetroAPIError

**Blockers:** None
