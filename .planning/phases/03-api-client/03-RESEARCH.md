# Phase 3: API Client - Research

**Researched:** 2026-02-01
**Domain:** Python HTTP API client with throttle management, state persistence, schema validation
**Confidence:** HIGH

## Summary

This research covers the extraction of API communication logic into a dedicated `api_client.py` module with proactive throttle management, persistent state, and response schema validation. The current `_make_api_call()` method in `plugin.py` (lines 137-276) handles HTTP requests with basic throttle detection but lacks proactive token budget management and state persistence.

The standard approach uses a single `NetroAPIClient` class encapsulating all HTTP communication, with throttle state stored in Indigo's `pluginPrefs` for persistence across restarts. Response validation uses TypedDict for lightweight schema checking without adding external dependencies (Pydantic would be overkill for this use case).

**Primary recommendation:** Extract `_make_api_call()` and related API methods into `NetroAPIClient` class with proactive throttle prevention (pause when tokens <100), persistent throttle state via pluginPrefs, and TypedDict-based schema validation.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| requests | 2.32+ | HTTP client | Already bundled with Indigo, well-tested, synchronous |
| typing | stdlib | Type hints and TypedDict | Built-in, no dependencies, sufficient for lightweight validation |
| dataclasses | stdlib | Data structures for throttle state | Built-in since Python 3.7, clean API |
| datetime | stdlib | Timestamp handling | Built-in, required for throttle timing |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| json | stdlib | JSON parsing | Already used for API response parsing |
| traceback | stdlib | Exception formatting | Already used for debug logging |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| TypedDict | Pydantic | Pydantic adds dependency, runtime validation is more powerful but overkill for warning-only schema checking |
| requests | httpx | httpx is more modern with async support, but would require significant refactoring and async is unnecessary for Indigo plugins |
| Manual throttle | requests-ratelimiter | External library adds complexity; Netro's simple 2000 calls/day limit is easier to manage manually |

**Installation:**
```bash
# No additional installation needed - all libraries are Python stdlib or Indigo-bundled
```

## Architecture Patterns

### Recommended Project Structure
```
Server Plugin/
    plugin.py           # Slim coordinator, uses api_client
    api_client.py       # NEW: NetroAPIClient class (~250 lines)
    constants.py        # API URLs, defaults (from Phase 2)
    exceptions.py       # ThrottleDelayError, NetroAPIError (from Phase 2)
    utils.py            # Helper functions (from Phase 2)
    validators.py       # Validation functions (from Phase 4)
```

### Pattern 1: Single API Client Class
**What:** Encapsulate all HTTP communication in one class that owns throttle state
**When to use:** Small-to-medium APIs with consistent authentication and error handling
**Example:**
```python
# Source: Based on Python API client best practices
class NetroAPIClient:
    """HTTP client for Netro Public API with throttle management."""

    def __init__(
        self,
        timeout: int = DEFAULT_API_TIMEOUT_SECONDS,
        logger: Optional[logging.Logger] = None,
        prefs_getter: Optional[Callable[[], dict]] = None,
        prefs_setter: Optional[Callable[[str, Any], None]] = None
    ):
        """Initialize API client.

        Args:
            timeout: Request timeout in seconds
            logger: Logger instance for debug output
            prefs_getter: Callable returning pluginPrefs dict (for state restore)
            prefs_setter: Callable to set pluginPrefs key (for state save)
        """
        self.timeout = timeout
        self.logger = logger or logging.getLogger(__name__)
        self._prefs_getter = prefs_getter
        self._prefs_setter = prefs_setter

        # Throttle state (restored from prefs on init)
        self._throttle_until: Optional[datetime] = None
        self._token_remaining: int = 2000
        self._token_reset: Optional[datetime] = None
        self._restore_throttle_state()

        # Request configuration
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        # Connection error suppression
        self._displayed_connection_error = False
```

### Pattern 2: Proactive Throttle Prevention
**What:** Pause polling before hitting rate limit, not just after
**When to use:** APIs with daily token budgets where exhaustion is worse than pausing
**Example:**
```python
# Source: Netro API requirements - 2000 calls/day
TOKEN_PAUSE_THRESHOLD: Final[int] = 100   # Stop polling at this level
TOKEN_WARNING_THRESHOLD: Final[int] = 200  # Log warning at this level

def should_pause_polling(self) -> bool:
    """Check if polling should pause due to low token budget.

    Returns True if remaining tokens are below pause threshold.
    This is PROACTIVE prevention, not reactive throttle response.
    """
    return self._token_remaining < TOKEN_PAUSE_THRESHOLD

def _update_token_budget(self, meta: dict) -> None:
    """Update token tracking from API response metadata.

    Args:
        meta: Response meta dict containing token_remaining and token_reset
    """
    try:
        self._token_remaining = int(meta.get("token_remaining", 2000))
        reset_str = meta.get("token_reset", "")
        if reset_str:
            self._token_reset = datetime.strptime(reset_str, "%Y-%m-%dT%H:%M:%S")
    except (ValueError, TypeError) as exc:
        self.logger.warning(f"Could not parse token info: {exc}")

    # Log warnings at thresholds
    if self._token_remaining < TOKEN_WARNING_THRESHOLD:
        self.logger.warning(
            f"API tokens low: {self._token_remaining} remaining, "
            f"resets at {self._token_reset}"
        )

    # Persist state
    self._save_throttle_state()
```

### Pattern 3: Persistent Throttle State via pluginPrefs
**What:** Save/restore throttle state to survive plugin restarts
**When to use:** When rate limit penalties persist across restarts
**Example:**
```python
# Source: Indigo plugin documentation - pluginPrefs persistence
def _save_throttle_state(self) -> None:
    """Persist throttle state to pluginPrefs."""
    if not self._prefs_setter:
        return

    state = {
        "throttle_until": self._throttle_until.isoformat() if self._throttle_until else None,
        "token_remaining": self._token_remaining,
        "token_reset": self._token_reset.isoformat() if self._token_reset else None,
        "last_saved": datetime.now().isoformat()
    }
    self._prefs_setter("throttle_state", json.dumps(state))

def _restore_throttle_state(self) -> None:
    """Restore throttle state from pluginPrefs on startup."""
    if not self._prefs_getter:
        return

    prefs = self._prefs_getter()
    state_json = prefs.get("throttle_state", "")
    if not state_json:
        return

    try:
        state = json.loads(state_json)

        # Restore throttle expiry if still in future
        if state.get("throttle_until"):
            throttle_until = datetime.fromisoformat(state["throttle_until"])
            if throttle_until > datetime.now():
                self._throttle_until = throttle_until
                self.logger.info(
                    f"Restored throttle state: paused until {throttle_until}"
                )

        # Restore token info
        self._token_remaining = state.get("token_remaining", 2000)
        if state.get("token_reset"):
            self._token_reset = datetime.fromisoformat(state["token_reset"])

    except (json.JSONDecodeError, ValueError) as exc:
        self.logger.warning(f"Could not restore throttle state: {exc}")
```

### Pattern 4: TypedDict Schema Validation
**What:** Define expected response shapes with TypedDict for lightweight validation
**When to use:** When you want warnings on API changes without runtime errors
**Example:**
```python
# Source: Python typing module - TypedDict for API response schemas
from typing import TypedDict, List, Optional

class DeviceZoneSchema(TypedDict, total=False):
    id: str
    ith: int
    name: str
    enabled: bool
    smart: bool  # Can be bool or str "SMART"/"MANUAL"
    maxRuntime: int

class DeviceSchema(TypedDict, total=False):
    id: str
    serial: str
    name: str
    status: str  # "ONLINE" or "OFFLINE" or "STANDBY"
    version: str
    model: str
    zones: List[DeviceZoneSchema]

class MetaSchema(TypedDict, total=False):
    time: int
    token_remaining: int
    token_reset: str
    last_active: int
    version: int

class DeviceInfoResponse(TypedDict, total=False):
    status: str
    data: dict  # Contains "device" key
    meta: MetaSchema

def validate_response_schema(
    response: dict,
    expected_keys: set,
    endpoint: str
) -> None:
    """Log warning if response structure differs from expected.

    This is WARNING-only validation - does not raise exceptions.
    Purpose is to detect API changes early, not block operation.

    Args:
        response: Parsed JSON response
        expected_keys: Set of keys expected at top level
        endpoint: Endpoint name for logging
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
            f"API response from {endpoint} has unexpected keys: {extra}"
        )
```

### Anti-Patterns to Avoid
- **Global throttle state:** Don't use module-level variables for throttle state; keep it in the client instance for testability
- **Blocking on throttle:** Don't wait/sleep in API client methods; return status and let caller decide
- **Hard failure on schema mismatch:** Log warnings, don't raise exceptions for missing fields; API changes shouldn't break existing functionality
- **Tight coupling to Plugin:** Don't import `indigo` directly in api_client.py; pass logger and prefs callbacks as constructor arguments

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON parsing | Custom parser | `response.json()` | requests handles encoding, errors |
| HTTP retry | Manual retry loops | `requests.adapters.HTTPAdapter` with `Retry` | Handles backoff, status codes correctly |
| Type validation | Manual isinstance checks | TypedDict + key checks | More maintainable, self-documenting |
| State persistence | Custom file I/O | Indigo pluginPrefs | Already exists, handled by framework |
| Timeout handling | Manual socket ops | `requests.get(..., timeout=N)` | Cleaner, handles all edge cases |

**Key insight:** The Netro API is simple enough that heavy libraries (httpx, pydantic, requests-ratelimiter) add more complexity than they solve. The daily token limit with explicit remaining count is easier to track manually than with a rate limiter library.

## Common Pitfalls

### Pitfall 1: Throttle State Not Persisted
**What goes wrong:** Plugin restarts during throttle period, immediately hits rate limit again
**Why it happens:** Throttle expiry stored only in memory
**How to avoid:** Save throttle_until timestamp to pluginPrefs on every throttle event, restore on startup
**Warning signs:** Plugin works fine until restart, then immediately shows rate limit errors

### Pitfall 2: Timestamps as Strings
**What goes wrong:** TypeError or ValueError when parsing Netro timestamps
**Why it happens:** Netro API returns timestamps as strings, not integers (documented in API_NOTES.md)
**How to avoid:** Always parse with `float(value) if isinstance(value, str) else value`
**Warning signs:** Errors like "cannot convert str to int" in schedule parsing

### Pitfall 3: Token Count Ignored Until Too Late
**What goes wrong:** Plugin exhausts daily API tokens, all users locked out until reset
**Why it happens:** Only checking token count when already at 0
**How to avoid:** Warn at 200 tokens, pause polling at 100 tokens
**Warning signs:** API errors with "rate limit exceeded" and negative token counts

### Pitfall 4: Circular Imports with Plugin
**What goes wrong:** ImportError when loading plugin
**Why it happens:** api_client.py imports from plugin.py
**How to avoid:** Pass logger and prefs as callbacks/arguments, never import Plugin class
**Warning signs:** "ImportError: cannot import name 'Plugin'" at startup

### Pitfall 5: Schema Validation Breaks on API Updates
**What goes wrong:** Plugin stops working after Netro adds new API fields
**Why it happens:** Strict validation rejects responses with extra/different keys
**How to avoid:** Schema validation logs warnings only, never raises on mismatch
**Warning signs:** Working plugin suddenly fails after no code changes

### Pitfall 6: Not Handling "device" vs "devices" Response
**What goes wrong:** KeyError accessing device data
**Why it happens:** Netro returns `data.device` (singular), not `data.devices` (array)
**How to avoid:** Check for both patterns, document expected structure
**Warning signs:** KeyError: 'devices' in device info responses

## Code Examples

Verified patterns from official sources and existing codebase:

### Complete API Client Class Structure
```python
# Source: Based on plugin.py _make_api_call() + research patterns
"""Netro API client for HTTP communication with throttle management."""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Final, Optional, Set

import requests

from constants import (
    DEFAULT_API_TIMEOUT_SECONDS,
    THROTTLE_LIMIT_MINUTES,
    DEVICE_INFO_ENDPOINT,
    DEVICE_SCHEDULES_ENDPOINT,
    DEVICE_MOISTURES_ENDPOINT,
    DEVICE_SENSOR_DATA_ENDPOINT,
    DEVICE_WATER_ENDPOINT,
    DEVICE_STOP_WATER_ENDPOINT,
    DEVICE_SET_STATUS_ENDPOINT,
    DEVICE_NO_WATER_ENDPOINT,
    DEVICE_REPORT_WEATHER_ENDPOINT,
)
from exceptions import ThrottleDelayError, NetroAPIError


# Proactive throttle thresholds
TOKEN_PAUSE_THRESHOLD: Final[int] = 100
TOKEN_WARNING_THRESHOLD: Final[int] = 200

# Expected response keys for validation
EXPECTED_INFO_KEYS: Final[Set[str]] = {"status", "data", "meta"}
EXPECTED_META_KEYS: Final[Set[str]] = {"time", "token_remaining", "token_reset", "last_active"}


class NetroAPIClient:
    """HTTP client for Netro Public API with throttle management.

    This class encapsulates all HTTP communication with the Netro API,
    including:
    - Request/response handling with proper error classification
    - Proactive throttle prevention (pause before hitting limit)
    - Throttle state persistence across plugin restarts
    - Response schema validation with warning-only logging

    Attributes:
        timeout: Request timeout in seconds
        is_throttled: True if currently in throttle period
        token_remaining: Current API token count (2000 max)
        should_pause_polling: True if token count below threshold
    """

    def __init__(
        self,
        timeout: int = DEFAULT_API_TIMEOUT_SECONDS,
        logger: Optional[logging.Logger] = None,
        prefs_getter: Optional[Callable[[], dict]] = None,
        prefs_setter: Optional[Callable[[str, Any], None]] = None
    ) -> None:
        self.timeout = timeout
        self.logger = logger or logging.getLogger(__name__)
        self._prefs_getter = prefs_getter
        self._prefs_setter = prefs_setter

        # Throttle state
        self._throttle_until: Optional[datetime] = None
        self._token_remaining: int = 2000
        self._token_reset: Optional[datetime] = None

        # HTTP configuration
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        # Connection error suppression
        self._displayed_connection_error = False

        # Restore state from prefs
        self._restore_throttle_state()

    @property
    def is_throttled(self) -> bool:
        """Check if API calls are currently throttled."""
        if not self._throttle_until:
            return False
        if datetime.now() >= self._throttle_until:
            self._throttle_until = None
            self.logger.info("API throttle period expired - resuming normal operation")
            self._save_throttle_state()
            return False
        return True

    @property
    def throttle_expires(self) -> Optional[datetime]:
        """Get throttle expiration time if throttled."""
        return self._throttle_until if self.is_throttled else None

    @property
    def token_remaining(self) -> int:
        """Get current token count."""
        return self._token_remaining

    @property
    def should_pause_polling(self) -> bool:
        """Check if polling should pause due to low tokens."""
        return self._token_remaining < TOKEN_PAUSE_THRESHOLD

    def make_request(
        self,
        url: str,
        method: str = "get",
        data: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Make API request with error handling and throttle enforcement."""
        # Check throttle state
        if self.is_throttled:
            raise ThrottleDelayError(
                f"API calls throttled until {self._throttle_until:%H:%M:%S}",
                retry_after=self._throttle_until
            )

        try:
            self.logger.debug(f"API call: {method.upper()} {url}")

            # Select HTTP method
            if method == "put":
                http_method = requests.put
            elif method == "post":
                http_method = requests.post
            else:
                http_method = requests.get

            # Make request
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

            # Handle response
            if response.status_code == 200:
                result = response.json()
                self._displayed_connection_error = False

                # Update token tracking from meta
                if "meta" in result:
                    self._update_token_budget(result["meta"])

                return result

            elif response.status_code == 204:
                self._displayed_connection_error = False
                return True

            else:
                response.raise_for_status()

        except requests.exceptions.ConnectionError as exc:
            if not self._displayed_connection_error:
                self.logger.error(
                    "Connection to Netro API failed. Will retry silently."
                )
                self._displayed_connection_error = True
            raise

        except requests.exceptions.Timeout as exc:
            if not self._displayed_connection_error:
                self.logger.error(
                    "Netro API request timed out. Will retry silently."
                )
                self._displayed_connection_error = True
            raise

        except requests.exceptions.HTTPError as exc:
            self._handle_http_error(exc)
            raise

    def _handle_http_error(self, exc: requests.exceptions.HTTPError) -> None:
        """Handle HTTP errors, detecting rate limit responses."""
        # ... error handling logic from current _make_api_call()
        pass

    def _update_token_budget(self, meta: dict) -> None:
        """Update token tracking from response metadata."""
        # ... implementation shown in Pattern 2 above
        pass

    def _save_throttle_state(self) -> None:
        """Persist throttle state to pluginPrefs."""
        # ... implementation shown in Pattern 3 above
        pass

    def _restore_throttle_state(self) -> None:
        """Restore throttle state from pluginPrefs."""
        # ... implementation shown in Pattern 3 above
        pass

    # Convenience methods for each endpoint
    def get_device_info(self, serial: str) -> Dict[str, Any]:
        """Get device information from Netro API."""
        return self.make_request(f"{DEVICE_INFO_ENDPOINT}?key={serial}")

    def get_schedules(self, serial: str) -> Dict[str, Any]:
        """Get device schedules from Netro API."""
        return self.make_request(f"{DEVICE_SCHEDULES_ENDPOINT}?key={serial}")

    def get_moistures(self, serial: str) -> Dict[str, Any]:
        """Get moisture levels from Netro API."""
        return self.make_request(f"{DEVICE_MOISTURES_ENDPOINT}?key={serial}")

    def get_sensor_data(self, serial: str) -> Dict[str, Any]:
        """Get Whisperer sensor data from Netro API."""
        return self.make_request(f"{DEVICE_SENSOR_DATA_ENDPOINT}?key={serial}")

    def start_watering(
        self,
        serial: str,
        zones: list,
        delay: int = 0,
        start_time: Optional[int] = None
    ) -> Dict[str, Any]:
        """Start watering with optional delay."""
        data = {"key": serial, "zones": zones}
        if delay > 0:
            data["delay"] = delay
        if start_time:
            data["start_time"] = start_time
        return self.make_request(DEVICE_WATER_ENDPOINT, method="post", data=data)

    def stop_watering(self, serial: str) -> Dict[str, Any]:
        """Stop all zones."""
        return self.make_request(
            DEVICE_STOP_WATER_ENDPOINT,
            method="post",
            data={"key": serial}
        )
```

### Plugin Integration Pattern
```python
# Source: Based on plugin.py architecture
class Plugin(indigo.PluginBase):
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        super().__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        # Create API client with prefs callbacks for state persistence
        self.api_client = NetroAPIClient(
            timeout=int(pluginPrefs.get("apiTimeout", DEFAULT_API_TIMEOUT_SECONDS)),
            logger=self.logger,
            prefs_getter=lambda: self.pluginPrefs,
            prefs_setter=lambda k, v: self.pluginPrefs.__setitem__(k, v)
        )

    def runConcurrentThread(self):
        while True:
            try:
                # Check proactive pause before polling
                if self.api_client.should_pause_polling:
                    self.logger.warning(
                        f"Polling paused: only {self.api_client.token_remaining} "
                        f"tokens remaining (threshold: {TOKEN_PAUSE_THRESHOLD})"
                    )
                else:
                    self._update_from_netro()
            except self.StopThread:
                raise
            except Exception:
                self.logger.exception("Error in polling loop")

            self.sleep(self.pollingInterval * 60)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Inline API calls | Dedicated API client class | 2023+ | Testability, separation of concerns |
| Reactive throttle only | Proactive + reactive throttle | 2024+ | Prevents exhausting daily limit |
| Memory-only throttle state | Persistent via pluginPrefs | This phase | Survives restarts |
| No schema validation | TypedDict + warning logging | This phase | Early API change detection |

**Deprecated/outdated:**
- urllib: Replaced by requests for cleaner API
- Manual connection pooling: requests.Session handles this
- Global state variables: Instance attributes preferred for testability

## Open Questions

Things that couldn't be fully resolved:

1. **Token reset timezone**
   - What we know: Netro returns token_reset in ISO format
   - What's unclear: Is it UTC or local time?
   - Recommendation: Parse as naive datetime, test empirically

2. **Optimal pause threshold**
   - What we know: 100 tokens = ~33 polling cycles at 3 calls/cycle
   - What's unclear: User tolerance for paused polling
   - Recommendation: Make configurable in future if users complain

3. **Schema version detection**
   - What we know: Responses have meta.version field
   - What's unclear: How Netro uses this for versioning
   - Recommendation: Log version in debug, track for future changes

## Sources

### Primary (HIGH confidence)
- **Existing plugin.py** - Current implementation of `_make_api_call()` (lines 137-276)
- **docs/NETRO_API.md** - Complete API endpoint documentation
- **docs/API_NOTES.md** - API quirks and discoveries from live testing
- **.planning/research/MODULES.md** - Module organization patterns with NetroAPIClient design

### Secondary (MEDIUM confidence)
- [Design Pattern for Python API Client Libraries](https://bhomnick.net/design-pattern-python-api-client/) - Session management, class structure patterns
- [requests-ratelimiter PyPI](https://pypi.org/project/requests-ratelimiter/) - Persistence patterns for rate limit state
- [Indigo Plugin Guide](https://wiki.indigodomo.com/doku.php?id=indigo_2025.1_documentation:plugin_guide) - pluginPrefs persistence

### Tertiary (LOW confidence - patterns only)
- [Python API Client Best Practices 2025](https://realpython.com/api-integration-in-python/) - General patterns
- [Dataclasses vs TypedDict](https://hevalhazalkurt.medium.com/dataclasses-vs-pydantic-vs-typeddict-vs-namedtuple-in-python-85b8c03402ad) - Schema validation approach selection

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Using existing requests library and stdlib
- Architecture: HIGH - Based on working UK-Trains pattern and existing codebase
- Throttle management: HIGH - Requirements clearly specified, implementation straightforward
- Schema validation: MEDIUM - TypedDict approach is standard but warning-only validation is a design choice
- State persistence: HIGH - Indigo pluginPrefs is documented and proven

**Research date:** 2026-02-01
**Valid until:** 2026-03-01 (stable domain, 30-day validity)
