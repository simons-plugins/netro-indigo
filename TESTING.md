# Testing Guide

This guide explains how to run and write tests for the Netro Sprinklers plugin.

## Test Structure

```
netro/
├── tests/                               # Test suite
│   ├── conftest.py                      # Shared pytest fixtures
│   ├── test_api_client.py              # API communication tests (17 tests)
│   ├── test_validation.py              # Configuration validation (24 tests)
│   ├── test_actions.py                 # Action callback tests (23 tests)
│   └── fixtures/                        # Mock API responses
│       ├── info_response.json
│       ├── schedules_response.json
│       ├── moistures_response.json
│       ├── sensor_data_response.json
│       └── error_responses.json
├── test_local_api.py                    # Standalone API testing script
└── LOCAL_TESTING.md                     # Guide for local API testing
```

**Total: 64 automated tests**

## Running Tests

### Prerequisites

```bash
# Install test dependencies
pip3 install pytest pytest-cov pytest-mock requests
```

### Run All Tests

```bash
# From netro directory
cd /path/to/Indigo/netro
pytest tests/
```

### Run Specific Test File

```bash
# Test API client only
pytest tests/test_api_client.py

# Test validation only
pytest tests/test_validation.py

# Test actions only
pytest tests/test_actions.py
```

### Run with Coverage Report

```bash
# Generate coverage report
pytest tests/ --cov --cov-report=html

# View report
open htmlcov/index.html
```

### Run Specific Test

```bash
# Run single test by name
pytest tests/test_api_client.py::test_successful_get_request

# Run tests matching pattern
pytest tests/ -k "validation"
```

### Verbose Output

```bash
# Show all test names and output
pytest tests/ -v

# Show print statements
pytest tests/ -s

# Both verbose and print
pytest tests/ -vs
```

## Test Categories

### 1. API Client Tests (`test_api_client.py`)

Tests the `_make_api_call()` method and API integration.

**What it tests**:
- ✅ Successful GET/POST/PUT requests
- ✅ JSON response parsing
- ✅ HTTP error handling (404, 429, 500)
- ✅ Timeout handling
- ✅ Connection error handling
- ✅ Throttle delay enforcement
- ✅ Throttle expiration
- ✅ Error message suppression after first display

**Example**:
```python
def test_successful_get_request(plugin):
    """Test successful GET request returns JSON data."""
    with patch('requests.get') as mock_get:
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "OK", "data": {}}
        mock_get.return_value = mock_response

        # Make API call
        result = plugin._make_api_call("http://test.com/api", "get")

        # Verify
        assert result == {"status": "OK", "data": {}}
        mock_get.assert_called_once()
```

**See full file for all 17 tests**

## Writing New Tests

### Test File Template

```python
"""Tests for [feature description]."""

import pytest
from unittest.mock import MagicMock, patch

def test_feature_success(plugin, mock_device):
    """Test successful [feature] operation."""
    # Arrange
    expected_result = {...}

    with patch.object(plugin, 'some_method') as mock_method:
        mock_method.return_value = expected_result

        # Act
        result = plugin.method_under_test()

        # Assert
        assert result == expected_result
        mock_method.assert_called_once()
```

### Using Fixtures

Available fixtures from `conftest.py`:

- **plugin**: Fully configured Plugin instance
- **mock_device**: Mock Indigo sprinkler device
- **mock_indigo**: Mocked indigo module

### Common Testing Patterns

**Testing validation methods**:
```python
def test_validation_with_errors():
    values = {"bad_field": "invalid"}
    is_valid, values, errors = plugin.validatePrefsConfigUi(values)
    assert not is_valid
    assert "bad_field" in errors
```

**Mocking API calls**:
```python
def test_api_interaction(plugin):
    with patch.object(plugin, '_make_api_call') as mock_api:
        mock_api.return_value = {"status": "OK", "data": {}}
        plugin._update_from_netro()
        assert mock_api.called
```

## Coverage Goals

**Target**: >70% code coverage

Run `pytest --cov` to see current coverage.

## Local API Testing

For testing against real Netro hardware:

```bash
python3 test_local_api.py --serial YOUR_SERIAL --help
```

See [LOCAL_TESTING.md](LOCAL_TESTING.md) for details.

## Additional Resources

- pytest documentation: https://docs.pytest.org
- Indigo SDK: See Indigo SDK/docs/

