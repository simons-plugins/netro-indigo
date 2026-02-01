# Codebase Structure

**Analysis Date:** 2026-02-01

## Directory Layout

```
netro/
├── Netro Sprinklers.indigoPlugin/        # Plugin bundle (macOS app package)
│   └── Contents/
│       ├── Info.plist                    # Plugin metadata and version
│       ├── Server Plugin/
│       │   ├── plugin.py                 # Main implementation (1635 lines)
│       │   ├── Devices.xml               # Device type definitions
│       │   ├── Actions.xml               # Custom action definitions
│       │   ├── Events.xml                # Trigger event definitions
│       │   ├── MenuItems.xml             # Plugin menu items
│       │   ├── PluginConfig.xml          # Plugin settings UI
│       │   └── requirements.txt           # Python dependencies
│       └── Resources/                    # Web content and assets
├── docs/                                 # Documentation
│   ├── CLAUDE.md                         # Developer guide
│   ├── NETRO_API.md                      # Complete API reference
│   ├── API_NOTES.md                      # API quirks and discoveries
│   ├── TESTING.md                        # Test suite guide
│   ├── TROUBLESHOOTING.md                # User troubleshooting
│   ├── LOCAL_TESTING.md                  # Standalone API tester guide
│   ├── DEPENDENCIES.md                   # Package management
│   └── test_local_api.py                 # Standalone API test utility
├── tests/                                # Test suite (64 tests documented)
│   ├── conftest.py                       # pytest fixtures (documented, not in repo)
│   ├── test_api_client.py                # API tests (17 tests, documented)
│   ├── test_validation.py                # Validation tests (24 tests, documented)
│   ├── test_actions.py                   # Action tests (23 tests, documented)
│   └── fixtures/                         # Mock API responses (documented)
├── .planning/                            # GSD planning documents
│   └── codebase/                         # Codebase analysis
├── .github/                              # GitHub configuration
│   └── workflows/                        # CI/CD workflows
├── pytest.ini                            # pytest configuration
├── README.md                             # User-facing plugin documentation
├── CLAUDE.md                             # Developer guide (root level)
└── .env                                  # Environment configuration (git-ignored)
```

## Directory Purposes

**Netro Sprinklers.indigoPlugin:**
- Purpose: macOS-compatible plugin bundle recognized by Indigo
- Structure: Standard macOS app bundle structure with `Contents/` directory
- Installed to: `/Library/Application Support/Perceptive Automation/Indigo 2023.2/Plugins/`

**Contents/Server Plugin:**
- Purpose: Python plugin implementation and configuration
- Contains: Main `plugin.py` class (inherits `indigo.PluginBase`), XML configuration files, dependencies list
- Entry point: `plugin.py` - main Plugin class with all handlers

**Contents/Info.plist:**
- Purpose: Plugin metadata for Indigo and macOS
- Contains: Version, bundle identifier, API version, GitHub info
- Current: v2025.1.7, API v3.6, identifier `com.simons-plugins.netro`

**Contents/Resources:**
- Purpose: Static web assets (if using HTTP Responder features)
- Current state: Exists but minimal content (not heavily used in this plugin)

**docs/:**
- Purpose: Developer and user documentation
- CLAUDE.md: Comprehensive developer reference with architecture, workflow, code patterns
- NETRO_API.md: Complete Netro API endpoint reference
- API_NOTES.md: API quirks discovered during development (timestamps, device structure, offline status)
- TESTING.md: How to run test suite and test patterns
- TROUBLESHOOTING.md: User-facing troubleshooting guide
- test_local_api.py: Standalone utility to test API calls against real Netro API

**tests/:**
- Purpose: Automated test suite (64 tests, >70% coverage)
- conftest.py: pytest fixtures for mocking Indigo, device data, API responses
- test_api_client.py: 17 tests for `_make_api_call()`, throttling, error handling
- test_validation.py: 24 tests for config/action/device validation
- test_actions.py: 23 tests for action execution and state updates
- fixtures/: Mock Netro API response files
- Run: `pytest tests/` with coverage

**.planning/codebase/:**
- Purpose: GSD (Generative Software Development) planning documents
- Content: Architecture analysis, structure guide, conventions, testing patterns, concerns
- Created by: `/gsd:map-codebase` command

**.github/workflows/:**
- Purpose: CI/CD pipeline configuration
- Contains: GitHub Actions workflows for testing, linting, release automation

**pytest.ini:**
- Purpose: pytest configuration and options
- Specifies: Test discovery, coverage settings, output format

**README.md:**
- Purpose: User-facing plugin documentation
- Contains: Features, device types, setup instructions, API usage, troubleshooting links

## Key File Locations

**Entry Points:**

- `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py`: Main plugin implementation
  - Class: `Plugin(indigo.PluginBase)` at line 132
  - Lifecycle: `__init__` → `startup` → `runConcurrentThread` → `shutdown`

- `Netro Sprinklers.indigoPlugin/Contents/Info.plist`: Plugin metadata
  - Indigo reads this to identify plugin, load version, display name

- `docs/test_local_api.py`: Standalone API testing tool
  - Run: `python3 test_local_api.py --serial YOUR_SERIAL`

**Configuration:**

- `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/PluginConfig.xml`: Plugin settings UI
  - Fields: Polling interval, API timeout, max zone runtime, debug logging
  - Validation: `validatePrefsConfigUi()` in plugin.py line 1031

- `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/Devices.xml`: Device type definitions
  - Types: `sprinkler` (line 9), `Whisperer` (line 199)
  - States: 40+ states for sprinkler (zones, schedules, moisture, API info)
  - States: 15+ states for sensor (temperature, moisture, sunlight, battery)

**Core Logic:**

- `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py` key methods:
  - `__init__` (line 157): Initialize plugin state
  - `_make_api_call` (line 195): HTTP requests with throttling and error handling
  - `_update_from_netro` (line 373): Main polling cycle, state refresh
  - `runConcurrentThread` (line 810): Background polling loop (3+ minute interval)
  - `actionControlSprinkler` (line 1238): Zone on/off actions
  - `setNoWater` (line 1350): Rain delay action
  - `setStandbyMode` (line 1383): Standby mode action
  - `startZoneWithDelay` (line 1408): Delayed zone start action
  - `reportWeather` (line 1479): Weather reporting action

**Testing:**

- `tests/test_api_client.py`: API integration tests
- `tests/test_validation.py`: Configuration validation tests
- `tests/test_actions.py`: Action execution tests
- `tests/conftest.py`: pytest fixtures (mocks, test data)
- `docs/TESTING.md`: Testing guide and patterns

**Documentation:**

- `docs/CLAUDE.md`: Developer reference (architecture, patterns, quirks)
- `docs/NETRO_API.md`: API endpoint reference with examples
- `docs/API_NOTES.md`: Discovered API quirks and workarounds
- `docs/TROUBLESHOOTING.md`: User issues and solutions
- `README.md`: User-facing overview

## Naming Conventions

**Files:**

- Python files: `plugin.py`, `test_*.py`, lowercase with underscores
- XML files: `Devices.xml`, `Actions.xml`, `Events.xml`, `PluginConfig.xml`, `MenuItems.xml` (PascalCase)
- Documentation: `UPPERCASE.md` (NETRO_API.md, API_NOTES.md, TROUBLESHOOTING.md)
- Configuration: `pytest.ini`, `.env`, `.gitignore`

**Directories:**

- Plugin bundle: `PluginName.indigoPlugin` (exact case match required by Indigo)
- Server Plugin: `Server Plugin/` (space-separated, matches Indigo convention)
- Source code: lowercase (`plugin.py`, not `Plugin.py`)
- Documentation: `docs/` (lowercase)
- Tests: `tests/` (lowercase)

**Functions/Methods:**

- Module-level: `convert_timestamp()` (line 101), `get_key_from_dict()` (line 117) - lowercase with underscores
- Class methods (Plugin): `_make_api_call()` (private, single underscore prefix) - lowercase with underscores
- Public methods: `actionControlSprinkler()`, `setNoWater()`, `startZoneWithDelay()` (camelCase, matches Indigo convention)
- Private helpers: `_update_from_netro()`, `_get_device_dict()`, `_get_zone_dict()` (single underscore prefix)
- Callback methods: `validatePrefsConfigUi()`, `deviceStartComm()`, `triggerStartProcessing()` (camelCase, matches Indigo callback names)

**Variables:**

- Instance: `self.throttle_next_call`, `self.pollingInterval`, `self.netro_devices` (camelCase with underscores for clarity)
- Module-level constants: `NETRO_API_VERSION`, `DEFAULT_API_CALL_TIMEOUT`, `MINIMUM_POLLING_INTERVAL` (UPPER_SNAKE_CASE)
- Local: `dev`, `dev_id`, `zone_dict`, `reply_dict` (lowercase with underscores)

**Device IDs:**

- Type IDs (in Devices.xml): `sprinkler` (lowercase), `Whisperer` (PascalCase)
- State IDs (in Devices.xml): `status`, `activeZone`, `nextScheduleTime` (camelCase)
- Action IDs (in Actions.xml): `setStandbyMode`, `setNoWater`, `startZoneWithDelay` (camelCase)
- Event IDs (in Events.xml): `sprinklerError`, `commError` (camelCase)

## Where to Add New Code

**New Feature (e.g., smart scheduling):**

1. **Add action definition:**
   - Edit `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/Actions.xml`
   - Add `<Action>` block with fields for user input
   - Reference your callback method name

2. **Implement callback:**
   - Add method to `Plugin` class in `plugin.py`
   - Follow naming: `def myNewAction(self, pluginAction, dev):`
   - Check throttle state at start
   - Make API call via `_make_api_call()`
   - Fire trigger on failure: `self._fireTrigger("myActionFailed", dev.id)`
   - Log success/failure: `self.logger.info()` or `self.logger.error()`

3. **Add event definition:**
   - Edit `Events.xml` if feature can fail
   - Add `<Event>` with IDs for error conditions

4. **Add tests:**
   - Create or update test file in `tests/`
   - Mock API responses in `tests/fixtures/`
   - Test success and failure paths
   - Test parameter validation
   - Run: `pytest tests/test_actions.py::test_new_action -v`

5. **Update documentation:**
   - Add to `docs/CLAUDE.md` Architecture section
   - Add API endpoint to `docs/NETRO_API.md`
   - Add usage example to `README.md`

**New Device Type (e.g., Smart Hose):**

1. **Define device type:**
   - Edit `Devices.xml`
   - Add `<Device type="...">` block
   - Define states and properties
   - Example: `<Device type="hose" id="SmartHose">`

2. **Add update logic:**
   - Edit `_update_from_netro()` method
   - Add device type check: `if dev.deviceTypeId == "SmartHose":`
   - Call appropriate API endpoints
   - Build state update list
   - Update device: `dev.updateStatesOnServer(update_list)`

3. **Add validation:**
   - Update `validateDeviceConfigUi()` for device type validation
   - Check serial number, capabilities, etc.

4. **Add tests:**
   - Test device discovery
   - Test state updates
   - Test error handling

**Utility/Helper Function:**

- Location: Add to top of `plugin.py` before Plugin class (around line 100)
- Scope: Module-level functions for reusable logic
- Example: `convert_timestamp()` (line 101), `get_key_from_dict()` (line 117)
- Pattern: Use type hints where possible, add docstring
- Test: Create unit tests in `tests/test_api_client.py` or new file

**Error/Exception Handling:**

- Location: Wrap in try/except in appropriate layer (API, Control, Data Sync)
- Pattern: Log error with context, fire trigger if user action failed, continue execution
- Never: Crash plugin or exit background thread
- Always: Re-raise connection errors in API layer, catch in Control/Data layers

## Special Directories

**Netro Sprinklers.indigoPlugin:**
- Purpose: macOS app bundle structure (required format for Indigo)
- Generated: No (hand-authored structure)
- Committed: Yes
- Note: Entire directory is the installable plugin; contains source and all resources

**tests/fixtures/:**
- Purpose: Mock Netro API response JSON files
- Generated: No (hand-authored mock data)
- Committed: Yes
- Structure: Filename matches endpoint (e.g., `device_info_response.json`)

**.planning/codebase/:**
- Purpose: GSD (Generative Software Development) analysis documents
- Generated: Yes (by `/gsd:map-codebase` and `/gsd:map-phase` commands)
- Committed: Yes (part of development planning)
- Created by: Claude Code via GSD orchestrator

**.github/workflows/:**
- Purpose: CI/CD pipeline automation (GitHub Actions)
- Generated: No (hand-authored workflows)
- Committed: Yes
- Files: Test runs, linting, release automation

**Contents/Packages/:**
- Purpose: Bundled Python dependencies (if used)
- Generated: No in this plugin (uses Indigo-provided requests library)
- Committed: No
- Note: Could contain vendored dependencies if needed

---

*Structure analysis: 2026-02-01*
