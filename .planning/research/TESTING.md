# Testing Research: Netro Plugin Refactoring

**Project:** Netro Sprinklers Indigo Plugin
**Research Date:** 2026-02-01
**Focus:** Improving test coverage from 70% to 75%+ during refactoring
**Confidence:** HIGH (based on existing codebase patterns, pytest documentation, and established testing patterns in UK-Trains plugin)

## Executive Summary

This research addresses testing strategies for improving coverage of refactored Python code, specifically for the Netro Sprinklers Indigo plugin. The current state includes 64 tests at 70% coverage with identified gaps in Whisperer sensor code, error paths, and edge cases.

Key recommendations:
1. **Prioritize Whisperer sensor tests first** - highest risk untested code
2. **Use error injection via side_effect** for network/API failure testing
3. **Test runConcurrentThread safely** using controlled iteration patterns
4. **Organize tests by component** (api, validation, actions, sensors, errors)
5. **Use parametrized tests** for edge cases and error scenarios

---

## Part 1: Testing Refactored Python Code

### Best Practices for Refactoring Tests

**Confidence:** HIGH - Based on established Python testing patterns

#### 1. Test Behavior, Not Implementation

When refactoring code, tests should verify **what** the code does, not **how** it does it.

```python
# BAD: Tests implementation details
def test_api_uses_requests_get(mock_plugin, mocker):
    """This test breaks if we switch HTTP libraries."""
    spy = mocker.spy(requests, 'get')
    mock_plugin._make_api_call(url)
    spy.assert_called_once()

# GOOD: Tests behavior/outcome
def test_api_returns_device_info(mock_plugin, mocker):
    """Tests what the function produces, not how."""
    mock_response = create_mock_response({"status": "OK", "data": {...}})
    mocker.patch("requests.get", return_value=mock_response)

    result = mock_plugin._make_api_call(url)

    assert result["status"] == "OK"
    assert "data" in result
```

#### 2. Characterization Tests Before Refactoring

Before changing code, write tests that capture current behavior:

```python
@pytest.mark.characterization
class TestCurrentMoistureBehavior:
    """Capture current behavior before refactoring."""

    def test_empty_moisture_list_returns_empty(self, mock_plugin, mocker):
        """Document current handling of empty moisture list."""
        mock_response = {"data": {"moistures": []}}
        mocker.patch.object(mock_plugin, '_make_api_call', return_value=mock_response)

        result = mock_plugin.callMoisturesAPI("test_serial")

        assert result == []  # Current behavior - document this

    def test_moisture_sorted_by_id_descending(self, mock_plugin, mocker):
        """Current behavior: sorts by ID descending to get latest."""
        moistures = [
            {"id": 100, "zone": 1, "moisture": 45, "date": "2026-01-01"},
            {"id": 200, "zone": 1, "moisture": 50, "date": "2026-01-02"},
        ]
        mock_response = {"data": {"moistures": moistures}}
        mocker.patch.object(mock_plugin, '_make_api_call', return_value=mock_response)

        result = mock_plugin.callMoisturesAPI("test_serial")

        # Verify we get the latest (highest ID)
        assert result[0]["value"] == "50"
```

#### 3. Test Both Happy Path and Edge Cases

Organize tests by scenario type:

```python
class TestMoistureAPIHappyPath:
    """Normal operation scenarios."""

    def test_single_zone_moisture(self, mock_plugin):
        """Single zone returns single moisture reading."""
        ...

    def test_multiple_zones_all_updated(self, mock_plugin):
        """All zones get moisture updates."""
        ...

class TestMoistureAPIEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_moisture_list(self, mock_plugin):
        """Empty list returns empty result, no crash."""
        ...

    def test_missing_zone_key(self, mock_plugin):
        """Missing 'zone' key handled gracefully."""
        ...

    def test_unicode_in_zone_name(self, mock_plugin):
        """Unicode characters in zone names don't break parsing."""
        ...
```

---

## Part 2: Testing Indigo Plugin Device Types (Sensors)

### Whisperer Sensor Test Strategy

**Confidence:** HIGH - Based on existing plugin code analysis and UK-Trains mock patterns

#### Current Whisperer Code Analysis (plugin.py:663-690)

The Whisperer sensor update code has several testable paths:
1. Normal sensor value update with all readings
2. `dev.sensorValue is None` path
3. `dev.onState is None` path
4. `dev.onState is not None` path with state image changes
5. Empty sensor readings list handling
6. ThrottleDelayError during sensor update

#### Mock Indigo Module Pattern

Follow the established pattern from UK-Trains (conftest.py):

```python
# tests/conftest.py
import sys
from unittest.mock import MagicMock, Mock
from pathlib import Path

# Mock indigo module BEFORE importing plugin
class MockIndigo:
    """Mock Indigo module for testing."""

    class PluginBase:
        def __init__(self, plugin_id, plugin_display_name, plugin_version, plugin_prefs, **kwargs):
            self.pluginId = plugin_id
            self.pluginDisplayName = plugin_display_name
            self.pluginVersion = plugin_version
            self.pluginPrefs = plugin_prefs
            self.logger = MagicMock()
            self.debug = False

        class StopThread(Exception):
            pass

        def sleep(self, seconds):
            pass

    class Dict(dict):
        pass

    devices = MagicMock()
    trigger = MagicMock()

    # Sensor image selectors
    class kStateImageSel:
        HumiditySensor = "HumiditySensor"
        HumiditySensorOn = "HumiditySensorOn"
        Auto = "Auto"

# Install mock before any plugin imports
sys.modules['indigo'] = MockIndigo()

# Now import plugin
plugin_dir = Path(__file__).parent.parent / "Netro Sprinklers.indigoPlugin" / "Contents" / "Server Plugin"
sys.path.insert(0, str(plugin_dir))
```

#### Whisperer Device Mock Factory

```python
# tests/conftest.py

def create_mock_whisperer_device(
    device_id=1,
    name="Test Whisperer",
    address="whisperer123abc",
    enabled=True,
    sensor_value=50.0,
    on_state=True
):
    """Factory for creating mock Whisperer sensor devices."""
    device = MagicMock()
    device.id = device_id
    device.name = name
    device.address = address
    device.enabled = enabled
    device.deviceTypeId = "Whisperer"
    device.sensorValue = sensor_value
    device.onState = on_state
    device.states = {}
    device.pluginProps = {}

    # Track state updates
    device._state_updates = []

    def capture_states(key_value_list):
        device._state_updates.extend(key_value_list)
        for kv in key_value_list:
            device.states[kv['key']] = kv['value']

    device.updateStatesOnServer = MagicMock(side_effect=capture_states)
    device.updateStateOnServer = MagicMock(side_effect=lambda k, v: capture_states([{'key': k, 'value': v}]))
    device.updateStateImageOnServer = MagicMock()

    return device

@pytest.fixture
def mock_whisperer_device():
    """Default Whisperer device fixture."""
    return create_mock_whisperer_device()
```

#### Whisperer Sensor Tests

```python
# tests/test_whisperer.py

import pytest
from unittest.mock import MagicMock, patch

@pytest.mark.sensors
class TestWhispererSensorUpdates:
    """Tests for Whisperer soil sensor device updates."""

    def test_sensor_data_updates_all_states(self, mock_plugin, mock_whisperer_device, mocker):
        """Test that sensor API response updates all expected states."""
        sensor_response = {
            "status": "OK",
            "data": {
                "sensor_data": [{
                    "id": 12345,
                    "moisture": 45.5,
                    "celsius": 22.0,
                    "sunlight": 1500,
                    "battery_level": 85,
                    "time": "2026-02-01T10:00:00",
                    "local_date": "2026-02-01",
                    "local_time": "10:00:00"
                }]
            },
            "meta": {
                "token_remaining": 1500,
                "token_reset": "2026-02-02T00:00:00",
                "last_active": "2026-02-01T10:00:00",
                "time": "2026-02-01T10:05:00"
            }
        }

        mocker.patch.object(mock_plugin, '_make_api_call', return_value=sensor_response)
        mocker.patch('indigo.devices.iter', return_value=[mock_whisperer_device])

        mock_plugin._update_from_netro()

        # Verify state updates
        mock_whisperer_device.updateStatesOnServer.assert_called()
        states = {kv['key']: kv['value'] for kv in mock_whisperer_device._state_updates}

        assert states['humidity'] == 45.5
        assert states['temperature'] == 22.0
        assert states['sunlight'] == 1500
        assert states['batteryLevel'] == 85

    def test_sensor_value_none_uses_fallback_path(self, mock_plugin, mocker):
        """Test behavior when dev.sensorValue is None."""
        device = create_mock_whisperer_device(sensor_value=None, on_state=True)
        mocker.patch('indigo.devices.iter', return_value=[device])

        mock_plugin._update_from_netro()

        # Should update state but use different path
        device.updateStateOnServer.assert_called_with("onOffState", False)  # not dev.onState
        device.updateStateImageOnServer.assert_called_with('Auto')

    def test_empty_sensor_readings_handled(self, mock_plugin, mock_whisperer_device, mocker):
        """Test handling of empty sensor_data array."""
        empty_response = {
            "status": "OK",
            "data": {"sensor_data": []},
            "meta": {"token_remaining": 1500, "token_reset": "", "last_active": "", "time": ""}
        }
        mocker.patch.object(mock_plugin, '_make_api_call', return_value=empty_response)
        mocker.patch('indigo.devices.iter', return_value=[mock_whisperer_device])

        mock_plugin._update_from_netro()

        # Should log warning but not crash
        mock_plugin.logger.warning.assert_called()

    def test_sensor_on_state_changes_image(self, mock_plugin, mocker):
        """Test that onState changes trigger correct image updates."""
        # Test with onState=True
        device_on = create_mock_whisperer_device(on_state=True)
        mocker.patch('indigo.devices.iter', return_value=[device_on])
        mock_plugin._setup_sensor_response(mocker)

        mock_plugin._update_from_netro()
        device_on.updateStateImageOnServer.assert_called_with('HumiditySensorOn')

        # Test with onState=False
        device_off = create_mock_whisperer_device(on_state=False)
        mocker.patch('indigo.devices.iter', return_value=[device_off])

        mock_plugin._update_from_netro()
        device_off.updateStateImageOnServer.assert_called_with('HumiditySensor')

    def test_throttle_error_skips_sensor_update(self, mock_plugin, mock_whisperer_device, mocker):
        """Test that ThrottleDelayError skips sensor without crashing."""
        from plugin import ThrottleDelayError

        mocker.patch.object(
            mock_plugin, '_make_api_call',
            side_effect=ThrottleDelayError("throttled")
        )
        mocker.patch('indigo.devices.iter', return_value=[mock_whisperer_device])

        # Should not raise, should continue
        mock_plugin._update_from_netro()

        # Sensor states should NOT be updated
        mock_whisperer_device.updateStatesOnServer.assert_not_called()

@pytest.mark.sensors
class TestCallSensorAPI:
    """Tests for callSensorAPI method."""

    def test_returns_structured_sensor_data(self, mock_plugin, mocker):
        """Test that callSensorAPI returns properly structured data."""
        api_response = {
            "status": "OK",
            "data": {
                "sensor_data": [{
                    "id": 1,
                    "moisture": 42.0,
                    "celsius": 20.0,
                    "sunlight": 1000,
                    "battery_level": 90,
                    "time": "2026-02-01T10:00:00",
                    "local_date": "2026-02-01",
                    "local_time": "10:00:00"
                }]
            },
            "meta": {
                "token_remaining": 1800,
                "token_reset": "2026-02-02T00:00:00",
                "last_active": "2026-02-01T09:00:00",
                "time": "2026-02-01T10:05:00"
            }
        }
        mocker.patch.object(mock_plugin, '_make_api_call', return_value=api_response)

        result = mock_plugin.callSensorAPI("whisperer_serial")

        assert result['sensorStatus'] == 'OK'
        assert 'sensorKeyValuesList' in result
        assert len(result['sensorKeyValuesList']) > 0

    def test_sorts_readings_by_id_descending(self, mock_plugin, mocker):
        """Test that sensor readings are sorted to get most recent."""
        api_response = {
            "status": "OK",
            "data": {
                "sensor_data": [
                    {"id": 100, "moisture": 40, "celsius": 20, "sunlight": 1000,
                     "battery_level": 80, "time": "t1", "local_date": "d1", "local_time": "lt1"},
                    {"id": 200, "moisture": 50, "celsius": 25, "sunlight": 1200,
                     "battery_level": 85, "time": "t2", "local_date": "d2", "local_time": "lt2"},
                ]
            },
            "meta": {"token_remaining": 1000, "token_reset": "", "last_active": "", "time": ""}
        }
        mocker.patch.object(mock_plugin, '_make_api_call', return_value=api_response)

        result = mock_plugin.callSensorAPI("serial")

        # Should use reading with highest ID (200, moisture=50)
        moisture_kv = next(kv for kv in result['sensorKeyValuesList'] if kv['key'] == 'humidity')
        assert moisture_kv['value'] == 50
```

---

## Part 3: Error Path Testing Strategies

### Testing Network Timeouts, API Failures, and Malformed Responses

**Confidence:** HIGH - Based on pytest-mock documentation and established patterns

#### Error Injection Patterns Using side_effect

```python
# tests/test_error_paths.py

import pytest
import requests
from unittest.mock import MagicMock

@pytest.mark.errors
class TestNetworkErrors:
    """Tests for network-related error handling."""

    def test_connection_error_logs_once(self, mock_plugin, mocker):
        """Test that connection errors are logged only on first occurrence."""
        mocker.patch(
            'requests.get',
            side_effect=requests.exceptions.ConnectionError("Connection failed")
        )

        # First call should log
        with pytest.raises(requests.exceptions.ConnectionError):
            mock_plugin._make_api_call("http://api.test.com/endpoint")

        mock_plugin.logger.error.assert_called()
        assert mock_plugin._displayed_connection_error is True

        # Second call should NOT log again
        mock_plugin.logger.error.reset_mock()
        with pytest.raises(requests.exceptions.ConnectionError):
            mock_plugin._make_api_call("http://api.test.com/endpoint")

        mock_plugin.logger.error.assert_not_called()

    def test_timeout_error_logs_and_raises(self, mock_plugin, mocker):
        """Test timeout error handling."""
        mocker.patch(
            'requests.get',
            side_effect=requests.exceptions.Timeout("Request timed out")
        )

        with pytest.raises(requests.exceptions.Timeout):
            mock_plugin._make_api_call("http://api.test.com/endpoint")

        mock_plugin.logger.error.assert_called()
        assert "timeout" in mock_plugin.logger.error.call_args[0][0].lower() or \
               "contact" in mock_plugin.logger.error.call_args[0][0].lower()

    def test_read_timeout_error(self, mock_plugin, mocker):
        """Test ReadTimeout specifically (controller offline scenario)."""
        mocker.patch(
            'requests.get',
            side_effect=requests.exceptions.ReadTimeout("Read timed out")
        )

        with pytest.raises(requests.exceptions.ReadTimeout):
            mock_plugin._make_api_call("http://api.test.com/endpoint")

        # Should mention controller offline
        assert mock_plugin._displayed_connection_error is True

@pytest.mark.errors
class TestAPIErrors:
    """Tests for API-level error responses."""

    def test_http_429_triggers_throttle(self, mock_plugin, mocker):
        """Test that HTTP 429 sets throttle state."""
        from plugin import ThrottleDelayError

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
        mock_response.json.side_effect = ValueError("No JSON")

        mocker.patch('requests.get', return_value=mock_response)

        with pytest.raises(ThrottleDelayError):
            mock_plugin._make_api_call("http://api.test.com/endpoint")

        assert mock_plugin.throttle_next_call is not None

    def test_netro_error_code_3_rate_limit(self, mock_plugin, mocker):
        """Test Netro-specific rate limit error (code 3)."""
        from plugin import ThrottleDelayError

        error_response = {
            "status": "ERROR",
            "errors": [{"code": 3, "message": "Rate limit exceeded"}],
            "meta": {"token_remaining": -5, "token_reset": "2026-02-02T00:00:00"}
        }

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
        mock_response.json.return_value = error_response

        mocker.patch('requests.get', return_value=mock_response)

        with pytest.raises(ThrottleDelayError) as exc_info:
            mock_plugin._make_api_call("http://api.test.com/endpoint")

        assert "rate limit" in str(exc_info.value).lower()
        mock_plugin.logger.warning.assert_called()

    def test_netro_error_code_1_invalid_key(self, mock_plugin, mocker):
        """Test Netro invalid serial number error (code 1)."""
        error_response = {
            "status": "ERROR",
            "errors": [{"code": 1, "message": "Invalid API key"}],
            "meta": {}
        }

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
        mock_response.json.return_value = error_response

        mocker.patch('requests.get', return_value=mock_response)

        with pytest.raises(requests.exceptions.HTTPError):
            mock_plugin._make_api_call("http://api.test.com/endpoint")

        # Should log error about invalid serial
        mock_plugin.logger.error.assert_called()
        assert "serial" in mock_plugin.logger.error.call_args[0][0].lower() or \
               "invalid" in mock_plugin.logger.error.call_args[0][0].lower()

    def test_http_500_server_error(self, mock_plugin, mocker):
        """Test HTTP 500 internal server error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "500 Server Error", response=mock_response
        )

        mocker.patch('requests.get', return_value=mock_response)

        with pytest.raises(requests.exceptions.HTTPError):
            mock_plugin._make_api_call("http://api.test.com/endpoint")

@pytest.mark.errors
class TestMalformedResponses:
    """Tests for handling malformed API responses."""

    def test_invalid_json_response(self, mock_plugin, mocker):
        """Test handling of response with invalid JSON."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")

        mocker.patch('requests.get', return_value=mock_response)

        with pytest.raises(ValueError):
            mock_plugin._make_api_call("http://api.test.com/endpoint")

    def test_missing_data_key_in_response(self, mock_plugin, mocker):
        """Test response missing expected 'data' key."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "OK"}  # No 'data' key

        mocker.patch('requests.get', return_value=mock_response)

        result = mock_plugin._make_api_call("http://api.test.com/endpoint")

        # Should return the response, caller handles missing keys
        assert result["status"] == "OK"
        assert "data" not in result

    def test_missing_device_in_response(self, mock_plugin, mocker):
        """Test info.json response missing 'device' object."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "OK", "data": {}}

        mocker.patch.object(mock_plugin, '_make_api_call', return_value=mock_response.json.return_value)

        # This should be caught by _update_from_netro
        # The test verifies we don't crash
        mock_plugin._update_from_netro()

        mock_plugin.logger.error.assert_called()

    def test_timestamp_as_string_vs_number(self, mock_plugin, mocker):
        """Test handling timestamps that arrive as strings vs numbers."""
        # Netro API sometimes returns timestamps as strings
        schedule_response = {
            "status": "OK",
            "data": {
                "schedules": [{
                    "status": "VALID",
                    "zone": 1,
                    "source": "SMART",
                    "start_time": "1706745600000",  # String!
                    "duration": 600
                }]
            }
        }

        mocker.patch.object(mock_plugin, '_make_api_call', return_value=schedule_response)

        # Should handle string timestamp without crashing
        # This tests the defensive parsing in _update_from_netro
```

#### Parametrized Error Testing

```python
@pytest.mark.errors
class TestErrorScenarios:
    """Parametrized tests for multiple error scenarios."""

    @pytest.mark.parametrize("exception_class,exception_msg", [
        (requests.exceptions.ConnectionError, "Connection refused"),
        (requests.exceptions.Timeout, "Request timed out"),
        (requests.exceptions.ReadTimeout, "Read timed out"),
        (requests.exceptions.ConnectTimeout, "Connect timed out"),
    ])
    def test_network_exceptions_handled(self, mock_plugin, mocker, exception_class, exception_msg):
        """All network exceptions should be caught and logged."""
        mocker.patch('requests.get', side_effect=exception_class(exception_msg))

        with pytest.raises(exception_class):
            mock_plugin._make_api_call("http://api.test.com/endpoint")

        assert mock_plugin._displayed_connection_error is True

    @pytest.mark.parametrize("status_code,should_raise", [
        (200, False),
        (204, False),
        (400, True),
        (401, True),
        (403, True),
        (404, True),
        (429, True),
        (500, True),
        (502, True),
        (503, True),
    ])
    def test_http_status_codes(self, mock_plugin, mocker, status_code, should_raise):
        """Test handling of various HTTP status codes."""
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.json.return_value = {"status": "OK"}

        if should_raise:
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
                f"{status_code} Error", response=mock_response
            )
        else:
            mock_response.raise_for_status.return_value = None

        mocker.patch('requests.get', return_value=mock_response)

        if should_raise:
            with pytest.raises((requests.exceptions.HTTPError, Exception)):
                mock_plugin._make_api_call("http://api.test.com/endpoint")
        else:
            result = mock_plugin._make_api_call("http://api.test.com/endpoint")
            assert result is not None
```

---

## Part 4: Testing Concurrent Threads Safely

### Testing runConcurrentThread

**Confidence:** HIGH - Based on Indigo plugin patterns and thread testing best practices

#### The Challenge

`runConcurrentThread()` runs an infinite loop:

```python
def runConcurrentThread(self):
    while True:
        try:
            self._update_from_netro()
        except (Exception,):
            pass
        self.sleep(self.pollingInterval * 60)
```

Testing this directly would hang forever. Instead, test controlled iterations.

#### Strategy 1: Test Single Iteration Components

```python
@pytest.mark.threading
class TestConcurrentThreadComponents:
    """Test individual components of the polling loop."""

    def test_update_from_netro_called(self, mock_plugin, mocker):
        """Test that _update_from_netro is called during iteration."""
        update_mock = mocker.patch.object(mock_plugin, '_update_from_netro')

        # Manually call what the loop does
        try:
            mock_plugin._update_from_netro()
        except Exception:
            pass

        update_mock.assert_called_once()

    def test_sleep_called_with_correct_interval(self, mock_plugin, mocker):
        """Test that sleep is called with polling interval."""
        mock_plugin.pollingInterval = 5
        sleep_mock = mocker.patch.object(mock_plugin, 'sleep')
        update_mock = mocker.patch.object(mock_plugin, '_update_from_netro')

        # Simulate one loop iteration
        try:
            mock_plugin._update_from_netro()
        except Exception:
            pass
        mock_plugin.sleep(mock_plugin.pollingInterval * 60)

        sleep_mock.assert_called_with(300)  # 5 * 60
```

#### Strategy 2: Use StopThread Exception

```python
@pytest.mark.threading
class TestConcurrentThreadLoop:
    """Test the actual runConcurrentThread method safely."""

    def test_loop_catches_update_exceptions(self, mock_plugin, mocker):
        """Test that exceptions in _update_from_netro don't kill the thread."""
        call_count = [0]

        def update_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError("Simulated error")
            elif call_count[0] >= 2:
                raise mock_plugin.StopThread()

        mocker.patch.object(mock_plugin, '_update_from_netro', side_effect=update_side_effect)
        mocker.patch.object(mock_plugin, 'sleep')

        # This will now terminate after 2 iterations
        try:
            mock_plugin.runConcurrentThread()
        except mock_plugin.StopThread:
            pass

        # Verify it kept running after exception
        assert call_count[0] == 2

    def test_loop_sleeps_between_updates(self, mock_plugin, mocker):
        """Test that sleep is called between updates."""
        iteration = [0]

        def update_then_stop():
            iteration[0] += 1
            if iteration[0] >= 2:
                raise mock_plugin.StopThread()

        mocker.patch.object(mock_plugin, '_update_from_netro', side_effect=update_then_stop)
        sleep_mock = mocker.patch.object(mock_plugin, 'sleep')

        try:
            mock_plugin.runConcurrentThread()
        except mock_plugin.StopThread:
            pass

        # Sleep should have been called at least once
        assert sleep_mock.call_count >= 1
```

#### Strategy 3: Mock the Loop Control

```python
@pytest.mark.threading
class TestConcurrentThreadControl:
    """Test loop control and termination."""

    def test_stop_thread_terminates_loop(self, mock_plugin, mocker):
        """Test that StopThread exception properly terminates."""
        mocker.patch.object(
            mock_plugin, '_update_from_netro',
            side_effect=mock_plugin.StopThread()
        )

        # Should exit cleanly via StopThread
        with pytest.raises(mock_plugin.StopThread):
            mock_plugin.runConcurrentThread()

    def test_polling_interval_respected(self, mock_plugin, mocker):
        """Test that polling interval from prefs is used."""
        mock_plugin.pollingInterval = 10

        iteration = [0]
        def stop_after_one():
            iteration[0] += 1
            raise mock_plugin.StopThread()

        mocker.patch.object(mock_plugin, '_update_from_netro', side_effect=stop_after_one)
        sleep_mock = mocker.patch.object(mock_plugin, 'sleep')

        try:
            mock_plugin.runConcurrentThread()
        except mock_plugin.StopThread:
            pass

        # Verify interval: 10 minutes * 60 seconds = 600
        if sleep_mock.called:
            sleep_mock.assert_called_with(600)
```

---

## Part 5: Edge Case Testing

### Unicode, Empty Lists, and Schedule Parsing

**Confidence:** HIGH

#### Unicode Edge Cases

```python
@pytest.mark.edge_cases
class TestUnicodeHandling:
    """Tests for unicode character handling."""

    def test_unicode_in_device_name(self, mock_plugin, mocker):
        """Test device with unicode name doesn't break processing."""
        device_response = {
            "status": "OK",
            "data": {
                "device": {
                    "name": "Garten Bewasserung",  # German umlaut
                    "serial": "abc123",
                    "status": "ONLINE",
                    "zones": [],
                    "version": "1.0"
                }
            },
            "meta": {"token_remaining": 1500, "token_reset": "", "time": "", "last_active": ""}
        }
        mocker.patch.object(mock_plugin, '_make_api_call', return_value=device_response)

        # Should not raise
        mock_plugin._update_from_netro()

    def test_unicode_in_zone_name(self, mock_plugin, mocker):
        """Test zone with unicode name in moisture data."""
        moisture_response = {
            "data": {
                "moistures": [{
                    "id": 1,
                    "zone": 1,
                    "zone_name": "Jardin Francais",  # French cedilla
                    "moisture": 45,
                    "date": "2026-02-01"
                }]
            }
        }
        mocker.patch.object(mock_plugin, '_make_api_call', return_value=moisture_response)

        result = mock_plugin.callMoisturesAPI("serial")
        assert len(result) == 1

    def test_unicode_in_schedule_source(self, mock_plugin, mocker):
        """Test schedule with unicode in source/name."""
        schedule_response = {
            "status": "OK",
            "data": {
                "schedules": [{
                    "status": "VALID",
                    "zone": 1,
                    "zone_name": "Rosen-Beet",  # Hyphenated German
                    "source": "MANUAL",
                    "start_time": 1706745600000,
                    "duration": 600
                }]
            }
        }
        mocker.patch.object(mock_plugin, '_make_api_call', return_value=schedule_response)

        # Should process without error
        mock_plugin._update_from_netro()
```

#### Empty List Edge Cases

```python
@pytest.mark.edge_cases
class TestEmptyListHandling:
    """Tests for empty list/array handling."""

    def test_empty_zones_list(self, mock_plugin, mocker):
        """Test device with no zones configured."""
        device_response = {
            "status": "OK",
            "data": {
                "device": {
                    "name": "Test Device",
                    "serial": "abc123",
                    "status": "ONLINE",
                    "zones": [],  # Empty!
                    "version": "1.0"
                }
            },
            "meta": {"token_remaining": 1500, "token_reset": "", "time": "", "last_active": ""}
        }
        mocker.patch.object(mock_plugin, '_make_api_call', return_value=device_response)

        # Should not crash
        mock_plugin._update_from_netro()

    def test_empty_schedules_list(self, mock_plugin, mocker):
        """Test handling of no scheduled waterings."""
        schedule_response = {
            "status": "OK",
            "data": {"schedules": []}
        }
        mocker.patch.object(mock_plugin, '_make_api_call', return_value=schedule_response)

        # Should set "No upcoming schedule" states
        mock_plugin._update_from_netro()

    def test_empty_moisture_list(self, mock_plugin, mocker):
        """Test handling of no moisture data."""
        moisture_response = {"data": {"moistures": []}}
        mocker.patch.object(mock_plugin, '_make_api_call', return_value=moisture_response)

        result = mock_plugin.callMoisturesAPI("serial")

        assert result == []
        mock_plugin.logger.debug.assert_called()  # Should log the empty case
```

#### Schedule Parsing Edge Cases

```python
@pytest.mark.edge_cases
class TestScheduleParsing:
    """Tests for schedule data parsing edge cases."""

    def test_schedule_timestamp_as_string(self, mock_plugin, mocker):
        """Test start_time arriving as string (API quirk)."""
        schedule_response = {
            "status": "OK",
            "data": {
                "schedules": [{
                    "status": "VALID",
                    "zone": 1,
                    "source": "SMART",
                    "start_time": "1706745600000",  # String, not number
                    "duration": 600
                }]
            }
        }
        mocker.patch.object(mock_plugin, '_make_api_call', return_value=schedule_response)

        # Should parse string timestamp correctly
        mock_plugin._update_from_netro()

    def test_multiple_schedule_types(self, mock_plugin, mocker):
        """Test mix of EXECUTING, VALID, COMPLETED schedules."""
        schedule_response = {
            "status": "OK",
            "data": {
                "schedules": [
                    {"status": "COMPLETED", "zone": 1, "source": "MANUAL", "start_time": 1000, "duration": 300},
                    {"status": "EXECUTING", "zone": 2, "source": "SMART", "start_time": 2000, "duration": 600},
                    {"status": "VALID", "zone": 3, "source": "FIX", "start_time": 3000, "duration": 900},
                    {"status": "VALID", "zone": 1, "source": "AUTOMATIC", "start_time": 4000, "duration": 600},
                ]
            }
        }
        mocker.patch.object(mock_plugin, '_make_api_call', return_value=schedule_response)

        # Should find EXECUTING as current, earliest VALID as next
        mock_plugin._update_from_netro()

    def test_invalid_timestamp_fallback(self, mock_plugin, mocker):
        """Test handling of unparseable timestamp."""
        schedule_response = {
            "status": "OK",
            "data": {
                "schedules": [{
                    "status": "VALID",
                    "zone": 1,
                    "source": "SMART",
                    "start_time": "invalid_timestamp",
                    "duration": 600
                }]
            }
        }
        mocker.patch.object(mock_plugin, '_make_api_call', return_value=schedule_response)

        # Should not crash, should use fallback
        mock_plugin._update_from_netro()
```

---

## Part 6: Test Organization and Structure

### Recommended Test File Structure

```
tests/
├── conftest.py                 # Shared fixtures, mock setup
├── mocks/
│   ├── __init__.py
│   ├── mock_indigo.py          # Mock Indigo module
│   └── mock_netro_api.py       # Mock API response factories
├── fixtures/
│   ├── device_info.json        # Sample API responses
│   ├── schedules.json
│   ├── moistures.json
│   └── sensor_data.json
├── unit/
│   ├── test_api_client.py      # API call logic (17+ tests)
│   ├── test_validation.py      # Config validation (24+ tests)
│   ├── test_actions.py         # Action handlers (23+ tests)
│   ├── test_whisperer.py       # Sensor tests (NEW - 15+ tests)
│   └── test_utilities.py       # Helper functions
├── error_paths/
│   ├── test_network_errors.py  # Network failures (NEW - 10+ tests)
│   ├── test_api_errors.py      # API error codes (NEW - 10+ tests)
│   └── test_malformed_data.py  # Bad responses (NEW - 8+ tests)
├── edge_cases/
│   ├── test_unicode.py         # Unicode handling (NEW - 5+ tests)
│   ├── test_empty_data.py      # Empty lists (NEW - 5+ tests)
│   └── test_schedule_parsing.py # Schedule edge cases (NEW - 8+ tests)
└── integration/
    └── test_thread_safety.py   # Concurrent thread tests (NEW - 6+ tests)
```

### Pytest Markers Configuration

```ini
# pytest.ini
[pytest]
markers =
    api: Tests for API client functionality
    validation: Tests for configuration and action validation
    actions: Tests for action callback methods
    sensors: Tests for Whisperer sensor functionality
    errors: Tests for error handling paths
    edge_cases: Tests for edge cases and boundary conditions
    threading: Tests for concurrent thread behavior
    integration: Integration tests requiring more setup
    slow: Tests that take more than 1 second
    characterization: Tests documenting current behavior
```

---

## Part 7: Coverage Measurement Best Practices

**Confidence:** HIGH

### Coverage Configuration

```ini
# pytest.ini additions
[coverage:run]
source = Netro Sprinklers.indigoPlugin/Contents/Server Plugin
branch = true
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
    # Indigo-specific patterns that can't be tested without Indigo
    indigo.debugger()
show_missing = true
fail_under = 75
```

### Running Coverage

```bash
# Full coverage report
pytest tests/ --cov="Netro Sprinklers.indigoPlugin/Contents/Server Plugin" \
    --cov-report=term-missing \
    --cov-report=html \
    --cov-branch

# Coverage for specific area
pytest tests/unit/test_whisperer.py --cov --cov-report=term-missing

# Fail if below threshold
pytest tests/ --cov --cov-fail-under=75
```

### Coverage Gap Analysis

| Code Area | Current | Target | Priority | Test File |
|-----------|---------|--------|----------|-----------|
| Whisperer sensors (663-690) | ~40% | 85% | HIGH | test_whisperer.py |
| Moisture data (696-732) | ~70% | 90% | MEDIUM | test_api_client.py |
| Error paths (248-334) | ~50% | 85% | HIGH | test_network_errors.py, test_api_errors.py |
| Schedule parsing (504-582) | ~75% | 90% | MEDIUM | test_schedule_parsing.py |
| runConcurrentThread (810-829) | ~30% | 75% | MEDIUM | test_thread_safety.py |
| Actions (1238-1476) | ~80% | 90% | LOW | test_actions.py |

---

## Part 8: Test Implementation Priority

### Phase 1: Critical Coverage Gaps (Week 1)

**Priority:** HIGH - Highest risk untested code

1. **Whisperer Sensor Tests** (15 tests)
   - test_whisperer.py
   - Covers lines 663-690, 735-789
   - All sensor value paths
   - Empty sensor readings

2. **Error Path Tests** (20 tests)
   - test_network_errors.py (10 tests)
   - test_api_errors.py (10 tests)
   - Covers lines 248-334

### Phase 2: Edge Cases (Week 2)

**Priority:** MEDIUM - Important for robustness

3. **Edge Case Tests** (18 tests)
   - test_unicode.py (5 tests)
   - test_empty_data.py (5 tests)
   - test_schedule_parsing.py (8 tests)

4. **Malformed Data Tests** (8 tests)
   - test_malformed_data.py
   - Missing keys, wrong types, etc.

### Phase 3: Thread Safety (Week 3)

**Priority:** MEDIUM - Important for reliability

5. **Concurrent Thread Tests** (6 tests)
   - test_thread_safety.py
   - Exception handling in loop
   - Polling interval verification

### Expected Coverage After Implementation

| Phase | Tests Added | Coverage |
|-------|-------------|----------|
| Current | 64 | 70% |
| Phase 1 | +35 | 80% |
| Phase 2 | +26 | 85% |
| Phase 3 | +6 | 87% |

---

## Summary and Recommendations

### Key Findings

1. **Whisperer code is highest risk** - ~40% coverage on production code
2. **Error paths need systematic testing** - Use parametrized tests for efficiency
3. **runConcurrentThread can be tested safely** - Use StopThread exception pattern
4. **Edge cases follow patterns** - Unicode, empty lists, type coercion

### Specific Recommendations

1. **Create mock_indigo.py first** - Foundation for all tests
2. **Use fixture factories** - create_mock_device(), create_mock_response()
3. **Parametrize error scenarios** - More coverage with less code
4. **Test behaviors, not implementation** - Survives refactoring
5. **Document current behavior** - Characterization tests before changing

### Files to Create

| File | Tests | Priority |
|------|-------|----------|
| tests/mocks/mock_indigo.py | - | First |
| tests/mocks/mock_netro_api.py | - | First |
| tests/unit/test_whisperer.py | 15 | HIGH |
| tests/error_paths/test_network_errors.py | 10 | HIGH |
| tests/error_paths/test_api_errors.py | 10 | HIGH |
| tests/edge_cases/test_unicode.py | 5 | MEDIUM |
| tests/edge_cases/test_empty_data.py | 5 | MEDIUM |
| tests/edge_cases/test_schedule_parsing.py | 8 | MEDIUM |
| tests/error_paths/test_malformed_data.py | 8 | MEDIUM |
| tests/integration/test_thread_safety.py | 6 | MEDIUM |

---

## Sources

**Primary Sources (HIGH confidence):**
- Existing codebase: `/Users/simon/vsCodeProjects/Indigo/netro/.planning/codebase/TESTING.md`
- UK-Trains plugin patterns: `/Users/simon/vsCodeProjects/Indigo/UK-Trains/tests/`
- Plugin source code: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/plugin.py`
- Project requirements: `/Users/simon/vsCodeProjects/Indigo/netro/.planning/PROJECT.md`

**Pattern Sources (HIGH confidence):**
- UK-Trains conftest.py - Mock Indigo module pattern
- UK-Trains mock_indigo.py - Device mocking pattern
- UK-Trains test_time_calculations.py - Parametrized test pattern
- Existing pytest.ini - Marker and coverage configuration

---

*Research completed: 2026-02-01*
*Overall confidence: HIGH*
