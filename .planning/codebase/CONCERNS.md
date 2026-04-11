# Codebase Concerns

**Analysis Date:** 2026-04-11

## Tech Debt

**V2 Status Set Incomplete — SLEEPING and POWEROFF Treated as Offline:**
- Issue: `V2_ONLINE_STATUSES` only includes `"ONLINE"` and `"WATERING"`. The v2 API returns 7 status values: `STANDBY`, `SETUP`, `ONLINE`, `WATERING`, `OFFLINE`, `SLEEPING`, `POWEROFF`. `SLEEPING` (battery-powered deep sleep) is treated as offline, but may be a temporary low-power state where the device is functionally available. `SETUP` is also unhandled.
- Files: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/constants.py` (line 193), `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/device_handlers.py` (line 99)
- Impact: Users with battery-powered controllers may see spurious offline error states during normal sleep cycles.
- Fix approach: Review Netro v2 documentation for intended semantics of `SLEEPING`/`SETUP`, add appropriate status values or treat `SLEEPING` as a degraded-but-online state.

**Legacy `ZONE_START_ENDPOINT` Used for Zone On (v1 Only, No v2 Counterpart):**
- Issue: `actionControlSprinkler()` calls `self.api_client.make_request(ZONE_START_ENDPOINT, ...)` with a PUT method — this is the legacy `/zone/start` endpoint and does not route through `_get_device_auth()`. For v2 devices (API key auth), this call uses the wrong auth and the wrong endpoint.
- Files: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py` (line 1530), `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/constants.py` (line 76)
- Impact: Zone On action silently fails for v2 devices. No trigger or error clearly attributes the failure to this cause.
- Fix approach: Replace with `self.api_client.start_watering(key, zones, api_version=api_version)` after resolving v2 zone ID format (which may differ between v1 and v2).

**`import re` Inside a Method:**
- Issue: `_slugify()` in `plugin.py` does `import re` inside the static method body. While Python caches module imports, this is non-standard and could confuse linters or static analysis tools.
- Files: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py` (line 250)
- Impact: Negligible runtime cost, but poor style; `re` should be a top-level import.
- Fix approach: Move `import re` to the top-level imports section of `plugin.py`.

**`setNoWater` Trigger Name Mismatch:**
- Issue: `_fireTrigger("setNoWater", dev.id)` fires the trigger `"setNoWater"`, but the `COMM_ERROR_EVENTS` and `OPERATIONAL_ERROR_EVENTS` sets use distinct names like `"setStandbyFailed"`. There is no event named `"setNoWater"` registered in `Events.xml` — it would silently fail to match any trigger type.
- Files: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py` (line 1629)
- Impact: Rain delay failures do not fire user triggers; users cannot automate responses to rain delay errors.
- Fix approach: Either add `"setNoWaterFailed"` to `OPERATIONAL_ERROR_EVENTS` and `Events.xml`, or correct the trigger name to an existing one like `"commError"`.

**Dual Headers Dict — Plugin and APIClient Both Define HTTP Headers:**
- Issue: `Plugin.__init__()` initializes `self.headers` (lines 125-129) but never uses it. All actual HTTP calls go through `NetroAPIClient` which has its own headers. The plugin-level headers dict is dead code from the pre-refactor era.
- Files: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py` (lines 125-129)
- Impact: Confusing to read; could mislead future developers into calling `requests` directly from `plugin.py`.
- Fix approach: Remove the `self.headers` assignment from `Plugin.__init__()`.

**Polling Timers Not Reset When Prefs Change:**
- Issue: When polling intervals are updated via `closedPrefsConfigUi()`, the main `_loop_interval` sleep is recalculated, but the per-endpoint `_next_*_update` timers are not reset. An endpoint set to 60-minute polling that fires at T+0 will still fire at T+60 regardless of whether the interval was changed to 5 minutes at T+10.
- Files: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py` (lines 1196-1220)
- Impact: After changing polling intervals, users must wait for the old interval to expire before seeing the new cadence take effect. This is particularly noticeable for long-interval endpoints like schedules (default 30 min).
- Fix approach: When an interval is reduced in `closedPrefsConfigUi()`, reset the corresponding `_next_*_update` to `datetime.now()` to trigger immediate next-cycle execution.

**`battery_level` for Whisperer Returns Float (0.0-1.0) in v2 but Int (0-100) in v1:**
- Issue: The v2 API returns `battery_level` as a float `0.0-1.0` (per `NETRO_API_V2.md` line 116), while v1 returns it as an integer 0-100. `WhispererHandler.process_sensor_data()` calls `dev_states.get("battery_level", 0)` without version-aware conversion, meaning v2 devices will show battery as `0.85` instead of `85`.
- Files: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/device_handlers.py` (line 564)
- Impact: Incorrect battery level display for v2 Whisperer sensors.
- Fix approach: In `WhispererHandler.process_sensor_data()`, check `api_version` and multiply by 100 when v2 float format is detected.

## Known Bugs

**Zone On Action Uses Wrong Endpoint for v2 Devices:**
- Symptoms: Starting a zone via Indigo sprinkler controls on a v2-authenticated device sends a PUT to the v1 `/zone/start` endpoint without the v2 API key, causing an authentication failure or incorrect behavior. No clear error is shown.
- Files: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py` (line 1530)
- Trigger: User performs Zone On action on a sprinkler device configured with an API key (v2 mode).
- Workaround: Use the custom "Start Zone with Delay" action (via `startZoneWithDelay()`), which correctly uses `_get_device_auth()`.

**`person` Dict Overwrites on Each Poll — Multi-Device Support is Broken:**
- Symptoms: `_update_sprinkler_device()` rebuilds `self.person` from each device's API response in sequence. If multiple sprinkler devices exist, each overwrites the shared `self.person` and `self.netro_devices`. Any code that reads `self.person` after the loop sees only the last device's data.
- Files: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py` (lines 780-783)
- Trigger: User has two or more sprinkler controller devices configured.
- Workaround: Use separate plugin instances per controller (documented as a known limitation).

## Security Considerations

**API Keys Stored in Indigo pluginProps (Plaintext):**
- Risk: v2 API keys are stored as plaintext values in Indigo device pluginProps, which are persisted to Indigo's XML database on disk. If the Indigo database file is accessed by another process or user, the key is exposed.
- Files: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py` (line 371), `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/validators.py` (line 353)
- Current mitigation: API key is masked in debug log output (`masked_url` in `api_client.py` line 285). Indigo itself provides no encryption for pluginProps.
- Recommendations: This is an Indigo platform limitation that cannot be fully addressed at the plugin level. Consider documenting to users that the API key provides only device-level access (not account access) to reduce perceived risk. Do not log the key or include it in trigger payloads.

**Tomorrow.io API Key Stored in Indigo pluginPrefs (Plaintext):**
- Risk: Same pattern as above — Tomorrow.io API key is stored in pluginPrefs and persisted to disk.
- Files: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py` (lines 386-387)
- Current mitigation: None beyond not logging it.
- Recommendations: Same as above — document the limited blast radius of a leaked Tomorrow.io key (rate-limited, not billing-linked on free tier).

**Serial Number Used as URL Parameter (v1):**
- Risk: The device serial number is embedded in API request URLs as `?key={serial}`. This serial appears in HTTP access logs on any intermediary proxy/router, and in debug logs if `masked_url` logic is bypassed.
- Files: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/api_client.py` (lines 285, 657)
- Current mitigation: `masked_url` masks only `key=` params in debug logs. v1 serial is still logged correctly.
- Recommendations: v2 API key is treated the same as v1 serial for masking, which is correct. No further mitigation available without Netro API changes.

## Performance Bottlenecks

**Zone Variable Scan Iterates All Sprinkler Devices on Every Variable Change:**
- Problem: `variableUpdated()` loops over all `self.sprinkler` devices and parses their `zoneVariableMap` JSON on every Indigo variable change — not just zone moisture variables.
- Files: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py` (lines 1429-1484)
- Cause: No precomputed reverse index mapping variable IDs to (device, zone) pairs. The reverse scan happens on every `variableUpdated()` call because Indigo subscribes to ALL variable changes at startup (line 1030).
- Improvement path: Build and cache a `{var_id: (dev_id, zone_num)}` lookup dict at startup and update it in `_ensure_zone_variables()`. Early-exit `variableUpdated()` on cache miss without scanning all devices.

**Schedule Processing Re-Sorts and Re-Scans on Every Polling Cycle:**
- Problem: `process_schedules()` and `process_zone_schedules()` iterate all schedules returned by the API to find the current and next schedule. At 50 schedules per device, this is O(n) per device per poll cycle, run on every device info + schedule refresh.
- Files: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/device_handlers.py` (lines 169-200, 614-630)
- Cause: No caching of schedule parse results between polls. Data is reprocessed even when the API returns the same response.
- Improvement path: Compare response hash or schedule list length before reprocessing. For typical usage (3-5 devices, 50 schedules each), this is negligible but worth noting as device count grows.

**Forecast Reporting Makes N API Calls Per Device Per Day:**
- Problem: `_update_forecast_from_tomorrow()` calls `report_weather` once per forecast day per device. With 6 forecast days and 3 sprinkler devices, each forecast cycle consumes 18 Netro API tokens.
- Files: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py` (lines 543-575)
- Cause: Netro's report_weather API is per-day, requiring one call per forecast day. No way to batch.
- Improvement path: Reduce default `forecastInterval` or limit forecast days sent. Consider only sending the current + next day rather than all 6.

## Fragile Areas

**`_get_device_dict()` Uses `self.person["devices"]` — KeyError if `person` Not Yet Populated:**
- Files: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py` (lines 186-190)
- Why fragile: `self.person` is initialized to `{}` in `__init__`. `_get_device_dict()` immediately accesses `self.person["devices"]` without checking if the key exists. If called before the first successful API poll (e.g. from `setNoWater()` before any poll has run), this raises a `KeyError`.
- Safe modification: Always guard with `self.person.get("devices", [])` instead of `self.person["devices"]`.
- Test coverage: No test exercises `_get_device_dict()` on an uninitialized plugin.

**Zone Variable Mapping Stored as JSON String in pluginProps:**
- Files: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py` (lines 273-348)
- Why fragile: `zoneVariableMap` is serialized as a JSON string in `dev.pluginProps`. If the JSON is malformed (e.g., due to a partial write), `_ensure_zone_variables()` silently resets the map and recreates variables, potentially creating duplicates with name conflicts. The error path at line 329 catches `Exception` and attempts to recover by looking up the variable by name, which may pick up a wrong variable.
- Safe modification: Add a schema version field to the JSON and validate structure before use. Add a dry-run path that checks for name conflicts before writing.
- Test coverage: No tests cover the corruption/recovery path.

**`runConcurrentThread()` Catches All Exceptions and Continues:**
- Files: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py` (lines 1074-1076)
- Why fragile: The outer exception handler at line 1074 catches any `Exception` not already handled by the per-device update methods. While this prevents the thread from dying, it means transient bugs (e.g., a `NameError` in new code) will be silently swallowed and retried every polling cycle, flooding the Indigo log with the same error every N minutes without any operator action.
- Safe modification: Consider distinguishing between `Exception` (catch and retry) and programming errors (`AttributeError`, `NameError`) that should be reported at higher severity. The current approach is acceptable for a home automation plugin but makes bug reproduction harder.
- Test coverage: Not directly testable without Indigo runtime.

**`_update_sprinkler_device()` Only Updates Zone Devices When Device Info Also Fires:**
- Files: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py` (lines 792-840)
- Why fragile: Schedules, moistures, and zone device updates are gated inside the `if now >= self._next_device_info_update` block. If the device info endpoint fires on a different cycle than moistures (e.g., device info every 10 min, moistures every 10 min but offset), moistures data is fetched but never applied to zone devices unless device info also ran. This is by design but the dependency is subtle and not documented in code.
- Safe modification: Cache the last `device_data` response so zone device updates can run independently of device info polling.
- Test coverage: No integration test covers the timer offset scenario.

**`_ensure_zone_devices()` Calls `indigo.device.create()` Without Checking for Name Collisions:**
- Files: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py` (lines 635-656)
- Why fragile: If a zone device already exists with the same name but different `pluginProps` (e.g., the user manually created a device, or `parentDeviceId` changed), `indigo.device.create()` raises an exception. The error is caught and logged, but the zone device is not created, and subsequent polls will keep trying and logging errors.
- Safe modification: Check `existing` dict before calling `create()`. Verify no existing non-zone device shares the name `expected_name`.
- Test coverage: Not covered.

## Scaling Limits

**Single Plugin Instance — One Global `self.person` Dict:**
- Current capacity: Functionally one sprinkler controller per plugin behavior (see multi-device bug above).
- Limit: Two or more sprinkler devices cause `self.person` to only reflect the last-polled device's data. Actions that call `_get_device_dict()` will fail or return incorrect data for all but the last-updated device.
- Scaling path: Replace `self.person` with a `{device_id: person_data}` dict keyed by Indigo device ID, or remove the shared cache entirely since per-device data is already embedded in each device's states/props.

**API Token Budget — 2000/day per Netro Device:**
- Current capacity: With default intervals (device info 10 min, schedules 30 min, moistures 10 min, events 5 min, sensor 30 min) and 1 device: ~approx. 200-300 calls/day, well within limit.
- Limit: Each additional sprinkler or Whisperer device multiplies token consumption. With 5 devices at default intervals and weather forecast reporting (18 calls per cycle), approaching 1200+ calls/day.
- Scaling path: Token pause threshold (`TOKEN_PAUSE_THRESHOLD = 100`) is the safety valve. Consider per-device configurable intervals as a future enhancement.

## Dependencies at Risk

**`requests` Library Bundled as Single Runtime Dependency:**
- Risk: `requirements.txt` pins `requests==2.32.5`. This is a single, stable dependency that Indigo auto-installs. No known active CVEs but `requests` has had HTTP injection vulnerabilities in the past (CVE-2023-32681 fixed in 2.31.0).
- Impact: If Indigo's Python environment drifts or the user has an older version installed, HTTP behaviour may differ.
- Migration plan: No alternative; `requests` is the correct choice for synchronous HTTP in Indigo plugins. Ensure version pinned to 2.31.0+ for the CVE fix.

## Missing Critical Features

**No Rate Limit Trigger for Token Depletion (Only for HTTP 429):**
- Problem: The plugin fires `rateLimitExceeded` only on HTTP 429. Token-budget pause (when `token_remaining < TOKEN_PAUSE_THRESHOLD`) does not fire any trigger, so users cannot automate alerts for proactive token warnings.
- Blocks: Users with high polling frequencies or multiple devices have no automated notification before service interruption.

**No Cleanup When a Zone Device's Parent Controller is Deleted:**
- Problem: Zone devices store their parent's `parentDeviceId` in `pluginProps`, but there is no `deviceStopComm()` or `deviceDeleted()` handler that removes orphaned zone devices when a parent controller is deleted.
- Blocks: Orphaned zone devices accumulate in Indigo after controller removal and require manual cleanup.

## Test Coverage Gaps

**`plugin.py` Has 0% Test Coverage:**
- What's not tested: All plugin lifecycle methods (`startup`, `shutdown`, `runConcurrentThread`), all action handlers (`setNoWater`, `setStandbyMode`, `startZoneWithDelay`, `reportWeather`, `setZoneMoisture`), all Indigo callbacks (`variableUpdated`, `triggerStartProcessing`, `actionControlSprinkler`), and the entire polling loop.
- Files: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py` (898 statements, 0 covered per htmlcov)
- Risk: Any regression in the main plugin class will not be caught by CI. All plugin.py bugs reach production.
- Priority: High — this is the highest-impact gap. Even smoke tests with a heavily mocked `indigo` module would catch most action handler bugs.

**`api_client.py` Has 17% Coverage (Throttle and Error Paths Not Tested):**
- What's not tested: `_handle_http_error()` rate-limit branch, `_restore_throttle_state()` v1→v2 migration path, `_validate_response_schema()`, `should_pause_polling_for()` auto-reset logic.
- Files: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/api_client.py` (205/255 statements missing)
- Risk: Throttle state corruption after restart or during v1→v2 migration is undetected.
- Priority: High — throttle management is critical to API budget safety.

**`tomorrow_client.py` Has 7% Coverage:**
- What's not tested: `fetch_current_weather()`, `fetch_forecast()`, `_transform_response()`, `_transform_forecast_response()`, all HTTP error paths.
- Files: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/tomorrow_client.py` (138/153 statements missing)
- Risk: Weather integration failures will not be caught by tests. Incorrect unit conversion or missing fields could silently corrupt Netro's smart scheduling data.
- Priority: Medium — weather integration is optional but regressions here are hard to detect without live API calls.

**`device_handlers.py` Has 10% Coverage (Most Handler Logic Untested):**
- What's not tested: `SprinklerHandler.process_moistures()`, `SprinklerHandler.extract_zone_info()`, `SprinklerHandler.process_events()`, `WhispererHandler.process_sensor_data()`, `ZoneHandler.process_zone_schedules()`, all v2 code paths in schedule/timestamp handling.
- Files: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/device_handlers.py` (219/250 statements missing)
- Risk: API response parsing bugs will reach production silently.
- Priority: High — these are pure Python functions with no Indigo dependency and are straightforward to unit test.

**`validators.py` Has 10% Coverage Despite Clean Architecture:**
- What's not tested: `validate_prefs_config()`, `validate_action_config()` for `reportWeather` and `setMoisture` action types, `validate_event_config()`, `validate_api_key()`, `is_indigo_substitution()`.
- Files: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/validators.py` (193/226 statements missing)
- Risk: Invalid user configurations that should be rejected may be accepted and cause runtime errors.
- Priority: Medium — validators are pure functions that are easy to test. The gap is surprising given the modular design.

---

*Concerns audit: 2026-04-11*
