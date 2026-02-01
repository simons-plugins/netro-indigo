# External Integrations

**Analysis Date:** 2026-02-01

## APIs & External Services

**Netro Smart Irrigation API:**
- Service: Netro Public API (NPA) v1
- What it's used for: Complete control and monitoring of Netro sprinkler controllers and Whisperer sensors
  - SDK/Client: `requests` library (2.32.5)
  - Auth: Device serial number as URL parameter (`key={serial}`)
  - Base URL: `http://api.netrohome.com/npa/v1/`

**Supported Devices:**
- Netro Sprite
- Netro Pixie
- Netro Spark
- Whisperer soil moisture sensors

## API Endpoints

Location: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py:60-74`

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `info.json` | GET | Get device status, zones, model, serial number |
| `schedules.json` | GET | Get current and upcoming watering schedules |
| `moistures.json` | GET | Get soil moisture levels per zone |
| `sensor_data.json` | GET | Get Whisperer sensor readings (moisture, temp, sunlight) |
| `water.json` | POST | Start watering zone(s) with optional delay/schedule |
| `stop_water.json` | POST | Stop all watering |
| `set_status.json` | POST | Set standby mode on/off |
| `no_water.json` | POST | Set rain delay (N days no watering) |
| `report_weather.json` | POST | Report local weather for AI scheduling |
| `zone/start` | PUT | Start specific zone (alternative endpoint) |

## Rate Limiting

**API Quota:**
- Daily limit: 2,000 API calls per day
- Reset time: Midnight UTC (stored in `meta.token_reset`)
- Remaining quota: Tracked in `meta.token_remaining`

**Plugin Rate Limit Management:**
- Location: `plugin.py:91-98, 195-335`
- Throttle enforcement: 61-minute backoff on HTTP 429 or API error code 3
- Throttle state: `self.throttle_next_call` datetime
- Automatic reset: Clears when expiry time passes
- Default polling (3 min): ~480 calls/day (safe)
- Aggressive polling (1 min): ~1440 calls/day (risky)

**Error Handling:**
- HTTP 429 responses trigger `ThrottleDelayError` exception
- Netro API error code 3 (rate limit) parsed from JSON response
- Fallback to 61-minute delay if reset time cannot be parsed
- Logs warning and fires "rateLimitExceeded" trigger

## Data Storage

**In-Memory Caching:**
- `self.person` - Cached device data from last API call
  - Structure: `{"id": serial, "devices": [...]}`
  - Updated every poll cycle in `_update_from_netro()`
- `self.netro_devices` - Flattened list of cached devices
- `self.key_val_list` - Cached Whisperer sensor readings

**Indigo Device State Storage:**
- Device states for sprinkler controllers:
  - `id` - Controller serial number
  - `status` - ONLINE/OFFLINE
  - `activeZone` - Currently watering zone (1-16)
  - `activeSchedule` - Current schedule type (Smart, Manual, etc.)
  - `nextScheduleTime` - Next scheduled watering timestamp
  - `nextScheduleZone` - Next zone name
  - `token_remaining` - API calls left today
  - `zone_1_moisture` through `zone_16_moisture` - Per-zone moisture %
  - `paused`, `scheduleModeType`, `model`, `api_version` - Metadata

- Device states for Whisperer sensors:
  - `sensorValue` - Current moisture percentage
  - `humidity` - Soil moisture
  - `temperature` - Celsius reading
  - `soilTemperature` - Same as temperature
  - `sunlight` - Lux reading
  - `batteryLevel` - Battery percentage
  - `readingTime`, `readingLocalDate`, `readingLocalTime` - Timestamps
  - `token_remaining`, `token_reset` - API quota info

**Databases:**
- None used - pure API integration with in-memory caching

**File Storage:**
- None - all configuration in Indigo database

**Caching:**
- In-memory only, no persistence across plugin restarts
- Cache refreshed every polling interval (default 3 minutes)

## Authentication & Identity

**Auth Provider:**
- Custom: Serial number-based authentication
- Implementation: Device serial number passed as `key` parameter in all API calls
  - Query parameter format: `?key={serial}` for GET requests
  - JSON body format: `{"key": "{serial}", ...}` for POST/PUT requests
- Serial number location: Device configuration (set by user during setup)
- Serial number source: Found on physical device or Netro mobile app Settings

**Security Considerations:**
- Serial numbers are not secret - Netro treats them as public
- Serial number grants full API access to controller
- No bearer tokens, API keys, or OAuth used
- Plugin requires active internet connection to api.netrohome.com

## Monitoring & Observability

**Error Tracking:**
- None (no external error tracking service)
- All errors logged to Indigo Event Log via `self.logger`

**Logging:**
- Framework: Indigo's built-in logging (`indigo.PluginBase.logger`)
- Levels used:
  - `logger.debug()` - Verbose output, API call details
  - `logger.info()` - Normal operation, state changes
  - `logger.warning()` - Rate limit warnings, token low
  - `logger.error()` - API errors, validation failures
  - `logger.exception()` - Full stack traces (via traceback format)
- Destination: Indigo Event Log (viewable in Indigo UI)

**Monitoring Points:**
- API token counts logged at polling (tokens <50: error, <200: warning, <500: info)
- Connection errors logged once, then silent retries
- Throttle state displayed in error messages with retry time
- Device online/offline status updated every poll

## Webhooks & Callbacks

**Incoming:**
- None - plugin uses pull model (polling) not push (webhooks)

**Outgoing:**
- None - Netro API does not provide webhook support
- Plugin can send data via `report_weather.json` endpoint but does not receive callbacks

**Internal Callbacks (Indigo Framework):**
- Location: `plugin.py:1162-1233`
- `deviceStartComm()` - Triggers initial API update when device enabled
- `deviceStopComm()` - Called when device disabled
- `triggerStartProcessing()` - Called when Indigo trigger enabled
- `triggerStopProcessing()` - Called when Indigo trigger disabled
- `closedPrefsConfigUi()` - Applies config changes without plugin restart

## Events & Triggers

**Plugin-defined Triggers** (defined in `Events.xml`):
- `sprinklerError` - Zone start, stop, or standby mode failures
- `commError` - API communication failures
- `rateLimitExceeded` - API rate limit hit
- `setNoWater` - Rain delay action failed
- `setStandbyFailed` - Standby mode action failed
- `startZoneFailed` - Zone start action failed
- `stopFailed` - Stop all zones action failed
- `getScheduleCall` - Schedule fetch failed
- `personInfoCall` - Device info fetch failed
- `forecastCall` - Forecast/weather fetch failed

**Trigger Firing:**
- Location: `plugin.py:1134-1174`
- Method: `_fireTrigger(event, dev_id=None)`
- Fired during API errors to enable user automation
- Example: Alert user when rate limit exceeded

**Standard Indigo Triggers Used:**
- `RequestStatus` action - Forces immediate API update
- Sprinkler Zone On/Off actions - Standard Indigo sprinkler control

## Plugin Configuration Flow

1. **User installs plugin** → Indigo loads `Info.plist`
2. **User configures plugin** → Sets polling interval, timeout, max zone runtime in `PluginConfig.xml` UI
3. **User creates device** → Specifies Netro controller serial number
4. **Plugin validates config** → `validateDeviceConfigUi()` and `validatePrefsConfigUi()`
5. **Device enabled** → `deviceStartComm()` triggers immediate `_update_from_netro()` call
6. **Concurrent thread starts** → Polls API every N minutes (minimum 3)
7. **API responses parsed** → Device states updated in Indigo
8. **User creates actions** → Custom actions for rain delay, weather reporting, zone delay
9. **User creates triggers** → Event triggers fire on errors

## Environment Configuration

**Required env vars:**
- None - all configuration via Indigo UI

**Secrets location:**
- Device serial numbers stored in Indigo device configuration
- Not in environment variables or config files
- Stored encrypted by Indigo database

**Connection Testing:**
- Plugin includes standalone test utility: `docs/test_local_api.py`
- Useful for debugging API connectivity before plugin integration

---

*Integration audit: 2026-02-01*
