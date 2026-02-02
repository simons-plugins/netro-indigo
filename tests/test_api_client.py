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
        """Save should call prefs_setter with JSON."""
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
        assert "throttle_until" in saved_state
        assert "token_remaining" in saved_state
        assert "last_saved" in saved_state

    def test_restore_throttle_state_from_valid_prefs(self, mock_logger):
        """Restore should parse JSON and set state."""
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

        assert client._token_remaining == 500
        assert client._throttle_until is not None
        # Check throttle is approximately correct (within 1 second)
        assert abs((client._throttle_until - future_time).total_seconds()) < 1

    def test_restore_throttle_state_ignores_expired(self, mock_logger):
        """Restore ignores throttle_until if in past."""
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
        assert client._token_remaining == 500

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

    def test_should_pause_when_below_threshold(self, client):
        """token_remaining < 100 returns True."""
        client._token_remaining = TOKEN_PAUSE_THRESHOLD - 1
        assert client.should_pause_polling is True

    def test_should_not_pause_when_above_threshold(self, client):
        """token_remaining > 100 returns False."""
        client._token_remaining = TOKEN_PAUSE_THRESHOLD + 100
        assert client.should_pause_polling is False

    def test_should_not_pause_at_exactly_threshold(self, client):
        """token_remaining == 100 returns False (boundary test)."""
        client._token_remaining = TOKEN_PAUSE_THRESHOLD
        assert client.should_pause_polling is False

    def test_token_remaining_property(self, client):
        """Verify property returns current count."""
        client._token_remaining = 1500
        assert client.token_remaining == 1500

    def test_update_token_budget_from_meta(self, client):
        """_update_token_budget parses meta correctly."""
        meta = {
            "token_remaining": 750,
            "token_reset": "2026-02-02T00:00:00"
        }
        client._update_token_budget(meta)
        assert client._token_remaining == 750
        assert client._token_reset == datetime(2026, 2, 2, 0, 0, 0, tzinfo=timezone.utc)

    def test_update_token_budget_logs_warning_below_200(self, client, mock_logger):
        """Logs warning when tokens < 200."""
        meta = {"token_remaining": TOKEN_WARNING_THRESHOLD - 1}
        client._update_token_budget(meta)
        mock_logger.warning.assert_called()
        # Verify warning contains token info
        warning_call = mock_logger.warning.call_args[0][0]
        assert "tokens" in warning_call.lower() or str(TOKEN_WARNING_THRESHOLD - 1) in warning_call

    def test_update_token_budget_no_warning_above_200(self, client, mock_logger):
        """No warning when tokens >= 200."""
        mock_logger.warning.reset_mock()
        meta = {"token_remaining": TOKEN_WARNING_THRESHOLD + 100}
        client._update_token_budget(meta)
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
        client._update_token_budget(meta)

        assert "throttle_state" in prefs_data

    def test_update_token_budget_sets_safe_default_on_parse_failure(self, client, mock_logger):
        """Sets safe token count on parsing failure to trigger proactive pause."""
        # Start with high token count
        client._token_remaining = 1500

        # Try to parse invalid token data
        meta = {"token_remaining": "invalid"}
        client._update_token_budget(meta)

        # Should set to safe default (below pause threshold)
        assert client._token_remaining == TOKEN_PAUSE_THRESHOLD - 1
        assert client.should_pause_polling is True
        mock_logger.warning.assert_called()

    def test_should_pause_polling_auto_resets_past_reset_time(self, client, mock_logger):
        """Auto-resets token count when past token_reset time to prevent self-locking."""
        # Set low tokens and a reset time in the past
        client._token_remaining = 50  # Below threshold
        client._token_reset = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)  # Past date

        # Check should_pause_polling - will auto-reset tokens since reset time passed
        should_pause = client.should_pause_polling

        # Tokens should be auto-reset to 2000 (not paused)
        assert should_pause is False
        assert client._token_remaining == 2000
        assert client._token_reset is None
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
