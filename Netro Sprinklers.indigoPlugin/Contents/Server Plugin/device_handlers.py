"""Device handlers for transforming API responses to Indigo state updates.

This module provides handler classes that transform Netro API responses into
state update dictionaries suitable for Indigo's updateStatesOnServer() method.

Handlers are responsible for:
- Parsing API response structure
- Transforming data to Indigo state format
- Providing sensible defaults for missing data
- Logging errors for malformed responses

Handlers do NOT:
- Make API calls (plugin coordinator does this)
- Import indigo (pure Python for testability)
- Modify devices directly (return state dicts instead)

Classes:
    SprinklerHandler: Handles sprinkler controller device state updates
    WhispererHandler: Handles Whisperer sensor device state updates

Example:
    >>> handler = SprinklerHandler(logger=my_logger)
    >>> states, is_online, device_data = handler.process_device_info(api_response, "ABC123")
    >>> dev.updateStatesOnServer(states)
"""

import logging
import time
from datetime import datetime, timezone
from operator import itemgetter
from typing import Any, Dict, List, Optional, Tuple

from constants import V2_ONLINE_STATUSES
from utils import get_key_from_dict

_MODULE_LOGGER = logging.getLogger(__name__)


__all__ = ["SprinklerHandler", "WhispererHandler", "ZoneHandler"]


class SprinklerHandler:
    """Handles state transformation for sprinkler controller devices.

    This handler transforms Netro API responses into Indigo state update
    dictionaries. It processes device info, schedules, and moisture data.

    Attributes:
        logger: Logger instance for error/debug output

    Example:
        >>> handler = SprinklerHandler(logger=plugin_logger)
        >>> states, is_online, dev_data = handler.process_device_info(response, serial)
        >>> if states:
        ...     dev.updateStatesOnServer(states)
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        """Initialize handler with optional logger.

        Args:
            logger: Logger instance for output (defaults to module logger)
        """
        self.logger = logger or logging.getLogger(__name__)

    # pylint: disable=too-many-locals
    def process_device_info(
        self,
        api_response: Dict[str, Any],
        serial: str,
        api_version: str = "1"
    ) -> Tuple[List[Dict[str, Any]], bool, Dict[str, Any]]:
        """Process device info API response.

        Transforms the device info API response into a list of state updates
        for Indigo. Extracts device status, token info, and basic properties.

        Handles both v1 and v2 response formats:
        - v1: status is ONLINE/OFFLINE, version is integer
        - v2: status includes WATERING/SLEEPING/POWEROFF, version is string "2.0",
              adds sw_version and battery_level fields

        Args:
            api_response: Response from api_client.get_device_info()
            serial: Device serial for logging context
            api_version: API version ("1" or "2")

        Returns:
            Tuple of:
            - List of state update dicts for updateStatesOnServer()
            - is_online: True if device reports an online status
            - device_data: Raw device dict for zone processing
        """
        try:
            reply_dict_data = api_response["data"]
            reply_dict_device = reply_dict_data["device"]
            reply_dict_meta = api_response.get("meta", {})

            # Determine online status — v2 has expanded status values
            device_status = reply_dict_device.get("status", "")
            if api_version == "2":
                is_online = device_status in V2_ONLINE_STATUSES
            else:
                is_online = device_status == "ONLINE"

            # API version value — v1 returns integer, v2 returns string like "2.0"
            api_ver_value = str(reply_dict_device.get("version", "0"))

            # Build update list for device states
            update_list = [
                {"key": "id", "value": reply_dict_device.get("serial", serial)},
                {"key": "api_version", "value": api_ver_value},
                {"key": "status", "value": get_key_from_dict("status", reply_dict_device)},
                {"key": "token_remaining", "value": reply_dict_meta.get("token_remaining", 0)},
                {"key": "time", "value": reply_dict_meta.get("time", "unknown")},
                {"key": "last_active", "value": reply_dict_device.get("last_active", "unknown")},
                {"key": "token_reset", "value": reply_dict_meta.get("token_reset", "unknown")},
                {"key": "name", "value": reply_dict_device.get("name", "Unknown")},
            ]

            # V2 adds sw_version (firmware) field
            if api_version == "2" and "sw_version" in reply_dict_device:
                update_list.append(
                    {"key": "sw_version", "value": reply_dict_device["sw_version"]}
                )

            return (update_list, is_online, reply_dict_device)

        except (KeyError, TypeError, AttributeError) as exc:
            self.logger.error(f"Malformed device info for {serial}: {exc}")
            # Return minimal update marking device in error state
            error_states = [
                {"key": "status", "value": "ERROR"},
                {"key": "id", "value": serial},
            ]
            return (error_states, False, {})

    def process_schedules(
        self,
        api_response: Dict[str, Any],
        api_version: str = "1"
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Process schedules API response.

        Transforms the schedules API response into state updates for active
        and upcoming schedules.

        Handles both v1 and v2 timestamp formats:
        - v1: start_time is millisecond Unix timestamp (number or string)
        - v2: start_time is ISO 8601 string, has local_start_time/local_end_time

        Args:
            api_response: Response from api_client.get_schedules()
            api_version: API version ("1" or "2")

        Returns:
            Tuple of:
            - List of state update dicts for updateStatesOnServer()
            - active_schedule_name: Name of currently executing schedule, or None
        """
        update_list: List[Dict[str, Any]] = []
        active_schedule_name: Optional[str] = None

        try:
            all_schedules_data = api_response["data"]
            all_schedules = all_schedules_data["schedules"]

            current_schedule_dict: Optional[Dict[str, Any]] = None
            next_schedule_dict: Optional[Dict[str, Any]] = None
            earliest_start_time: Optional[float] = None

            for sch_dict in all_schedules:
                # Find currently executing schedule (guard against stale
                # EXECUTING entries left behind by Netro cloud)
                if self._schedule_actually_executing(sch_dict, api_version):
                    current_schedule_dict = sch_dict
                elif sch_dict.get("status") == "EXECUTING":
                    self.logger.debug(
                        "Ignoring stale EXECUTING schedule id=%s zone=%s end_time=%s",
                        sch_dict.get("id"), sch_dict.get("zone"), sch_dict.get("end_time"),
                    )
                # Find next valid (upcoming) schedule with earliest start time
                elif sch_dict.get("status") == "VALID":
                    start_time = self._parse_schedule_sort_key(
                        sch_dict.get("start_time", 0), api_version
                    )
                    if earliest_start_time is None or start_time < earliest_start_time:
                        earliest_start_time = start_time
                        next_schedule_dict = sch_dict

            # Update current/active schedule states
            if current_schedule_dict:
                update_list.append(
                    {"key": "activeZone", "value": current_schedule_dict.get("zone", 0)}
                )
                active_schedule_name = current_schedule_dict.get("source", "Unknown").title()
                update_list.append({"key": "activeSchedule", "value": active_schedule_name})
            else:
                update_list.append({"key": "activeSchedule", "value": "No active schedule"})
                update_list.append({"key": "activeZone", "value": 0})

            # Update next schedule states
            if next_schedule_dict:
                update_list.extend(
                    self._format_next_schedule(next_schedule_dict, api_version)
                )
            else:
                update_list.extend(self._no_upcoming_schedule())

            return (update_list, active_schedule_name)

        except (KeyError, TypeError) as exc:
            self.logger.error(f"Error parsing schedules: {exc}")
            return (
                [{"key": "activeSchedule", "value": "Error getting schedule"}],
                None
            )

    @staticmethod
    def _parse_schedule_sort_key(raw_value: Any, api_version: str = "1") -> float:
        """Parse a schedule timestamp into a sortable float value.

        Args:
            raw_value: Timestamp — ms integer/string (v1) or ISO 8601 string (v2)
            api_version: API version ("1" or "2")

        Returns:
            Float timestamp for sorting (Unix seconds)
        """
        try:
            if api_version == "2":
                # V2: ISO 8601 string → Unix timestamp for sorting
                dt = datetime.fromisoformat(str(raw_value))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.timestamp()
            else:
                # V1: Millisecond timestamp (may be string)
                return float(raw_value) if isinstance(raw_value, str) else float(raw_value)
        except (ValueError, TypeError) as exc:
            _MODULE_LOGGER.debug(
                "Unparseable Netro timestamp %r (api v%s): %s",
                raw_value, api_version, exc,
            )
            return float('inf')  # Unparseable schedules sort last (never "next")

    @staticmethod
    def _schedule_actually_executing(
        schedule: Dict[str, Any],
        api_version: str = "1",
    ) -> bool:
        """Check if an EXECUTING schedule is truly still running.

        Why: Netro cloud sometimes leaves a completed schedule marked
        EXECUTING long after its end_time has passed (seen with MANUAL
        runs). Trusting status alone leaves the controller's activeZone
        and the zone's isIrrigating state stuck on True for days.

        Returns True if status is "EXECUTING" and either the end_time
        is missing/unparseable (fall back to trusting status) or the
        end_time is in the future. Returns False for a "stale" EXECUTING
        whose end_time has already passed.
        """
        if not isinstance(schedule, dict):
            return False  # malformed entry — caller should not act on it
        if schedule.get("status") != "EXECUTING":
            return False
        end_raw = schedule.get("end_time")
        if end_raw in (None, ""):
            return True  # can't verify — trust cloud
        end_seconds = SprinklerHandler._parse_schedule_sort_key(end_raw, api_version)
        if end_seconds == float('inf'):
            return True  # unparseable — trust cloud
        if api_version != "2":
            # V1 returned raw ms; convert to seconds for comparison
            end_seconds = end_seconds / 1000.0
        return end_seconds > time.time()

    def _format_next_schedule(
        self,
        schedule_dict: Dict[str, Any],
        api_version: str = "1"
    ) -> List[Dict[str, Any]]:
        """Format next schedule info as state updates.

        Args:
            schedule_dict: Schedule dict from API response
            api_version: API version ("1" or "2")

        Returns:
            List of state update dicts for next schedule
        """
        updates: List[Dict[str, Any]] = []

        if api_version == "2":
            # V2: Use local_start_time if available, otherwise parse ISO 8601
            local_start = schedule_dict.get("local_start_time")
            local_date = schedule_dict.get("local_date", "")
            if local_start and local_date:
                start_time_str = f"{local_date} {local_start}"
            else:
                try:
                    start_dt = datetime.fromisoformat(str(schedule_dict.get("start_time", "")))
                    start_time_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    start_time_str = "Invalid timestamp"
        else:
            # V1: Convert millisecond timestamp to readable format
            start_time_raw = schedule_dict.get("start_time", 0)
            try:
                start_time_ms = (
                    float(start_time_raw)
                    if isinstance(start_time_raw, str)
                    else start_time_raw
                )
                start_time_dt = datetime.fromtimestamp(start_time_ms / 1000.0)
                start_time_str = start_time_dt.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError, OSError):
                start_time_str = "Invalid timestamp"

        updates.append({"key": "nextScheduleTime", "value": start_time_str})
        updates.append({
            "key": "nextScheduleZone",
            "value": schedule_dict.get("zone_name", f"Zone {schedule_dict.get('zone', '?')}")
        })
        updates.append({
            "key": "nextScheduleSource",
            "value": schedule_dict.get("source", "Unknown").title()
        })

        # Duration: v1 has duration in seconds, v2 needs calculation from start/end
        if api_version == "2":
            duration_min = self._calc_v2_duration(schedule_dict)
        else:
            duration_sec = schedule_dict.get("duration") or 0
            duration_min = int(duration_sec / 60)
        updates.append({"key": "nextScheduleDuration", "value": duration_min})

        return updates

    def _calc_v2_duration(self, schedule_dict: Dict[str, Any]) -> int:
        """Calculate schedule duration in minutes from v2 start/end times.

        Args:
            schedule_dict: V2 schedule dict with ISO 8601 start_time and end_time

        Returns:
            Duration in minutes, or 0 if calculation fails
        """
        try:
            start_str = schedule_dict.get("start_time", "")
            end_str = schedule_dict.get("end_time", "")
            if start_str and end_str:
                start_dt = datetime.fromisoformat(str(start_str))
                end_dt = datetime.fromisoformat(str(end_str))
                delta = end_dt - start_dt
                return max(0, int(delta.total_seconds() / 60))
        except (ValueError, TypeError) as exc:
            self.logger.warning(
                f"Could not calculate v2 schedule duration from "
                f"start='{schedule_dict.get('start_time')}' "
                f"end='{schedule_dict.get('end_time')}': {exc}"
            )
        return 0

    def _no_upcoming_schedule(self) -> List[Dict[str, Any]]:
        """Return state updates for no upcoming schedule.

        Returns:
            List of state update dicts with default values
        """
        return [
            {"key": "nextScheduleTime", "value": "No upcoming schedule"},
            {"key": "nextScheduleZone", "value": "None"},
            {"key": "nextScheduleSource", "value": "None"},
            {"key": "nextScheduleDuration", "value": 0},
        ]

    def process_moistures(
        self,
        api_response: Dict[str, Any],
        api_version: str = "1"
    ) -> List[Dict[str, Any]]:
        """Process moistures API response.

        Transforms the moistures API response into zone moisture state updates.
        Filters to only the most recent date's readings.

        Args:
            api_response: Response from api_client.get_moistures()

        Returns:
            List of state update dicts for zone moisture levels
        """
        try:
            jdata = api_response["data"]
            jmoistures = jdata["moistures"]

            # Guard against empty moistures list
            if not jmoistures:
                self.logger.debug("No moisture data available from API")
                return []

            # Sort by ID to get most recent first
            jmoistures.sort(key=lambda x: x.get("id", 0), reverse=True)

            # Get all moistures from the most recent date
            max_date = jmoistures[0]["date"]
            max_date_moistures = [m for m in jmoistures if m.get("date") == max_date]

            # Build state updates for each zone
            current_moistures: List[Dict[str, Any]] = []
            for moisture_data in max_date_moistures:
                zone = moisture_data.get("zone", 0)
                state_dict = {
                    "key": f"zone_{zone}_moisture",
                    "value": str(moisture_data.get("moisture", 0))
                }
                current_moistures.append(state_dict)

            return current_moistures

        except (KeyError, TypeError, IndexError, AttributeError) as exc:
            self.logger.error(f"Error parsing moistures: {exc}")
            return []

    def extract_zone_info(
        self,
        device_data: Dict[str, Any],
        max_zone_runtime: int
    ) -> Tuple[str, List[str], List[Dict[str, Any]]]:
        """Extract zone information for pluginProps update.

        Processes the zones array from device data to build zone names,
        max durations, and zone data for dropdown lists.

        Args:
            device_data: Device dict containing zones array
            max_zone_runtime: Maximum zone runtime from plugin prefs

        Returns:
            Tuple of:
            - zone_names: Comma-separated zone names string
            - max_durations: List of max duration strings per zone
            - zones_data: List of zone dicts for JSON storage
        """
        zone_names = ""
        max_durations: List[str] = []
        zones_data: List[Dict[str, Any]] = []

        try:
            zones = device_data.get("zones", [])
            for zone in sorted(zones, key=itemgetter("ith")):
                # Build comma-separated zone names
                zone_names += f", {zone['name']}" if zone_names else zone["name"]

                # Set max duration to plugin max for enabled zones, 0 for disabled
                max_duration = max_zone_runtime if zone.get("enabled", False) else 0
                max_durations.append(str(max_duration))

                # Store zone ID and name for dropdown lists
                zones_data.append({
                    "id": zone.get("ith", 0),
                    "name": zone.get("name", f"Zone {zone.get('ith', '?')}"),
                    "enabled": zone.get("enabled", False)
                })

        except (KeyError, TypeError) as exc:
            self.logger.error(f"Error extracting zone info: {exc}")

        return (zone_names, max_durations, zones_data)

    def process_events(
        self,
        api_response: Dict[str, Any],
        last_event_id: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Process events API response (v2 only).

        Parses the events array and filters to only events newer than
        the last seen event ID.

        Args:
            api_response: Response from api_client.get_events()
            last_event_id: ID of the last event we processed (0 = first run)

        Returns:
            Tuple of:
            - List of new event dicts: {"id": int, "event": int, "time": str, "message": str}
            - highest_event_id: The highest event ID seen (for tracking)
        """
        try:
            events_data = api_response.get("data", {})
            events = events_data.get("events", [])

            if not events or not isinstance(events, list):
                return ([], last_event_id)

            # Filter to events newer than last seen
            new_events = [e for e in events if e.get("id", 0) > last_event_id]

            # Find highest event ID
            highest_id = max(
                (e.get("id", 0) for e in events),
                default=last_event_id
            )

            return (new_events, highest_id)

        except (KeyError, TypeError, AttributeError) as exc:
            self.logger.error(f"Error parsing events: {exc}")
            return ([], last_event_id)


# pylint: disable=too-few-public-methods
class WhispererHandler:
    """Handles state transformation for Whisperer sensor devices.

    This handler transforms Netro API responses into Indigo state update
    dictionaries for Whisperer soil moisture sensors.

    Attributes:
        logger: Logger instance for error/debug output

    Example:
        >>> handler = WhispererHandler(logger=plugin_logger)
        >>> states, has_readings = handler.process_sensor_data(response, serial)
        >>> if states:
        ...     dev.updateStatesOnServer(states)
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        """Initialize handler with optional logger.

        Args:
            logger: Logger instance for output (defaults to module logger)
        """
        self.logger = logger or logging.getLogger(__name__)

    # pylint: disable=too-many-locals
    def process_sensor_data(
        self,
        api_response: Dict[str, Any],
        serial: str,
        api_version: str = "1"
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """Process sensor data API response.

        Transforms the sensor data API response into state updates for
        Whisperer devices. Extracts the most recent sensor reading.

        Args:
            api_response: Response from api_client.get_sensor_data()
            serial: Device serial for logging context

        Returns:
            Tuple of:
            - List of state update dicts for updateStatesOnServer()
            - has_readings: True if sensor has recent readings
        """
        try:
            jdata = api_response["data"]
            jmeta = api_response.get("meta", {})
            sensor_readings = jdata.get("sensor_data", [])

            # Guard against empty sensor readings list
            if not sensor_readings:
                self.logger.info(
                    f"No sensor data available from API for device {serial} "
                    "(sensor offline or not reporting)"
                )
                # Return minimal meta-only update
                meta_updates = [
                    {"key": "token_remaining", "value": jmeta.get("token_remaining", 0)},
                    {"key": "token_reset", "value": jmeta.get("token_reset", "unknown")},
                    {"key": "api_last_active", "value": jmeta.get("last_active", "unknown")},
                    {"key": "time", "value": jmeta.get("time", "unknown")},
                ]
                return (meta_updates, False)

            # Sort by ID to get most recent first
            sensor_readings.sort(key=lambda x: x.get("id", 0), reverse=True)
            dev_states = sensor_readings[0]
            self.logger.debug(f"Sensor reading: {dev_states}")

            # Build state updates from sensor reading
            moisture = dev_states.get("moisture", 0)
            key_values_list: List[Dict[str, Any]] = [
                {
                    "key": "sensorValue",
                    "value": moisture,
                    "uiValue": f"{moisture:.1f} %"
                },
                {"key": "humidity", "value": moisture},
                {"key": "soilMoisture", "value": moisture},
                {"key": "temperature", "value": dev_states.get("celsius", 0)},
                {"key": "soilTemperature", "value": dev_states.get("celsius", 0)},
                {"key": "sunlight", "value": dev_states.get("sunlight", 0)},
                {"key": "readingID", "value": dev_states.get("id", 0)},
                {"key": "readingTime", "value": dev_states.get("time", "unknown")},
                {"key": "readingLocalDate", "value": dev_states.get("local_date", "unknown")},
                {"key": "readingLocalTime", "value": dev_states.get("local_time", "unknown")},
                {"key": "id", "value": dev_states.get("id", 0)},
                {"key": "token_remaining", "value": jmeta.get("token_remaining", 0)},
                {"key": "token_reset", "value": jmeta.get("token_reset", "unknown")},
                {"key": "api_last_active", "value": jmeta.get("last_active", "unknown")},
                {"key": "sensor_last_active", "value": dev_states.get("time", "unknown")},
                {"key": "time", "value": jmeta.get("time", "unknown")},
                {"key": "batteryLevel", "value": dev_states.get("battery_level", 0)},
            ]

            return (key_values_list, True)

        except KeyError as exc:
            self.logger.error(
                f"Missing expected field in sensor data for device {serial}: {exc}"
            )
            # Return minimal update
            return ([], False)
        except (TypeError, AttributeError) as exc:
            self.logger.error(f"Malformed sensor data for {serial}: {exc}")
            return ([], False)


class ZoneHandler:
    """Handles state transformation for individual zone devices.

    Transforms Netro API responses into per-zone Indigo state updates.
    All data comes from the parent controller's API calls — no extra
    API requests needed.

    Attributes:
        logger: Logger instance for error/debug output
    """

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)

    def process_zone_schedules(self, api_response, zone_number, api_version="1"):
        """Process schedules response for a single zone.

        Extracts isIrrigating, last watering, and next watering states
        for the given zone number.

        Args:
            api_response: Response from api_client.get_schedules()
            zone_number: Zone ith number (1-based)
            api_version: API version ("1" or "2")

        Returns:
            List of state update dicts for updateStatesOnServer()
        """
        is_irrigating = False
        last_schedule = None
        next_schedule = None
        next_start_sort = None

        try:
            schedules = api_response["data"]["schedules"]
            zone_schedules = [s for s in schedules if s.get("zone") == zone_number]

            for sch in zone_schedules:
                status = sch.get("status", "")
                if status == "EXECUTING":
                    if SprinklerHandler._schedule_actually_executing(sch, api_version):
                        is_irrigating = True
                    else:
                        # Stale EXECUTING (end_time in past) — Netro left it stuck.
                        # Demote to a completed-schedule record so the zone's
                        # lastWatering* fields still show when the run happened.
                        # Overwrite status so the UI doesn't say "Last watering:
                        # Executing" for a watering that has actually ended.
                        self.logger.debug(
                            "Ignoring stale EXECUTING schedule id=%s zone=%s end_time=%s",
                            sch.get("id"), sch.get("zone"), sch.get("end_time"),
                        )
                        if last_schedule is None or sch.get("id", 0) > last_schedule.get("id", 0):
                            last_schedule = dict(sch)
                            last_schedule["status"] = "EXECUTED"
                elif status in ("EXECUTED", "CANCELLED"):
                    if last_schedule is None or sch.get("id", 0) > last_schedule.get("id", 0):
                        last_schedule = sch
                elif status == "VALID":
                    sort_key = SprinklerHandler._parse_schedule_sort_key(
                        sch.get("start_time", 0), api_version
                    )
                    if next_start_sort is None or sort_key < next_start_sort:
                        next_start_sort = sort_key
                        next_schedule = sch

        except (KeyError, TypeError) as exc:
            self.logger.error(f"Error parsing zone schedules: {exc}")

        states = [{"key": "isIrrigating", "value": is_irrigating}]
        states.extend(self._format_last_watering(last_schedule, api_version))
        states.extend(self._format_next_watering(next_schedule, api_version))
        return states

    def _format_last_watering(self, schedule, api_version="1"):
        """Format last watering states from a schedule dict."""
        if not schedule:
            return [
                {"key": "lastWateringStart", "value": ""},
                {"key": "lastWateringEnd", "value": ""},
                {"key": "lastWateringSource", "value": ""},
                {"key": "lastWateringStatus", "value": ""},
            ]
        return [
            {"key": "lastWateringStart", "value": self._format_timestamp(schedule.get("start_time"), api_version)},
            {"key": "lastWateringEnd", "value": self._format_timestamp(schedule.get("end_time"), api_version)},
            {"key": "lastWateringSource", "value": schedule.get("source", "Unknown").title()},
            {"key": "lastWateringStatus", "value": schedule.get("status", "Unknown").title()},
        ]

    def _format_next_watering(self, schedule, api_version="1"):
        """Format next watering states from a schedule dict."""
        if not schedule:
            return [
                {"key": "nextWateringStart", "value": ""},
                {"key": "nextWateringEnd", "value": ""},
                {"key": "nextWateringSource", "value": ""},
            ]
        return [
            {"key": "nextWateringStart", "value": self._format_timestamp(schedule.get("start_time"), api_version)},
            {"key": "nextWateringEnd", "value": self._format_timestamp(schedule.get("end_time"), api_version)},
            {"key": "nextWateringSource", "value": schedule.get("source", "Unknown").title()},
        ]

    @staticmethod
    def _format_timestamp(raw_value, api_version="1"):
        """Format a timestamp for display."""
        if not raw_value:
            return ""
        try:
            if api_version == "2":
                dt = datetime.fromisoformat(str(raw_value))
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            else:
                ms = float(raw_value) if isinstance(raw_value, str) else float(raw_value)
                dt = datetime.fromtimestamp(ms / 1000.0)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError, OSError):
            return ""

    def process_zone_moisture(self, api_response, zone_number):
        """Extract moisture for a single zone from moistures response.

        Uses the most recent date's reading for the zone.

        Args:
            api_response: Response from api_client.get_moistures()
            zone_number: Zone ith number (1-based)

        Returns:
            A list containing a single
            ``{"key": "moisture", "value": int, "uiValue": "<n>%"}`` dict when
            a reading for ``zone_number`` exists on the most recent date.
            Returns ``[]`` (empty list) when:
              - ``moistures`` is empty or missing,
              - no entry matches ``zone_number`` on the most-recent date, or
              - the response shape triggers ``KeyError``/``TypeError``/
                ``IndexError`` (the error is logged via ``self.logger.error``,
                not raised).

            The empty-list shape signals "no forecast data this cycle" so the
            caller can skip writing ``moistureForecast`` rather than persisting
            a fake 0%.
        """
        try:
            moistures = api_response["data"]["moistures"]
            if not moistures:
                return []

            moistures_sorted = sorted(moistures, key=lambda x: x.get("id", 0), reverse=True)
            max_date = moistures_sorted[0].get("date")

            for m in moistures_sorted:
                if m.get("zone") == zone_number and m.get("date") == max_date:
                    val = m.get("moisture", 0)
                    return [{"key": "moisture", "value": val, "uiValue": f"{val}%"}]

            return []

        except (KeyError, TypeError, IndexError) as exc:
            self.logger.error(f"Error parsing zone moisture: {exc}")
            return []

    def extract_zone_states(self, zones, zone_number):
        """Extract enabled and smartMode for a single zone from info data.

        Args:
            zones: List of zone dicts from device_data["zones"]
            zone_number: Zone ith number (1-based)

        Returns:
            List of state update dicts for updateStatesOnServer()
        """
        for zone in zones:
            if zone.get("ith") == zone_number:
                return [
                    {"key": "enabled", "value": zone.get("enabled", False)},
                    {"key": "smartMode", "value": zone.get("smart", "Unknown")},
                ]
        return [
            {"key": "enabled", "value": False},
            {"key": "smartMode", "value": "Unknown"},
        ]
