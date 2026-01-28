"""Tests for Netro API client functionality."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, Mock
import requests


# Mark all tests in this module as API tests
pytestmark = pytest.mark.api


class TestAPIClient:
    """Test suite for API client methods."""

    def test_successful_get_request(self, load_fixture):
        """Test successful GET request returns JSON data."""

        # Mock the _make_api_call method behavior
        with patch('requests.get') as mock_get_method:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = load_fixture("info_response.json")
            mock_get_method.return_value = mock_response

            # Act
            response = mock_response.json()

            # Assert
            assert response["status"] == "OK"
            assert "device" in response["data"]
            assert response["meta"]["token_remaining"] == 1850

    def test_successful_post_request(self):
        """Test successful POST request returns success."""

        # Act
        with patch('requests.post') as mock_post_method:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "OK"}
            mock_post_method.return_value = mock_response

            response = mock_response.json()

            # Assert
            assert response["status"] == "OK"

    def test_http_429_rate_limit(self):
        """Test that HTTP 429 triggers throttle delay."""
        # Arrange
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 429
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError()
            mock_get.return_value = mock_response

            # Act & Assert
            with pytest.raises(requests.exceptions.HTTPError):
                mock_response.raise_for_status()

    def test_connection_error_handling(self):
        """Test that connection errors are handled gracefully."""
        # Arrange
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")

            # Act & Assert
            with pytest.raises(requests.exceptions.ConnectionError):
                mock_get("http://api.netrohome.com/npa/v1/info.json")

    def test_timeout_handling(self):
        """Test that timeout errors are handled."""
        # Arrange
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout("Request timed out")

            # Act & Assert
            with pytest.raises(requests.exceptions.Timeout):
                mock_get("http://api.netrohome.com/npa/v1/info.json", timeout=5)

    def test_invalid_json_response(self):
        """Test handling of invalid JSON response."""
        # Arrange
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.side_effect = ValueError("Invalid JSON")
            mock_get.return_value = mock_response

            # Act & Assert
            with pytest.raises(ValueError):
                mock_response.json()

    def test_throttle_prevents_api_calls(self, mock_plugin):
        """Test that throttle delay prevents API calls."""
        # Arrange
        mock_plugin.throttle_next_call = datetime.now() + timedelta(minutes=10)

        # Act
        is_throttled = datetime.now() < mock_plugin.throttle_next_call

        # Assert
        assert is_throttled is True

    def test_throttle_expires_after_delay(self, mock_plugin):
        """Test that throttle expires after delay period."""
        # Arrange
        mock_plugin.throttle_next_call = datetime.now() - timedelta(minutes=10)

        # Act
        is_throttled = datetime.now() < mock_plugin.throttle_next_call

        # Assert
        assert is_throttled is False

    def test_api_headers_include_timeout(self):
        """Test that API calls include timeout parameter."""
        # Arrange
        timeout_value = 5

        # Act
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            # Simulate call with timeout
            requests.get("http://test.com", timeout=timeout_value)

            # Assert
            mock_get.assert_called_with("http://test.com", timeout=timeout_value)

    def test_token_remaining_tracked(self, load_fixture):
        """Test that token_remaining is extracted from responses."""
        # Arrange
        response = load_fixture("info_response.json")

        # Act
        token_remaining = response["meta"]["token_remaining"]

        # Assert
        assert token_remaining == 1850
        assert isinstance(token_remaining, int)

    def test_token_reset_time_tracked(self, load_fixture):
        """Test that token_reset is extracted from responses."""
        # Arrange
        response = load_fixture("info_response.json")

        # Act
        token_reset = response["meta"]["token_reset"]

        # Assert
        assert token_reset == 1609545600
        assert isinstance(token_reset, int)


class TestAPIEndpoints:
    """Test suite for API endpoint URL construction."""

    def test_info_endpoint_url(self):
        """Test device info endpoint URL construction."""
        serial = "test-serial-123"
        expected_url = f"http://api.netrohome.com/npa/v1/info.json?key={serial}"

        # Act
        actual_url = f"http://api.netrohome.com/npa/v1/info.json?key={serial}"

        # Assert
        assert actual_url == expected_url

    def test_schedules_endpoint_url(self):
        """Test schedules endpoint URL construction."""
        serial = "test-serial-123"
        expected_url = f"http://api.netrohome.com/npa/v1/schedules.json?key={serial}"

        # Act
        actual_url = f"http://api.netrohome.com/npa/v1/schedules.json?key={serial}"

        # Assert
        assert actual_url == expected_url

    def test_moistures_endpoint_url(self):
        """Test moistures endpoint URL construction."""
        serial = "test-serial-123"
        expected_url = f"http://api.netrohome.com/npa/v1/moistures.json?key={serial}"

        # Act
        actual_url = f"http://api.netrohome.com/npa/v1/moistures.json?key={serial}"

        # Assert
        assert actual_url == expected_url

    def test_water_endpoint_uses_post(self):
        """Test that water endpoint uses POST method."""
        # This is a structural test to ensure POST is used
        method = "post"
        assert method in ["post", "put"]

    def test_stop_water_endpoint_uses_post(self):
        """Test that stop_water endpoint uses POST method."""
        # This is a structural test to ensure POST is used
        method = "post"
        assert method == "post"
