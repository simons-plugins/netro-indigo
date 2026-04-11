# Coding Conventions

**Analysis Date:** 2026-04-11

## Naming Patterns

**Files:**
- `snake_case.py` for all Python source files: `api_client.py`, `device_handlers.py`, `tomorrow_client.py`, `validators.py`, `utils.py`, `constants.py`, `exceptions.py`
- `test_<module>.py` for test files: `test_api_client.py`, `test_device_handlers.py`
- XML config files use PascalCase: `Devices.xml`, `Actions.xml`, `PluginConfig.xml`

**Functions and Methods:**
- `snake_case` for all module-level functions: `validate_device_config()`, `convert_weather_us_to_metric()`, `get_key_from_dict()`
- `camelCase` for Indigo framework callbacks (required by SDK): `actionControlSprinkler()`, `validateDeviceConfigUi()`, `runConcurrentThread()`
- Private methods prefixed with underscore: `_make_api_call()`, `_get_device_dict()`, `_save_throttle_state()`
- Static helpers prefixed with underscore if module-private: `_slugify()`

**Variables:**
- `snake_case` for local variables and instance attributes: `token_remaining`, `prefs_getter`, `device_handlers`
- `camelCase` for Indigo-required attribute names: `pluginPrefs`, `pluginId`, `triggerDict`, `serialNo`
- Timer attributes prefixed with `_next_`: `_next_device_info_update`, `_next_schedules_update`
- Interval attributes prefixed with `_` and suffixed with `_interval`: `_events_interval`, `_weather_update_interval`

**Constants:**
- `SCREAMING_SNAKE_CASE` throughout `constants.py`: `MAX_ZONE_DURATION_SECONDS`, `DEFAULT_API_TIMEOUT_SECONDS`, `TOKEN_PAUSE_THRESHOLD`
- Annotated with `typing.Final` to indicate immutability: `NETRO_API_VERSION: Final[str] = "1"`
- Each constant has a docstring on the following line explaining purpose

**Classes:**
- `PascalCase` for all class names: `NetroAPIClient`, `SprinklerHandler`, `WhispererHandler`, `ZoneHandler`, `DeviceTokenState`
- Exception classes named `Netro<Type>Error` inheriting from `NetroError`: `ThrottleDelayError`, `NetroAPIError`

**Type Aliases:**
- Defined at module level with docstring: `ValidationResult = Tuple[bool, Dict[str, Any], Dict[str, str]]`

## Code Style

**Formatting:**
- No formatter configured (no `.prettierrc`, `black`, or `autopep8` config)
- Max line length: 120 characters (configured in `pyproject.toml` `[tool.pylint.format]`)
- 4-space indentation (Python standard)

**Linting:**
- `pylint` with target score 9.0 (`fail-under = 9.0` in `pyproject.toml`)
- Key rules disabled for Indigo plugin patterns:
  - `too-many-lines` — large plugin.py by design
  - `too-many-public-methods` — Indigo requires many callbacks
  - `invalid-name` — Indigo requires camelCase callbacks
- `method-rgx = "[a-z_][a-zA-Z0-9_]{2,}$"` to allow both snake_case and camelCase methods

## Import Organization

**Order within files:**
1. Python standard library: `import json`, `from datetime import datetime`
2. Third-party: `import requests`
3. Local plugin modules: `from constants import ...`, `from exceptions import ...`

**Path management in tests:**
Every test file manually inserts the Server Plugin directory into `sys.path` using `pathlib.Path`:
```python
SERVER_PLUGIN_DIR = (
    Path(__file__).parent.parent
    / "Netro Sprinklers.indigoPlugin"
    / "Contents"
    / "Server Plugin"
)
sys.path.insert(0, str(SERVER_PLUGIN_DIR))
```

**Module `__all__` usage:**
Modules with public APIs declare `__all__`: `validators.py`, `device_handlers.py`, `api_client.py`. This explicitly controls what is exported and documents the public surface.

**Circular import prevention:**
Each module has explicit rules in its docstring:
- `constants.py` — no dependencies on other plugin modules
- `exceptions.py` — no dependencies on other plugin modules
- `utils.py` — no dependencies on other plugin modules
- `validators.py` — only imports from `constants.py`
- `device_handlers.py` — only imports from `constants.py` and `utils.py`
- `api_client.py` — only imports from `constants.py` and `exceptions.py`

## Error Handling

**Exception hierarchy:**
All plugin exceptions inherit from `NetroError` (in `exceptions.py`):
```
NetroError (base)
├── ThrottleDelayError   - API rate limit exceeded
├── NetroAPIError        - API returned error response
├── NetroConnectionError - Network connection failed
└── NetroTimeoutError    - Request timed out
```

**Exception constructors:**
All custom exceptions take `message: str` as first arg with a sensible default, plus context-specific optional attributes (`retry_after`, `status_code`, `error_code`, `timeout_seconds`). Always call `super().__init__(message)`.

**Fail gracefully pattern:**
```python
# From utils.py - silent fallback for API response parsing
try:
    return data[key]
except KeyError:
    return "unavailable from API" if default is None else default
except (TypeError, AttributeError):
    return "unknown error" if default is None else default
```

**Connection error suppression:**
Plugin tracks `_displayed_connection_error` to log network errors once then suppress repeats:
```python
if not self._displayed_connection_error:
    self.logger.error("Timeout - will retry silently")
    self._displayed_connection_error = True
```

**Throttle management:**
`ThrottleDelayError` is raised and caught at the API client level. Plugin checks `client.is_throttled` before making calls. State is persisted across restarts via `pluginPrefs`.

## Logging

**Framework:** Indigo's built-in logger via `self.logger` (injected as constructor argument in extracted modules)

**Log methods used:**
- `self.logger.debug(...)` — detailed trace, only shown when debug enabled
- `self.logger.info(...)` — significant state changes, startup, successful operations
- `self.logger.warning(...)` — token budget warnings (<200 remaining), non-fatal anomalies
- `self.logger.error(...)` — failures that degrade functionality, first-occurrence connection errors
- `self.logger.exception(exc)` — unexpected exceptions with full traceback

**Logger injection pattern:**
Extracted modules (api_client, device_handlers, tomorrow_client) receive logger as constructor arg with fallback to module logger:
```python
def __init__(self, logger=None):
    self.logger = logger or logging.getLogger(__name__)
```

## Comments

**Module docstrings:**
Every module has a docstring describing purpose, key features, dependency rules, and usage. Format is plain prose, not Google/NumPy style.

**Class docstrings:**
PascalCase classes have docstrings covering purpose, key attributes, and usage examples.

**Method docstrings:**
All public methods use Google-style Args/Returns/Raises sections:
```python
def process_device_info(self, api_response, serial, api_version="1"):
    """Process device info API response.

    Args:
        api_response: Dict with Netro API response structure
        serial: Device serial number for logging
        api_version: API version string ("1" or "2")

    Returns:
        Tuple of (states_list, is_online, device_data_dict)
    """
```

**Section separators:**
Long files use `# =============================================================================` banners to divide logical sections (e.g., "API Configuration", "Default Values", "Event Sets" in `constants.py`).

**Inline comments:**
Used for non-obvious logic: API quirks, backward compatibility notes, legacy constants. Example: `# Legacy constant — kept for backward compatibility during migration`.

**pylint inline disables:**
Used sparingly at class/method level with explicit reason:
```python
# pylint: disable=too-many-public-methods,too-many-instance-attributes
class Plugin(indigo.PluginBase):
```

## Function Design

**Size:** Large methods are accepted for `plugin.py` given Indigo's callback-driven architecture. Extracted utility modules (api_client, device_handlers, validators, utils) keep functions small and focused.

**Parameters:** Constructor dependency injection preferred over global state. Callbacks (prefs_getter, prefs_setter) passed as callables rather than direct object references to avoid circular imports.

**Return Values:**
- Validators return 3-tuple: `(is_valid: bool, sanitized_values: dict, errors: dict)`
- Handlers return lists of state dicts for `updateStatesOnServer()`
- API methods return parsed JSON dict or raise typed exception

## Module Design

**Exports:**
Modules declare `__all__` to define their public API surface.

**Barrel files:**
Not used. Each module is imported directly by name.

**Dataclasses:**
Used for simple value objects: `DeviceTokenState` in `api_client.py`, `ValidationResult` type alias in `validators.py`.

**Constants module:**
All magic numbers and configuration strings live in `constants.py`. Do not define numeric literals in business logic — import the named constant.

---

*Convention analysis: 2026-04-11*
