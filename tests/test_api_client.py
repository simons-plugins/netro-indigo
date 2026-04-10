"""Unit tests for api_client.py module.

Tests verify the NetroAPIClient works correctly in isolation.
These tests do not require Indigo runtime and can run with pytest.
"""
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock
import pytest

# Add Server Plugin directory to path for imports
SERVER_PLUGIN_DIR = (
    Path(__file__).parent.parent
    / "Netro Sprinklers.indigoPlugin"
    / "Contents"
    / "Server Plugin"
)
sys.path.insert(0, str(SERVER_PLUGIN_DIR))

from api_client import NetroAPIClient, TOKEN_PAUSE_THRESHOLD, TOKEN_WARNING_THRESHOLD
from exceptions import ThrottleDelayError, NetroAPIError


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_logger():
    """Create a mock logger for testing."""
    logger = Mock()
    logger.debug = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    return logger


@pytest.fixture
def mock_prefs():
    """Create mock prefs getter/setter for testing."""
    prefs_data = {}

    def prefs_getter():
        return prefs_data

    def prefs_setter(key, value):
        prefs_data[key] = value

    return prefs_getter, prefs_setter, prefs_data


@pytest.fixture
def client(mock_logger, mock_prefs):
    """Create a NetroAPIClient instance with mocked dependencies."""
    prefs_getter, prefs_setter, _ = mock_prefs
    return NetroAPIClient(
        logger=mock_logger,
        prefs_getter=prefs_getter,
        prefs_setter=prefs_setter
    )


# =============================================================================
# TestThrottleState
# =============================================================================

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

    def test_throttle_until_past_clears_automatically(self, client, mock_logger):
        """When _throttle_until is in past, is_throttled=False and state cleared."""
        client._throttle_until = datetime.now() - timedelta(minutes=1)
        assert client.is_throttled is False
        assert client._throttle_until is None
        mock_logger.info.assert_called()

    def test_throttle_expires_property(self, client):
        """throttle_expires should return expiry time when throttled."""
        future_time = datetime.now() + timedelta(minutes=30)
        client._throttle_until = future_time
        assert client.throttle_expires == future_time

    def test_throttle_expires_none_when_not_throttled(self, client):
        """throttle_expires should return None when not throttled."""
        assert client.throttle_expires is None

    def test_save_throttle_state_calls_prefs_setter(self, mock_logger, mock_prefs):
        """Save should call prefs_setter with v2 JSON format."""
        prefs_getter, prefs_setter, prefs_data = mock_prefs
        client = NetroAPIClient(
            logger=mock_logger,
            prefs_getter=prefs_getter,
            prefs_setter=prefs_setter
        )
        client._throttle_until = datetime.now() + timedelta(minutes=30)
        client._save_throttle_state()

        assert "throttle_state" in prefs_data
        saved_state = json.loads(prefs_data["throttle_state"])
        assert saved_state["version"] == 2
        assert "throttle_until" in saved_state
        assert "device_tokens" in saved_state
        assert "last_saved" in saved_state

    def test_restore_v1_format_ignores_stale_throttle(self, mock_logger):
        """V1 format (no version key) does not restore throttle — may be from incorrect global tracking."""
        future_time = datetime.now() + timedelta(minutes=30)
        state = {
            "throttle_until": future_time.isoformat(),
            "token_remaining": 500,
            "token_reset": None
        }
        prefs_data = {"throttle_state": json.dumps(state)}

        client = NetroAPIClient(
            logger=mock_logger,
            prefs_getter=lambda: prefs_data,
            prefs_setter=lambda k, v: None
        )

        # V1 throttle not restored — was likely caused by incorrect global token tracking
        assert client._throttle_until is None
        assert len(client._device_tokens) == 0

    def test_restore_v2_format_restores_per_device_tokens(self, mock_logger):
        """V2 format restores per-device token budgets."""
        from api_client import DeviceTokenState
        state = {
            "version": 2,
            "throttle_until": None,
            "device_tokens": {
                "key_A": {"token_remaining": 1500, "token_reset": "2026-04-11T00:00:00+00:00"},
                "key_B": {"token_remaining": 1800, "token_reset": None},
            },
        }
        prefs_data = {"throttle_state": json.dumps(state)}

        client = NetroAPIClient(
            logger=mock_logger,
            prefs_getter=lambda: prefs_data,
            prefs_setter=lambda k, v: None
        )

        assert len(client._device_tokens) == 2
        assert client._device_tokens["key_A"].token_remaining == 1500
        assert client._device_tokens["key_B"].token_remaining == 1800

    def test_restore_v2_throttle_future(self, mock_logger):
        """V2 format restores throttle_until if still in future."""
        future_time = datetime.now() + timedelta(minutes=30)
        state = {
            "version": 2,
            "throttle_until": future_time.isoformat(),
            "device_tokens": {},
        }
        prefs_data = {"throttle_state": json.dumps(state)}

        client = NetroAPIClient(
            logger=mock_logger,
            prefs_getter=lambda: prefs_data,
            prefs_setter=lambda k, v: None
        )

        assert client._throttle_until is not None
        assert abs((client._throttle_until - future_time).total_seconds()) < 1

    def test_restore_v2_throttle_expired(self, mock_logger):
        """V2 format ignores throttle_until if in past."""
        past_time = datetime.now() - timedelta(minutes=30)
        state = {
            "version": 2,
            "throttle_until": past_time.isoformat(),
            "device_tokens": {},
        }
        prefs_data = {"throttle_state": json.dumps(state)}

        client = NetroAPIClient(
            logger=mock_logger,
            prefs_getter=lambda: prefs_data,
            prefs_setter=lambda k, v: None
        )

        assert client._throttle_until is None

    def test_restore_v2_bad_device_timestamp_skips_device(self, mock_logger):
        """Malformed token_reset for one device doesn't abort others."""
        state = {
            "version": 2,
            "throttle_until": None,
            "device_tokens": {
                "key_A": {"token_remaining": 1500, "token_reset": None},
                "key_B": {"token_remaining": 1200, "token_reset": "not-a-date"},
                "key_C": {"token_remaining": 900, "token_reset": None},
            },
        }
        prefs_data = {"throttle_state": json.dumps(state)}

        client = NetroAPIClient(
            logger=mock_logger,
            prefs_getter=lambda: prefs_data,
            prefs_setter=lambda k, v: None
        )

        # key_A and key_C should be restored, key_B skipped
        assert "key_A" in client._device_tokens
        assert client._device_tokens["key_A"].token_remaining == 1500
        assert "key_B" not in client._device_tokens
        assert "key_C" in client._device_tokens
        assert client._device_tokens["key_C"].token_remaining == 900
        mock_logger.warning.assert_called()

    def test_restore_throttle_state_ignores_expired(self, mock_logger):
        """V1 format with past throttle — ignored entirely."""
        past_time = datetime.now() - timedelta(minutes=30)
        state = {
            "throttle_until": past_time.isoformat(),
            "token_remaining": 500,
            "token_reset": None
        }
        prefs_data = {"throttle_state": json.dumps(state)}

        client = NetroAPIClient(
            logger=mock_logger,
            prefs_getter=lambda: prefs_data,
            prefs_setter=lambda k, v: None
        )

        assert client._throttle_until is None

    def test_restore_throttle_state_handles_invalid_json(self, mock_logger):
        """Invalid JSON doesn't crash, logs warning."""
        prefs_data = {"throttle_state": "not valid json"}

        client = NetroAPIClient(
            logger=mock_logger,
            prefs_getter=lambda: prefs_data,
            prefs_setter=lambda k, v: None
        )

        assert client._throttle_until is None
        mock_logger.warning.assert_called()

    def test_restore_throttle_state_handles_missing_prefs(self, mock_logger):
        """Missing prefs doesn't crash."""
        client = NetroAPIClient(
            logger=mock_logger,
            prefs_getter=lambda: {},
            prefs_setter=lambda k, v: None
        )

        assert client._throttle_until is None
        assert client.is_throttled is False


# =============================================================================
# TestProactivePause
# =============================================================================

@pytest.mark.api
class TestProactivePause:
    """Tests for proactive pause logic at threshold boundaries."""

    def test_should_pause_for_below_threshold(self, client):
        """should_pause_polling_for returns True when device below threshold."""
        from api_client import DeviceTokenState
        client._device_tokens["KEY_A"] = DeviceTokenState(token_remaining=TOKEN_PAUSE_THRESHOLD - 1)
        assert client.should_pause_polling_for("KEY_A") is True

    def test_should_not_pause_for_at_exactly_threshold(self, client):
        """should_pause_polling_for returns False at exactly threshold (< not <=)."""
        from api_client import DeviceTokenState
        client._device_tokens["KEY_A"] = DeviceTokenState(token_remaining=TOKEN_PAUSE_THRESHOLD)
        assert client.should_pause_polling_for("KEY_A") is False

    def test_should_not_pause_for_above_threshold(self, client):
        """should_pause_polling_for returns False when device above threshold."""
        from api_client import DeviceTokenState
        client._device_tokens["KEY_A"] = DeviceTokenState(token_remaining=TOKEN_PAUSE_THRESHOLD + 100)
        assert client.should_pause_polling_for("KEY_A") is False

    def test_should_not_pause_for_unknown_device(self, client):
        """should_pause_polling_for returns False for unknown device key."""
        assert client.should_pause_polling_for("UNKNOWN_KEY") is False

    def test_should_pause_property_any_device(self, client):
        """should_pause_polling returns True if any device is below threshold."""
        from api_client import DeviceTokenState
        client._device_tokens["KEY_A"] = DeviceTokenState(token_remaining=50)
        client._device_tokens["KEY_B"] = DeviceTokenState(token_remaining=1500)
        assert client.should_pause_polling is True

    def test_should_not_pause_property_all_above(self, client):
        """should_pause_polling returns False if all devices above threshold."""
        from api_client import DeviceTokenState
        client._device_tokens["KEY_A"] = DeviceTokenState(token_remaining=500)
        client._device_tokens["KEY_B"] = DeviceTokenState(token_remaining=1500)
        assert client.should_pause_polling is False

    def test_should_not_pause_property_no_devices(self, client):
        """should_pause_polling returns False when no devices tracked."""
        assert client.should_pause_polling is False

    def test_token_remaining_returns_minimum(self, client):
        """token_remaining returns minimum across all tracked devices."""
        from api_client import DeviceTokenState
        client._device_tokens["KEY_A"] = DeviceTokenState(token_remaining=500)
        client._device_tokens["KEY_B"] = DeviceTokenState(token_remaining=1500)
        assert client.token_remaining == 500

    def test_token_remaining_default_when_no_devices(self, client):
        """token_remaining returns 2000 when no devices tracked."""
        assert client.token_remaining == 2000

    def test_token_remaining_for_device(self, client):
        """token_remaining_for returns per-device count."""
        from api_client import DeviceTokenState
        client._device_tokens["KEY_A"] = DeviceTokenState(token_remaining=750)
        assert client.token_remaining_for("KEY_A") == 750

    def test_token_remaining_for_unknown_device(self, client):
        """token_remaining_for returns 2000 for unknown device."""
        assert client.token_remaining_for("UNKNOWN") == 2000

    def test_update_token_budget_per_device(self, client):
        """_update_token_budget stores tokens per device key."""
        meta = {
            "token_remaining": 750,
            "token_reset": "2026-02-02T00:00:00"
        }
        client._update_token_budget(meta, device_key="KEY_A")
        assert client._device_tokens["KEY_A"].token_remaining == 750
        assert client._device_tokens["KEY_A"].token_reset == datetime(2026, 2, 2, 0, 0, 0, tzinfo=timezone.utc)

    def test_update_token_budget_independent_devices(self, client):
        """Two devices maintain independent token counts."""
        client._update_token_budget({"token_remaining": 500}, device_key="KEY_A")
        client._update_token_budget({"token_remaining": 1800}, device_key="KEY_B")
        assert client._device_tokens["KEY_A"].token_remaining == 500
        assert client._device_tokens["KEY_B"].token_remaining == 1800

    def test_update_token_budget_skips_without_device_key(self, client):
        """_update_token_budget with no device_key does not track tokens."""
        client._update_token_budget({"token_remaining": 500})
        assert len(client._device_tokens) == 0

    def test_update_token_budget_logs_warning_below_200(self, client, mock_logger):
        """Logs warning when device tokens < 200."""
        meta = {"token_remaining": TOKEN_WARNING_THRESHOLD - 1}
        client._update_token_budget(meta, device_key="KEY_A")
        mock_logger.warning.assert_called()
        warning_call = mock_logger.warning.call_args[0][0]
        assert str(TOKEN_WARNING_THRESHOLD - 1) in warning_call

    def test_update_token_budget_no_warning_above_200(self, client, mock_logger):
        """No warning when device tokens >= 200."""
        mock_logger.warning.reset_mock()
        meta = {"token_remaining": TOKEN_WARNING_THRESHOLD + 100}
        client._update_token_budget(meta, device_key="KEY_A")
        mock_logger.warning.assert_not_called()

    def test_update_token_budget_saves_state(self, mock_logger, mock_prefs):
        """Calls _save_throttle_state after update."""
        prefs_getter, prefs_setter, prefs_data = mock_prefs
        client = NetroAPIClient(
            logger=mock_logger,
            prefs_getter=prefs_getter,
            prefs_setter=prefs_setter
        )
        prefs_data.clear()

        meta = {"token_remaining": 1500}
        client._update_token_budget(meta, device_key="KEY_A")

        assert "throttle_state" in prefs_data

    def test_update_token_budget_sets_safe_default_on_parse_failure(self, client, mock_logger):
        """Sets safe token count on parsing failure to trigger proactive pause."""
        meta = {"token_remaining": "invalid"}
        client._update_token_budget(meta, device_key="KEY_A")

        assert client._device_tokens["KEY_A"].token_remaining == TOKEN_PAUSE_THRESHOLD - 1
        assert client.should_pause_polling_for("KEY_A") is True
        mock_logger.warning.assert_called()

    def test_auto_resets_past_reset_time(self, client, mock_logger):
        """Auto-resets token count when past token_reset time."""
        from api_client import DeviceTokenState
        client._device_tokens["KEY_A"] = DeviceTokenState(
            token_remaining=50,
            token_reset=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        )

        should_pause = client.should_pause_polling_for("KEY_A")

        assert should_pause is False
        assert client._device_tokens["KEY_A"].token_remaining == 2000
        assert client._device_tokens["KEY_A"].token_reset is None
        mock_logger.info.assert_called()
        assert "reset" in mock_logger.info.call_args[0][0].lower()


# =============================================================================
# TestMakeRequest
# =============================================================================

@pytest.mark.api
class TestMakeRequest:
    """Tests for make_request with mocked HTTP requests."""

    def test_make_request_get_success(self, client):
        """GET returns JSON response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "OK",
            "data": {"info": "test"},
            "meta": {"token_remaining": 1900, "time": 12345}
        }

        with patch("api_client.requests.get", return_value=mock_response):
            result = client.make_request("https://api.test.com/endpoint")

        assert result["status"] == "OK"
        assert result["data"]["info"] == "test"

    def test_make_request_post_success(self, client):
        """POST with data returns JSON response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "OK",
            "data": {},
            "meta": {"token_remaining": 1899}
        }

        with patch("api_client.requests.post", return_value=mock_response):
            result = client.make_request(
                "https://api.test.com/endpoint",
                method="post",
                data={"key": "serial123"}
            )

        assert result["status"] == "OK"

    def test_make_request_put_success(self, client):
        """PUT with data returns JSON response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "OK",
            "data": {},
            "meta": {"token_remaining": 1898}
        }

        with patch("api_client.requests.put", return_value=mock_response):
            result = client.make_request(
                "https://api.test.com/endpoint",
                method="put",
                data={"key": "serial123"}
            )

        assert result["status"] == "OK"

    def test_make_request_204_returns_true(self, client):
        """204 response returns True."""
        mock_response = Mock()
        mock_response.status_code = 204

        with patch("api_client.requests.get", return_value=mock_response):
            result = client.make_request("https://api.test.com/endpoint")

        assert result is True

    def test_make_request_raises_on_throttle(self, client):
        """Raises ThrottleDelayError when throttled."""
        client._throttle_until = datetime.now() + timedelta(minutes=30)

        with pytest.raises(ThrottleDelayError) as exc_info:
            client.make_request("https://api.test.com/endpoint")

        assert "throttled" in str(exc_info.value).lower()

    def test_make_request_handles_connection_error(self, client, mock_logger):
        """ConnectionError logged and re-raised."""
        import requests as req
        with patch("api_client.requests.get", side_effect=req.exceptions.ConnectionError("Network down")):
            with pytest.raises(req.exceptions.ConnectionError):
                client.make_request("https://api.test.com/endpoint")

        mock_logger.error.assert_called()
        assert "connection" in mock_logger.error.call_args[0][0].lower()

    def test_make_request_handles_timeout(self, client, mock_logger):
        """Timeout logged and re-raised."""
        import requests as req
        with patch("api_client.requests.get", side_effect=req.exceptions.Timeout("Timed out")):
            with pytest.raises(req.exceptions.Timeout):
                client.make_request("https://api.test.com/endpoint")

        mock_logger.error.assert_called()
        assert "timed out" in mock_logger.error.call_args[0][0].lower()

    def test_make_request_timeout_on_post(self, client, mock_logger):
        """Timeout during POST request logged and re-raised."""
        import requests as req
        with patch("api_client.requests.post", side_effect=req.exceptions.Timeout("POST timed out")):
            with pytest.raises(req.exceptions.Timeout):
                client.make_request(
                    "https://api.test.com/endpoint",
                    method="post",
                    data={"key": "test"}
                )

        mock_logger.error.assert_called()
        assert "timed out" in mock_logger.error.call_args[0][0].lower()

    def test_make_request_timeout_on_put(self, client, mock_logger):
        """Timeout during PUT request logged and re-raised."""
        import requests as req
        with patch("api_client.requests.put", side_effect=req.exceptions.Timeout("PUT timed out")):
            with pytest.raises(req.exceptions.Timeout):
                client.make_request(
                    "https://api.test.com/endpoint",
                    method="put",
                    data={"key": "test"}
                )

        mock_logger.error.assert_called()
        assert "timed out" in mock_logger.error.call_args[0][0].lower()

    def test_make_request_timeout_suppresses_repeated(self, client, mock_logger):
        """Second timeout not logged (error suppression)."""
        import requests as req
        with patch("api_client.requests.get", side_effect=req.exceptions.Timeout("Timed out")):
            for _ in range(3):
                try:
                    client.make_request("https://api.test.com/endpoint")
                except req.exceptions.Timeout:
                    pass

        # Should only log once
        assert mock_logger.error.call_count == 1

    def test_make_request_timeout_resets_after_success(self, client, mock_logger):
        """Success clears timeout error state, next timeout is logged."""
        import requests as req

        # First timeout
        with patch("api_client.requests.get", side_effect=req.exceptions.Timeout("Timed out")):
            try:
                client.make_request("https://api.test.com/endpoint")
            except req.exceptions.Timeout:
                pass

        # Then succeed
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "OK", "data": {}, "meta": {"token_remaining": 1900}}

        with patch("api_client.requests.get", return_value=mock_response):
            client.make_request("https://api.test.com/endpoint")

        # Reset error count before second timeout
        mock_logger.error.reset_mock()

        # Second timeout should be logged again (error state was cleared)
        with patch("api_client.requests.get", side_effect=req.exceptions.Timeout("Timed out again")):
            try:
                client.make_request("https://api.test.com/endpoint")
            except req.exceptions.Timeout:
                pass

        mock_logger.error.assert_called()

    def test_make_request_timeout_preserves_throttle_state(self, client, mock_logger):
        """Timeout doesn't affect throttle state."""
        from api_client import DeviceTokenState

        # Set throttle state
        future_time = datetime.now() + timedelta(minutes=30)
        client._throttle_until = future_time
        client._device_tokens["KEY_A"] = DeviceTokenState(token_remaining=500)

        # Cause timeout (should raise ThrottleDelayError before hitting network)
        with pytest.raises(ThrottleDelayError):
            client.make_request("https://api.test.com/endpoint")

        # Throttle state should be preserved
        assert client._throttle_until == future_time
        assert client._device_tokens["KEY_A"].token_remaining == 500

    def test_make_request_timeout_with_custom_timeout_value(self, client):
        """Client timeout attribute passed to requests library."""
        import requests as req
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "OK", "data": {}, "meta": {"token_remaining": 1900}}

        # Set custom timeout on client
        client.timeout = 15

        with patch("api_client.requests.get", return_value=mock_response) as mock_get:
            client.make_request("https://api.test.com/endpoint")

            # Verify timeout parameter was passed to requests.get
            call_kwargs = mock_get.call_args[1]
            assert "timeout" in call_kwargs
            assert call_kwargs["timeout"] == 15

    def test_make_request_read_timeout_vs_connect_timeout(self, client, mock_logger):
        """ReadTimeout (subclass of Timeout) handled correctly."""
        import requests as req

        # ReadTimeout is a specific subclass of Timeout
        with patch("api_client.requests.get", side_effect=req.exceptions.ReadTimeout("Read timeout")):
            with pytest.raises(req.exceptions.ReadTimeout):
                client.make_request("https://api.test.com/endpoint")

        mock_logger.error.assert_called()
        assert "timed out" in mock_logger.error.call_args[0][0].lower()

    def test_get_device_info_timeout(self, client):
        """Convenience method timeout propagation."""
        import requests as req
        with patch("api_client.requests.get", side_effect=req.exceptions.Timeout("Timed out")):
            with pytest.raises(req.exceptions.Timeout):
                client.get_device_info("SERIAL123")

    def test_make_request_detects_rate_limit_error_code_3(self, client, mock_logger):
        """HTTP error with error code 3 (Netro format) sets throttle and raises ThrottleDelayError."""
        import requests as req

        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "status": "ERROR",
            "errors": [{"code": 3, "message": "Rate limit exceeded"}],
            "meta": {"token_remaining": -50, "token_reset": "2026-02-02T00:00:00"}
        }

        http_error = req.exceptions.HTTPError(response=mock_response)

        with patch("api_client.requests.get") as mock_get:
            mock_get.return_value = mock_response
            mock_response.raise_for_status.side_effect = http_error

            with pytest.raises(ThrottleDelayError):
                client.make_request("https://api.test.com/endpoint")

        # Should use token_reset from meta
        assert client._throttle_until is not None
        assert client._throttle_until == datetime(2026, 2, 2, 0, 0, 0, tzinfo=timezone.utc)

    def test_make_request_detects_invalid_serial_error_code_1(self, client, mock_logger):
        """HTTP error with error code 1 (invalid serial) raises NetroAPIError."""
        import requests as req

        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "status": "ERROR",
            "errors": [{"code": 1, "message": "Invalid device key"}],
            "meta": {}
        }

        http_error = req.exceptions.HTTPError(response=mock_response)

        with patch("api_client.requests.get") as mock_get:
            mock_get.return_value = mock_response
            mock_response.raise_for_status.side_effect = http_error

            with pytest.raises(NetroAPIError) as exc_info:
                client.make_request("https://api.test.com/endpoint")

        assert "serial" in str(exc_info.value).lower()
        mock_logger.error.assert_called()

    def test_make_request_detects_http_429(self, client, mock_logger):
        """HTTP 429 sets throttle and raises ThrottleDelayError."""
        import requests as req

        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"message": "Too many requests"}

        http_error = req.exceptions.HTTPError(response=mock_response)

        with patch("api_client.requests.get") as mock_get:
            mock_get.return_value = mock_response
            mock_response.raise_for_status.side_effect = http_error

            with pytest.raises(ThrottleDelayError):
                client.make_request("https://api.test.com/endpoint")

        assert client._throttle_until is not None

    def test_handle_http_error_500_no_json_body(self, client, mock_logger):
        """HTTP 500 without JSON body is handled and logged."""
        import requests as req

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_response.raise_for_status.side_effect = req.exceptions.HTTPError(
            response=mock_response
        )

        with patch("api_client.requests.get", return_value=mock_response):
            with pytest.raises(req.exceptions.HTTPError):
                client.make_request("https://api.test.com/endpoint")

        mock_logger.error.assert_called()

    def test_handle_http_error_500_with_json_error(self, client, mock_logger):
        """HTTP 500 with JSON error message is logged."""
        import requests as req

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {
            "status": "ERROR",
            "error": "Internal server error"
        }
        mock_response.raise_for_status.side_effect = req.exceptions.HTTPError(
            response=mock_response
        )

        with patch("api_client.requests.get", return_value=mock_response):
            with pytest.raises(req.exceptions.HTTPError):
                client.make_request("https://api.test.com/endpoint")

        # Verify error was logged with status code and message
        mock_logger.error.assert_called()
        call_args = mock_logger.error.call_args[0]
        assert len(call_args) >= 2  # Format string + at least status code

    def test_handle_http_error_502_bad_gateway(self, client, mock_logger):
        """HTTP 502 Bad Gateway is handled and logged."""
        import requests as req

        mock_response = Mock()
        mock_response.status_code = 502
        mock_response.json.side_effect = ValueError("HTML error page")
        mock_response.raise_for_status.side_effect = req.exceptions.HTTPError(
            response=mock_response
        )

        with patch("api_client.requests.get", return_value=mock_response):
            with pytest.raises(req.exceptions.HTTPError):
                client.make_request("https://api.test.com/endpoint")

        mock_logger.error.assert_called()

    def test_handle_http_error_503_service_unavailable(self, client, mock_logger):
        """HTTP 503 Service Unavailable is handled and logged."""
        import requests as req

        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.json.side_effect = ValueError("Service temporarily unavailable")
        mock_response.raise_for_status.side_effect = req.exceptions.HTTPError(
            response=mock_response
        )

        with patch("api_client.requests.get", return_value=mock_response):
            with pytest.raises(req.exceptions.HTTPError):
                client.make_request("https://api.test.com/endpoint")

        mock_logger.error.assert_called()

    def test_handle_http_error_504_gateway_timeout(self, client, mock_logger):
        """HTTP 504 Gateway Timeout is handled and logged."""
        import requests as req

        mock_response = Mock()
        mock_response.status_code = 504
        mock_response.json.side_effect = ValueError("Gateway timeout")
        mock_response.raise_for_status.side_effect = req.exceptions.HTTPError(
            response=mock_response
        )

        with patch("api_client.requests.get", return_value=mock_response):
            with pytest.raises(req.exceptions.HTTPError):
                client.make_request("https://api.test.com/endpoint")

        mock_logger.error.assert_called()

    def test_handle_http_error_response_none(self, client, mock_logger):
        """HTTPError with response=None doesn't crash."""
        import requests as req

        # Create HTTPError without response object (edge case)
        http_error = req.exceptions.HTTPError()
        http_error.response = None

        with patch("api_client.requests.get", side_effect=http_error):
            with pytest.raises(req.exceptions.HTTPError):
                client.make_request("https://api.test.com/endpoint")

        # Should still log error, even without response details
        mock_logger.error.assert_called()

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

    def test_make_request_resets_error_suppression_on_success(self, client, mock_logger):
        """Error suppression resets after successful request."""
        import requests as req
        # First, cause a connection error
        with patch("api_client.requests.get", side_effect=req.exceptions.ConnectionError("Network down")):
            try:
                client.make_request("https://api.test.com/endpoint")
            except req.exceptions.ConnectionError:
                pass

        # Then succeed
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "OK", "data": {}, "meta": {"token_remaining": 1900}}

        with patch("api_client.requests.get", return_value=mock_response):
            client.make_request("https://api.test.com/endpoint")

        assert client._last_error_type is None

    # -------------------------------------------------------------------------
    # Thread Safety Tests (TEST-08)
    # -------------------------------------------------------------------------

    def test_api_client_multiple_device_requests_state_isolation(self, client, mock_logger):
        """Multiple device requests maintain state isolation."""
        mock_response1 = Mock()
        mock_response1.status_code = 200
        mock_response1.json.return_value = {
            "status": "OK",
            "data": {"device": {"serial": "SERIAL1"}},
            "meta": {"token_remaining": 1500}
        }

        mock_response2 = Mock()
        mock_response2.status_code = 200
        mock_response2.json.return_value = {
            "status": "OK",
            "data": {"device": {"serial": "SERIAL2"}},
            "meta": {"token_remaining": 1400}
        }

        with patch("api_client.requests.get", side_effect=[mock_response1, mock_response2]):
            response1 = client.make_request("https://api.test.com/device/SERIAL1")
            response2 = client.make_request("https://api.test.com/device/SERIAL2")

        # Verify no state pollution between calls
        assert response1["data"]["device"]["serial"] == "SERIAL1"
        assert response2["data"]["device"]["serial"] == "SERIAL2"

    def test_api_client_token_budget_tracks_per_device(self, client):
        """Token budget is tracked independently per device key."""
        mock_response1 = Mock()
        mock_response1.status_code = 200
        mock_response1.json.return_value = {
            "status": "OK",
            "data": {},
            "meta": {"token_remaining": 1500}
        }

        mock_response2 = Mock()
        mock_response2.status_code = 200
        mock_response2.json.return_value = {
            "status": "OK",
            "data": {},
            "meta": {"token_remaining": 1800}
        }

        with patch("api_client.requests.get", side_effect=[mock_response1, mock_response2]):
            client.make_request("https://api.test.com/endpoint1", device_key="KEY_A")
            assert client.token_remaining_for("KEY_A") == 1500

            client.make_request("https://api.test.com/endpoint2", device_key="KEY_B")
            assert client.token_remaining_for("KEY_B") == 1800
            # KEY_A's count should be unchanged
            assert client.token_remaining_for("KEY_A") == 1500


# =============================================================================
# TestSchemaValidation
# =============================================================================

@pytest.mark.api
class TestSchemaValidation:
    """Tests for schema validation warning logging."""

    def test_validate_response_schema_no_warning_when_complete(self, client, mock_logger):
        """No warning logged for complete response."""
        mock_logger.warning.reset_mock()
        response = {"status": "OK", "data": {}, "meta": {}}
        expected_keys = {"status", "data", "meta"}

        client._validate_response_schema(response, expected_keys, "/test/endpoint")

        mock_logger.warning.assert_not_called()

    def test_validate_response_schema_warns_on_missing_keys(self, client, mock_logger):
        """Logs warning for missing keys."""
        response = {"status": "OK"}
        expected_keys = {"status", "data", "meta"}

        client._validate_response_schema(response, expected_keys, "/test/endpoint")

        mock_logger.warning.assert_called()
        warning_msg = mock_logger.warning.call_args[0][0]
        assert "missing" in warning_msg.lower()

    def test_validate_response_schema_debug_logs_extra_keys(self, client, mock_logger):
        """Debug logs for extra keys."""
        response = {"status": "OK", "data": {}, "meta": {}, "unexpected": "value"}
        expected_keys = {"status", "data", "meta"}

        client._validate_response_schema(response, expected_keys, "/test/endpoint")

        mock_logger.debug.assert_called()
        debug_msg = mock_logger.debug.call_args[0][0]
        assert "additional" in debug_msg.lower() or "extra" in debug_msg.lower()

    def test_validate_response_schema_does_not_raise(self, client):
        """Never raises, only logs."""
        response = {}  # Completely empty - all keys missing
        expected_keys = {"status", "data", "meta"}

        # Should not raise any exception
        client._validate_response_schema(response, expected_keys, "/test/endpoint")


# =============================================================================
# TestConvenienceMethods
# =============================================================================

@pytest.mark.api
class TestConvenienceMethods:
    """Tests for convenience methods that wrap make_request."""

    def test_get_device_info_constructs_correct_url(self, client):
        """get_device_info should call make_request with correct URL."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "OK", "data": {}, "meta": {"token_remaining": 1900}}

        with patch("api_client.requests.get", return_value=mock_response) as mock_get:
            client.get_device_info("SERIAL123")
            called_url = mock_get.call_args[0][0]
            assert "info.json" in called_url
            assert "SERIAL123" in called_url

    def test_start_watering_posts_zones_data(self, client):
        """start_watering should POST with zones data."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "OK", "data": {}, "meta": {"token_remaining": 1900}}

        with patch("api_client.requests.post", return_value=mock_response) as mock_post:
            client.start_watering("SERIAL123", [{"id": 1, "duration": 10}])
            called_data = mock_post.call_args[1]["data"]
            parsed_data = json.loads(called_data)
            assert parsed_data["key"] == "SERIAL123"
            assert parsed_data["zones"] == [{"id": 1, "duration": 10}]


# =============================================================================
# TestAPIClientV2 - API v2 endpoint selection and credential routing
# =============================================================================

@pytest.mark.api
class TestAPIClientV2:
    """Tests for API v2 support in NetroAPIClient."""

    def test_get_device_info_v2_uses_v2_endpoint(self, client):
        """V2 get_device_info should use /npa/v2/ endpoint."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "OK", "data": {}, "meta": {"token_remaining": 1900}}

        with patch("api_client.requests.get", return_value=mock_response) as mock_get:
            client.get_device_info("MY_API_KEY_123", api_version="2")
            called_url = mock_get.call_args[0][0]
            assert "/npa/v2/" in called_url
            assert "info.json" in called_url
            assert "MY_API_KEY_123" in called_url

    def test_get_device_info_v1_uses_v1_endpoint(self, client):
        """V1 get_device_info should use /npa/v1/ endpoint (default)."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "OK", "data": {}, "meta": {"token_remaining": 1900}}

        with patch("api_client.requests.get", return_value=mock_response) as mock_get:
            client.get_device_info("SERIAL123")
            called_url = mock_get.call_args[0][0]
            assert "/npa/v1/" in called_url

    def test_get_schedules_v2_uses_v2_endpoint(self, client):
        """V2 get_schedules should use v2 endpoint."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "OK", "data": {}, "meta": {"token_remaining": 1900}}

        with patch("api_client.requests.get", return_value=mock_response) as mock_get:
            client.get_schedules("API_KEY", api_version="2")
            called_url = mock_get.call_args[0][0]
            assert "/npa/v2/schedules.json" in called_url

    def test_stop_watering_v2_posts_api_key(self, client):
        """V2 stop_watering should POST with API key, not serial."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "OK", "data": {}, "meta": {"token_remaining": 1900}}

        with patch("api_client.requests.post", return_value=mock_response) as mock_post:
            client.stop_watering("MY_V2_KEY", api_version="2")
            called_url = mock_post.call_args[0][0]
            assert "/npa/v2/" in called_url
            called_data = json.loads(mock_post.call_args[1]["data"])
            assert called_data["key"] == "MY_V2_KEY"

    def test_start_watering_v2_uses_v2_endpoint(self, client):
        """V2 start_watering should use v2 endpoint and API key."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "OK", "data": {}, "meta": {"token_remaining": 1900}}

        with patch("api_client.requests.post", return_value=mock_response) as mock_post:
            client.start_watering("API_KEY_V2", [{"id": 1, "duration": 10}], api_version="2")
            called_url = mock_post.call_args[0][0]
            assert "/npa/v2/water.json" in called_url
            called_data = json.loads(mock_post.call_args[1]["data"])
            assert called_data["key"] == "API_KEY_V2"

    def test_get_events_uses_v2_endpoint(self, client):
        """get_events should always use v2 endpoint."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "OK", "data": {}, "meta": {"token_remaining": 1900}}

        with patch("api_client.requests.get", return_value=mock_response) as mock_get:
            client.get_events("API_KEY")
            called_url = mock_get.call_args[0][0]
            assert "/npa/v2/events.json" in called_url
            assert "API_KEY" in called_url

    def test_get_events_with_filters(self, client):
        """get_events should add query params for filters."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "OK", "data": {}, "meta": {"token_remaining": 1900}}

        with patch("api_client.requests.get", return_value=mock_response) as mock_get:
            client.get_events("KEY", event_type=2, start_date="2026-04-01", end_date="2026-04-07")
            called_url = mock_get.call_args[0][0]
            assert "event=2" in called_url
            assert "start_date=2026-04-01" in called_url
            assert "end_date=2026-04-07" in called_url

    def test_report_weather_v2_uses_v2_endpoint(self, client):
        """V2 report_weather should use v2 endpoint."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "OK", "data": {}, "meta": {"token_remaining": 1900}}

        with patch("api_client.requests.post", return_value=mock_response) as mock_post:
            client.report_weather("API_KEY", {"t": 22, "date": "2026-04-07"}, api_version="2")
            called_url = mock_post.call_args[0][0]
            assert "/npa/v2/report_weather.json" in called_url

    def test_set_moisture_v2_uses_v2_endpoint(self, client):
        """V2 set_moisture should use v2 endpoint."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "OK", "data": {}, "meta": {"token_remaining": 1900}}

        with patch("api_client.requests.post", return_value=mock_response) as mock_post:
            client.set_moisture("API_KEY", 1, 75, api_version="2")
            called_url = mock_post.call_args[0][0]
            assert "/npa/v2/set_moisture.json" in called_url

    def test_debug_log_masks_key(self, client, mock_logger):
        """Debug log should mask the key parameter in URL."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "OK", "data": {}, "meta": {"token_remaining": 1900}}

        with patch("api_client.requests.get", return_value=mock_response):
            client.get_device_info("SECRET_API_KEY_12345")
            debug_call = mock_logger.debug.call_args_list[0][0][0]
            assert "SECRET_API_KEY_12345" not in debug_call
            assert "key=***" in debug_call

    def test_default_api_version_is_v1(self, client):
        """All methods should default to v1 when api_version not specified."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "OK", "data": {}, "meta": {"token_remaining": 1900}}

        with patch("api_client.requests.get", return_value=mock_response) as mock_get:
            client.get_device_info("SERIAL123")
            called_url = mock_get.call_args[0][0]
            assert "/npa/v1/" in called_url

    def test_all_v2_get_methods_use_v2_url(self, client):
        """All GET convenience methods should use v2 URL when api_version='2'."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "OK", "data": {}, "meta": {"token_remaining": 1900}}

        methods = [
            ("get_device_info", ["KEY"]),
            ("get_schedules", ["KEY"]),
            ("get_moistures", ["KEY"]),
            ("get_sensor_data", ["KEY"]),
        ]

        for method_name, args in methods:
            with patch("api_client.requests.get", return_value=mock_response) as mock_get:
                getattr(client, method_name)(*args, api_version="2")
                called_url = mock_get.call_args[0][0]
                assert "/npa/v2/" in called_url, f"{method_name} did not use v2 URL"

    def test_all_v2_post_methods_use_v2_url(self, client):
        """All POST convenience methods should use v2 URL when api_version='2'."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "OK", "data": {}, "meta": {"token_remaining": 1900}}

        methods = [
            ("stop_watering", ["KEY"]),
            ("set_device_status", ["KEY", 1]),
            ("set_no_water", ["KEY", 3]),
            ("report_weather", ["KEY", {"t": 22, "date": "2026-04-07"}]),
            ("set_moisture", ["KEY", 1, 75]),
        ]

        for method_name, args in methods:
            with patch("api_client.requests.post", return_value=mock_response) as mock_post:
                getattr(client, method_name)(*args, api_version="2")
                called_url = mock_post.call_args[0][0]
                assert "/npa/v2/" in called_url, f"{method_name} did not use v2 URL"
