# INTEGRATIONS.md — External API Integrations

## 1. Netro Public API (NPA)

### Versions

Two API versions are supported simultaneously. Per-device version is
auto-detected from device config: if an `apiKey` prop is set, v2 is used;
otherwise v1 serial-number auth is used. Detection happens in
`Plugin._get_device_auth(dev)` in
`Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py`.

### API v1

- **Base URL**: `https://api.netrohome.com/npa/v1/`
- **Auth**: Serial number passed as `?key={serial}` (GET) or `{"key": serial}` (POST body)
- **Official docs**: https://www.netrohome.com/en/shop/articles/10
- **Timestamp format**: Millisecond Unix epoch — **but often returned as strings**
  (see `docs/API_NOTES.md` quirk #1)

### API v2

- **Base URL**: `https://api.netrohome.com/npa/v2/`
- **Auth**: Per-device 32-char API key, same parameter name `key`
- **Obtain**: netrohome.com → Account → API Key → Generate (per device)
- **Official docs**: https://netrohome.com/en/shop/user_guides/7
- **Timestamp format**: ISO 8601 strings
- **New in v2**: expanded device statuses, `events.json` endpoint, metric units
  for weather, `token_limit` field in meta

### Endpoints

All defined as `Final[str]` constants in
`Netro Sprinklers.indigoPlugin/Contents/Server Plugin/constants.py`:

| Constant | v1 URL | v2 URL | Method |
|----------|--------|--------|--------|
| `DEVICE_INFO_ENDPOINT` / `_V2_` | `info.json` | `info.json` | GET |
| `DEVICE_SCHEDULES_ENDPOINT` / `_V2_` | `schedules.json` | `schedules.json` | GET |
| `DEVICE_MOISTURES_ENDPOINT` / `_V2_` | `moistures.json` | `moistures.json` | GET |
| `DEVICE_SENSOR_DATA_ENDPOINT` / `_V2_` | `sensor_data.json` | `sensor_data.json` | GET |
| `DEVICE_WATER_ENDPOINT` / `_V2_` | `water.json` | `water.json` | POST |
| `DEVICE_STOP_WATER_ENDPOINT` / `_V2_` | `stop_water.json` | `stop_water.json` | POST |
| `DEVICE_SET_STATUS_ENDPOINT` / `_V2_` | `set_status.json` | `set_status.json` | POST |
| `DEVICE_NO_WATER_ENDPOINT` / `_V2_` | `no_water.json` | `no_water.json` | POST |
| `DEVICE_REPORT_WEATHER_ENDPOINT` / `_V2_` | `report_weather.json` | `report_weather.json` | POST |
| `DEVICE_SET_MOISTURE_ENDPOINT` / `_V2_` | `set_moisture.json` | `set_moisture.json` | POST |
| `DEVICE_EVENTS_V2_ENDPOINT` | — | `events.json` | GET (v2 only) |

### Rate Limiting

- **Daily quota**: 2,000 calls/day per device (shared between v1 and v2 keys for the same device)
- **Reset**: Midnight UTC
- **HTTP 429**: Rate limit exceeded — plugin enforces a 61-minute lockout
  (`THROTTLE_LIMIT_MINUTES = 61` in `constants.py`)
- **Proactive pause**: When `token_remaining < TOKEN_PAUSE_THRESHOLD` (100),
  polling is suspended before hitting the limit
- **Warning threshold**: `TOKEN_WARNING_THRESHOLD = 200` — logs a warning

### Polling budgets at default intervals

| Interval | Calls/day | Safety |
|----------|-----------|--------|
| 3 min (minimum) | ~480 | Safe |
| 5 min (events default) | ~288 | Very safe |
| 10 min (device info/moisture default) | ~144 | Comfortable |
| 30 min (schedules/sensor default) | ~48 | Very conservative |

### Response envelope

```json
{
  "status": "OK",
  "data": { ... },
  "meta": {
    "token_remaining": 1850,
    "token_reset": "2026-04-08T00:00:00"   // v2 ISO; v1 is Unix timestamp
  }
}
```

Error codes: `1`=invalid key, `3`=rate limit, `4`=invalid device,
`5`=server error, `6`=parameter error.

### Known API Quirks (see `docs/API_NOTES.md` for full details)

1. Timestamps sometimes returned as strings, not numbers — plugin normalises with
   `float(raw) if isinstance(raw, str) else raw`
2. Device info response uses singular `device` key, not `devices` array
3. `STANDBY` status means offline OR user-set standby (ambiguous)
4. `zones[].smart` can be boolean (v1) or string enum `SMART`/`ASSISTANT`/`TIMER` (v2)
5. Moisture data updates once per day maximum
6. Whisperer sensor reports every 4-6 hours (no force-refresh API)
7. Weather units differ: v1 uses US units (°F, inches, mph, inHg); v2 uses metric

---

## 2. Tomorrow.io Weather API (optional)

- **Purpose**: Fetch real-time and forecast weather to report to Netro for
  smarter scheduling decisions
- **Client**: `TomorrowClient` in
  `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/tomorrow_client.py`
- **Auth**: API key configured in plugin prefs (`tomorrowApiKey`)
- **Location**: Lat/lon string configured in plugin prefs (`tomorrowLocation`)
- **Endpoints used**:
  - Realtime weather (current conditions)
  - Daily forecast (multi-day ahead)
- **Units**: Tomorrow.io returns metric; client passes metric through. `plugin.py`
  converts to US units when forwarding to Netro v1 via
  `convert_weather_metric_to_us()` in `utils.py`
- **Condition mapping**: Tomorrow.io weather codes (1000–8000) mapped to Netro
  condition codes (0=Clear, 1=Cloudy, 2=Rain, 3=Snow, 4=Wind) via
  `_TOMORROW_TO_NETRO_CONDITION` dict in `tomorrow_client.py`
- **Optional**: Feature disabled if `tomorrowEnabled` pref is False or API key /
  location not set; `_tomorrow_client` will be `None`
- **Polling intervals**: Realtime every 30 min (`DEFAULT_WEATHER_UPDATE_INTERVAL_MINUTES`),
  forecast every 4 hours (`DEFAULT_FORECAST_INTERVAL_MINUTES`)

### v1 vs v2 unit handling for weather

`utils.py` provides bidirectional converters:

| Function | Direction |
|----------|-----------|
| `convert_weather_metric_to_us()` | °C→°F, mm→in, m/s→mph, hPa→inHg |
| `convert_weather_us_to_metric()` | reverse |

Note: v1 Netro API does not accept `t_dew` field — plugin strips it before
sending to v1 devices.
