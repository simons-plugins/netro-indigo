# Testing Patterns

**Analysis Date:** 2026-04-11

## Test Framework

**Runner:**
- pytest 8.0+ (configured in `pytest.ini` and `pyproject.toml`)
- Config: `/Users/simon/vsCodeProjects/Indigo/netro/pytest.ini`

**Assertion Library:**
- pytest's built-in assertions (no separate assertion library)

**Coverage:**
- `pytest-cov` with branch coverage enabled
- HTML report written to `htmlcov/`
- Minimum required: 85% (`fail_under = 85` in `pytest.ini`)
- Current actual coverage: ~10% for most modules (coverage target is aspirational; plugin.py at 0% because it requires Indigo runtime)

**Run Commands:**
```bash
# Run all tests with coverage (default via pytest.ini addopts)
cd /Users/simon/vsCodeProjects/Indigo/netro && python3 -m pytest

# Run without coverage (faster)
python3 -m pytest --no-cov

# Run specific file
python3 -m pytest tests/test_api_client.py

# Run by marker
python3 -m pytest -m api
python3 -m pytest -m handlers
python3 -m pytest -m weather

# Run single test by name
python3 -m pytest tests/test_api_client.py::TestThrottleState::test_initial_state_not_throttled

# Run with pattern match
python3 -m pytest -k "throttle"

# View HTML coverage report
open htmlcov/index.html
```

## Test File Organization

**Location:** Separate `tests/` directory at repo root (not co-located with source)

**Naming:**
- Files: `test_<module>.py` matching the source module name
- Classes: `Test<Feature>` (e.g., `TestThrottleState`, `TestSprinklerHandlerDeviceInfo`)
- Functions: `test_<scenario>` with descriptive name (e.g., `test_throttle_until_past_clears_automatically`)

**Structure:**
```
netro/
├── tests/
│   ├── conftest.py                    # Shared fixtures (auto-discovered by pytest)
│   ├── test_api_client.py             # NetroAPIClient tests
│   ├── test_base_modules.py           # constants, exceptions, utils tests
│   ├── test_device_handlers.py        # SprinklerHandler, WhispererHandler tests
│   ├── test_validators.py             # validate_* function tests
│   ├── test_tomorrow_client.py        # TomorrowClient tests
│   ├── test_weather_integration.py    # Weather unit conversion + prefs validation
│   └── test_zone_handler.py           # ZoneHandler tests
└── pytest.ini                         # pytest configuration
```

**Total tests:** 427 collected (as of 2026-04-11)

## Test Structure

**Suite Organization — class-based grouping:**
```python
@pytest.mark.api
class TestThrottleState:
    """Tests for throttle state management."""

    def test_initial_state_not_throttled(self, client):
        """New client should have is_throttled=False."""
        assert client.is_throttled is False

    def test_throttle_until_future_is_throttled(self, client):
        """When _throttle_until is in future, is_throttled=True."""
        client._throttle_until = datetime.now() + timedelta(minutes=30)
        assert client.is_throttled is True
```

**Key patterns:**
- Every test method has a one-line docstring describing the expected behavior (the "should" statement)
- Arrange/Act/Assert structure used but not labeled with comments
- Fixtures injected via pytest parameters, not instantiated in test bodies
- Test classes organized by feature/behavior boundary, not by method-under-test

**Markers defined in `pytest.ini`:**
- `api` — Tests for API client functionality
- `handlers` — Tests for device handler functionality
- `validation` — Tests for configuration and action validation
- `actions` — Tests for action callback methods
- `weather` — Tests for Tomorrow.io weather integration
- `integration` — Integration tests requiring external services
- `slow` — Tests that take more than 1 second

## Mocking

**Framework:** `unittest.mock` (stdlib) — `Mock`, `patch`, `MagicMock`

**Standard mock pattern for HTTP requests:**
```python
def test_make_request_success(self, client):
    """Successful GET returns parsed JSON."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "OK", "data": {}}

    with patch("requests.get", return_value=mock_response):
        result = client.get_device_info(serial="ABC123")

    assert result["status"] == "OK"
```

**Standard mock for logger (used in every test file):**
```python
@pytest.fixture
def mock_logger():
    """Create a mock logger for testing."""
    logger = Mock()
    logger.debug = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    logger.exception = Mock()
    return logger
```

**Dependency injection via constructor (preferred over patching):**
The extracted modules (api_client, device_handlers, tomorrow_client) accept `logger`, `prefs_getter`, and `prefs_setter` as constructor args. Tests pass mocks directly rather than patching module-level imports:
```python
@pytest.fixture
def client(mock_logger, mock_prefs):
    """Create a NetroAPIClient instance with mocked dependencies."""
    prefs_getter, prefs_setter, _ = mock_prefs
    return NetroAPIClient(
        logger=mock_logger,
        prefs_getter=prefs_getter,
        prefs_setter=prefs_setter
    )
```

**What to mock:**
- `requests.get` / `requests.post` for all HTTP calls
- `logger` — always inject mock logger in unit tests
- `prefs_getter`/`prefs_setter` callables for API client state persistence
- Indigo module — `indigo` is not installed in test environment; mock it if needed

**What NOT to mock:**
- `constants.py` values — use real constants
- `exceptions.py` classes — use real exceptions
- Pure utility functions in `utils.py` — test them directly
- `validators.py` functions — test them directly (no side effects)

## Fixtures and Factories

**Shared fixtures in `conftest.py`** (`/Users/simon/vsCodeProjects/Indigo/netro/tests/conftest.py`):

```python
@pytest.fixture
def mock_logger():
    """Provides Mock with debug/info/warning/error/exception methods."""

@pytest.fixture
def sample_api_response():
    """Base successful API v1 response: {status: OK, data: {}, meta: {...}}"""

@pytest.fixture
def mock_prefs():
    """Returns (prefs_getter, prefs_setter, prefs_data) tuple for API client tests."""

@pytest.fixture
def sample_api_v2_response():
    """Base successful API v2 response with extended meta fields."""

@pytest.fixture
def sample_v2_device_info():
    """Full device info v2 response with zones array."""

@pytest.fixture
def sample_v2_schedules():
    """Schedules v2 response with ISO 8601 timestamps."""

@pytest.fixture
def sample_v2_sensor_data():
    """Sensor data v2 response."""
```

**Note:** `mock_logger` and `mock_prefs` are duplicated in `test_api_client.py` and `test_device_handlers.py` as local fixtures. Prefer the shared versions from `conftest.py` for new tests.

**Test data pattern:**
Fixtures return realistic dict structures matching the actual Netro API response format. Tests modify the returned dict for specific scenarios rather than creating new data from scratch:
```python
def test_device_offline(self, sprinkler_handler, sample_device_info_response):
    sample_device_info_response["data"]["device"]["status"] = "OFFLINE"
    states, is_online, _ = sprinkler_handler.process_device_info(
        sample_device_info_response, "ABC123"
    )
    assert is_online is False
```

## Coverage

**Requirements:** 85% minimum enforced by `pytest.ini` (`fail_under = 85`)

**Excluded from coverage:**
- `*/tests/*` — test files themselves
- `def __repr__`
- `raise AssertionError`, `raise NotImplementedError`
- `if __name__ == .__main__.:`
- `if TYPE_CHECKING:`
- `@abstractmethod`
- Lines marked `# pragma: no cover`

**Current coverage gaps:**
- `plugin.py` — 0% (requires Indigo runtime; all tests bypass this file)
- `api_client.py` — 17% (HTTP request paths require extensive mocking)
- `device_handlers.py` — 10% (many handler paths not yet exercised)
- `validators.py` — 10%
- `utils.py` — 17%
- `constants.py` — 100% (trivially satisfied)

**View coverage:**
```bash
python3 -m pytest  # Generates term-missing + HTML report
open /Users/simon/vsCodeProjects/Indigo/netro/htmlcov/index.html
```

## Test Types

**Unit Tests (all current tests):**
- Test individual modules in isolation
- No Indigo runtime dependency
- Fast, can run offline
- Mock all external I/O

**Integration Tests (not yet implemented):**
- Marked with `@pytest.mark.integration`
- Would require live Netro API access
- `docs/test_local_api.py` provides a standalone script for manual API testing against real hardware

**E2E Tests:**
- Not implemented
- Manual testing against Indigo server on `jarvis.local` is the current E2E approach

## Common Patterns

**Async Testing:**
Not applicable — plugin uses synchronous HTTP (`requests`) with Indigo's threading model. No async test patterns needed.

**Error Testing:**
```python
def test_raises_throttle_error_on_429(self, client):
    """HTTP 429 response raises ThrottleDelayError."""
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError()

    with patch("requests.post", return_value=mock_response):
        with pytest.raises(ThrottleDelayError):
            client.start_zone(serial="ABC123", zone=1, duration=600)
```

**Parametrize pattern (used in validators tests):**
```python
@pytest.mark.parametrize("invalid_serial", ["", "ABC", "TOOLONGSERIAL1234"])
def test_invalid_serial_rejected(self, invalid_serial):
    is_valid, _, errors = validate_device_config({"address": invalid_serial}, "sprinkler")
    assert is_valid is False
    assert "address" in errors
```

**State assertion via dict comprehension:**
Handler tests convert the returned state list to a dict for easy assertion:
```python
states = zone_handler.extract_zone_states(sample_zones, zone_number=1)
state_dict = {s["key"]: s["value"] for s in states}
assert state_dict["enabled"] is True
assert state_dict["smartMode"] == "SMART"
```

**Validation return value unpacking:**
All validator tests use 3-tuple unpacking to check each component separately:
```python
is_valid, sanitized, errors = validate_device_config(values, "sprinkler")
assert is_valid is True
assert sanitized["address"] == "0123456789AB"
assert errors == {}
```

---

*Testing analysis: 2026-04-11*
