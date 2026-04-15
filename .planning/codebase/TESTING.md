# TESTING.md — Test Suite

## Summary

- **Total tests**: 427 collected (April 2026)
- **Runner**: pytest 7.4.3 on Python 3.11.6
- **Config**: `pytest.ini` + `pyproject.toml [tool.pytest.ini_options]`
- **Coverage** (from `--co` run): ~10% overall; `constants.py` 100%,
  `plugin.py` 0% (requires Indigo runtime)
- **Run**:
  ```bash
  cd /Users/simon/vsCodeProjects/Indigo/netro
  pytest tests/
  pytest tests/ --cov --cov-report=html
  ```

## Test Files

All tests live in `/Users/simon/vsCodeProjects/Indigo/netro/tests/`.

| File | Subject | Tests |
|------|---------|-------|
| `test_api_client.py` | `NetroAPIClient` | ~100+ |
| `test_device_handlers.py` | `SprinklerHandler`, `WhispererHandler` | ~50+ |
| `test_zone_handler.py` | `ZoneHandler` | ~20+ |
| `test_validators.py` | `validate_*` functions | ~60+ |
| `test_base_modules.py` | `constants`, `exceptions`, `utils` | ~30+ |
| `test_tomorrow_client.py` | `TomorrowClient` | ~40+ |
| `test_weather_integration.py` | unit conversion + weather integration | ~30+ |

## conftest.py Fixtures

`/Users/simon/vsCodeProjects/Indigo/netro/tests/conftest.py` provides shared
fixtures available to all test files:

| Fixture | Returns | Used for |
|---------|---------|---------|
| `mock_logger` | `Mock()` with all log methods | Passed to handlers and clients |
| `sample_api_response` | Base v1 success dict `{status, data, meta}` | API response testing |
| `mock_prefs` | `(getter_fn, setter_fn, prefs_dict)` | Testing throttle persistence |
| `sample_api_v2_response` | Base v2 success dict with ISO timestamps | v2 API testing |
| `sample_v2_device_info` | Full v2 device info response | Handler tests |
| `sample_v2_schedules` | v2 schedules response | Schedule processing tests |
| `sample_v2_sensor_data` | v2 sensor data response | Whisperer handler tests |

## Mocking Strategy

### No Indigo runtime — stub at import time

Every test file adds the plugin's `Server Plugin` directory to `sys.path`
before any imports:

```python
SERVER_PLUGIN_DIR = (
    Path(__file__).parent.parent
    / "Netro Sprinklers.indigoPlugin"
    / "Contents"
    / "Server Plugin"
)
sys.path.insert(0, str(SERVER_PLUGIN_DIR))
```

`plugin.py` is never imported in tests (it requires the Indigo runtime).
Only the extracted pure-Python modules are imported.

### HTTP requests

All HTTP calls are patched with `unittest.mock.patch`:

```python
@patch("requests.get")
def test_make_request_get_success(self, mock_get, client):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {...}
```

No actual network calls are made in the test suite.

### Logger

`mock_logger` fixture provides a `Mock()` with all standard log methods.
Passed to constructors via the `logger=` parameter.

### Prefs (throttle persistence)

`mock_prefs` fixture provides getter/setter callables backed by a plain dict,
allowing `NetroAPIClient` to be tested without `pluginPrefs`.

## Test Classes and Markers

Tests are organised into classes within each file. `test_api_client.py` uses
`@pytest.mark.api` on class `TestThrottleState`, `TestProactivePause`,
`TestMakeRequest`, `TestSchemaValidation`, `TestConvenienceMethods`.

Pattern: one class per behaviour area, one method per scenario.

## Key Test Scenarios

### `test_api_client.py`

- Throttle state: initial, future lockout, expiry auto-clear
- Throttle persistence: save/restore to prefs (v1 and v2 formats)
- Proactive pause: pause below threshold, no-pause at/above, per-device isolation
- `make_request`: GET/POST/PUT success, 204 response, timeout (including
  repeated suppression and reset on success), connection errors, 429,
  error code 3, error code 1, 500/502/503/504 HTTP errors
- Schema validation: warn on missing keys, debug log on extra keys, no raise
- Multi-device token budget isolation

### `test_device_handlers.py`

- `SprinklerHandler.process_device_info`: v1 and v2 responses, online/offline
  status, zone extraction
- `process_schedules`: executing zone, next schedule, v2 ISO timestamps,
  empty/cancelled schedules
- `process_moistures`: zone moisture, latest date selection, missing zone
- `WhispererHandler.process_sensor_data`: all sensor fields, battery level

### `test_validators.py`

- Serial number format (12 hex chars)
- API key format
- Polling interval minimums (per-endpoint)
- Action config ranges (duration 1-180, delay 0-60, weather ranges)
- Date format validation

## Standalone API Tester

`/Users/simon/vsCodeProjects/Indigo/netro/test_local_api.py` — a CLI script
for testing against the real Netro API (not part of the pytest suite):

```bash
python3 test_local_api.py --serial YOUR_SERIAL
python3 test_local_api.py --serial YOUR_SERIAL --full   # includes write ops
```

See `docs/LOCAL_TESTING.md` for details.

## Coverage Notes

Current coverage is low for modules with Indigo dependencies or complex
integration paths:

| Module | Coverage | Reason |
|--------|----------|--------|
| `constants.py` | 100% | Pure constants, trivially covered |
| `plugin.py` | 0% | Requires Indigo runtime |
| `device_handlers.py` | ~10% | Many paths still untested |
| `validators.py` | ~10% | Many edge cases untested |
| `api_client.py` | ~17% | Core paths covered, edge cases not |
| `tomorrow_client.py` | ~7% | Tomorrow.io integration minimally tested |

Target from `docs/CLAUDE.md`: increase to 85%+.
