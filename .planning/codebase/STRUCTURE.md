# Codebase Structure

**Analysis Date:** 2026-04-11

## Directory Layout

```
netro/                                          # Repo root
├── Netro Sprinklers.indigoPlugin/              # Plugin bundle (loaded by Indigo server)
│   └── Contents/
│       ├── Info.plist                          # Plugin metadata, version, bundle ID
│       ├── Resources/
│       │   └── icon.png                        # Plugin icon
│       └── Server Plugin/                      # All Python source (Indigo loads this)
│           ├── plugin.py                       # Main plugin class (entry point)
│           ├── api_client.py                   # Netro API HTTP client
│           ├── tomorrow_client.py              # Tomorrow.io weather API client
│           ├── device_handlers.py              # API response → Indigo state transformers
│           ├── validators.py                   # Pure config validation functions
│           ├── constants.py                    # API URLs, defaults, event sets
│           ├── exceptions.py                   # Custom exception hierarchy
│           ├── utils.py                        # Unit conversions, dict helpers
│           ├── Devices.xml                     # Indigo device type definitions + states
│           ├── Actions.xml                     # Indigo action definitions
│           ├── Events.xml                      # Indigo trigger/event definitions
│           ├── MenuItems.xml                   # Plugin menu item definitions
│           ├── PluginConfig.xml                # Plugin-level preferences UI
│           └── requirements.txt               # Python dependencies
├── tests/                                      # Test suite (runs outside Indigo)
│   ├── conftest.py                             # Pytest fixtures (indigo mock, logger)
│   ├── test_api_client.py                      # NetroAPIClient unit tests
│   ├── test_base_modules.py                    # constants, exceptions, utils tests
│   ├── test_device_handlers.py                 # SprinklerHandler, WhispererHandler tests
│   ├── test_validators.py                      # validators.py unit tests
│   ├── test_tomorrow_client.py                 # TomorrowClient unit tests
│   ├── test_weather_integration.py             # Weather integration tests
│   └── test_zone_handler.py                    # ZoneHandler unit tests
├── docs/                                       # Developer documentation
│   ├── CLAUDE.md                               # Plugin-specific dev guide (primary reference)
│   ├── NETRO_API.md                            # Netro API v1 endpoint documentation
│   ├── NETRO_API_V2.md                         # Netro API v2 endpoint documentation
│   ├── API_NOTES.md                            # Known API quirks and limitations
│   ├── TESTING.md                              # Testing guide
│   ├── LOCAL_TESTING.md                        # Local/manual testing instructions
│   ├── TROUBLESHOOTING.md                      # Common issues and fixes
│   └── plans/                                  # Design documents
│       ├── 2026-04-07-zone-devices-design.md
│       └── 2026-04-07-zone-devices-plan.md
├── .planning/                                  # GSD planning system
│   ├── PROJECT.md                              # Project goals and scope
│   ├── STATE.md                                # Current project state
│   ├── MILESTONES.md                           # Milestone definitions
│   ├── codebase/                               # Codebase analysis docs (this dir)
│   ├── milestones/                             # Milestone files
│   ├── phases/                                 # Completed phase plans + summaries
│   └── research/                               # Research documents
├── .github/workflows/
│   ├── version-check.yml                       # CI: verifies PluginVersion bumped in PRs
│   └── create-release.yml                      # CI: creates GitHub release on version tag
├── pyproject.toml                              # Python project config (pytest, coverage)
├── pytest.ini                                  # Pytest configuration
├── htmlcov/                                    # HTML coverage report (generated, not committed)
└── README.md                                   # Public-facing plugin README
```

## Directory Purposes

**`Netro Sprinklers.indigoPlugin/Contents/Server Plugin/`:**
- Purpose: All Python source that Indigo loads when the plugin is enabled
- Contains: `plugin.py` (main), plus the extracted module files
- Key files: `plugin.py` (coordinator), `api_client.py` (Netro HTTP), `device_handlers.py` (state transform)
- Note: The `Server Plugin/` name is an Indigo convention — do not rename

**`tests/`:**
- Purpose: Pytest test suite that runs outside Indigo (no Indigo server required)
- Contains: One test file per source module; `conftest.py` provides `indigo` mock
- Key files: `conftest.py` (mock setup), `test_api_client.py` (most critical coverage)

**`docs/`:**
- Purpose: Developer-facing documentation and API reference
- Contains: Guides for testing, API quirks, troubleshooting
- Key files: `CLAUDE.md` (primary dev guide), `NETRO_API.md` / `NETRO_API_V2.md` (API reference)

**`.planning/`:**
- Purpose: GSD planning system — milestones, phases, research
- Generated: No — manually maintained by GSD commands
- Committed: Yes

**`htmlcov/`:**
- Purpose: Generated HTML coverage report from `pytest --cov`
- Generated: Yes (by `pytest --cov --cov-report=html`)
- Committed: Yes (`.gitignore` inside htmlcov excludes nothing — entire dir tracked)

## Key File Locations

**Entry Points:**
- `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py`: Main plugin class, Indigo lifecycle

**Configuration:**
- `Netro Sprinklers.indigoPlugin/Contents/Info.plist`: Plugin version (`PluginVersion`), bundle ID
- `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/Devices.xml`: Device types and state definitions
- `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/PluginConfig.xml`: Plugin preferences UI
- `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/Actions.xml`: User-invokable actions
- `pyproject.toml`: Test dependencies and coverage settings
- `pytest.ini`: Test paths and options

**Core Logic:**
- `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/api_client.py`: All Netro API HTTP calls
- `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/device_handlers.py`: State transformation
- `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/validators.py`: Config validation
- `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/constants.py`: All magic numbers and URLs
- `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/tomorrow_client.py`: Weather API client

**Testing:**
- `tests/conftest.py`: Shared fixtures including `indigo` module mock
- `tests/test_api_client.py`: Most comprehensive test file

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (e.g., `api_client.py`, `device_handlers.py`)
- Test files: `test_{module_name}.py` (e.g., `test_api_client.py`)
- XML config files: `PascalCase.xml` (Indigo convention — `Devices.xml`, `Actions.xml`)
- Docs: `UPPER_SNAKE.md` for reference docs, `lower-kebab-date-title.md` for plans

**Directories:**
- Indigo bundle: `Plugin Name.indigoPlugin` (spaces allowed, `.indigoPlugin` suffix required)
- Plugin source: `Server Plugin/` (Indigo convention, fixed name)

**Python identifiers:**
- Constants: `SCREAMING_SNAKE_CASE` with `typing.Final`
- Classes: `PascalCase` (e.g., `NetroAPIClient`, `SprinklerHandler`)
- Methods/functions: `snake_case`; private helpers prefixed `_`
- Indigo callback methods: `camelCase` (Indigo SDK convention, e.g., `runConcurrentThread`, `validateDeviceConfigUi`)

## Where to Add New Code

**New API endpoint:**
1. Add URL constant to `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/constants.py`
2. Add convenience method to `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/api_client.py`
3. Add processing to the appropriate handler in `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/device_handlers.py`
4. Wire into polling timer logic in `plugin.py` `_update_sprinkler_device()` or `_update_whisperer_device()`
5. Add tests in `tests/test_api_client.py` and `tests/test_device_handlers.py`

**New device type:**
1. Add device definition to `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/Devices.xml`
2. Create new handler class in `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/device_handlers.py`
3. Add update method to `plugin.py` (`_update_newtype_device()`)
4. Add branch in `_update_from_netro()` for `dev.deviceTypeId == "newtype"`
5. Add test file `tests/test_newtype_handler.py`

**New validation:**
- Add function to `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/validators.py`
- Return `ValidationResult` tuple: `(bool, Dict, Dict)`
- Import and call from appropriate `validate*ConfigUi` method in `plugin.py`
- Add tests in `tests/test_validators.py`

**New Indigo action:**
1. Define action in `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/Actions.xml`
2. Implement callback in `plugin.py` following naming convention from Indigo SDK
3. Validate input via `validators.validate_action_config()` pattern

**Utilities:**
- Shared helpers with no plugin dependencies: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/utils.py`

## Special Directories

**`Netro Sprinklers.indigoPlugin/`:**
- Purpose: Indigo plugin bundle (directory with `.indigoPlugin` extension loaded as app bundle)
- Generated: No
- Committed: Yes — all source is inside the bundle

**`htmlcov/`:**
- Purpose: HTML coverage report from pytest
- Generated: Yes, by `pytest --cov --cov-report=html` from repo root
- Committed: Yes (tracked in git)

**`.planning/`:**
- Purpose: GSD project management system
- Generated: Partially (by GSD commands)
- Committed: Yes

**`tests/`:**
- Purpose: Test suite lives outside the plugin bundle (can't be bundled with plugin)
- Generated: No
- Committed: Yes
- Note: `sys.path` manipulation in `conftest.py` makes plugin source importable for tests

---

*Structure analysis: 2026-04-11*
