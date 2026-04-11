# Technology Stack

**Analysis Date:** 2026-04-11

## Languages

**Primary:**
- Python 3.10+ - All plugin logic; `pyproject.toml` sets `requires-python = ">=3.10"`
- Python 3.11 - Development host runtime (3.11.6 detected via `python3 --version`)

**Secondary:**
- XML - Indigo plugin configuration files (`Devices.xml`, `Actions.xml`, `Events.xml`, `MenuItems.xml`, `PluginConfig.xml`)
- Plist - Plugin metadata (`Info.plist`)

## Runtime

**Environment:**
- macOS (Indigo home automation platform runs on macOS only)
- Plugin runs inside Indigo's Python 3.10+ interpreter at `/Library/Frameworks/Python.framework/Versions/Current/bin/python3`

**Package Manager:**
- pip (no lockfile — `requirements.txt` pins exact versions)
- Lockfile: Not present (only `requirements.txt` with pinned versions)
- Indigo auto-installs packages from `requirements.txt` on plugin load

## Frameworks

**Core:**
- `indigo.PluginBase` - Indigo home automation SDK base class; plugin class `Plugin` in `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py` inherits from it
- No web framework (Indigo provides the runtime and UI via XML config files)

**Testing:**
- pytest 7.4.3 - Test runner; config in `pytest.ini` and `pyproject.toml`
- pytest-cov 4.1.0 - Coverage reporting (85% minimum enforced via `[coverage:report] fail_under = 85`)

**Build/Dev:**
- pylint - Static analysis; configured in `pyproject.toml` with minimum score 9.0
- No build system (plugin is deployed by copying the `.indigoPlugin` bundle)

## Key Dependencies

**Critical:**
- `requests==2.32.5` - HTTP client for all Netro API and Tomorrow.io API calls; declared in `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/requirements.txt`

**Standard Library (key usage):**
- `json` - API request/response serialization and throttle state persistence
- `datetime`, `timedelta`, `timezone` - Rate limit token reset tracking
- `dataclasses` - `DeviceTokenState` dataclass in `api_client.py`
- `typing` - Type hints throughout; `Final` for immutable constants
- `logging` - Logger passed as callback into `NetroAPIClient` and `TomorrowClient`
- `unittest.mock` - Mock objects in test suite (`conftest.py`, all test files)
- `pathlib` - Test path manipulation in `conftest.py`

**Infrastructure:**
- `indigo` - Indigo SDK module; imported directly in `plugin.py`; provides `indigo.PluginBase`, device/trigger APIs, `pluginPrefs`

## Configuration

**Environment:**
- `.env` file present (excluded from git per `.gitignore`)
- Plugin user config stored in Indigo's `pluginPrefs` dict (persists across restarts)
- Key plugin prefs: `showDebugInfo`, `apiTimeout`, `eventsInterval`, `deviceInfoInterval`, `moisturesInterval`, `schedulesInterval`, `sensorInterval`, `weatherUpdateInterval`, `forecastInterval`, `maxZoneRunTime`, `throttle_state` (JSON blob)
- Tomorrow.io API key and location configured via `PluginConfig.xml` UI, stored in `pluginPrefs`
- Netro device serial numbers / API keys configured per-device, not globally

**Build:**
- `pyproject.toml` - pylint and pytest configuration
- `pytest.ini` - Pytest options including coverage targets
- No Makefile or build script; deployment is manual bundle copy

## Platform Requirements

**Development:**
- Python 3.10+ (3.11 on development host)
- pytest and pytest-cov installed in dev environment
- pylint installed in dev environment
- Indigo not required to run tests (mocked via `unittest.mock`)

**Production:**
- Indigo 2023.2+ (requires Python 3.10+)
- macOS running Indigo server
- Active internet connection for Netro API and Tomorrow.io API calls
- Plugin bundle: `Netro Sprinklers.indigoPlugin` copied to Indigo Plugins folder

---

*Stack analysis: 2026-04-11*
