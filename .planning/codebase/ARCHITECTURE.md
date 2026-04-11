# Architecture

**Analysis Date:** 2026-04-11

## Pattern Overview

**Overall:** Indigo Plugin with layered separation of concerns

**Key Characteristics:**
- Plugin coordinator (`plugin.py`) owns the Indigo lifecycle and orchestrates all data flow
- No-dependency base modules (constants, exceptions, utils) are importable anywhere
- API clients (`api_client.py`, `tomorrow_client.py`) are pure Python — no `indigo` import
- Device handlers (`device_handlers.py`) transform API responses to Indigo state dicts — no `indigo` import
- Validators (`validators.py`) are pure functions with no side effects — fully testable in isolation

## Layers

**Base Layer (no dependencies):**
- Purpose: Shared constants, exception types, utility functions
- Location: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/constants.py`, `exceptions.py`, `utils.py`
- Contains: API URL constants, timing defaults, exception hierarchy, unit conversion functions
- Depends on: Python stdlib only
- Used by: All other modules

**API Client Layer:**
- Purpose: HTTP communication with external APIs, rate-limit management
- Location: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/api_client.py`, `tomorrow_client.py`
- Contains: `NetroAPIClient` (Netro Public API), `TomorrowClient` (Tomorrow.io weather API)
- Depends on: `constants`, `exceptions`, `requests`
- Used by: `plugin.py`

**Validation Layer:**
- Purpose: Pure validation of user-supplied config before it reaches the plugin
- Location: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/validators.py`
- Contains: `validate_device_config`, `validate_action_config`, `validate_event_config`, `validate_prefs_config`
- Depends on: `constants` only
- Used by: `plugin.py` in `validateDeviceConfigUi` / `validateActionConfigUi` / `validatePrefsConfigUi` callbacks

**Handler Layer:**
- Purpose: Transform raw API response dicts into Indigo state-update lists
- Location: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/device_handlers.py`
- Contains: `SprinklerHandler`, `WhispererHandler`, `ZoneHandler`
- Depends on: `constants`, `utils`
- Used by: `plugin.py`

**Plugin Coordinator:**
- Purpose: Indigo lifecycle, polling loop, Indigo device/variable management
- Location: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py`
- Contains: `Plugin(indigo.PluginBase)` class
- Depends on: All other layers, `indigo` (Indigo SDK)
- Used by: Indigo server (loaded as plugin bundle)

## Data Flow

**Polling Cycle (every `_loop_interval` minutes):**

1. `runConcurrentThread()` wakes and calls `_update_from_netro()`
2. `_update_from_netro()` iterates `indigo.devices.iter(filter="self")` for enabled devices
3. For each sprinkler: `_update_sprinkler_device(dev)` checks per-endpoint timers
4. Per-timer endpoint calls fire: `api_client.get_device_info()` → `api_client.get_schedules()` → `api_client.get_moistures()` → `api_client.get_events()`
5. API responses are passed to handler methods: `sprinkler_handler.process_device_info()` → returns `(state_list, is_online, device_data)`
6. `plugin.py` calls `dev.updateStatesOnServer(state_list)` and `dev.replacePluginPropsOnServer(props)`
7. Zone devices are created/updated via `_ensure_zone_devices()` and `_update_zone_devices()`
8. Indigo variables for moisture are maintained via `_ensure_zone_variables()`

**Weather Flow (optional, Tomorrow.io):**

1. `runConcurrentThread()` calls `_update_weather_from_tomorrow()` and `_update_forecast_from_tomorrow()` on their own timers
2. `TomorrowClient.fetch_current_weather()` / `fetch_forecast()` returns metric weather dict
3. `plugin.py` converts units for v1 devices (`convert_weather_metric_to_us`) — v2 stays metric
4. `api_client.report_weather()` posts to Netro to improve smart scheduling
5. Weather device states updated on the sprinkler device

**User Action Flow:**

1. User invokes action in Indigo UI
2. `plugin.py` action callback validates parameters via `validators.validate_action_config()`
3. Plugin calls `api_client.start_watering()` / `stop_watering()` / `set_no_water()` etc.
4. API response logged; state updated next polling cycle

**State Management:**
- API throttle state persisted to `pluginPrefs["throttle_state"]` as JSON (survives restarts)
- Per-endpoint timers are in-memory `datetime` attributes on the `Plugin` instance
- Zone-to-variable mapping stored in device `pluginProps["zoneVariableMap"]` as JSON
- Last-seen event ID tracked in `self._last_event_ids` dict (in-memory, keyed by Indigo device ID)

## Key Abstractions

**NetroAPIClient (`api_client.py`):**
- Purpose: All HTTP communication with Netro Public API; per-device token budget tracking
- Pattern: Dependency-injection for logger and prefs callbacks — no `indigo` import
- Constructor receives `prefs_getter` / `prefs_setter` callbacks to persist throttle state

**DeviceTokenState (`api_client.py`):**
- Purpose: Dataclass tracking token budget per device (keyed by API key or serial)
- Pattern: Per-device tracking (2000 tokens/day limit is per-device, not account-wide)

**SprinklerHandler / WhispererHandler / ZoneHandler (`device_handlers.py`):**
- Purpose: Stateless transformers — receive API response dict, return list of state update dicts
- Pattern: No `indigo` import, no side effects; fully unit-testable
- Return type: `List[Dict[str, Any]]` matching `updateStatesOnServer()` format

**ValidationResult (`validators.py`):**
- Purpose: Consistent return type from all validators
- Pattern: `Tuple[bool, Dict[str, Any], Dict[str, str]]` — `(is_valid, sanitized_values, errors_dict)`

**Dual API version support (`api_client.py`, `device_handlers.py`, `plugin.py`):**
- Purpose: Support both v1 (serial number auth) and v2 (API key auth) simultaneously
- Pattern: `_get_device_auth(dev)` returns `(key, api_version)` — all downstream calls parameterised by version
- Endpoint selection: `_ENDPOINT_MAP` dict keyed by `(name, version)` in `NetroAPIClient`

## Entry Points

**Plugin Bundle Load:**
- Location: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py`
- Triggers: Indigo server loads plugin bundle on startup or enable
- Responsibilities: `Plugin.__init__()` initialises all state, handlers, clients

**`startup()` (`plugin.py` line ~1002):**
- Triggers: After `__init__`, before first concurrent thread tick
- Responsibilities: Logs API version per device, subscribes to Indigo variable changes

**`runConcurrentThread()` (`plugin.py` line ~1040):**
- Triggers: Called by Indigo after `startup()`; runs until `StopThread`
- Responsibilities: Per-endpoint timer-based polling loop; sleeps `_loop_interval * 60` seconds

**Action Callbacks:**
- Pattern: All action handlers in `plugin.py` validate via `validators.validate_action_config()` then delegate to `api_client`

## Error Handling

**Strategy:** Layered — API layer raises typed exceptions; plugin coordinator catches and logs; polling loop continues

**Patterns:**
- `NetroAPIClient.make_request()` raises `ThrottleDelayError` on rate-limit; `NetroAPIError` on API error; `requests` exceptions propagate
- `ThrottleDelayError` caught silently in `_update_sprinkler_device()` — polling just skips the device
- Connection/timeout errors logged once per error type, then silently retried (suppression via `_last_error_type`)
- Device handlers return error state list on `KeyError`/`TypeError` — never raise
- Validators return `(False, values, errors)` — never raise
- Outer try/except in `runConcurrentThread()` ensures loop never exits on unexpected exception

## Cross-Cutting Concerns

**Logging:** Uses `self.logger` (Indigo's logger) everywhere; API key values masked in debug logs (`key=***`); error suppression avoids log spam on repeated connection failures

**Validation:** All user-facing config goes through `validators.py` before reaching plugin logic; integer-range helpers enforce minimums

**Authentication:** Per-device — `_get_device_auth(dev)` reads `pluginProps["apiKey"]`; if present, uses v2 (API key); otherwise v1 (serial from `dev.address`)

**Rate Limiting:** Proactive — tracks per-device token budget from every response meta; pauses polling when `token_remaining < TOKEN_PAUSE_THRESHOLD` (100); persisted to survive restarts

---

*Architecture analysis: 2026-04-11*
