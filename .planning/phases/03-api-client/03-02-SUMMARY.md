---
phase: 03-api-client
plan: 02
status: complete
completed: 2026-02-01

subsystem: plugin-integration
tags: [api-client, refactoring, throttle-management, proactive-pause]

dependency_graph:
  requires: [03-01]
  provides: [integrated-api-client, proactive-throttling]
  affects: [05-device-handlers]

tech_stack:
  added: []
  patterns: [callback-injection, proactive-pause, state-delegation]

key_files:
  created: []
  modified:
    - "Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py"

decisions:
  - id: 03-02-a
    decision: "Use api_client convenience methods for most calls"
    rationale: "Cleaner code, encapsulated endpoint URLs, consistent error handling"
  - id: 03-02-b
    decision: "Keep ZONE_START_ENDPOINT import for direct make_request call"
    rationale: "Zone start uses PUT method with different data structure, convenience method not warranted"
  - id: 03-02-c
    decision: "Log warning once per poll cycle when paused, not continuously"
    rationale: "Avoid log spam during low-token periods"

metrics:
  duration: "4 min"
  tasks: 3
  commits: 3
  lines_removed: 213
  lines_added: 53
---

# Phase 03 Plan 02: Plugin API Client Integration Summary

Wired plugin.py to use NetroAPIClient for all API communication.

## One-Liner

Replaced inline _make_api_call method with api_client convenience methods, added proactive polling pause, reduced plugin.py by 160 lines.

## What Was Built

### Plugin Integration Changes

**Removed:**
- 140-line `_make_api_call` method (now in api_client.py)
- `self.throttle_next_call` instance variable (managed by api_client)
- Unused endpoint constant imports (9 endpoints)
- Unused `timedelta` import

**Added:**
- `from api_client import NetroAPIClient` import
- `self.api_client` initialization with prefs callbacks
- Proactive pause check in `runConcurrentThread`

### API Call Site Updates

| Location | Before | After |
|----------|--------|-------|
| _update_from_netro (device info) | `_make_api_call(f"{DEVICE_INFO_ENDPOINT}?key={addr}")` | `api_client.get_device_info(addr)` |
| _update_from_netro (schedules) | `_make_api_call(f"{DEVICE_SCHEDULES_ENDPOINT}?key={serial}")` | `api_client.get_schedules(serial)` |
| callMoisturesAPI | `_make_api_call(url)` | `api_client.get_moistures(serial)` |
| callSensorAPI | `_make_api_call(url)` | `api_client.get_sensor_data(serial)` |
| actionControlSprinkler (zone on) | `_make_api_call(ZONE_START_ENDPOINT, ...)` | `api_client.make_request(ZONE_START_ENDPOINT, ...)` |
| actionControlSprinkler (off) | `_make_api_call(DEVICE_STOP_WATER_ENDPOINT, ...)` | `api_client.stop_watering(addr)` |
| setNoWater | `_make_api_call(DEVICE_NO_WATER_ENDPOINT, ...)` | `api_client.set_no_water(addr, days)` |
| setStandbyMode | `_make_api_call(DEVICE_SET_STATUS_ENDPOINT, ...)` | `api_client.set_device_status(addr, status)` |
| startZoneWithDelay | `_make_api_call(DEVICE_WATER_ENDPOINT, ...)` | `api_client.start_watering(addr, zones, delay, time)` |
| reportWeather | `_make_api_call(DEVICE_REPORT_WEATHER_ENDPOINT, ...)` | `api_client.report_weather(addr, data)` |

### Throttle Check Update

```python
# Before
if self.throttle_next_call and datetime.now() < self.throttle_next_call:
    ...
    f"{self.throttle_next_call:%H:%M:%S}"

# After
if self.api_client.is_throttled:
    ...
    f"{self.api_client.throttle_expires:%H:%M:%S}"
```

### Proactive Pause

```python
def runConcurrentThread(self):
    while True:
        try:
            if self.api_client.should_pause_polling:
                self.logger.warning(
                    f"Polling paused: only {self.api_client.token_remaining} tokens "
                    f"remaining (threshold: 100), will resume when tokens reset"
                )
            else:
                self._update_from_netro()
        except self.StopThread:
            raise
        ...
```

## Commits

| Hash | Type | Description |
|------|------|-------------|
| 85e1238 | feat | Add NetroAPIClient import and initialization |
| 243506e | refactor | Replace _make_api_call with api_client methods |
| 31f4c47 | feat | Add proactive polling pause in runConcurrentThread |

## Decisions Made

1. **Use convenience methods for most calls** - The api_client provides typed methods like `get_device_info()`, `stop_watering()`, etc. that encapsulate endpoint URLs and parameter formatting. Cleaner and less error-prone than raw URL construction.

2. **Keep ZONE_START_ENDPOINT for zone on** - The zone start call uses PUT method with a different data structure (id/duration rather than key/zones). Creating a convenience method didn't add value, so we use `make_request()` directly.

3. **Log warning once per cycle when paused** - When tokens are low, we log a warning each polling cycle but don't repeat if we're still paused next cycle. This prevents log spam during extended low-token periods.

## Deviations from Plan

None - plan executed as written.

## Verification Results

```
_make_api_call references: 0 (removed)
api_client usage count: 15 occurrences
Module imports: OK (all supporting modules load correctly)
Pylint score: 9.52/10
```

## Test Coverage

No new tests added in this plan. The api_client methods are tested in 03-03-PLAN.md. Integration testing requires the Indigo environment.

## Next Phase Readiness

**Phase 3 Complete:**
- api_client.py provides HTTP communication
- plugin.py uses api_client for all API calls
- Throttle state persists across plugin restarts
- Proactive pause prevents API exhaustion

**Ready for Phase 5 (Device Handlers):**
- Clean API access pattern established
- Error handling delegated to api_client
- Plugin focuses on business logic

**Blockers:** None
