# Phase 6: Testing Expansion - Research

**Researched:** 2026-02-02
**Domain:** Python testing with pytest, test coverage expansion for Indigo plugins
**Confidence:** HIGH

## Summary

This research investigates best practices for expanding test coverage from 70% (current reported) to 87% in a Python project using pytest. The actual coverage on testable modules is already excellent (api_client: 87%, device_handlers: 93%, validators: 91%, constants/exceptions/utils: 100%), while plugin.py is at 0% due to its `import indigo` dependency.

The focus is on:
1. Adding 15 Whisperer sensor tests covering edge cases (TEST-01)
2. Adding 8 network timeout error tests (TEST-02)
3. Adding 6 API 500 error tests (TEST-03)
4. Adding 6 malformed JSON response tests (TEST-04)
5. Adding 6 unicode edge case tests (TEST-05)
6. Adding 6 empty data edge case tests (TEST-06)
7. Adding 6 schedule parsing edge case tests (TEST-07)
8. Adding 6 concurrent thread tests (TEST-08)
9. Updating test coverage configuration (TEST-09)
10. Achieving 87% overall coverage (TEST-10)

The current test suite has 197 tests across 4 files with excellent patterns already established. The existing mocking patterns using `unittest.mock` with `side_effect` parameter are well-suited for error path testing.

**Primary recommendation:** Focus test expansion on the extracted modules (api_client, device_handlers, validators) where coverage can be measured and verified. Target the specific uncovered lines identified in coverage reports. Use parametrized tests for unicode and edge cases to maximize test value with minimal code.

## Standard Stack

The established libraries/tools for this domain:

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | >= 8.0.0 | Test framework | Already configured, de facto Python standard |
| pytest-cov | >= 4.1.0 | Coverage reporting | Already configured with branch coverage |
| pytest-mock | >= 3.12.0 | Mocking fixtures | Already in use via `unittest.mock` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| coverage.py | (via pytest-cov) | Line/branch coverage | Reports, HTML output |
| unittest.mock | (stdlib) | Mock objects | Already in use extensively |

### Already Configured

The project has optimal configuration in `pytest.ini`:
```ini
addopts =
    -v
    --strict-markers
    --tb=short
    --cov="Netro Sprinklers.indigoPlugin/Contents/Server Plugin"
    --cov-report=term-missing
    --cov-report=html
    --cov-branch

markers =
    api: Tests for API client functionality
    handlers: Tests for device handler functionality
    validation: Tests for configuration and action validation
    actions: Tests for action callback methods
    integration: Integration tests requiring external services
    slow: Tests that take more than 1 second
```

**No additional installation needed** - all dependencies already in place.

## Architecture Patterns

### Current Test Structure
```text
tests/
├── test_api_client.py       # 38 tests - NetroAPIClient functionality
├── test_base_modules.py     # 56 tests - constants, exceptions, utils
├── test_device_handlers.py  # 50 tests - SprinklerHandler, WhispererHandler
└── test_validators.py       # 53 tests - validation functions
```

### Recommended Additions
```text
tests/
├── conftest.py              # NEW: Shared fixtures (mock_logger, sample responses)
├── test_api_client.py       # EXPAND: +14 network error tests
├── test_base_modules.py     # NO CHANGE: 100% coverage
├── test_device_handlers.py  # EXPAND: +27 edge case tests
└── test_validators.py       # NO CHANGE: 91% coverage adequate
```

### Pattern 1: AAA Pattern (Arrange-Act-Assert)

**What:** All existing tests follow this structure consistently
**When to use:** Every test must follow this
**Example from existing codebase:**
```python
def test_process_device_info_online_device(self, sprinkler_handler, sample_device_info_response):
    """Online device returns is_online=True."""
    # Arrange: fixtures provide handler and response
    # Act
    states, is_online, device_data = sprinkler_handler.process_device_info(
        sample_device_info_response, "ABC123456789"
    )
    # Assert
    assert is_online is True
    assert len(states) > 0
```

### Pattern 2: Mocking Network Errors with side_effect

**What:** Use `side_effect` parameter to simulate exceptions
**When to use:** Testing network error paths (Timeout, ConnectionError, HTTPError)
**Example from existing test_api_client.py:**
```python
def test_make_request_handles_timeout(self, client, mock_logger):
    """Timeout logged and re-raised."""
    import requests as req
    with patch("api_client.requests.get", side_effect=req.exceptions.Timeout("Timed out")):
        with pytest.raises(req.exceptions.Timeout):
            client.make_request("https://api.test.com/endpoint")

    mock_logger.error.assert_called()
    assert "timed out" in mock_logger.error.call_args[0][0].lower()
```

### Pattern 3: Parametrized Tests for Edge Cases

**What:** Use `@pytest.mark.parametrize` to test multiple inputs
**When to use:** Unicode edge cases, boundary values, multiple error scenarios
**Example for new unicode tests:**
```python
@pytest.mark.parametrize("zone_name,expected_in_output", [
    ("Lawn", True),                    # ASCII
    ("Jardin Trasero", True),          # Spanish with space
    ("Zona del Jardin", True),         # Accented characters
    ("Zone\u2019s Name", True),        # Smart apostrophe
    ("", True),                        # Empty string
    ("Z" * 500, True),                 # Very long name
    ("\u4e2d\u6587\u533a\u57df", True),  # Chinese characters
    ("Zone \U0001f4a7", True),         # Emoji (water drop)
])
def test_extract_zone_info_unicode(sprinkler_handler, zone_name, expected_in_output):
    """Zone names with various unicode characters are handled."""
    device_data = {"zones": [{"ith": 1, "name": zone_name, "enabled": True}]}
    zone_names, _, zones_data = sprinkler_handler.extract_zone_info(device_data, 3600)
    if expected_in_output:
        assert zones_data[0]["name"] == zone_name
```

### Pattern 4: Mock Response Objects for HTTP Errors

**What:** Create mock response objects with specific status codes
**When to use:** Testing HTTP 500, 502, 503, 504, 429 responses
**Example for HTTP 500 testing:**
```python
def test_make_request_handles_http_500(client, mock_logger):
    """HTTP 500 error logged and re-raised."""
    import requests as req

    mock_response = Mock()
    mock_response.status_code = 500
    mock_response.json.side_effect = ValueError("Not JSON")  # 500 often not JSON
    mock_response.raise_for_status.side_effect = req.exceptions.HTTPError(
        response=mock_response
    )

    with patch("api_client.requests.get", return_value=mock_response):
        with pytest.raises(req.exceptions.HTTPError):
            client.make_request("https://api.test.com/endpoint")

    mock_logger.error.assert_called()
```

### Pattern 5: Fixture-based Test Organization

**What:** Group related fixtures in conftest.py or at module level
**When to use:** Sharing fixtures across multiple test classes
**Example for new conftest.py:**
```python
# tests/conftest.py
import pytest
from unittest.mock import Mock

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

### Anti-Patterns to Avoid

- **Testing plugin.py directly:** Import errors due to `import indigo` - test extracted modules instead
- **Mocking at wrong level:** Mock `api_client.requests.get` not just `requests.get`
- **Ignoring branch coverage:** Use `--cov-branch` and check partial branches
- **Single test file bloat:** Keep test files focused on single module
- **Over-mocking:** Don't mock the unit under test, only dependencies

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP request mocking | Manual response objects | `Mock(side_effect=...)` | Handles edge cases properly |
| Coverage measurement | Manual line counting | pytest-cov + Coverage.py | Branch coverage, HTML reports |
| Test discovery | Manual test registration | pytest auto-discovery | `test_*.py` files auto-discovered |
| Fixture management | Global test state | pytest fixtures with scopes | Isolation, dependency injection |
| Test parametrization | Loops in tests | `@pytest.mark.parametrize` | Better reporting, isolation |
| Timeout simulation | Real network delays | `side_effect=requests.Timeout()` | Fast, deterministic |

**Key insight:** The existing test patterns are well-designed. Expansion should follow the same patterns, not introduce new ones.

## Common Pitfalls

### Pitfall 1: Testing plugin.py Directly

**What goes wrong:** Attempting to unit test plugin.py results in `ModuleNotFoundError: No module named 'indigo'`
**Why it happens:** Plugin.py has `import indigo` at module level which fails outside Indigo runtime
**How to avoid:** Test extracted modules (api_client, device_handlers, validators) which are Indigo-free. Verify plugin.py integration by running the plugin in Indigo manually.
**Warning signs:** Import errors during test collection

### Pitfall 2: Mocking at Wrong Level

**What goes wrong:** Test passes but actual code path not exercised
**Why it happens:** Mocking `requests.get` instead of `api_client.requests.get`
**How to avoid:** Always mock where the name is LOOKED UP, not where it's defined
**Warning signs:** Mock assertions pass but coverage shows line not hit

### Pitfall 3: Missing Branch Coverage

**What goes wrong:** `is_throttled` only tested when True, missing False path
**Why it happens:** Happy path bias in test writing
**How to avoid:** Use branch coverage (`--cov-branch`) and check for partial branches in coverage report
**Warning signs:** Coverage shows `176->183` notation indicating partial branch

### Pitfall 4: Ignoring Error Suppression Logic

**What goes wrong:** Tests for repeated errors miss the "log once" behavior
**Why it happens:** api_client.py has `_last_error_type` that suppresses repeated errors
**How to avoid:** Test sequences of errors, verify `call_count` is 1 after multiple failures, then test reset
**Warning signs:** Unexpected error logging or missing log calls

### Pitfall 5: Empty List Edge Cases

**What goes wrong:** Code assumes non-empty lists, fails on `[]`
**Why it happens:** Only testing happy path with data
**How to avoid:** Explicit tests for empty moistures, empty schedules, empty sensor_data
**Warning signs:** `IndexError: list index out of range` or `KeyError` in production

### Pitfall 6: StopThread Testing Limitation

**What goes wrong:** Cannot test runConcurrentThread directly without Indigo
**Why it happens:** `self.StopThread` is an Indigo-provided exception class
**How to avoid:** Test the methods that runConcurrentThread calls (_update_from_netro) rather than the thread itself
**Warning signs:** AttributeError: 'NoneType' object has no attribute 'StopThread'

## Code Examples

Verified patterns from existing test files:

### Network Timeout Error (Existing Pattern)
```python
def test_make_request_handles_timeout(self, client, mock_logger):
    """Timeout logged and re-raised."""
    import requests as req
    with patch("api_client.requests.get", side_effect=req.exceptions.Timeout("Timed out")):
        with pytest.raises(req.exceptions.Timeout):
            client.make_request("https://api.test.com/endpoint")

    mock_logger.error.assert_called()
    assert "timed out" in mock_logger.error.call_args[0][0].lower()
```

### Connection Error (Existing Pattern)
```python
def test_make_request_handles_connection_error(self, client, mock_logger):
    """ConnectionError logged and re-raised."""
    import requests as req
    with patch("api_client.requests.get", side_effect=req.exceptions.ConnectionError("Network down")):
        with pytest.raises(req.exceptions.ConnectionError):
            client.make_request("https://api.test.com/endpoint")

    mock_logger.error.assert_called()
    assert "connection" in mock_logger.error.call_args[0][0].lower()
```

### Error Suppression Test (Existing Pattern)
```python
def test_make_request_suppresses_repeated_connection_errors(self, client, mock_logger):
    """Connection errors are logged only once."""
    import requests as req
    with patch("api_client.requests.get", side_effect=req.exceptions.ConnectionError("Network down")):
        for _ in range(3):
            try:
                client.make_request("https://api.test.com/endpoint")
            except req.exceptions.ConnectionError:
                pass

    # Should only log once
    assert mock_logger.error.call_count == 1
```

### Empty Sensor Data (Existing Pattern)
```python
def test_process_sensor_data_empty_readings(self, whisperer_handler, mock_logger):
    """Empty readings returns minimal meta-only update."""
    response = {
        "status": "OK",
        "data": {"sensor_data": []},
        "meta": {"token_remaining": 1500, "token_reset": "2026-02-02", "last_active": "2026-02-01", "time": "now"}
    }
    states, has_readings = whisperer_handler.process_sensor_data(response, "SENSOR123")

    assert has_readings is False
    mock_logger.info.assert_called()
    assert len(states) > 0  # Meta states returned
```

### HTTP 500 Error (New Pattern Needed)
```python
def test_make_request_handles_http_500_no_json(client, mock_logger):
    """HTTP 500 without JSON body is handled."""
    import requests as req

    mock_response = Mock()
    mock_response.status_code = 500
    mock_response.json.side_effect = ValueError("Not JSON")
    mock_response.raise_for_status.side_effect = req.exceptions.HTTPError(response=mock_response)

    with patch("api_client.requests.get", return_value=mock_response):
        with pytest.raises(req.exceptions.HTTPError):
            client.make_request("https://api.test.com/endpoint")

    mock_logger.error.assert_called()
    assert "500" in str(mock_logger.error.call_args) or "http" in mock_logger.error.call_args[0][0].lower()
```

### Unicode Zone Names (New Pattern Needed)
```python
@pytest.mark.parametrize("zone_name", [
    "Lawn",                          # ASCII
    "Jardin Trasero",                # Spanish
    "\u00c9tage",                     # French with accent
    "",                              # Empty string
    "Z" * 200,                       # Long name
])
def test_extract_zone_info_handles_unicode_names(sprinkler_handler, zone_name):
    """Zone names with unicode characters are preserved."""
    device_data = {"zones": [{"ith": 1, "name": zone_name, "enabled": True}]}
    zone_names, max_durations, zones_data = sprinkler_handler.extract_zone_info(device_data, 3600)

    assert zones_data[0]["name"] == zone_name
```

## Coverage Gap Analysis

### Current Coverage by Module

| Module | Statements | Missing | Branch | Coverage | Status |
|--------|-----------|---------|--------|----------|--------|
| api_client.py | 198 | 23 | 74 | 87% | Target for error tests |
| constants.py | 47 | 0 | 0 | 100% | Complete |
| device_handlers.py | 130 | 8 | 28 | 93% | Target for edge cases |
| exceptions.py | 24 | 0 | 0 | 100% | Complete |
| plugin.py | 444 | 444 | 169 | 0% | Cannot unit test |
| utils.py | 8 | 0 | 2 | 100% | Complete |
| validators.py | 160 | 8 | 86 | 91% | Acceptable |

### Specific Uncovered Lines

**api_client.py (13 missing lines):**
- Lines 176->183: Throttle reset branch (is_throttled property)
- Lines 285-290: Timeout error handling branch
- Lines 339-340: HTTP error without JSON body
- Lines 349-351: HTTP error fallback throttle calculation
- Line 374: Generic HTTP error logging
- Lines 432-433, 443, 447-448: State save/restore error branches
- Lines 533, 544, 555, 577, 579, 591, 607, 623, 639-640: Convenience method return paths

**device_handlers.py (8 missing lines):**
- Line 154->149: Schedule parsing early return
- Lines 340-341: extract_zone_info KeyError handling
- Lines 444-452: WhispererHandler KeyError and TypeError handling

**validators.py (8 missing lines):**
- Lines 75-77: validate_integer_range with default when empty
- Lines 157, 159: validate_required_float min/max bounds
- Lines 193-194: validate_optional_float out of range
- Line 223: validate_date_format error
- Lines 274-297, 284-292: device config validation branches
- Lines 318-322, 327-331, 332-334: action config validation branches
- Lines 363-367: prefs config validation branches
- Lines 503->493: prefs field spec iteration branch

## Test Categories by Requirement

### TEST-01: Whisperer Sensor Tests (15 tests)

**Target:** WhispererHandler.process_sensor_data()
**Current tests:** 10 in TestWhispererHandler class
**Missing coverage:** Lines 444-452 (exception handling)

**New tests needed:**
1. `test_process_sensor_data_keyerror_missing_data_key` - Missing "data" key entirely
2. `test_process_sensor_data_typeerror_data_is_string` - data is string not dict
3. `test_process_sensor_data_typeerror_sensor_data_is_dict` - sensor_data is dict not list
4. `test_process_sensor_data_null_moisture_value` - moisture is None
5. `test_process_sensor_data_negative_moisture` - moisture is -10
6. `test_process_sensor_data_null_celsius_value` - celsius is None
7. `test_process_sensor_data_null_battery_level` - battery_level is None
8. `test_process_sensor_data_battery_zero` - battery_level is 0
9. `test_process_sensor_data_battery_100` - battery_level is 100
10. `test_process_sensor_data_unicode_time_field` - time has unicode
11. `test_process_sensor_data_very_large_reading_id` - id is 2^32
12. `test_process_sensor_data_missing_all_optional_fields` - only id and moisture
13. `test_process_sensor_data_extra_unexpected_fields` - response has unknown keys
14. `test_process_sensor_data_empty_serial_string` - serial is ""
15. `test_process_sensor_data_serial_with_unicode` - serial has special chars

### TEST-02: Network Timeout Tests (8 tests)

**Target:** NetroAPIClient.make_request() timeout handling
**Current tests:** 1 (test_make_request_handles_timeout)
**Missing coverage:** Lines 285-290 (timeout error branch)

**New tests needed:**
1. `test_make_request_timeout_on_post` - Timeout during POST request
2. `test_make_request_timeout_on_put` - Timeout during PUT request
3. `test_make_request_timeout_suppresses_repeated` - Second timeout not logged
4. `test_make_request_timeout_resets_after_success` - Success clears error state
5. `test_make_request_timeout_preserves_throttle_state` - Timeout doesn't affect throttle
6. `test_make_request_timeout_with_custom_timeout_value` - Tests timeout parameter
7. `test_make_request_read_timeout_vs_connect_timeout` - Different timeout types
8. `test_get_device_info_timeout` - Convenience method timeout propagation

### TEST-03: API 500 Error Tests (6 tests)

**Target:** NetroAPIClient._handle_http_error()
**Current tests:** 0 for 500 errors specifically
**Missing coverage:** Lines 339-340, 374

**New tests needed:**
1. `test_handle_http_error_500_no_json_body` - 500 with HTML error page
2. `test_handle_http_error_500_with_json_error` - 500 with {"error": "msg"}
3. `test_handle_http_error_502_bad_gateway` - 502 error
4. `test_handle_http_error_503_service_unavailable` - 503 error
5. `test_handle_http_error_504_gateway_timeout` - 504 error
6. `test_handle_http_error_response_none` - HTTPError with response=None

### TEST-04: Malformed JSON Tests (6 tests)

**Target:** Handler process_* methods
**Current tests:** Some exist (test_process_device_info_malformed_response)
**Missing coverage:** device_handlers lines 340-341, 444-452

**New tests needed:**
1. `test_process_device_info_data_is_list` - data is [] not {}
2. `test_process_device_info_device_key_is_null` - device is None
3. `test_process_schedules_schedules_is_dict` - schedules is {} not []
4. `test_process_moistures_moistures_is_string` - moistures is "none"
5. `test_process_sensor_data_sensor_data_is_int` - sensor_data is 0
6. `test_api_response_missing_status_key` - No "status" key in response

### TEST-05: Unicode Edge Cases (6 tests)

**Target:** Zone names, device names in handlers
**Current tests:** None specifically for unicode
**Missing coverage:** None (defensive code exists)

**New tests needed:**
1. `test_extract_zone_info_emoji_in_name` - Zone named "Garden \U0001f33b"
2. `test_extract_zone_info_chinese_characters` - Zone named "\u82b1\u56ed"
3. `test_extract_zone_info_rtl_arabic` - Zone named "\u062d\u062f\u064a\u0642\u0629"
4. `test_extract_zone_info_mixed_scripts` - Zone named "Zone1 \u003c\u0026\u003e"
5. `test_process_device_info_unicode_device_name` - Device name with accents
6. `test_process_sensor_data_unicode_in_timestamps` - Time field with unicode

### TEST-06: Empty Data Edge Cases (6 tests)

**Target:** process_moistures, process_schedules, process_sensor_data
**Current tests:** Some exist (empty_schedules, empty_readings)
**Missing coverage:** Branch paths for empty data

**New tests needed:**
1. `test_process_device_info_zones_key_missing` - No "zones" key at all
2. `test_process_schedules_data_key_empty_object` - data: {}
3. `test_process_moistures_most_recent_date_has_no_entries` - Edge in date filtering
4. `test_extract_zone_info_all_zones_disabled` - All zones have enabled: false
5. `test_process_sensor_data_meta_completely_missing` - No meta key
6. `test_api_response_completely_empty` - Response is {}

### TEST-07: Schedule Parsing Edge Cases (6 tests)

**Target:** SprinklerHandler.process_schedules()
**Current tests:** 11 in TestSprinklerHandlerSchedules
**Missing coverage:** Line 154->149 (early return branch)

**New tests needed:**
1. `test_process_schedules_start_time_is_float_string` - "1706817600000.0"
2. `test_process_schedules_multiple_executing` - Two schedules with EXECUTING
3. `test_process_schedules_all_invalid_status` - All have INVALID/SKIPPED status
4. `test_process_schedules_duration_zero` - Schedule with duration: 0
5. `test_process_schedules_duration_negative` - Schedule with duration: -1
6. `test_process_schedules_zone_name_fallback` - Missing zone_name, uses zone number

### TEST-08: Concurrent Thread Tests (6 tests)

**Target:** _update_from_netro() behavior
**Current tests:** 0 (cannot test plugin.py directly)
**Recommendation:** Test handler exception safety instead

**New tests needed:**
1. `test_sprinkler_handler_exception_in_process_device_info` - Handler logs, doesn't crash
2. `test_whisperer_handler_exception_in_process_sensor_data` - Handler logs, doesn't crash
3. `test_api_client_exception_clears_after_success` - Error state management
4. `test_api_client_throttle_check_prevents_request` - Throttle respected
5. `test_api_client_multiple_device_requests` - State isolation between calls
6. `test_api_client_token_budget_tracks_across_requests` - Token count updates

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| unittest only | pytest + pytest-mock | pytest maturity ~2020 | Simpler fixtures |
| Line coverage only | Branch coverage (--cov-branch) | Coverage.py 4.0+ | Catches partial paths |
| Manual mock cleanup | pytest-mock scoped fixtures | pytest-mock 1.0 | No test pollution |
| Hardcoded test data | Fixture-based data | pytest best practice | Reusable, maintainable |

**Current best practice:**
- Use pytest-cov with `--cov-branch` for branch coverage
- Target 80-90% coverage as realistic goal, not 100%
- Focus on critical paths and error handling
- Use parametrized tests for edge cases

## Open Questions

### 1. Plugin.py Coverage Target

**What we know:** plugin.py has 0% coverage and cannot be unit tested
**What's unclear:** Should 87% target include or exclude plugin.py?
**Recommendation:** Calculate target based on testable modules only. Current testable module average is ~93%. Adding 59 new tests will increase branch coverage depth, not line coverage percentage significantly. Target should be: "all testable modules at 85%+, overall reported as best achievable given plugin.py constraint."

### 2. Creating conftest.py

**What we know:** Each test file duplicates mock_logger fixture
**What's unclear:** Whether to centralize now or keep local
**Recommendation:** Create conftest.py with shared fixtures (mock_logger, sample_device_info_response, etc.) during this phase to reduce duplication and improve maintainability.

### 3. Test Execution Time

**What we know:** Current 197 tests run in 0.39s
**What's unclear:** How adding 59 tests will affect CI time
**Recommendation:** All new tests use mocking (no real network), should add <0.2s total. No concern.

## Testing Strategy Recommendations

### Priority Order

1. **TEST-02 + TEST-03** (Network errors) - Highest impact, covers critical resilience paths
2. **TEST-01** (Whisperer) - Addresses specific coverage gap, 15 tests
3. **TEST-04** (Malformed JSON) - Defends against API changes
4. **TEST-05 + TEST-06** (Edge cases) - Defensive, prevents production surprises
5. **TEST-07** (Schedules) - Addresses partial branch coverage
6. **TEST-08** (Thread safety) - Verifies error isolation

### Fixture Strategy

Create `tests/conftest.py` with:
```python
import pytest
from unittest.mock import Mock

@pytest.fixture
def mock_logger():
    """Standard mock logger for all tests."""
    logger = Mock()
    logger.debug = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    logger.exception = Mock()
    return logger

@pytest.fixture
def sample_api_response():
    """Base successful API response structure."""
    return {
        "status": "OK",
        "data": {},
        "meta": {"token_remaining": 1500, "token_reset": "2026-02-02T00:00:00"}
    }
```

### Coverage Configuration Update

Add to pytest.ini for better reporting:
```ini
[coverage:report]
fail_under = 85
show_missing = true
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
    @abstractmethod
    import indigo  # Cannot test Indigo imports
```

## Sources

### Primary (HIGH confidence)
- Existing test files: test_api_client.py, test_device_handlers.py, test_validators.py, test_base_modules.py
- pytest.ini configuration in project
- Coverage report from `pytest --cov` run (2026-02-02)
- Source code analysis of api_client.py, device_handlers.py, validators.py

### Secondary (MEDIUM confidence)
- pytest-dev/pytest GitHub - fixture patterns and parametrization
- pytest official documentation - monkeypatch and mock patterns

### Tertiary (LOW confidence)
- General Python testing best practices

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Already configured and working in project
- Architecture: HIGH - Patterns verified in existing test files
- Coverage gaps: HIGH - Derived from actual coverage report
- Pitfalls: HIGH - Based on existing code and test analysis

**Research date:** 2026-02-02
**Valid until:** 60 days (testing patterns are stable)
