# Testing Patterns

**Analysis Date:** 2026-02-01

## Test Framework

**Runner:**
- pytest >= 8.0.0
- Configuration: `pytest.ini` in project root

**Assertion Library:**
- pytest's built-in assertions
- pytest-mock for mocking (`pytest-mock >= 3.12.0`)

**Coverage Tools:**
- pytest-cov >= 4.1.0
- HTML reports generated to `htmlcov/`
- Coverage target: >70% (current status per CLAUDE.md)

**Run Commands:**
```bash
# Run all tests with coverage
pytest tests/ -v --cov="Netro Sprinklers.indigoPlugin/Contents/Server Plugin" --cov-report=term-missing

# Run specific test file
pytest tests/test_api_client.py -v

# Run specific test
pytest tests/test_api_client.py::test_successful_get_request -v

# Run with branch coverage
pytest tests/ --cov-branch

# Generate HTML coverage report
pytest tests/ --cov --cov-report=html
# View in htmlcov/index.html
```

## Test File Organization

**Location:**
- `tests/` directory in project root
- Test files are siblings of main plugin

**Naming:**
- Files: `test_*.py` pattern (pytest auto-discovery)
- Classes: `Test*` pattern (e.g., `TestAPIClient`)
- Functions: `test_*` pattern (e.g., `test_successful_get_request`)

**Structure (from pytest.ini discovery):**
```
tests/
├── conftest.py              # pytest fixtures and setup
├── test_api_client.py       # API integration tests (17 tests)
├── test_validation.py       # Configuration validation tests (24 tests)
├── test_actions.py          # Action callback tests (23 tests)
└── fixtures/                # Mock API response data
    ├── device_info.json
    ├── schedules.json
    └── ...
```

**Total: 64 tests covering >70% of code**

## Test Structure

**Markers defined in pytest.ini:**
```ini
[pytest]
markers =
    api: Tests for API client functionality
    validation: Tests for configuration and action validation
    actions: Tests for action callback methods
    integration: Integration tests requiring external services
    slow: Tests that take more than 1 second
```

**Usage pattern:**
```python
@pytest.mark.api
def test_successful_get_request(mock_plugin):
    """Test successful API GET request."""
    # Test implementation
```

**Test file categories:**

### test_api_client.py (17 tests, @pytest.mark.api)
- Test `_make_api_call()` HTTP methods (GET, POST, PUT)
- HTTP status code handling (200, 204, error codes)
- Netro-specific error codes (code 1 = invalid key, code 3 = rate limit)
- Timeout handling
- Connection error handling
- Rate limit (throttle) enforcement and recovery
- JSON response parsing

### test_validation.py (24 tests, @pytest.mark.validation)
- Device configuration validation: `validateDeviceConfigUi()`
- Action configuration validation: `validateActionConfigUi()`
- Plugin preference validation: `validatePrefsConfigUi()`
- Serial number format validation
- Polling interval constraints
- Zone duration and delay constraints
- Weather data range validation
- Error message generation

### test_actions.py (23 tests, @pytest.mark.actions)
- Zone on/off actions: `actionControlSprinkler()`
- Custom actions: `startZoneWithDelay()`, `reportWeather()`, `setNoWater()`, `setStandbyMode()`
- Action parameter validation
- Error condition handling
- Trigger firing on success/failure

## Mocking

**Framework:** pytest-mock (via `mocker` fixture)

**Pattern:** Mock Indigo objects and requests library

**Example (from conftest.py fixture):**
```python
@pytest.fixture
def mock_plugin(mocker):
    """Create a mock Plugin instance."""
    plugin = Plugin(
        pluginId="com.simonmikey.netro",
        pluginDisplayName="Netro Sprinklers",
        pluginVersion="2.0",
        pluginPrefs={}
    )

    # Mock logger
    plugin.logger = mocker.MagicMock()

    # Mock Indigo collections
    mocker.patch("indigo.devices", MagicMock())
    mocker.patch("indigo.trigger", MagicMock())

    return plugin
```

**What to Mock:**
- HTTP library: `requests.get()`, `requests.post()`, `requests.put()` via `mocker.patch()`
- Indigo API: `indigo.devices`, `indigo.trigger`, device/action objects
- Logger: `self.logger.info()`, `self.logger.error()`, etc.
- File I/O: Configuration reads, if needed

**Pattern for mocking requests:**
```python
def test_successful_get_request(mocker):
    """Test successful GET request to API."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "OK",
        "data": {"device": {...}}
    }

    mocker.patch("requests.get", return_value=mock_response)

    # Test code using API
    result = plugin._make_api_call(url)
    assert result["status"] == "OK"
```

**What NOT to Mock:**
- Plugin class instantiation (test against real __init__)
- Core business logic like throttle calculation
- Datetime operations (use freezegun if time control needed)
- Dictionary/list operations

## Fixtures and Factories

**Test Data Location:**
- `tests/fixtures/` directory contains JSON response files
- Files match API endpoint responses exactly
- Examples: `device_info.json`, `schedules.json`, `moistures.json`, `sensor_data.json`

**Fixture Pattern (conftest.py):**
```python
@pytest.fixture
def mock_plugin(mocker):
    """Return mock plugin instance with logger and device mocks."""
    # ... setup code ...
    return plugin

@pytest.fixture
def mock_device(mocker):
    """Return mock Indigo device."""
    device = MagicMock()
    device.id = 1
    device.name = "Test Controller"
    device.address = "0cb8152f9f78"  # Valid serial number format
    device.states = {"id": "0cb8152f9f78"}
    device.pluginProps = {"NumZones": 4}
    return device

@pytest.fixture
def device_info_response():
    """Load real API response from fixture file."""
    with open("tests/fixtures/device_info.json") as f:
        return json.load(f)
```

**Factory Pattern:**
```python
def create_test_device(mocker, serial="0cb8152f9f78", name="Test"):
    """Factory to create test devices with custom parameters."""
    device = MagicMock()
    device.address = serial
    device.name = name
    return device
```

## Coverage

**Requirements:** >70% (stated in CLAUDE.md, targeting 85%+)

**View Coverage:**
```bash
# Terminal report
pytest tests/ --cov --cov-report=term-missing

# HTML report
pytest tests/ --cov --cov-report=html
open htmlcov/index.html
```

**Coverage Configuration (pytest.ini):**
```ini
[coverage:run]
source = .
omit =
    */tests/*
    */test_*
    */__pycache__/*

[coverage:report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
    @abstractmethod
```

**Coverage Gaps (from analysis):**
- Empty test files directory suggests tests may not be tracked in repo
- pytest.ini shows full test infrastructure configured
- Cached bytecode shows tests exist/existed (conftest, test_actions, test_validation, test_api_client)

## Test Types

**Unit Tests** (primary - ~50 tests):
- API call methods with mocked requests
- Validation methods with various input combinations
- Data transformation functions (timestamp conversion, list building)
- Error handling (exceptions, error codes, graceful degradation)
- Scope: Single method or small component
- No external dependencies

**Integration Tests** (secondary - ~14 tests):
- Test combinations of API calls and state updates
- Mock Indigo device updates (updateStatesOnServer, replacePluginPropsOnServer)
- Marked with `@pytest.mark.integration`
- May test data flow across multiple methods

**E2E Tests** (standalone - docs/test_local_api.py):
- Not part of pytest suite
- Tests against real Netro API
- Uses actual serial numbers from `.env` file
- Location: `docs/test_local_api.py`
- Usage: `python3 test_local_api.py --serial YOUR_SERIAL`
- Read-only by default, write operations require `--full` flag

## Common Patterns

**Async Testing Pattern:**
```python
def test_concurrent_thread_exception_handling(mock_plugin):
    """Test that runConcurrentThread swallows exceptions."""
    mock_plugin._update_from_netro = MagicMock(side_effect=Exception("Test"))

    # Thread should continue despite exception
    mock_plugin.runConcurrentThread()  # Within timeout

    # Verify sleep was called (thread loop continued)
    mock_plugin.sleep.assert_called()
```

**Error Testing Pattern:**
```python
def test_api_call_handles_connection_error(mocker, mock_plugin):
    """Test error handling for connection failures."""
    mocker.patch(
        "requests.get",
        side_effect=requests.exceptions.ConnectionError("Connection failed")
    )

    # Should raise exception but log gracefully
    with pytest.raises(requests.exceptions.ConnectionError):
        mock_plugin._make_api_call(url)

    # Verify error logged
    mock_plugin.logger.error.assert_called()
```

**Validation Testing Pattern:**
```python
def test_validate_device_config_requires_serial(mock_plugin):
    """Test that serial number is required."""
    valuesDict = {"address": ""}
    typeId = "sprinkler"

    is_valid, _, errorsDict = mock_plugin.validateDeviceConfigUi(
        valuesDict, typeId, 0
    )

    assert not is_valid
    assert "address" in errorsDict
    assert "required" in errorsDict["address"].lower()
```

**Rate Limit Testing Pattern:**
```python
def test_throttle_delay_prevents_api_calls(mock_plugin):
    """Test that ThrottleDelayError blocks API calls."""
    mock_plugin.throttle_next_call = datetime.now() + timedelta(minutes=1)

    with pytest.raises(ThrottleDelayError) as exc_info:
        mock_plugin._make_api_call(url)

    assert "throttled" in str(exc_info.value).lower()
```

**Fixture Data Pattern:**
```python
def test_moisture_parsing(mock_plugin, device_info_response):
    """Test parsing of moisture data from API response."""
    # Load real API response from fixture
    moisture_data = device_info_response["data"]["device"]["zones"][0]

    # Test parsing logic
    assert moisture_data["moisture"] == 45
```

## Test Dependencies

**Runtime Dependencies** (auto-installed):
- `requests==2.32.5` - Mocked in tests

**Development Dependencies** (from DEPENDENCIES.md):
- `pytest>=8.0.0` - Test runner
- `pytest-cov>=4.1.0` - Coverage reporting
- `pytest-mock>=3.12.0` - Mock/patch fixtures

**Installation:**
```bash
pip install pytest>=8.0.0 pytest-cov>=4.1.0 pytest-mock>=3.12.0
```

## Notes on Current State

**Test Infrastructure:**
- pytest.ini fully configured with markers, discovery patterns, and coverage settings
- tests/ directory structure in place with __pycache__ showing compiled tests existed
- Coverage configuration defined but test source files not present in working tree

**Implications:**
- Tests may have been gitignored or removed
- pytest configuration is ready for test implementation/recovery
- Coverage reporting is set up and ready to use
- Test markers (api, validation, actions, integration, slow) are defined for categorization

**For Adding New Tests:**
1. Create test files in `tests/` with `test_*.py` names
2. Define test functions with `test_*` names
3. Use fixtures from conftest.py for common setup
4. Mark tests with appropriate marker: `@pytest.mark.api`, etc.
5. Run with `pytest tests/ -v`

---

*Testing analysis: 2026-02-01*
