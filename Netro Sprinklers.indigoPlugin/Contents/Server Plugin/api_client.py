"""Netro API client for HTTP communication with throttle management.

This module provides the NetroAPIClient class that encapsulates all HTTP
communication with the Netro Public API. Features include:

- Request/response handling with proper error classification
- Proactive throttle prevention (pause before hitting rate limit)
- Throttle state persistence across plugin restarts via pluginPrefs
- Response schema validation with warning-only logging

The client is designed to be independent of Indigo imports, receiving
logger and prefs callbacks as constructor arguments to avoid circular
imports with the main plugin module.

Note:
    This module does not import indigo directly. Plugin integration is
    achieved through callback functions passed to the constructor.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Final, List, Optional, Set, Union

import requests

from constants import (
    DEFAULT_API_TIMEOUT_SECONDS,
    DEVICE_INFO_ENDPOINT,
    DEVICE_MOISTURES_ENDPOINT,
    DEVICE_NO_WATER_ENDPOINT,
    DEVICE_REPORT_WEATHER_ENDPOINT,
    DEVICE_SCHEDULES_ENDPOINT,
    DEVICE_SET_MOISTURE_ENDPOINT,
    DEVICE_SENSOR_DATA_ENDPOINT,
    DEVICE_SET_STATUS_ENDPOINT,
    DEVICE_STOP_WATER_ENDPOINT,
    DEVICE_WATER_ENDPOINT,
    DEVICE_INFO_V2_ENDPOINT,
    DEVICE_MOISTURES_V2_ENDPOINT,
    DEVICE_NO_WATER_V2_ENDPOINT,
    DEVICE_REPORT_WEATHER_V2_ENDPOINT,
    DEVICE_SCHEDULES_V2_ENDPOINT,
    DEVICE_SET_MOISTURE_V2_ENDPOINT,
    DEVICE_SENSOR_DATA_V2_ENDPOINT,
    DEVICE_SET_STATUS_V2_ENDPOINT,
    DEVICE_STOP_WATER_V2_ENDPOINT,
    DEVICE_WATER_V2_ENDPOINT,
    DEVICE_EVENTS_V2_ENDPOINT,
    THROTTLE_LIMIT_MINUTES,
    TOKEN_PAUSE_THRESHOLD,
    TOKEN_WARNING_THRESHOLD,
)
from exceptions import NetroAPIError, ThrottleDelayError


# Re-export threshold constants for convenient access
__all__ = ["NetroAPIClient", "TOKEN_PAUSE_THRESHOLD", "TOKEN_WARNING_THRESHOLD"]

# =============================================================================
# Expected Response Keys (for schema validation)
# =============================================================================

EXPECTED_INFO_KEYS: Final[Set[str]] = {"status", "data", "meta"}
"""Expected top-level keys in device info response."""

EXPECTED_META_KEYS: Final[Set[str]] = {"time", "token_remaining", "token_reset", "last_active"}
"""Expected keys in v1 response meta section."""

EXPECTED_META_KEYS_V2: Final[Set[str]] = {
    "time", "tid", "version", "token_limit", "token_remaining", "token_reset", "last_active"
}
"""Expected keys in v2 response meta section."""


class NetroAPIClient:
    """HTTP client for Netro Public API with throttle management.

    This class encapsulates all HTTP communication with the Netro API,
    including request/response handling, error classification, proactive
    throttle prevention, state persistence, and schema validation.

    The client tracks API token usage and provides proactive warnings
    and polling pause recommendations before the daily limit is reached.
    Throttle state is persisted to survive plugin restarts.

    Attributes:
        timeout: Request timeout in seconds
        headers: HTTP headers for API requests

    Example:
        >>> client = NetroAPIClient(
        ...     logger=self.logger,
        ...     prefs_getter=lambda: self.pluginPrefs,
        ...     prefs_setter=lambda k, v: self.pluginPrefs.__setitem__(k, v)
        ... )
        >>> if not client.should_pause_polling:
        ...     info = client.get_device_info("DEVICE_SERIAL")
    """

    def __init__(
        self,
        timeout: int = DEFAULT_API_TIMEOUT_SECONDS,
        logger: Optional[logging.Logger] = None,
        prefs_getter: Optional[Callable[[], Dict[str, Any]]] = None,
        prefs_setter: Optional[Callable[[str, Any], None]] = None
    ) -> None:
        """Initialize API client.

        Args:
            timeout: Request timeout in seconds
            logger: Logger instance for debug output (defaults to module logger)
            prefs_getter: Callable returning pluginPrefs dict (for state restore)
            prefs_setter: Callable to set pluginPrefs key (for state save)
        """
        self.timeout = timeout
        self.logger = logger or logging.getLogger(__name__)
        self._prefs_getter = prefs_getter
        self._prefs_setter = prefs_setter

        # Throttle state
        self._throttle_until: Optional[datetime] = None
        self._token_remaining: int = 2000
        self._token_reset: Optional[datetime] = None

        # HTTP configuration
        self.headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        # Connection error suppression (log once per error type, then silently retry)
        self._last_error_type: Optional[str] = None

        # Restore state from prefs on initialization
        self._restore_throttle_state()

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def is_throttled(self) -> bool:
        """Check if API calls are currently throttled.

        Returns:
            True if throttle is active and not expired
        """
        if not self._throttle_until:
            return False
        # Ensure timezone-aware comparison
        now = datetime.now(timezone.utc) if self._throttle_until.tzinfo else datetime.now()
        if now >= self._throttle_until:
            self._throttle_until = None
            self.logger.info("API throttle period expired - resuming normal operation")
            self._save_throttle_state()
            return False
        return True

    @property
    def throttle_expires(self) -> Optional[datetime]:
        """Get throttle expiration time if throttled.

        Returns:
            Datetime when throttle expires, or None if not throttled
        """
        return self._throttle_until if self.is_throttled else None

    @property
    def token_remaining(self) -> int:
        """Get current API token count.

        Returns:
            Number of API tokens remaining (max 2000 per day)
        """
        return self._token_remaining

    @property
    def should_pause_polling(self) -> bool:
        """Check if polling should pause due to low token budget.

        This is PROACTIVE prevention - the plugin should check this
        before making API calls to avoid exhausting the daily limit.

        Auto-resets token count if past reset time to prevent self-locking.

        Returns:
            True if remaining tokens are below pause threshold
        """
        # Check if we're past the token reset time and should auto-reset
        if self._token_reset:
            now = datetime.now(timezone.utc) if self._token_reset.tzinfo else datetime.now()
            if now >= self._token_reset:
                # Past reset time - automatically reset to daily limit
                self._token_remaining = 2000
                self._token_reset = None
                self._save_throttle_state()
                self.logger.info("API token budget has reset to daily limit (2000)")

        return self._token_remaining < TOKEN_PAUSE_THRESHOLD

    # =========================================================================
    # Core Request Method
    # =========================================================================

    def make_request(
        self,
        url: str,
        method: str = "get",
        data: Optional[Dict[str, Any]] = None
    ) -> Union[Dict[str, Any], bool]:
        """Make API request with error handling and throttle enforcement.

        This is the core method for all API communication. It handles:
        - Throttle state checking before requests
        - HTTP method selection (GET/POST/PUT)
        - Response parsing and error handling
        - Token budget tracking from response metadata
        - Connection error suppression (log once)

        Args:
            url: Full URL for the API endpoint
            method: HTTP method ('get', 'post', or 'put')
            data: Optional request body data (for POST/PUT)

        Returns:
            Parsed JSON response dict, or True for 204 responses

        Raises:
            ThrottleDelayError: If API is throttled (rate limit exceeded)
            requests.exceptions.ConnectionError: If network connection fails
            requests.exceptions.Timeout: If request times out
            requests.exceptions.HTTPError: For other HTTP errors
        """
        # Check throttle state first
        if self.is_throttled:
            raise ThrottleDelayError(
                f"API calls throttled until {self._throttle_until:%H:%M:%S}",
                retry_after=self._throttle_until
            )

        try:
            # Mask the key value in debug logs to avoid exposing API keys
            masked_url = url.split("key=")[0] + "key=***" if "key=" in url else url
            self.logger.debug(f"API call: {method.upper()} {masked_url}")

            # Select HTTP method
            if method == "put":
                http_method = requests.put
            elif method == "post":
                http_method = requests.post
            else:
                http_method = requests.get

            # Make request with or without body
            if data and method in ("put", "post"):
                response = http_method(
                    url,
                    data=json.dumps(data),
                    headers=self.headers,
                    timeout=self.timeout
                )
            else:
                response = http_method(
                    url,
                    headers=self.headers,
                    timeout=self.timeout
                )

            # Handle successful responses
            if response.status_code == 200:
                result = response.json()
                self._last_error_type = None  # Clear error state on success

                # Validate response schema (warning only)
                self._validate_response_schema(result, EXPECTED_INFO_KEYS, url)

                # Update token tracking from meta
                if "meta" in result:
                    # Validate meta structure
                    self._validate_response_schema(result["meta"], EXPECTED_META_KEYS, f"{url}/meta")
                    self._update_token_budget(result["meta"])

                return result

            if response.status_code == 204:
                self._last_error_type = None  # Clear error state on success
                return True

            # Non-success status codes
            response.raise_for_status()

        except requests.exceptions.ConnectionError:
            # Log once per error type to avoid spam
            if self._last_error_type != "connection":
                self.logger.error(
                    "Connection to Netro API failed. Will retry silently."
                )
                self._last_error_type = "connection"
            raise

        except requests.exceptions.Timeout:
            # Log once per error type to avoid spam
            if self._last_error_type != "timeout":
                self.logger.error(
                    "Netro API request timed out. Will retry silently."
                )
                self._last_error_type = "timeout"
            raise

        except requests.exceptions.HTTPError as exc:
            self._handle_http_error(exc)
            raise

        # This return is unreachable but satisfies type checker
        return None  # pragma: no cover

    # =========================================================================
    # Error Handling
    # =========================================================================

    def _handle_http_error(self, exc: requests.exceptions.HTTPError) -> None:
        """Handle HTTP errors, detecting rate limit responses.

        Netro API returns errors in format:
        {"status": "ERROR", "errors": [{"code": 3, "message": "..."}], "meta": {...}}

        Error codes:
        - 1: Invalid device serial number
        - 3: Rate limit exceeded

        When rate limit is detected, sets throttle state and saves to prefs.

        Args:
            exc: HTTPError exception from requests
        """
        response = exc.response
        status_code = response.status_code if response is not None else None

        # Try to parse Netro error response body
        error_code = None
        error_message = str(exc)
        meta = None

        if response is not None:
            try:
                error_data = response.json()
                # Netro returns {"status": "ERROR", "errors": [...], "meta": {...}}
                if error_data.get("status") == "ERROR":
                    errors_list = error_data.get("errors", [])
                    meta = error_data.get("meta", {})

                    # Get first error code and message
                    if errors_list and isinstance(errors_list, list):
                        first_error = errors_list[0]
                        error_code = first_error.get("code")
                        error_message = first_error.get("message", str(exc))
            except (ValueError, AttributeError, TypeError):
                pass  # Response body not JSON or missing expected structure

        # Check for rate limit (error code 3 or HTTP 429)
        if error_code == 3 or status_code == 429:
            # Use token_reset from meta if available, otherwise fallback to fixed delay
            if meta and meta.get("token_reset"):
                try:
                    reset_str = meta.get("token_reset")
                    self._throttle_until = datetime.fromisoformat(reset_str).replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    # Fallback to fixed delay
                    self._throttle_until = datetime.now(timezone.utc) + timedelta(minutes=THROTTLE_LIMIT_MINUTES)
            else:
                self._throttle_until = datetime.now(timezone.utc) + timedelta(minutes=THROTTLE_LIMIT_MINUTES)

            self._save_throttle_state()
            self.logger.warning(
                f"API rate limit exceeded. Throttled until {self._throttle_until:%H:%M:%S}"
            )
            raise ThrottleDelayError(
                f"API rate limit exceeded. Throttled for {THROTTLE_LIMIT_MINUTES} minutes.",
                retry_after=self._throttle_until
            ) from exc

        # Check for invalid serial (error code 1)
        if error_code == 1:
            self.logger.error("Invalid device serial number: %s", error_message)
            raise NetroAPIError(
                f"Invalid serial number: {error_message}",
                status_code=status_code,
                error_code=error_code
            ) from exc

        # Log other HTTP errors
        self.logger.error("HTTP error %s: %s", status_code, error_message)

    # =========================================================================
    # Token Budget Management
    # =========================================================================

    def _update_token_budget(self, meta: Dict[str, Any]) -> None:
        """Update token tracking from API response metadata.

        Parses token_remaining and token_reset from the response meta
        section, logs warnings at thresholds, and saves state.

        Handles both v1 (strptime) and v2 (fromisoformat) timestamp formats.

        Args:
            meta: Response meta dict containing token info
        """
        try:
            self._token_remaining = int(meta.get("token_remaining", 2000))
            reset_str = meta.get("token_reset", "")
            if reset_str:
                self._token_reset = datetime.fromisoformat(reset_str).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError) as exc:
            self.logger.warning(f"Could not parse token info from response: {exc}")
            # Set safe default to trigger proactive pause and prevent exhausting token budget
            self._token_remaining = TOKEN_PAUSE_THRESHOLD - 1

        # Log warnings at thresholds
        if self._token_remaining < TOKEN_WARNING_THRESHOLD:
            reset_info = f", resets at {self._token_reset}" if self._token_reset else ""
            self.logger.warning(
                f"API tokens low: {self._token_remaining} remaining{reset_info}"
            )

        # Persist state
        self._save_throttle_state()

    # =========================================================================
    # State Persistence
    # =========================================================================

    def _save_throttle_state(self) -> None:
        """Persist throttle state to pluginPrefs.

        Serializes current throttle and token state to JSON and saves
        via the prefs_setter callback. Does nothing if no setter provided.
        """
        if not self._prefs_setter:
            return

        state = {
            "throttle_until": self._throttle_until.isoformat() if self._throttle_until else None,
            "token_remaining": self._token_remaining,
            "token_reset": self._token_reset.isoformat() if self._token_reset else None,
            "last_saved": datetime.now(timezone.utc).isoformat()
        }

        try:
            self._prefs_setter("throttle_state", json.dumps(state))
        except (TypeError, ValueError) as exc:
            self.logger.warning(f"Could not save throttle state: {exc}")

    def _restore_throttle_state(self) -> None:
        """Restore throttle state from pluginPrefs on startup.

        Loads and parses throttle state JSON from prefs. Only applies
        throttle_until if it's still in the future. Does nothing if
        no prefs_getter provided or state is missing/invalid.
        """
        if not self._prefs_getter:
            return

        try:
            prefs = self._prefs_getter()
        except (TypeError, AttributeError):
            return  # Prefs callback failed

        state_json = prefs.get("throttle_state", "")
        if not state_json:
            return

        try:
            state = json.loads(state_json)

            # Restore throttle expiry only if still in future
            if state.get("throttle_until"):
                throttle_until = datetime.fromisoformat(state["throttle_until"])
                # Ensure timezone-aware comparison
                now = datetime.now(timezone.utc) if throttle_until.tzinfo else datetime.now()
                if throttle_until > now:
                    self._throttle_until = throttle_until
                    self.logger.info(
                        f"Restored throttle state: paused until {throttle_until:%H:%M:%S}"
                    )

            # Restore token info
            self._token_remaining = state.get("token_remaining", 2000)
            if state.get("token_reset"):
                self._token_reset = datetime.fromisoformat(state["token_reset"])

        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            self.logger.warning("Could not restore throttle state: %s", exc)

    # =========================================================================
    # Schema Validation
    # =========================================================================

    def _validate_response_schema(
        self,
        response: Dict[str, Any],
        expected_keys: Set[str],
        endpoint: str
    ) -> None:
        """Log warning if response structure differs from expected.

        This is WARNING-only validation - it never raises exceptions.
        The purpose is to detect API changes early, not to block operation.

        Args:
            response: Parsed JSON response
            expected_keys: Set of keys expected at top level
            endpoint: Endpoint name for logging context
        """
        actual_keys = set(response.keys())
        missing = expected_keys - actual_keys
        extra = actual_keys - expected_keys

        if missing:
            self.logger.warning(
                f"API response from {endpoint} missing expected keys: {missing}"
            )
        if extra:
            self.logger.debug(
                f"API response from {endpoint} has additional keys: {extra}"
            )

    # =========================================================================
    # Endpoint Selection
    # =========================================================================

    # Maps (endpoint_name, api_version) to the correct URL constant.
    # v1 endpoints use serial number auth, v2 use API key auth.
    _ENDPOINT_MAP: Dict[str, Dict[str, str]] = {
        "info": {"1": DEVICE_INFO_ENDPOINT, "2": DEVICE_INFO_V2_ENDPOINT},
        "schedules": {"1": DEVICE_SCHEDULES_ENDPOINT, "2": DEVICE_SCHEDULES_V2_ENDPOINT},
        "moistures": {"1": DEVICE_MOISTURES_ENDPOINT, "2": DEVICE_MOISTURES_V2_ENDPOINT},
        "sensor_data": {"1": DEVICE_SENSOR_DATA_ENDPOINT, "2": DEVICE_SENSOR_DATA_V2_ENDPOINT},
        "water": {"1": DEVICE_WATER_ENDPOINT, "2": DEVICE_WATER_V2_ENDPOINT},
        "stop_water": {"1": DEVICE_STOP_WATER_ENDPOINT, "2": DEVICE_STOP_WATER_V2_ENDPOINT},
        "set_status": {"1": DEVICE_SET_STATUS_ENDPOINT, "2": DEVICE_SET_STATUS_V2_ENDPOINT},
        "no_water": {"1": DEVICE_NO_WATER_ENDPOINT, "2": DEVICE_NO_WATER_V2_ENDPOINT},
        "report_weather": {"1": DEVICE_REPORT_WEATHER_ENDPOINT, "2": DEVICE_REPORT_WEATHER_V2_ENDPOINT},
        "set_moisture": {"1": DEVICE_SET_MOISTURE_ENDPOINT, "2": DEVICE_SET_MOISTURE_V2_ENDPOINT},
    }

    def _endpoint(self, name: str, api_version: str = "1") -> str:
        """Get the endpoint URL for the given name and API version.

        Args:
            name: Endpoint name (e.g. "info", "schedules")
            api_version: "1" or "2"

        Returns:
            Full endpoint URL
        """
        versions = self._ENDPOINT_MAP[name]
        if api_version not in versions:
            self.logger.warning(
                f"Unknown API version '{api_version}' for endpoint '{name}', falling back to v1"
            )
            api_version = "1"
        return versions[api_version]

    # =========================================================================
    # Convenience Methods for Endpoints
    # =========================================================================

    def get_device_info(self, key: str, api_version: str = "1") -> Dict[str, Any]:
        """Get device information from Netro API.

        Args:
            key: Device serial number (v1) or API key (v2)
            api_version: API version to use ("1" or "2")

        Returns:
            API response containing device info
        """
        return self.make_request(f"{self._endpoint('info', api_version)}?key={key}")

    def get_schedules(self, key: str, api_version: str = "1") -> Dict[str, Any]:
        """Get device schedules from Netro API.

        Args:
            key: Device serial number (v1) or API key (v2)
            api_version: API version to use ("1" or "2")

        Returns:
            API response containing schedules
        """
        return self.make_request(f"{self._endpoint('schedules', api_version)}?key={key}")

    def get_moistures(self, key: str, api_version: str = "1") -> Dict[str, Any]:
        """Get moisture levels from Netro API.

        Args:
            key: Device serial number (v1) or API key (v2)
            api_version: API version to use ("1" or "2")

        Returns:
            API response containing moisture data
        """
        return self.make_request(f"{self._endpoint('moistures', api_version)}?key={key}")

    def get_sensor_data(self, key: str, api_version: str = "1") -> Dict[str, Any]:
        """Get Whisperer sensor data from Netro API.

        Args:
            key: Sensor serial number (v1) or API key (v2)
            api_version: API version to use ("1" or "2")

        Returns:
            API response containing sensor readings
        """
        return self.make_request(f"{self._endpoint('sensor_data', api_version)}?key={key}")

    def get_events(
        self,
        key: str,
        event_type: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get device events from Netro API (v2 only).

        Args:
            key: API key (v2 only)
            event_type: Optional filter — 1=offline, 2=online, 3=schedule start, 4=schedule end
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)

        Returns:
            API response containing device events
        """
        url = f"{DEVICE_EVENTS_V2_ENDPOINT}?key={key}"
        if event_type is not None:
            url += f"&event={event_type}"
        if start_date:
            url += f"&start_date={start_date}"
        if end_date:
            url += f"&end_date={end_date}"
        return self.make_request(url)

    def start_watering(
        self,
        key: str,
        zones: List[Dict[str, Any]],
        delay: int = 0,
        start_time: Optional[int] = None,
        api_version: str = "1"
    ) -> Dict[str, Any]:
        """Start watering with optional delay.

        Args:
            key: Device serial number (v1) or API key (v2)
            zones: List of zone dicts with id and duration
            delay: Delay in minutes before starting (default 0)
            start_time: Optional epoch timestamp for scheduled start
            api_version: API version to use ("1" or "2")

        Returns:
            API response confirming watering started
        """
        data: Dict[str, Any] = {"key": key, "zones": zones}
        if delay > 0:
            data["delay"] = delay
        if start_time:
            data["start_time"] = start_time
        return self.make_request(
            self._endpoint("water", api_version), method="post", data=data
        )

    def stop_watering(self, key: str, api_version: str = "1") -> Dict[str, Any]:
        """Stop all active watering on device.

        Args:
            key: Device serial number (v1) or API key (v2)
            api_version: API version to use ("1" or "2")

        Returns:
            API response confirming watering stopped
        """
        return self.make_request(
            self._endpoint("stop_water", api_version),
            method="post",
            data={"key": key}
        )

    def set_device_status(self, key: str, status: int, api_version: str = "1") -> Dict[str, Any]:
        """Set device status (online/standby).

        Args:
            key: Device serial number (v1) or API key (v2)
            status: 1 for online, 0 for standby
            api_version: API version to use ("1" or "2")

        Returns:
            API response confirming status change
        """
        return self.make_request(
            self._endpoint("set_status", api_version),
            method="post",
            data={"key": key, "status": status}
        )

    def set_no_water(self, key: str, days: int, api_version: str = "1") -> Dict[str, Any]:
        """Set rain delay (no watering for N days).

        Args:
            key: Device serial number (v1) or API key (v2)
            days: Number of days to skip watering (0 to cancel)
            api_version: API version to use ("1" or "2")

        Returns:
            API response confirming rain delay set
        """
        return self.make_request(
            self._endpoint("no_water", api_version),
            method="post",
            data={"key": key, "days": days}
        )

    def report_weather(
        self, key: str, weather_data: Dict[str, Any], api_version: str = "1"
    ) -> Dict[str, Any]:
        """Report local weather data to improve scheduling.

        Args:
            key: Device serial number (v1) or API key (v2)
            weather_data: Weather data dict (temperature, humidity, etc.)
            api_version: API version to use ("1" or "2")

        Returns:
            API response confirming weather report received
        """
        data = {"key": key, **weather_data}
        return self.make_request(
            self._endpoint("report_weather", api_version),
            method="post",
            data=data
        )

    def set_moisture(
        self, key: str, zone: int, moisture: int, api_version: str = "1"
    ) -> Dict[str, Any]:
        """Override moisture level for a specific zone.

        Args:
            key: Device serial number (v1) or API key (v2)
            zone: Zone number (1-based)
            moisture: Moisture percentage (0-100)
            api_version: API version to use ("1" or "2")

        Returns:
            API response confirming moisture override
        """
        if api_version == "2":
            # V2: flat format with zones array and moisture value
            data = {"key": key, "zones": [zone], "moisture": moisture}
        else:
            # V1: nested moistures array
            data = {"key": key, "moistures": [{"zone": zone, "moisture": moisture}]}
        return self.make_request(
            self._endpoint("set_moisture", api_version),
            method="post",
            data=data
        )
