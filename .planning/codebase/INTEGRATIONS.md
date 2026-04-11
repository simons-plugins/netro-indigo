# External Integrations

**Analysis Date:** 2026-04-11

## APIs & External Services

**Netro Public API (NPA) — Primary:**
- Netro smart irrigation controller API — device info, schedules, moisture levels, watering control, rain delay, sensor data, weather reporting
  - SDK/Client: `NetroAPIClient` class in `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/api_client.py`
  - Auth: Device serial number (v1) passed as `?key=<serial>` query param; API key (v2) passed the same way
  - Base URLs:
    - v1: `https://api.netrohome.com/npa/v1/` (serial auth)
    - v2: `https://api.netrohome.com/npa/v2/` (API key auth)
  - Rate limit: 2000 tokens/device/day; HTTP 429 or error code 3 triggers throttle
  - Throttle handling: state persisted to `pluginPrefs["throttle_state"]` as JSON; auto-restores on plugin restart
  - Supported endpoints (both v1 and v2 unless noted):
    - `info.json` — device status and zone info
    - `schedules.json` — watering schedules
    - `moistures.json` — per-zone moisture levels
    - `sensor_data.json` — Whisperer soil sensor readings
    - `water.json` — start watering (zones, duration, delay)
    - `stop_water.json` — stop active watering
    - `set_status.json` — online/standby toggle
    - `no_water.json` — rain delay (N days)
    - `report_weather.json` — push local weather data to improve smart scheduling
    - `set_moisture.json` — override zone moisture
    - `events.json` — device events (v2 only; online/offline/schedule start/end)

**Tomorrow.io Weather API — Secondary:**
- Real-time weather and daily forecast fetched to report to Netro's `report_weather` endpoint, improving smart irrigation scheduling
  - SDK/Client: `TomorrowClient` class in `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/tomorrow_client.py`
  - Auth: API key passed as `?apikey=<key>` query param; key stored in `pluginPrefs` (configured via `PluginConfig.xml` UI)
  - Endpoints used:
    - `https://api.tomorrow.io/v4/weather/realtime` — current conditions
    - `https://api.tomorrow.io/v4/weather/forecast` — daily forecast (`timesteps=1d`)
  - Response format: metric units (Celsius, mm, m/s, hPa)
  - Weather codes mapped to Netro conditions (0=Clear, 1=Cloudy, 2=Rain, 3=Snow, 4=Wind) via `_TOMORROW_TO_NETRO_CONDITION` dict in `tomorrow_client.py`
  - Default poll interval: 30 min realtime, 4 hours forecast (configurable via `pluginPrefs`)
  - Free tier provides ~6 days of daily forecast data

## Data Storage

**Databases:**
- None — no external database

**Plugin Preferences (Indigo-managed persistence):**
- All persistent state stored in Indigo's `pluginPrefs` dict
- Key entries:
  - `throttle_state` — JSON blob with per-device token budgets and throttle expiry
  - `showDebugInfo`, `apiTimeout`, polling interval prefs
  - Tomorrow.io API key and location
- Access pattern: `self.pluginPrefs.get(key, default)` / `self.pluginPrefs.__setitem__(key, value)`
- Callbacks passed into `NetroAPIClient`: `prefs_getter` and `prefs_setter` lambdas (in `plugin.py` at `NetroAPIClient` instantiation)

**File Storage:**
- Local filesystem only — plugin icon at `Netro Sprinklers.indigoPlugin/Contents/Resources/icon.png`
- No file-based data storage

**Caching:**
- In-memory only — device state cached in `self.person`, `self.netro_devices`, `self.zone_handler` during plugin runtime
- Throttle state persisted to `pluginPrefs` across restarts

## Authentication & Identity

**Netro v1 Auth:**
- Device serial number — passed as URL query param `?key=<serial>`
- No bearer tokens; no user account credentials

**Netro v2 Auth:**
- API key — passed as URL query param `?key=<api_key>`
- Configured per Indigo device in device config UI

**Tomorrow.io Auth:**
- API key — passed as `?apikey=<key>` query param
- Configured at plugin level via `PluginConfig.xml`; stored in `pluginPrefs`
- Key is masked in debug logs: `url.split("key=")[0] + "key=***"` (in `api_client.py` `make_request`)

## Monitoring & Observability

**Error Tracking:**
- None (no Sentry, Rollbar, or similar)

**Logs:**
- Indigo event log via `self.logger` (provided by `indigo.PluginBase`)
- Log levels: `debug`, `info`, `warning`, `error`, `exception`
- Connection errors suppressed after first occurrence to avoid log spam (`_last_error_type` field in `NetroAPIClient`)
- API key values masked before logging

## CI/CD & Deployment

**Hosting:**
- Plugin runs on macOS Indigo server (typically `jarvis.local` per workspace CLAUDE.md)
- No cloud hosting

**CI Pipeline:**
- None detected (no `.github/workflows/`, no CircleCI, no Travis)
- Manual deployment: copy plugin bundle to `/Volumes/Macintosh HD-1/Library/Application Support/Perceptive Automation/Indigo 2025.1/Plugins/`

**Version Control:**
- GitHub: `https://github.com/simons-plugins/netro-indigo.git`
- Version in `Info.plist`: `PluginVersion = 2026.4.0`

## Environment Configuration

**Required configuration (set via Indigo plugin UI, stored in pluginPrefs):**
- Netro device serial number or API key — per Indigo device
- Tomorrow.io API key — plugin-level preference (optional; disables weather reporting if absent)
- Tomorrow.io location string (lat,lon or place name) — plugin-level preference

**Dev/test environment:**
- `.env` file present but git-ignored; used for local testing (likely contains test API keys)
- `docs/test_local_api.py` — manual local API testing script

**Secrets location:**
- Runtime: Indigo `pluginPrefs` (encrypted by Indigo/macOS Keychain)
- Development: `.env` file (git-ignored)

## Webhooks & Callbacks

**Incoming:**
- None — plugin polls Netro API on a timer; no webhooks received

**Outgoing:**
- `report_weather` POST to Netro API — plugin pushes local weather data to Netro to influence smart scheduling
- All other interactions are GET/POST polling (not event-driven from the plugin's perspective)

---

*Integration audit: 2026-04-11*
