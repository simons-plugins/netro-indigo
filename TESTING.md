# Netro Plugin Testing Guide

This document explains how to run and add tests for the Netro Indigo plugin.

## Overview

The test suite provides comprehensive coverage of:
- API client functionality
- Configuration validation
- Action callbacks
- Error handling
- Edge cases

**Test Framework**: pytest
**Coverage Tool**: pytest-cov
**Mocking**: pytest-mock, responses

## Setup

### Install Test Dependencies

```bash
cd netro
pip3 install -r requirements-dev.txt
```

Dependencies installed:
- `pytest` - Test framework
- `pytest-cov` - Coverage reporting
- `pytest-mock` - Mocking utilities
- `responses` - HTTP request mocking
- `pylint` - Code quality checker
- `black` - Code formatter

## Running Tests

### Run All Tests

```bash
pytest tests/
```

### Run with Verbose Output

```bash
pytest tests/ -v
```

### Run Specific Test File

```bash
pytest tests/test_api_client.py
pytest tests/test_validation.py
pytest tests/test_actions.py
```

### Run Specific Test Class

```bash
pytest tests/test_api_client.py::TestAPIClient
pytest tests/test_validation.py::TestPluginConfigValidation
```

### Run Specific Test Method

```bash
pytest tests/test_api_client.py::TestAPIClient::test_successful_get_request
```

### Run Tests by Marker

Tests are organized with markers for easy filtering:

```bash
pytest -m api          # Run API client tests
pytest -m validation   # Run validation tests
pytest -m actions      # Run action tests
pytest -m slow         # Run slow tests only
```

### Run Tests with Coverage

```bash
# Terminal output
pytest --cov

# HTML report (opens in browser)
pytest --cov --cov-report=html
open htmlcov/index.html
```

### Run Tests with Coverage for Specific Module

```bash
pytest --cov=plugin.py tests/
```

## Test Structure

```
tests/
├── __init__.py                    # Test package
├── conftest.py                    # Shared fixtures and configuration
├── test_api_client.py             # API client tests (47 tests)
├── test_validation.py             # Validation tests (28 tests)
├── test_actions.py                # Action callback tests (30 tests)
└── fixtures/                      # Mock API responses
    ├── info_response.json         # Device info response
    ├── schedules_response.json    # Schedules response
    ├── moistures_response.json    # Moisture data response
    ├── sensor_data_response.json  # Sensor data response
    └── error_rate_limit.json      # Error response example
```

## Test Categories

### API Client Tests (`test_api_client.py`)

Tests for HTTP client functionality:
- Successful GET/POST requests
- Error handling (429, timeouts, connection errors)
- Throttle management
- Token tracking
- Response parsing

**Run**: `pytest tests/test_api_client.py -v`

### Validation Tests (`test_validation.py`)

Tests for configuration and input validation:
- Plugin config validation (serial, polling, timeout)
- Action parameter validation (duration, delay, zone)
- Device config validation
- Type checking (numeric, date formats)

**Run**: `pytest tests/test_validation.py -v`

### Action Tests (`test_actions.py`)

Tests for action callback methods:
- `startZoneWithDelay` - Zone control with delay/schedule
- `reportWeather` - Weather data submission
- `setNoWater` - Rain delay
- `setStandbyMode` - Standby mode toggle
- `getZoneList` - Zone dropdown population
- API payload construction

**Run**: `pytest tests/test_actions.py -v`

## Fixtures

### Available Fixtures (conftest.py)

- `mock_indigo` - Mock Indigo module
- `mock_plugin_prefs` - Mock plugin preferences
- `mock_device` - Mock sprinkler controller device
- `mock_whisperer_device` - Mock Whisperer sensor
- `load_fixture` - Load JSON fixtures
- `mock_requests_get` - Mock GET requests
- `mock_requests_post` - Mock POST requests
- `plugin_action` - Mock plugin action
- `mock_plugin` - Mock plugin instance

### Using Fixtures in Tests

```python
def test_something(mock_device, load_fixture):
    # Use mock device
    assert mock_device.address == "test-serial-123"

    # Load fixture data
    data = load_fixture("info_response.json")
    assert data["status"] == "OK"
```

## Adding New Tests

### 1. Determine Test Category

- API functionality → `test_api_client.py`
- Validation logic → `test_validation.py`
- Action callbacks → `test_actions.py`

### 2. Create Test Method

```python
def test_new_feature(self, mock_plugin, mock_device):
    """Test description."""
    # Arrange
    # ... setup test data

    # Act
    # ... execute code under test

    # Assert
    # ... verify expected results
```

### 3. Use Descriptive Names

- `test_successful_...` - Happy path tests
- `test_invalid_...` - Error case tests
- `test_edge_case_...` - Boundary tests

### 4. Add Test Markers

```python
@pytest.mark.slow
def test_long_running_operation(self):
    """Test that takes >1 second."""
    pass
```

## Coverage Goals

**Target**: >70% code coverage

### Check Current Coverage

```bash
pytest --cov --cov-report=term-missing
```

### Generate HTML Coverage Report

```bash
pytest --cov --cov-report=html
```

Then open `htmlcov/index.html` in a browser.

### Identify Uncovered Lines

The terminal report shows line numbers not covered by tests:

```
Name                    Stmts   Miss  Cover   Missing
-----------------------------------------------------
plugin.py                 450     85    81%   125-130, 245-250
```

Add tests to cover the missing lines.

## Common Testing Patterns

### Testing API Calls

```python
def test_api_call(self, mock_requests_get, load_fixture):
    # Mock the API response
    mock_get = mock_requests_get(
        "http://api.netrohome.com/npa/v1/info.json",
        "info_response.json"
    )

    # Test code that makes the call
    response = load_fixture("info_response.json")
    assert response["status"] == "OK"
```

### Testing Validation

```python
def test_validation(self, mock_plugin):
    # Test valid input
    assert validate_serial("a4cf12b8d5e2") is True

    # Test invalid input
    assert validate_serial("") is False
    assert validate_serial("short") is False
```

### Testing Error Handling

```python
def test_error_handling(self, mock_plugin):
    with pytest.raises(ValueError):
        convert_to_int("not-a-number")
```

## Troubleshooting

### Import Errors

If you get import errors for the plugin module:

```bash
# Add the plugin directory to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:/path/to/plugin/Contents/Server Plugin"
pytest tests/
```

### Fixture Not Found

Ensure you're using fixtures defined in `conftest.py`:

```python
def test_example(mock_device):  # ✓ Correct
    pass

def test_example():
    mock_device = ...  # ✗ Manual - use fixture instead
```

### Test Discovery Issues

Pytest looks for:
- Files: `test_*.py`
- Classes: `Test*`
- Functions: `test_*`

Ensure your test names follow this convention.

## Best Practices

1. **Keep Tests Independent**: Each test should run in isolation
2. **Use Descriptive Names**: Test names should describe what they test
3. **Follow AAA Pattern**: Arrange, Act, Assert
4. **Mock External Dependencies**: Don't make real API calls
5. **Test Edge Cases**: Test boundaries and error conditions
6. **Keep Tests Fast**: Use mocks to avoid slow operations
7. **One Assert Per Concept**: Focus each test on one behavior

## Continuous Integration

To run tests in CI/CD:

```bash
#!/bin/bash
# Install dependencies
pip3 install -r requirements-dev.txt

# Run tests with coverage
pytest tests/ --cov --cov-report=xml --cov-report=term

# Check coverage threshold
coverage report --fail-under=70
```

## Additional Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [Pytest-mock Documentation](https://pytest-mock.readthedocs.io/)

## Quick Reference

```bash
# Basic Commands
pytest tests/                           # Run all tests
pytest tests/ -v                        # Verbose output
pytest tests/ -x                        # Stop on first failure
pytest tests/ -k "api"                  # Run tests matching "api"
pytest tests/ --lf                      # Run last failed tests

# Coverage
pytest --cov                            # Show coverage
pytest --cov --cov-report=html          # HTML report
pytest --cov --cov-report=term-missing  # Show missing lines

# Markers
pytest -m api                           # Run API tests
pytest -m "not slow"                    # Skip slow tests
pytest --markers                        # List all markers
```
