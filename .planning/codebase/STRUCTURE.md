# STRUCTURE.md — Directory Layout

## Top-Level

```
netro/
├── .planning/codebase/          ← this documentation
├── docs/                        ← developer documentation
│   ├── CLAUDE.md                ← detailed architecture guide (primary reference)
│   ├── NETRO_API.md             ← NPA v1 endpoint reference
│   ├── NETRO_API_V2.md          ← NPA v2 endpoint reference
│   ├── API_NOTES.md             ← discovered quirks and edge cases
│   ├── TESTING.md               ← test suite guide
│   ├── LOCAL_TESTING.md         ← standalone API test script guide
│   └── TROUBLESHOOTING.md       ← user-facing troubleshooting
├── Netro Sprinklers.indigoPlugin/  ← plugin bundle (macOS double-click to install)
├── tests/                       ← pytest suite
├── htmlcov/                     ← coverage HTML output (gitignored)
├── CLAUDE.md                    ← root project instructions
├── README.md
├── pyproject.toml               ← pylint + pytest config
├── pytest.ini                   ← pytest path config
├── test_local_api.py            ← standalone CLI API tester (not in tests/)
├── .env                         ← local secrets (gitignored)
└── .coverage                    ← coverage data file
```

## Plugin Bundle

```
Netro Sprinklers.indigoPlugin/
└── Contents/
    ├── Info.plist               ← plugin metadata, version, bundle ID
    └── Server Plugin/           ← all Python source
        ├── plugin.py            ← Plugin(indigo.PluginBase), ~1900 lines
        ├── api_client.py        ← NetroAPIClient
        ├── device_handlers.py   ← SprinklerHandler, WhispererHandler, ZoneHandler
        ├── validators.py        ← pure validation functions
        ├── constants.py         ← URL constants, defaults, thresholds
        ├── exceptions.py        ← NetroError hierarchy
        ├── utils.py             ← unit conversion helpers
        ├── tomorrow_client.py   ← Tomorrow.io weather client
        ├── requirements.txt     ← runtime deps (requests==2.32.5)
        ├── Devices.xml          ← Indigo device type definitions
        ├── Actions.xml          ← custom action definitions
        ├── Events.xml           ← trigger/event definitions
        ├── PluginConfig.xml     ← plugin preferences UI
        └── MenuItems.xml        ← Indigo plugin menu items
```

## XML Configuration Files

### `Devices.xml`

Defines three device types:

| `deviceTypeId` | Display name | Indigo base type | Description |
|----------------|-------------|-----------------|-------------|
| `sprinkler` | Netro Controller | `indigo.kDeviceType.Sprinkler` | Sprite/Pixie/Spark controller |
| `Whisperer` | Netro Whisperer | plugin custom | Soil moisture sensor |
| `zone` | Netro Zone | plugin custom | Auto-created zone sub-device |

### `Actions.xml`

Defines custom plugin actions (beyond standard sprinkler start/stop):

| Action ID | Python callback | Purpose |
|-----------|----------------|---------|
| `startZoneWithDelay` | `startZoneWithDelay()` | Zone start with optional delay |
| `reportWeather` | `reportWeather()` | Submit local weather to Netro |
| `setNoWater` | `setNoWater()` | Rain delay (N days) |
| `setStandbyMode` | `setStandbyMode()` | Pause all automatic scheduling |

### `Events.xml`

Trigger event types for user automation:

- `startZoneFailed` — zone start API call failed
- `stopFailed` — stop watering failed
- `setStandbyFailed` — standby mode change failed
- `setMoistureFailed` — moisture override failed
- `rateLimitExceeded` — HTTP 429 received
- `personCall`, `personInfoCall`, `getScheduleCall`, `forecastCall` — comm errors
- V2 device events: `offline`, `online`, `schedule_started`, `schedule_ended`

### `PluginConfig.xml`

Plugin-level preferences:

- `apiTimeout` — request timeout seconds (default 5, range 1-60)
- `maxZoneRunTime` — max zone duration seconds (default 10800/3hr)
- Per-endpoint polling intervals (all configurable, each with a minimum)
- `tomorrowEnabled` / `tomorrowApiKey` / `tomorrowLocation` — Tomorrow.io
- `showDebugInfo` — debug logging toggle

## Tests Directory

```
tests/
├── conftest.py                  ← shared fixtures (mock_logger, sample_api_response,
│                                   mock_prefs, sample_api_v2_response, sample_v2_*)
├── test_api_client.py           ← NetroAPIClient unit tests
├── test_base_modules.py         ← constants, exceptions, utils tests
├── test_device_handlers.py      ← SprinklerHandler, WhispererHandler unit tests
├── test_tomorrow_client.py      ← TomorrowClient unit tests
├── test_validators.py           ← validate_* function tests
├── test_weather_integration.py  ← weather unit conversion + integration tests
└── test_zone_handler.py         ← ZoneHandler unit tests
```

Note: `tests/fixtures/` directory referenced in older `docs/TESTING.md` is no
longer present — test data is defined inline in fixtures and test files.

## Key File Paths (absolute)

- Main plugin: `/Users/simon/vsCodeProjects/Indigo/netro/Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py`
- API client: `/Users/simon/vsCodeProjects/Indigo/netro/Netro Sprinklers.indigoPlugin/Contents/Server Plugin/api_client.py`
- Constants: `/Users/simon/vsCodeProjects/Indigo/netro/Netro Sprinklers.indigoPlugin/Contents/Server Plugin/constants.py`
- Tests: `/Users/simon/vsCodeProjects/Indigo/netro/tests/`
- Info.plist: `/Users/simon/vsCodeProjects/Indigo/netro/Netro Sprinklers.indigoPlugin/Contents/Info.plist`
- pyproject.toml: `/Users/simon/vsCodeProjects/Indigo/netro/pyproject.toml`

## Installed Location (Indigo server)

```
/Volumes/Macintosh HD-1/Library/Application Support/Perceptive Automation/
  Indigo 2025.1/Plugins/Netro Sprinklers.indigoPlugin/
```
