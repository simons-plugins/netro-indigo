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
from datetime import datetime, timezone
from operator import itemgetter
from typing import Any, Dict, List, Optional, Tuple

from constants import V2_ONLINE_STATUSES
from utils import get_key_from_dict


__all__ = ["SprinklerHandler", "WhispererHandler"]


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
                {"key": "address", "value": get_key_from_dict("macAddress", reply_dict_device)},
                {"key": "model", "value": get_key_from_dict("model", reply_dict_device)},
                {"key": "paused", "value": get_key_from_dict("paused", reply_dict_device)},
                {
                    "key": "scheduleModeType",
                    "value": get_key_from_dict("scheduleModeType", reply_dict_device)
                },
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
                # Find currently executing schedule
                if sch_dict.get("status") == "EXECUTING":
                    current_schedule_dict = sch_dict
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
        except (ValueError, TypeError):
            return float('inf')  # Unparseable schedules sort last (never "next")

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
