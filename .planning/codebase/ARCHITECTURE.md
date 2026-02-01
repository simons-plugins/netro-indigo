# Architecture

**Analysis Date:** 2026-02-01

## Pattern Overview

**Overall:** Plugin-based Indigo integration with polling-based state synchronization

**Key Characteristics:**
- Single-file monolithic plugin architecture (1635 lines in `plugin.py`)
- Polling-based data refresh cycle via concurrent background thread
- Per-device serial number authentication (no plugin-level API keys)
- Graceful error handling with error suppression after first display
- Trigger-based event notification system

## Layers

**Presentation/Configuration Layer:**
- Purpose: Handle Indigo UI configuration and validation
- Location: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py` methods: `validatePrefsConfigUi()` (line 1031), `validateDeviceConfigUi()` (line 881), `validateActionConfigUi()` (line 923), `validateEventConfigUi()` (line 1010), and XML config files
- Contains: Plugin settings UI, device configuration, action parameter validation, event filter validation
- Depends on: None (independent layer)
- Used by: Indigo UI framework

**Control/Action Layer:**
- Purpose: Execute user-requested actions on Netro devices
- Location: `plugin.py` methods: `actionControlSprinkler()` (line 1238), `setNoWater()` (line 1350), `setStandbyMode()` (line 1383), `startZoneWithDelay()` (line 1408), `reportWeather()` (line 1479)
- Contains: Standard sprinkler actions (zone on/off), custom actions (rain delay, standby, weather reporting, zone with delay)
- Depends on: API Integration Layer (via `_make_api_call()`), State Management (throttle checking)
- Used by: Indigo action dispatcher

**State Management Layer:**
- Purpose: Maintain plugin and device state, manage throttling and tracking
- Location: `plugin.py` instance variables (lines 157-187): `throttle_next_call`, `_displayed_connection_error`, `triggerDict`, `person`, `netro_devices`
- Contains: Throttle expiry tracking, connection error tracking, active triggers, cached API response data, device metadata
- Depends on: API Integration Layer (to know when throttled), Polling Loop (to update state)
- Used by: All layers for state validation and status checks

**Data Synchronization Layer:**
- Purpose: Periodically poll Netro API and update Indigo device states
- Location: `plugin.py` methods: `_update_from_netro()` (line 373), `runConcurrentThread()` (line 810), `callMoisturesAPI()` (line 696), `callSensorAPI()` (line 735)
- Contains: Main polling loop, device state refresh for sprinklers and sensors, schedule fetching, moisture data retrieval, sensor reading updates
- Depends on: API Integration Layer (`_make_api_call()`), State Management (throttle checking)
- Used by: Background concurrent thread, manual refresh actions

**API Integration Layer:**
- Purpose: Handle HTTP communication with Netro Public API
- Location: `plugin.py` method: `_make_api_call()` (line 195)
- Contains: HTTP request/response handling, rate limit detection and throttling (HTTP 400 with error code 3), timeout handling, JSON parsing, error classification, connection error suppression
- Depends on: `requests` library
- Used by: Data Synchronization Layer, Control/Action Layer

**Trigger System Layer:**
- Purpose: Fire Indigo triggers based on operational and communication events
- Location: `plugin.py` methods: `_fireTrigger()` (line 1164), `triggerStartProcessing()` (line 1203), `triggerStopProcessing()` (line 1218)
- Contains: Trigger dispatch logic, event filtering, device association
- Depends on: Indigo trigger framework
- Used by: API Integration Layer (on errors), Control/Action Layer (on success/failure)

**Device Lifecycle Layer:**
- Purpose: Initialize and manage device communication
- Location: `plugin.py` methods: `deviceStartComm()` (line 1137), `deviceStopComm()` (line 1153), `didDeviceCommPropertyChange()` (line 1119)
- Contains: Device startup/shutdown, configuration change detection
- Depends on: State Management
- Used by: Indigo device framework

## Data Flow

**Polling Cycle (main loop, 3-300 minute intervals):**

1. `runConcurrentThread()` calls `_update_from_netro()` every N minutes
2. `_update_from_netro()` iterates over enabled sprinkler and sensor devices
3. For sprinkler controllers:
   - Call `_make_api_call(DEVICE_INFO_URL)` → Get device info, status, zones, token counts
   - Parse response, merge metadata, cache in `self.person` and `self.netro_devices`
   - Call `_make_api_call(DEVICE_SCHEDULES_URL)` → Get active and next schedule
   - Call `_make_api_call(DEVICE_MOISTURES_URL)` → Get moisture per zone
   - Build state update list with all values
   - Call `dev.updateStatesOnServer(update_list)` → Write to Indigo device
4. For sensor devices:
   - Call `_make_api_call(DEVICE_SENSOR_DATA_URL)` → Get temperature, moisture, sunlight, battery
   - Update sensor device states
5. Return to sleep, wake in N minutes and repeat

**Action Execution (triggered by user or automation):**

1. Action callback method receives action object and device
2. Check `self.throttle_next_call` - if throttled, log error and fire failure trigger, return
3. Build API request data dict with zone/action parameters
4. Call `_make_api_call(API_ENDPOINT, method, data)` → Make HTTP request
5. On success: log success message, update local device state, fire success trigger (implicit)
6. On API error: log error, fire failure trigger (explicit), do NOT update state
7. On connection error: log error once, re-raise exception

**Throttle Management Flow:**

1. API Integration Layer detects HTTP 400 with error code 3
2. Extract reset time from response meta: `meta.token_reset`
3. Store reset datetime in `self.throttle_next_call`
4. Fire "rateLimitExceeded" trigger
5. All subsequent API calls check `throttle_next_call` first
6. If throttled: raise `ThrottleDelayError`, Action Layer catches and fires failure trigger
7. When throttle expires: reset `throttle_next_call = None`, log resume message, resume normal operation

**Error Handling Flow:**

1. Exception raised from `_make_api_call()` or action execution
2. Check if this is the first display of this error type:
   - Connection errors: Check `self._displayed_connection_error`
   - API errors: Log once per API call
3. Log error with context (device name, zone, action, API response)
4. Raise exception or return False
5. Caller catches exception, fires appropriate trigger
6. Indigo continues operation (polling resumes, actions fail but don't crash plugin)

**State vs Properties:**

- **States** (frequently changing): `status`, `activeZone`, `activeSchedule`, `nextScheduleTime`, `nextScheduleZone`, `nextScheduleSource`, `nextScheduleDuration`, `token_remaining`, `moisture_1` through `moisture_12`, sensor readings
- **Properties** (static config): `address` (MAC), `model`, `name`, `serialNumber`, zone names and counts
- **Computed** (derived): `api_version`, `time` (last refresh), `last_active` (last API response time)

## Key Abstractions

**ThrottleDelayError:**
- Purpose: Indicate rate limit has been hit
- Location: `plugin.py` lines 91-98
- Pattern: Custom exception raised when `self.throttle_next_call` active, caught at action layer

**Device Type Abstraction:**
- Purpose: Support multiple Netro device types
- Examples: `deviceTypeId` "sprinkler" (in Devices.xml line 9), `deviceTypeId` "Whisperer" (line 199)
- Pattern: Type-specific update logic in `_update_from_netro()` based on `dev.deviceTypeId`

**State Update List Pattern:**
- Purpose: Batch device state updates for efficiency
- Location: `plugin.py` line 425, 696
- Pattern: Build list of dicts `[{"key": "state_id", "value": value}]`, pass to `dev.updateStatesOnServer()`

**Zone Dictionary Abstraction:**
- Purpose: Represent zone configuration and state
- Location: Returned by `_get_zone_dict()` (line 354)
- Pattern: Dict with keys: `id`, `name`, `maxRuntime`, `enabled`, index

**Device Dictionary Abstraction:**
- Purpose: Cache Netro API response structure
- Location: `self.person`, `self.netro_devices`
- Pattern: Mirrors Netro API response structure with keys: `device`, `zones`, `schedules`, `moistures`

## Entry Points

**Plugin Initialization:**
- Location: `__init__()` (line 157)
- Triggers: Indigo loads plugin
- Responsibilities: Initialize instance variables, parse preferences, set up data structures

**Plugin Startup:**
- Location: `startup()` (line 793)
- Triggers: Indigo enables plugin
- Responsibilities: Log startup (minimal), defer heavy initialization to concurrent thread

**Concurrent Polling Thread:**
- Location: `runConcurrentThread()` (line 810)
- Triggers: Indigo launches background thread
- Responsibilities: Loop forever, call `_update_from_netro()` every N minutes, catch and suppress exceptions

**Device Communication:**
- Location: `deviceStartComm()` (line 1137), `deviceStopComm()` (line 1153)
- Triggers: Indigo device enabled/disabled or plugin reloaded
- Responsibilities: Log device lifecycle, allow concurrent thread to process devices

**User Actions:**
- Location: `actionControlSprinkler()` (line 1238), custom action handlers
- Triggers: User executes action from Indigo UI or automation
- Responsibilities: Validate throttle state, execute API call, update state, fire triggers

**Triggers:**
- Location: `triggerStartProcessing()` (line 1203), `triggerStopProcessing()` (line 1218)
- Triggers: User creates/deletes Indigo trigger
- Responsibilities: Register/deregister trigger in `self.triggerDict`

## Error Handling

**Strategy:** Fail gracefully without crashing plugin; log details; fire triggers for user automation

**Patterns:**

**Connection Errors** (ConnectionError, Timeout, ReadTimeout):
```python
except requests.exceptions.ConnectionError as exc:
    if not self._displayed_connection_error:
        self.logger.error("Connection to Netro API server failed. Will continue to retry silently.")
        self._displayed_connection_error = True
    raise exc
```
- Location: `plugin.py` lines 248-252
- Behavior: Log once, suppress subsequent logs, re-raise to caller
- Caller catches and continues polling cycle

**Rate Limit Errors** (HTTP 400 with error code 3):
```python
if error.get("code") == 3:
    reset_dt = datetime.strptime(token_reset, "%Y-%m-%dT%H:%M:%S")
    self.throttle_next_call = reset_dt
    self.logger.error(f"netro api rate limit exceeded ({token_msg}), calls will resume after {reset_dt}")
    self._fireTrigger("rateLimitExceeded")
```
- Location: `plugin.py` lines 276-294
- Behavior: Parse reset time, store in `throttle_next_call`, fire trigger, log error
- All API calls check throttle state, action layer fires failure trigger

**Validation Errors** (invalid input):
- Location: `validatePrefsConfigUi()` (line 1031), `validateDeviceConfigUi()` (line 881), `validateActionConfigUi()` (line 923)
- Behavior: Check constraints (serial format, polling interval, parameter ranges), return `(False, error_message)` to Indigo
- Indigo prevents invalid configuration from being saved

**Action Execution Errors**:
```python
try:
    self._make_api_call(ZONE_START_URL, request_method="put", data=data)
    self.logger.info(f'sent "{dev.name} - {zoneName}" on')
except (Exception,):
    self.logger.error(f'send "{dev.name} - {zoneName}" on failed')
    self._fireTrigger("startZoneFailed", dev.id)
```
- Location: `plugin.py` lines 1281-1290
- Behavior: Try to execute, catch any exception, log error, fire failure trigger
- Device state NOT updated on failure (Netro is source of truth)

## Cross-Cutting Concerns

**Logging:**
- Framework: Python `logging` via `self.logger`
- Pattern: Debug level for API calls, info for actions, error for failures
- Example: `self.logger.debug(f"API call: {request_method.upper()} {url}")` (line 220)

**Validation:**
- Configuration validation: Enforce serial format (12 hex chars), polling interval (≥3 min), timeout (1-60s), max zone runtime (60-10800s)
- Action parameter validation: Zone duration (1-180 min for delays), delay (0-60 min), rain days (1-100), weather ranges
- Location: `validatePrefsConfigUi()` (line 1031), `validateDeviceConfigUi()` (line 881), `validateActionConfigUi()` (line 923)

**Authentication:**
- Method: Serial number as URL parameter `?key={serial}`
- Location: `_update_from_netro()` line 397: `DEVICE_INFO_URL?key={dev.address}`
- Per-device: Each device has own serial number stored in `dev.address`
- No bearer tokens or plugin-level keys

**Rate Limiting:**
- Netro limit: 2000 calls/day shared across all plugin instances
- Detection: HTTP 400 with error code 3 and `token_reset` time
- Response: 61-minute backoff, store reset time in `throttle_next_call`
- Monitoring: Display `token_remaining` state, warn when <200 tokens left
- Prevention: Default 5-minute polling = ~288 calls/day (safe)

---

*Architecture analysis: 2026-02-01*
