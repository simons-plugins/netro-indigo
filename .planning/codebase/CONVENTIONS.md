# CONVENTIONS.md — Code Conventions

## Python Style

- **Style guide**: Google Python Style Guide with Indigo SDK conventions
- **Line length**: 120 characters (set in `pyproject.toml`)
- **String formatting**: f-strings throughout (Python 3.10+)
- **Type hints**: Present in extracted modules (`api_client.py`, `validators.py`,
  `device_handlers.py`); absent in `plugin.py` (tech debt)
- **Constants**: `SCREAMING_SNAKE_CASE` with `typing.Final` for immutability
- **Dataclasses**: Used for structured data (`DeviceTokenState` in `api_client.py`,
  `ValidationResult` alias in `validators.py`)

## Naming Conventions

Indigo requires camelCase method names for its callbacks; pylint is configured
to allow this:

```
# Indigo-required camelCase callbacks
def actionControlSprinkler(self, action, dev): ...
def validateDeviceConfigUi(self, values, type_id, dev_id): ...
def triggerStartProcessing(self, trigger): ...

# Internal helper methods use snake_case
def _get_device_auth(self, dev): ...
def _update_from_netro(self): ...
def _ensure_zone_devices(self, parent_dev, zones_data): ...
```

Private helpers are prefixed with `_`.

## Docstrings

All public methods and classes have Google-style docstrings:

```python
def _get_device_auth(self, dev):
    """Get API authentication key and version for a device.

    Args:
        dev: Indigo device with pluginProps

    Returns:
        Tuple of (key, api_version) where key is the auth credential
        and api_version is "1" or "2"
    """
```

Module-level docstrings are required and describe purpose, classes exported,
and any dependency constraints (e.g. "does not import indigo").

## Logging

Uses `self.logger` in `Plugin` (injected by `indigo.PluginBase`). All other
modules receive a logger via constructor injection:

```python
# Handlers and client accept optional logger
def __init__(self, logger: Optional[logging.Logger] = None) -> None:
```

### Log levels

| Level | When to use |
|-------|-------------|
| `debug` | Polling skips, raw API data, state before/after |
| `info` | Successful API calls, device state changes, zone created/renamed |
| `warning` | Token count low, Tomorrow.io misconfigured, non-fatal issues |
| `error` | API errors, action failures, unexpected exceptions |
| `exception` | Use in `except` blocks where traceback is needed — logs full stack |

### Error suppression pattern

Repeated connection errors are suppressed after the first display. The
`_displayed_connection_error` flag in `Plugin.__init__` and equivalent logic
in `NetroAPIClient` prevent log spam during extended outages:

```python
if not self._displayed_connection_error:
    self.logger.error("Connection failed - will retry silently")
    self._displayed_connection_error = True
# On next success: self._displayed_connection_error = False
```

## Error Handling Philosophy

"Fail gracefully, log details, continue operation."

- API errors do not crash the polling loop — exceptions are caught at the
  per-device level
- Actions fire Indigo triggers on failure so users can automate responses
- `traceback.format_exc(10)` is used for debug-level stack traces
- Never expose serial numbers or API keys in log messages

## Module Isolation Pattern

All extracted modules (`api_client.py`, `device_handlers.py`, `validators.py`,
`utils.py`, `constants.py`, `exceptions.py`) are designed with no `indigo`
dependency. This is enforced by convention (not by import guards) and enables
unit testing without the Indigo runtime.

`plugin.py` is the only module that imports `indigo`. It acts as the
coordinator that:
1. Reads Indigo device/prefs state
2. Calls extracted modules with plain Python data structures
3. Writes results back to Indigo

## Configuration Access

Plugin preferences accessed via `self.pluginPrefs` (a dict-like object).
Device configuration accessed via `dev.pluginProps`. Both are persisted by
Indigo automatically.

Throttle state is persisted to `pluginPrefs` via injected callbacks:

```python
self.api_client = NetroAPIClient(
    prefs_getter=lambda: dict(self.pluginPrefs),
    prefs_setter=lambda k, v: self.pluginPrefs.__setitem__(k, v)
)
```

This allows the API client to remain `indigo`-free while still persisting
state across plugin restarts.

## Version Bumping

Every PR must bump `PluginVersion` in
`Netro Sprinklers.indigoPlugin/Contents/Info.plist`.

Format: `YYYY.R.patch` — e.g. `2026.4.0`.

- Patch bump for fixes and docs
- Minor bump (R) for new features

CI fails if the version already exists as a git tag. Do not merge with
failing checks.
