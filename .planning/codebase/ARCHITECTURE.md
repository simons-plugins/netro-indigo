# ARCHITECTURE.md — Plugin Architecture

## Overview

The Netro Sprinklers plugin is a polling-based Indigo plugin. It polls the
Netro Public API on per-endpoint timers and writes state to Indigo device
objects. There is no push/webhook mechanism.

## Module Dependency Graph

```
plugin.py (Plugin class)
  ├── api_client.py (NetroAPIClient)
  │     ├── constants.py
  │     └── exceptions.py
  ├── device_handlers.py (SprinklerHandler, WhispererHandler, ZoneHandler)
  │     ├── constants.py
  │     └── utils.py
  ├── validators.py
  │     └── constants.py
  ├── tomorrow_client.py (TomorrowClient)
  ├── utils.py
  ├── constants.py
  └── exceptions.py
```

All modules except `plugin.py` are free of `indigo` imports — they are pure
Python and fully unit-testable without the Indigo runtime.

---

## Plugin Lifecycle

Defined in
`Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py`:

```
__init__()
  - Read pluginPrefs (polling intervals, timeout, Tomorrow.io config)
  - Compute _loop_interval = min of all per-endpoint intervals
  - Create NetroAPIClient (with prefs callbacks for throttle persistence)
  - Create SprinklerHandler, WhispererHandler, ZoneHandler
  - Create TomorrowClient (or None if not configured)
  - Initialise per-endpoint next-update timers (all set to now → fire immediately)

startup()
  - Logs startup message

runConcurrentThread()
  - Loops every _loop_interval minutes using self.sleep()
  - On each tick, calls _update_from_netro() if due
  - On each tick, calls _update_weather_from_tomorrow() if due
  - On each tick, calls _update_forecast_from_tomorrow() if due

shutdown()
  - Clean shutdown (no explicit teardown needed)
```

---

## Per-Endpoint Polling Timers

Each data type has an independent timer. The main loop sleeps for the
shortest interval so fast endpoints can fire on schedule:

| Timer variable | Default interval | Min interval |
|----------------|-----------------|--------------|
| `_next_device_info_update` | 10 min | 5 min |
| `_next_schedules_update` | 30 min | 10 min |
| `_next_moistures_update` | 10 min | 5 min |
| `_next_events_update` | 5 min | 3 min |
| `_next_sensor_update` | 30 min | 10 min |
| `_next_weather_update` | 30 min | 10 min |
| `_next_forecast_update` | 240 min | 60 min |

---

## Device Hierarchy

Three Indigo device types are defined in
`Netro Sprinklers.indigoPlugin/Contents/Server Plugin/Devices.xml`:

### 1. `sprinkler` — Controller device

- Represents a Netro Sprite, Pixie, or Spark controller
- Inherits Indigo's built-in sprinkler device type
- Key device states: `status`, `activeZone`, `activeScheduleType`,
  `nextScheduleZone`, `nextScheduleTime`, `nextScheduleDuration`,
  `tokenRemaining`, `tokenReset`, `weather_*` fields
- One controller per Indigo device instance
- Config: `address` = serial number (v1 auth), `apiKey` = optional API key
  (v2 auth)

### 2. `Whisperer` — Soil sensor device

- Represents a Netro Whisperer wireless soil/sunlight sensor
- Key device states: `moisture`, `celsius`, `fahrenheit`, `sunlight`,
  `battery_level`, `lastReadingTime`
- Config: `address` = sensor serial number, `apiKey` = optional v2 key

### 3. `zone` — Zone sub-device (auto-created)

- One device per enabled zone on a controller
- Auto-created by `Plugin._ensure_zone_devices()` when controller first seen
- Renamed automatically if the zone is renamed in the Netro app
- Key states: moisture level, enabled status, zone name
- Linked to parent controller via `pluginProps["parentDeviceId"]`
- Zone number stored in `pluginProps["zoneNumber"]`

---

## State Update Flow

```
runConcurrentThread()
  └── _update_from_netro()
        └── for each enabled Indigo device:
              ├── Sprinkler: api_client.get_device_info()
              │     ├── sprinkler_handler.process_device_info() → state dict
              │     ├── sprinkler_handler.process_schedules()   → state dict
              │     ├── sprinkler_handler.process_moistures()   → state dict
              │     └── dev.updateStatesOnServer(states)
              │
              ├── Sprinkler (v2 only): api_client.get_events()
              │     └── fire Indigo triggers on new events
              │
              ├── Sprinkler: _ensure_zone_devices()  (auto-create zone devs)
              │     └── _update_zone_devices()       (update zone dev states)
              │
              ├── Sprinkler: _ensure_zone_variables()  (create Indigo variables)
              │
              └── Whisperer: api_client.get_sensor_data()
                    ├── whisperer_handler.process_sensor_data() → state dict
                    └── dev.updateStatesOnServer(states)
```

---

## API Client (`api_client.py`)

`NetroAPIClient` is a stateful HTTP client that:

1. Constructs endpoint URLs (v1 or v2) based on `api_version` parameter
2. Enforces the 61-minute throttle lockout (`_throttle_until`)
3. Tracks per-device token budget (`_device_tokens: Dict[str, DeviceTokenState]`)
4. Proactively pauses all calls when any device's `token_remaining < 100`
5. Logs warnings when `token_remaining < 200`
6. Persists throttle state to `pluginPrefs` via injected callbacks
   (`prefs_getter` / `prefs_setter`) — survives plugin restarts
7. Suppresses repeated connection error logs (shows first error, then silently
   retries until success)

Error types raised by `make_request()`:
- `ThrottleDelayError` — rate limit hit or proactive pause
- `NetroAPIError` — API returned `"status": "ERROR"` or error code
- `NetroConnectionError` — `requests.ConnectionError`
- `NetroTimeoutError` — `requests.Timeout`

---

## Device Handlers (`device_handlers.py`)

Handlers are pure Python classes that transform API response dicts into Indigo
state update lists. They do not import `indigo` and do not call the API.

- **`SprinklerHandler`**: processes `info.json`, `schedules.json`,
  `moistures.json` responses into state dicts
- **`WhispererHandler`**: processes `sensor_data.json` into state dicts
- **`ZoneHandler`**: helper for per-zone state extraction

The separation enables full unit testing without an Indigo runtime.

---

## Trigger System

Trigger events are defined in
`Netro Sprinklers.indigoPlugin/Contents/Server Plugin/Events.xml`.

`triggerDict` in `Plugin` maps event names to active `indigo.Trigger` objects.
Fired via `Plugin._fireTrigger(event, dev_id)`.

Operational error events (`OPERATIONAL_ERROR_EVENTS`):
- `startZoneFailed`, `stopFailed`, `setStandbyFailed`, `setMoistureFailed`

Communication error events (`COMM_ERROR_EVENTS`):
- `personCall`, `personInfoCall`, `getScheduleCall`, `forecastCall`

V2 device event types (from `events.json`): `offline`, `online`,
`schedule_started`, `schedule_ended` — fire corresponding Indigo triggers.

---

## Variable System

For each zone on a sprinkler controller, the plugin creates an Indigo variable
in a "Netro" folder to expose moisture levels to other Indigo scripts and
triggers. Variable names follow the pattern:

```
zone_moisture_{device_slug}_{zone_slug}   # multi-zone
zone_moisture_{device_slug}               # single-zone / Pixie
```

Zone→variable mapping is stored as JSON in `dev.pluginProps["zoneVariableMap"]`
and loaded on each update. Variables are renamed if zones are renamed in Netro.
