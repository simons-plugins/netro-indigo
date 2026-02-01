#! /usr/bin/env python
# -*- coding: utf-8 -*-
# pylint: disable=too-many-lines
"""Netro Smart Sprinkler Controller Plugin for Indigo.

This plugin integrates Netro smart irrigation controllers with Indigo home automation.
It provides real-time monitoring and control of sprinkler zones, schedules, moisture
levels, and weather integration through the Netro Public API (NPA).

Features:
    - Control individual zones remotely
    - Monitor moisture levels per zone
    - View current and upcoming watering schedules
    - Report local weather to improve Netro's smart scheduling
    - Set rain delays and standby modes
    - Support for Whisperer soil moisture sensors
    - Automatic rate limit handling (2000 API calls/day)

Architecture:
    - Uses Netro Public API v1 (http://api.netrohome.com/npa/v1/)
    - Authentication via device serial number
    - Polling interval: 3+ minutes (configurable)
    - Automatic throttle management on HTTP 429 responses
    - Real-time state updates via concurrent polling thread

Requirements:
    - Netro controller serial number
    - Active internet connection
    - Python 3.10+ with requests library (auto-installed by Indigo)

API Documentation:
    See NETRO_API.md for complete API endpoint documentation
    See API_NOTES.md for known quirks and limitations

Copyright (c) 2014, Perceptive Automation, LLC. All rights reserved.
http://www.indigodomo.com
"""

import json
import copy
import traceback
from operator import itemgetter
from datetime import datetime, timedelta, date

import indigo
import requests

# Import from extracted modules
from constants import (
    MAX_ZONE_DURATION_SECONDS,
    DEFAULT_API_TIMEOUT_SECONDS,
    MINIMUM_POLLING_INTERVAL_MINUTES,
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
    ZONE_START_ENDPOINT,
    OPERATIONAL_ERROR_EVENTS,
    COMM_ERROR_EVENTS,
)
from exceptions import ThrottleDelayError
from utils import get_key_from_dict


################################################################################
# pylint: disable=too-many-public-methods,too-many-instance-attributes
class Plugin(indigo.PluginBase):
    """Main plugin class for Netro Sprinkler Controller integration.

    This class manages communication with the Netro API, device state updates,
    and user actions. It inherits from indigo.PluginBase and implements the
    standard Indigo plugin lifecycle methods.

    Attributes:
        serial_number: Netro controller serial number for API authentication
        pollingInterval: Minutes between API polls (default 3, minimum 3)
        timeout: API request timeout in seconds (default 5)
        maxZoneRunTime: Maximum allowed zone runtime in seconds (default 3600)
        throttle_next_call: Datetime when throttle period expires (None if not throttled)
        person: Dict containing Netro user and device data from API
        netro_devices: List of Netro devices from API response
        triggerDict: Dict of active Indigo triggers for event handling
    """

    ########################################
    # pylint: disable=invalid-name
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        super().__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
        # Used to control when to show connection errors (vs just repeated retries)
        self._displayed_connection_error = False
        self.pluginId = pluginId
        self.debug = pluginPrefs.get("showDebugInfo", False)
        self.pollingInterval = int(pluginPrefs.get("pollingInterval", MINIMUM_POLLING_INTERVAL_MINUTES))
        self.timeout = int(pluginPrefs.get("apiTimeout", DEFAULT_API_TIMEOUT_SECONDS))

        self.unused_devices = {}
        # Netro API uses serial number for authentication (not bearer tokens)
        # Serial numbers are configured per-device, not at plugin level
        self.maxZoneRunTime = int(pluginPrefs.get("maxZoneRunTime", MAX_ZONE_DURATION_SECONDS))

        # HTTP headers for JSON requests
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        self.triggerDict = {}

        # Initialize throttle and weather update tracking
        self.throttle_next_call = None
        self._next_weather_update = datetime.now()

        # Initialize data structures populated by API calls
        self.person = {}
        self.netro_devices = []
        self.serialNo = None
        self.key_val_list = []


    ########################################
    # Internal helper methods
    ########################################

    # pylint: disable=too-many-branches,too-many-statements
    def _make_api_call(self, url, request_method="get", data=None):
        """Make an API call to Netro API with proper error handling.

        Args:
            url: Full URL to call
            request_method: HTTP method (get, post, put)
            data: Optional data dict for POST/PUT requests

        Returns:
            JSON response data or True for 204 responses

        Raises:
            ThrottleDelayError: If API calls are throttled
        """
        # Check if we're in a throttle period
        if self.throttle_next_call and datetime.now() < self.throttle_next_call:
            raise ThrottleDelayError(
                f"api calls throttled until {self.throttle_next_call:%H:%M:%S}"
            )
        elif self.throttle_next_call:
            # Throttle period has expired, reset it
            self.throttle_next_call = None
            self.logger.info("api rate limit throttle period has expired - resuming normal operation")

        try:
            self.logger.debug(f"API call: {request_method.upper()} {url}")

            # Select HTTP method
            if request_method == "put":
                method = requests.put
            elif request_method == "post":
                method = requests.post
            else:
                method = requests.get

            # Make the request
            if data and request_method in ["put", "post"]:
                r = method(url, data=json.dumps(data), headers=self.headers, timeout=self.timeout)
            else:
                r = method(url, headers=self.headers, timeout=self.timeout)

            # Handle response
            if r.status_code == 200:
                return_val = r.json()
                self._displayed_connection_error = False
            elif r.status_code == 204:
                return_val = True
                self._displayed_connection_error = False
            else:
                r.raise_for_status()
                return_val = None

            return return_val
        except requests.exceptions.ConnectionError as exc:
            if not self._displayed_connection_error:
                self.logger.error("Connection to Netro API server failed. Will continue to retry silently.")
                self._displayed_connection_error = True
            raise exc
        except requests.exceptions.ReadTimeout as exc:
            if not self._displayed_connection_error:
                self.logger.error(
                    "Unable to contact device - the controller may be offline. "
                    "Will continue to retry silently.")
                self._displayed_connection_error = True
            raise exc
        except requests.exceptions.Timeout as exc:
            if not self._displayed_connection_error:
                self.logger.error("Connection to Netro API server failed. Will continue to retry silently.")
                self._displayed_connection_error = True
            raise exc
        except requests.exceptions.HTTPError as exc:
            # Check for Netro-specific rate limit error (error code 3)
            # Netro returns HTTP 400 with JSON error response, not HTTP 429
            try:
                error_data = exc.response.json()
                if error_data.get("status") == "ERROR":
                    errors = error_data.get("errors", [])
                    meta = error_data.get("meta", {})

                    # Check for rate limit error (code 3)
                    for error in errors:
                        if error.get("code") == 3:
                            # Extract reset time from meta
                            token_reset = meta.get("token_reset", "")
                            token_remaining = meta.get("token_remaining", 0)

                            # Parse reset time (format: "2026-02-01T00:00:00")
                            try:
                                reset_dt = datetime.strptime(token_reset, "%Y-%m-%dT%H:%M:%S")
                                self.throttle_next_call = reset_dt
                                # Format token message based on positive/negative
                                if token_remaining >= 0:
                                    token_msg = f"{token_remaining} tokens remaining"
                                else:
                                    token_msg = f"{abs(token_remaining)} tokens over limit"
                                error_msg = (
                                    f"netro api rate limit exceeded ({token_msg}), "
                                    f"calls will resume after {reset_dt.strftime('%Y-%m-%d %H:%M:%S')}, "
                                    f"consider increasing polling interval in plugin preferences"
                                )
                            except (ValueError, TypeError):
                                # Fallback to fixed delay if we can't parse reset time
                                self.throttle_next_call = datetime.now() + timedelta(minutes=THROTTLE_LIMIT_MINUTES)
                                error_msg = (
                                    f"netro api rate limit exceeded, "
                                    f"will retry in {THROTTLE_LIMIT_MINUTES} minutes, "
                                    f"consider increasing polling interval"
                                )

                            self.logger.warning(error_msg)
                            self._fireTrigger("rateLimitExceeded")
                            raise ThrottleDelayError(error_msg)
                        elif error.get("code") == 1:
                            # Invalid key error
                            self.logger.error(
                                f"invalid netro serial number: {error.get('message')}, "
                                f"verify the serial number in your device configuration"
                            )
            except (ValueError, AttributeError):
                # If we can't parse JSON, check for HTTP 429 as fallback
                if exc.response.status_code == 429:
                    self.throttle_next_call = datetime.now() + timedelta(minutes=THROTTLE_LIMIT_MINUTES)
                    error_msg = (
                        f"api rate limit exceeded (http 429), "
                        f"will retry in {THROTTLE_LIMIT_MINUTES} minutes"
                    )
                    self.logger.warning(error_msg)
                    self._fireTrigger("rateLimitExceeded")
                    raise ThrottleDelayError(error_msg)
            raise exc
        except ThrottleDelayError:
            # Already logged when raised, just re-raise to propagate
            raise
        except Exception as exc:
            self.logger.error(
                f"Connection to Netro API server failed with exception: {exc.__class__.__name__}. "
                f"Check the log file for full details.")
            self.logger.debug(
                f"Connection to Netro API server failed with exception:\n{traceback.format_exc(10)}")
            raise exc
    ########################################
    def _get_device_dict(self, dev_id):
        """Get device dictionary from cached person data by device ID.

        Args:
            dev_id: Device ID (Netro serial number)

        Returns:
            Dict of device data if found, None otherwise
        """
        dev_list = [dev_dict for dev_dict in self.person["devices"] if dev_dict["id"] == dev_id]
        if len(dev_list):
            return dev_list[0]
        else:
            return None



    ########################################
    def _get_zone_dict(self, dev_id, zoneNumber):
        """Get zone dictionary from device by zone number.

        Args:
            dev_id: Device ID (Netro serial number)
            zoneNumber: Zone index number (1-based)

        Returns:
            Dict of zone data if found, None otherwise
        """
        dev_dict = self._get_device_dict(dev_id)
        if dev_dict:
            zone_list = [zone_dict for zone_dict in dev_dict["zones"] if zone_dict["ith"] == zoneNumber]
            if len(zone_list):
                return zone_list[0]
        return None

    ########################################
    # pylint: disable=too-many-branches,too-many-statements,too-many-locals,too-many-nested-blocks
    def _update_from_netro(self):
        """Update all Indigo devices from Netro API data.

        This method is called periodically by the concurrent thread to poll
        the Netro API and update device states in Indigo. It handles:
        - Sprinkler controller status and configuration
        - Current and upcoming schedules
        - Moisture levels per zone
        - Whisperer sensor readings
        - Token count warnings

        The method processes all enabled devices of type 'sprinkler' and
        'Whisperer', making API calls as needed to fetch current data.

        Exceptions are caught and logged without interrupting the polling cycle.
        """
        self.logger.debug("_update_from_netro")
        try:
            for dev in [s for s in indigo.devices.iter(filter="self") if s.enabled]:
                # Update defined Netro controllers
                if dev.deviceTypeId == "sprinkler":
                    try:
                        # Get device info using serial number from device address
                        reply_dict = self._make_api_call(
                            f"{DEVICE_INFO_ENDPOINT}?key={dev.address}")

                        reply_dict_data = reply_dict["data"]
                        reply_dict_device = reply_dict_data["device"]
                        reply_dict_meta = reply_dict["meta"]

                        # Create a dict of devices containing only single device
                        # Insert Netro serial number into dict as "id"
                        netroSerial = reply_dict_device["serial"]
                        reply_dict_device_serial = {"id": netroSerial}

                        # Insert on key based on "status"
                        if reply_dict_device["status"] == "ONLINE":
                            reply_dict_device_on = {"on": "true"}
                        else:
                            reply_dict_device_on = {"on": "false"}

                        reply_dict_device.update(reply_dict_device_serial)
                        reply_dict_device.update(reply_dict_meta)
                        reply_dict_device.update(reply_dict_device_on)
                        ls_reply_dict_devices = []
                        ls_reply_dict_devices.append(reply_dict_device)

                        self.person = {"id": netroSerial, "devices": ls_reply_dict_devices}
                        self.netro_devices = self.person["devices"]
                        self.logger.debug(self.netro_devices)

                        # Build update list for device states
                        update_list = [
                            {"key": "id", "value": reply_dict_device["id"]},
                            {"key": "api_version", "value": reply_dict_device["version"]},
                            {"key": "address",
                             "value": get_key_from_dict("macAddress", reply_dict_device)},
                            {"key": "model", "value": get_key_from_dict("model", reply_dict_device)},
                            {"key": "paused", "value": get_key_from_dict("paused", reply_dict_device)},
                            {"key": "scheduleModeType",
                             "value": get_key_from_dict("scheduleModeType", reply_dict_device)},
                            {"key": "status",
                             "value": get_key_from_dict("status", reply_dict_device)}
                        ]

                        # "status" is ONLINE or OFFLINE - if the latter it's unplugged or
                        # otherwise can't communicate with the cloud. Note: it often takes
                        # a REALLY long time for the API to return OFFLINE, sometimes never.
                        if dev.states["status"] == "OFFLINE":
                            dev.setErrorStateOnServer('unavailable')
                        else:
                            dev.setErrorStateOnServer('')

                        update_list.append(
                            {"key": "token_remaining",
                             'value': reply_dict_device["token_remaining"]})
                        update_list.append({"key": "time", 'value': reply_dict_device["time"]})
                        update_list.append(
                            {"key": "last_active", 'value': reply_dict_device["last_active"]})
                        update_list.append(
                            {"key": "token_reset", 'value': reply_dict_device["token_reset"]})
                        update_list.append({"key": "name", "value": reply_dict_device["name"]})

                        # Warn if API tokens are running low - parse defensively
                        try:
                            tokens_remaining = int(reply_dict_device.get("token_remaining", 2000))
                        except (ValueError, TypeError):
                            tokens_remaining = 2000
                            self.logger.debug("invalid token_remaining value from api, using default 2000")

                        try:
                            token_reset = str(reply_dict_device.get('token_reset', 'unknown'))
                        except (ValueError, TypeError):
                            token_reset = 'unknown'

                        # Calculate calls per polling cycle (info + schedules + moistures = 3)
                        calls_per_cycle = 3
                        try:
                            cycles_remaining = tokens_remaining // calls_per_cycle
                            hours_remaining = (cycles_remaining * self.pollingInterval) / 60
                        except (ZeroDivisionError, TypeError):
                            cycles_remaining = 0
                            hours_remaining = 0.0
                            self.logger.debug("error calculating token cycle estimates, using defaults")

                        if tokens_remaining <= 0:
                            self.logger.error(
                                f"api rate limit exceeded - no tokens remaining until {token_reset}, "
                                f"increase polling interval to prevent this tomorrow"
                            )
                        elif tokens_remaining < 50:
                            self.logger.error(
                                f"low api tokens: {tokens_remaining} of 2000 remaining "
                                f"(~{hours_remaining:.1f} hours), resets at {token_reset}, "
                                f"recommend increasing polling interval"
                            )
                        elif tokens_remaining < 200:
                            self.logger.warning(
                                f"api tokens low: {tokens_remaining} of 2000 remaining "
                                f"(~{hours_remaining:.1f} hours), resets at {token_reset}, "
                                f"consider increasing polling interval"
                            )
                        elif tokens_remaining < 500:
                            self.logger.info(
                                f"api tokens: {tokens_remaining} of 2000 remaining today "
                                f"(~{hours_remaining:.1f} hours at current rate)"
                            )

                        activeScheduleName = None

                        # Get the current schedule for the device - it will tell us if it's running or not
                        try:
                            schedule_dict = self._make_api_call(
                                f"{DEVICE_SCHEDULES_ENDPOINT}?key={netroSerial}")
                            # Loop all possible schedules to find active and next
                            all_schedules_data = schedule_dict["data"]
                            all_schedules = all_schedules_data["schedules"]

                            current_schedule_dict = None
                            next_schedule_dict = None
                            earliest_start_time = None

                            for sch_dict in all_schedules:
                                # Find currently executing schedule
                                if sch_dict["status"] == "EXECUTING":
                                    current_schedule_dict = sch_dict
                                # Find next valid (upcoming) schedule with earliest start time
                                elif sch_dict["status"] == "VALID":
                                    # Handle start_time as either string or number
                                    start_time_raw = sch_dict.get("start_time", 0)
                                    try:
                                        start_time = (float(start_time_raw) if isinstance(start_time_raw, str)
                                                      else start_time_raw)
                                    except (ValueError, TypeError):
                                        start_time = 0

                                    if earliest_start_time is None or start_time < earliest_start_time:
                                        earliest_start_time = start_time
                                        next_schedule_dict = sch_dict

                            # Update current/active schedule states
                            if current_schedule_dict:
                                # Something is running - use the source field to show schedule type
                                update_list.append(
                                    {"key": "activeZone", "value": current_schedule_dict["zone"]})
                                # Display schedule source (AUTOMATIC, MANUAL, SMART, FIX)
                                update_list.append(
                                    {"key": "activeSchedule",
                                     "value": current_schedule_dict["source"].title()})
                                activeScheduleName = current_schedule_dict["source"].title()
                            else:
                                update_list.append(
                                    {"key": "activeSchedule", "value": "No active schedule"})
                                # Show no zones active
                                update_list.append({"key": "activeZone", "value": 0})

                            # Update next schedule states
                            if next_schedule_dict:
                                # Convert timestamp to readable format
                                # Handle start_time as either string or number
                                start_time_raw = next_schedule_dict.get("start_time", 0)
                                try:
                                    start_time_ms = (float(start_time_raw) if isinstance(start_time_raw, str)
                                                     else start_time_raw)
                                    start_time_dt = datetime.fromtimestamp(start_time_ms / 1000.0)
                                    start_time_str = start_time_dt.strftime("%Y-%m-%d %H:%M:%S")
                                except (ValueError, TypeError, OSError):
                                    start_time_str = "Invalid timestamp"

                                update_list.append(
                                    {"key": "nextScheduleTime", "value": start_time_str})
                                update_list.append(
                                    {"key": "nextScheduleZone",
                                     "value": next_schedule_dict.get("zone_name",
                                                                      f"Zone {next_schedule_dict['zone']}")})
                                update_list.append(
                                    {"key": "nextScheduleSource",
                                     "value": next_schedule_dict["source"].title()})
                                # Duration is in seconds, convert to minutes (defensive coding)
                                duration_sec = next_schedule_dict.get("duration") or 0
                                duration_min = int(duration_sec / 60)
                                update_list.append(
                                    {"key": "nextScheduleDuration", "value": duration_min})
                            else:
                                # No upcoming schedules
                                update_list.append(
                                    {"key": "nextScheduleTime", "value": "No upcoming schedule"})
                                update_list.append({"key": "nextScheduleZone", "value": "None"})
                                update_list.append({"key": "nextScheduleSource", "value": "None"})
                                update_list.append({"key": "nextScheduleDuration", "value": 0})

                        except Exception:
                            update_list.append(
                                {"key": "activeSchedule", "value": "Error getting current schedule"})
                            self.logger.debug(f"API error: \n{traceback.format_exc(10)}")
                            self._fireTrigger("getScheduleCall")

                        # Send the state updates to the server
                        if len(update_list):
                            dev.updateStatesOnServer(update_list)

                        # Update zone information as necessary - these are properties, not states.
                        zoneNames = ""
                        maxZoneDurations = []
                        zones_data = []  # Store zone data for getZoneList()
                        dev_dict = ls_reply_dict_devices[0]
                        for zone in sorted(dev_dict["zones"], key=itemgetter('ith')):
                            zoneNames += f", {zone['name']}" if zoneNames else zone["name"]
                            # Set max duration to plugin max for enabled zones, 0 for disabled zones
                            max_duration = self.maxZoneRunTime if zone["enabled"] else 0
                            maxZoneDurations.append(str(max_duration))
                            # Store zone ID and name for dropdown lists
                            zones_data.append({
                                "id": zone["ith"],
                                "name": zone["name"],
                                "enabled": zone["enabled"]
                            })
                        props = copy.deepcopy(dev.pluginProps)
                        props["NumZones"] = len(dev_dict["zones"])
                        props["ZoneNames"] = zoneNames
                        props["MaxZoneDurations"] = ", ".join(maxZoneDurations)
                        props["zones"] = json.dumps(zones_data)  # Store as JSON string
                        if activeScheduleName:
                            props["ScheduledZoneDurations"] = activeScheduleName
                        dev.replacePluginPropsOnServer(props)

                        # Update Moisture levels per Zone
                        update_moisture = self.callMoisturesAPI(netroSerial)
                        dev.updateStatesOnServer(update_moisture)

                    except ThrottleDelayError:
                        # Already logged detailed error in _make_api_call, just skip this device
                        pass
                    except requests.exceptions.HTTPError as exc:
                        # Check if we already logged a detailed error for this
                        # Only skip logging for recognized error codes (1 = invalid key, 3 = rate limit)
                        if hasattr(exc, 'response') and exc.response is not None:
                            try:
                                error_data = exc.response.json()
                                if error_data.get("status") == "ERROR":
                                    # Check if this is a recognized error code
                                    errors = error_data.get("errors", [])
                                    recognized_codes = {1, 3}  # invalid key, rate limit
                                    is_recognized = any(
                                        error.get("code") in recognized_codes
                                        for error in errors
                                    )
                                    if is_recognized:
                                        # Already logged specific error in _make_api_call
                                        pass
                                    else:
                                        # Unrecognized error code - log it
                                        self.logger.error("error getting user data from netro api")
                                        self.logger.debug(f"API error: \n{traceback.format_exc(10)}")
                                else:
                                    self.logger.error("error getting user data from netro api")
                                    self.logger.debug(f"API error: \n{traceback.format_exc(10)}")
                            except (ValueError, AttributeError):
                                self.logger.error("error getting user data from netro api")
                                self.logger.debug(f"API error: \n{traceback.format_exc(10)}")
                        else:
                            self.logger.error("error getting user data from netro api")
                            self.logger.debug(f"API error: \n{traceback.format_exc(10)}")
                        self._fireTrigger("personInfoCall")
                    except Exception:
                        self.logger.error("Error getting user data from Netro via API.")
                        self.logger.debug(f"API error: \n{traceback.format_exc(10)}")
                        self._fireTrigger("personInfoCall")

                # Update Whisperer Plant Sensors
                if dev.deviceTypeId == "Whisperer":
                    try:
                        self.logger.debug(f"Device ID: {dev.address}")
                        self.serialNo = str(dev.address)
                        if dev.sensorValue is not None:
                            sensorValuesLatest = self.callSensorAPI(self.serialNo)
                            self.key_val_list = sensorValuesLatest['sensorKeyValuesList']
                            if dev.onState is not None:
                                self.key_val_list.append({'key': 'onOffState', 'value': not dev.onState})
                                dev.updateStatesOnServer(self.key_val_list)
                                if dev.onState:
                                    dev.updateStateImageOnServer(indigo.kStateImageSel.HumiditySensorOn)
                                else:
                                    dev.updateStateImageOnServer(indigo.kStateImageSel.HumiditySensor)
                            else:
                                dev.updateStatesOnServer(self.key_val_list)
                                dev.updateStateImageOnServer(indigo.kStateImageSel.HumiditySensor)
                        elif dev.onState is not None:
                            dev.updateStateOnServer("onOffState", not dev.onState)
                            dev.updateStateImageOnServer(indigo.kStateImageSel.Auto)
                        else:
                            dev.updateStateImageOnServer(indigo.kStateImageSel.Auto)
                    except ThrottleDelayError:
                        # Already logged detailed warning in _make_api_call, just skip this device
                        pass
                    except Exception:
                        self.logger.error(f"error getting sensor data from netro api for device \"{dev.name}\"")
                        self.logger.debug(f"API error: \n{traceback.format_exc(10)}")
        except Exception as exc:
            self.logger.error(f"unexpected error updating netro devices: {exc.__class__.__name__}")
            self.logger.debug(f"traceback:\n{traceback.format_exc(10)}")

    def callMoisturesAPI(self, serial):
        """Fetch moisture levels from Netro API for all zones.

        Args:
            serial: Device serial number

        Returns:
            List of dicts with zone moisture states
        """
        url = f"{DEVICE_MOISTURES_ENDPOINT}?key={serial}"
        jsonData = self._make_api_call(url)
        jdata = jsonData['data']
        jmoistures = jdata['moistures']

        # Guard against empty moistures list
        if not jmoistures:
            self.logger.debug("No moisture data available from API")
            return []

        # Sort by ID to get most recent first
        jmoistures.sort(key=lambda x: x.get('id'), reverse=True)

        # Get all moistures from the most recent date
        currentMoistures = jmoistures[0]
        maxDate = currentMoistures['date']
        maxDateMoistures = list(filter(lambda maxdate: maxdate['date'] == maxDate, jmoistures))

        # Build state updates for each zone
        current_moistures = []
        for moisture_data in maxDateMoistures:
            zone = moisture_data['zone']
            state_dict = {
                "key": f"zone_{zone}_moisture",
                "value": str(moisture_data["moisture"])
            }
            current_moistures.append(state_dict)

        return current_moistures

    def callSensorAPI(self, serial):
        """Fetch Whisperer sensor data from Netro API.

        Args:
            serial: Device serial number

        Returns:
            List of dicts with sensor states
        """
        url = f"{DEVICE_SENSOR_DATA_ENDPOINT}?key={serial}"
        self.logger.debug(url)
        jsonData = self._make_api_call(url)
        jdata = jsonData['data']
        jmeta = jsonData['meta']
        sensorReadings = jdata['sensor_data']

        # Guard against empty sensor readings list
        if not sensorReadings:
            self.logger.warning("No sensor data available from API")
            return {
                'sensorStatus': jsonData['status'],
                'sensorMeta': jsonData['meta'],
                'currentReadings': {},
                'sensorKeyValuesList': []
            }

        sensorReadings.sort(key=lambda x: x.get('id'), reverse=True)
        devStates=sensorReadings[0]
        self.logger.debug(devStates)
        key_values_list = [
            {'key': 'sensorValue', 'value': devStates['moisture'], 'uiValue':  f"{devStates['moisture']:.1f} %"},
            {'key': 'humidity', 'value': devStates['moisture']},
            {'key': 'soilMoisture', 'value': devStates['moisture']},
            {'key': 'temperature', 'value': devStates['celsius']},
            {'key': 'soilTemperature', 'value': devStates['celsius']},
            {'key': 'sunlight', 'value': devStates['sunlight']},
            {'key': 'readingID', 'value': devStates['id']},
            {'key': 'readingTime', 'value': devStates['time']},
            {'key': 'readingLocalDate', 'value': devStates['local_date']},
            {'key': 'readingLocalTime', 'value': devStates['local_time']},
            {'key': 'id', 'value': devStates['id']},
            {'key': 'token_remaining', 'value': jmeta["token_remaining"]},
            {'key': 'token_reset', 'value': jmeta["token_reset"]},
            {'key': 'api_last_active', 'value': jmeta["last_active"]},
            {'key': 'sensor_last_active', 'value': devStates["time"]},
            {'key': 'time', 'value': jmeta["time"]},
            {'key': 'batteryLevel', 'value': devStates['battery_level']}
        ]
        sensorValues = dict()
        sensorValues['sensorStatus'] = jsonData['status']
        sensorValues['sensorMeta'] = jsonData['meta']
        sensorValues['currentReadings'] = sensorReadings[0]
        sensorValues['sensorKeyValuesList'] = key_values_list
        # self.logger.info(u"Latest sensor #readings"+currentReading)
        return sensorValues
    ########################################
    # startup, concurrent thread, and shutdown methods
    ########################################
    def startup(self):
        """Called when plugin is first enabled.

        Logs startup message. Main initialization happens in __init__().
        """
        self.logger.info("Netro Sprinklers Started")

    ########################################
    def shutdown(self):
        """Called when plugin is disabled or Indigo quits.

        Logs shutdown message and performs cleanup.
        """
        self.logger.info("Netro Sprinklers Stopped")
        pass

    ########################################
    def runConcurrentThread(self):
        """Background thread that polls Netro API periodically.

        This thread runs continuously while the plugin is enabled, calling
        _update_from_netro() every pollingInterval minutes. Uses self.sleep()
        to allow clean shutdown when plugin is disabled.

        The polling interval is configurable but must be at least 3 minutes
        to avoid hitting Netro's API rate limit (2000 calls/day).

        Exceptions during updates are silently caught to prevent the thread
        from exiting - errors are logged within _update_from_netro().
        """
        self.logger.debug("Starting concurrent thread")
        while True:
            try:
                self._update_from_netro()
            except self.StopThread:
                # Clean shutdown requested by Indigo - must re-raise
                self.logger.debug("Concurrent thread stopping")
                raise
            except Exception:
                # Log error with full traceback but continue polling - thread must not die
                self.logger.exception("Error in polling loop, will retry next interval")
            self.sleep(self.pollingInterval * 60)


    ########################################



    ########################################
    # Dialog list callbacks
    ########################################
    # pylint: disable=unused-argument
    def availableControllers(self, dev_filter="", valuesDict=None, typeId="", targetId=0):
        """Get list of available Netro controllers for dropdown menus.

        Args:
            dev_filter: Device filter (unused)
            valuesDict: Current dialog values
            typeId: Device type ID
            targetId: Target device ID

        Returns:
            List of tuples (controller_id, controller_name)
        """
        self.logger.debug(f"availableControllers {self.unused_devices}")
        controller_list = [(dev_id, dev_dict['name']) for dev_id, dev_dict in self.unused_devices.items()]
        dev = indigo.devices.get(targetId, None)
        if dev and dev.configured:
            dev_dict = self._get_device_dict(dev.states[0])
            controller_list.append((dev.states[0], dev_dict["name"]))
        return controller_list

    ########################################
    # pylint: disable=unused-argument
    def sprinklerList(self, dev_filter="", valuesDict=None, typeId="", targetId=0):
        """Get list of all sprinkler devices for dropdown menus.

        Args:
            dev_filter: Device filter (unused)
            valuesDict: Current dialog values
            typeId: Device type ID
            targetId: Target device ID

        Returns:
            List of tuples (device_id, device_name) for all plugin devices
        """
        self.logger.threaddebug("sprinklerList")
        return [(s.id, s.name) for s in indigo.devices.iter(filter="self")]

    ########################################
    # Validation callbacks
    ########################################
    # pylint: disable=unused-argument
    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        """Validate device configuration before saving.

        Args:
            valuesDict: Device configuration values from UI
            typeId: Device type ID
            devId: Device ID

        Returns:
            Tuple of (is_valid, valuesDict, errorsDict)
        """
        self.logger.threaddebug("validateDeviceConfigUi")
        errorsDict = indigo.Dict()

        # Validate controller serial number (required)
        if typeId == "sprinkler":
            serial = valuesDict.get("address", "").strip()
            if not serial:
                errorsDict["address"] = "Serial number is required for Netro controller"
            elif len(serial) < 8:
                errorsDict["address"] = "Serial number appears too short (should be 12 hex characters)"

        # Validate Whisperer sensor serial number and set capabilities
        if typeId == "Whisperer":
            serial = valuesDict.get("address", "").strip()
            if not serial:
                errorsDict["address"] = "Serial number is required for Whisperer sensor"
            elif len(serial) < 8:
                errorsDict["address"] = "Serial number appears too short"

            # Set sensor capabilities
            valuesDict["SupportsBatteryLevel"] = True
            valuesDict["NumTemperatureInputs"] = 1
            valuesDict["NumHumidityInputs"] = 1
            valuesDict["SupportsTemperatureReporting"] = True

        if len(errorsDict):
            return False, valuesDict, errorsDict
        return True, valuesDict

    ########################################
    # pylint: disable=unused-argument,too-many-branches
    def validateActionConfigUi(self, valuesDict, typeId, devId):
        """Validate action configuration before saving.

        Args:
            valuesDict: Action configuration values
            typeId: Action type ID
            devId: Device ID

        Returns:
            Tuple of (is_valid, valuesDict, errorsDict)
        """
        self.logger.threaddebug(f"validateActionConfigUi for {typeId}")
        errorsDict = indigo.Dict()

        if typeId == "startZoneWithDelay":
            # Validate duration (1-180 minutes)
            try:
                duration = int(valuesDict.get("duration", 15))
                if duration < 1 or duration > 180:
                    errorsDict["duration"] = "Duration must be between 1 and 180 minutes"
            except (ValueError, TypeError):
                errorsDict["duration"] = "Duration must be a valid number"

            # Validate delay (0-60 minutes)
            try:
                delay = int(valuesDict.get("delay", 0))
                if delay < 0 or delay > 60:
                    errorsDict["delay"] = "Delay must be between 0 and 60 minutes"
            except (ValueError, TypeError):
                errorsDict["delay"] = "Delay must be a valid number"

            # Validate start_time if provided (must be valid Unix timestamp)
            start_time = valuesDict.get("start_time", "").strip()
            if start_time:
                try:
                    int(start_time)
                except ValueError:
                    errorsDict["start_time"] = "Start time must be a valid Unix timestamp (integer)"

            # Validate zone selected
            if not valuesDict.get("zone"):
                errorsDict["zone"] = "You must select a zone"

        elif typeId == "reportWeather":
            # Validate required temperature field
            temperature = valuesDict.get("temperature", "").strip()
            if not temperature:
                errorsDict["temperature"] = "Current temperature is required"
            else:
                try:
                    float(temperature)
                except ValueError:
                    errorsDict["temperature"] = "Temperature must be a valid number"

            # Validate optional numeric fields if provided
            for field, label, min_val, max_val in [
                ("t_max", "Max temperature", -50, 150),
                ("t_min", "Min temperature", -50, 150),
                ("humidity", "Humidity", 0, 100),
                ("rain", "Rainfall", 0, 100),
                ("rain_prob", "Rain probability", 0, 100),
                ("wind_speed", "Wind speed", 0, 200),
                ("pressure", "Pressure", 20, 35)
            ]:
                value = valuesDict.get(field, "").strip()
                if value:
                    try:
                        num_value = float(value)
                        if num_value < min_val or num_value > max_val:
                            errorsDict[field] = f"{label} must be between {min_val} and {max_val}"
                    except ValueError:
                        errorsDict[field] = f"{label} must be a valid number"

            # Validate date format if provided
            date_str = valuesDict.get("date", "").strip()
            if date_str:
                try:
                    datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    errorsDict["date"] = "Date must be in YYYY-MM-DD format"

        if len(errorsDict):
            return False, valuesDict, errorsDict
        return True, valuesDict

    ########################################
    # pylint: disable=unused-argument
    def validateEventConfigUi(self, valuesDict, typeId, devId):
        """Validate event/trigger configuration before saving.

        Args:
            valuesDict: Event configuration values from UI
            typeId: Event type ID
            devId: Device ID

        Returns:
            Tuple of (is_valid, valuesDict, errorsDict)
        """
        self.logger.threaddebug("validateEventConfigUi")
        errorsDict = indigo.Dict()
        if typeId == "sprinklerError":
            if valuesDict["serial"] == "":
                errorsDict["serial"] = "You must select a Netro Sprinkler device."
        if len(errorsDict):
            return False, valuesDict, errorsDict
        return True, valuesDict

    ########################################
    def validatePrefsConfigUi(self, valuesDict):
        """Validate plugin configuration before saving.

        Args:
            valuesDict: Configuration values from UI

        Returns:
            Tuple of (is_valid, valuesDict, errorsDict)
        """
        self.logger.threaddebug("validatePrefsConfigUi")
        errorsDict = indigo.Dict()

        # Validate polling interval (minimum 3 minutes to avoid rate limits)
        try:
            polling = int(valuesDict.get("pollingInterval", 3))
            if polling < 3:
                errorsDict["pollingInterval"] = "Polling interval must be at least 3 minutes to avoid API rate limits"
            elif polling > 1440:
                errorsDict["pollingInterval"] = "Polling interval cannot exceed 1440 minutes (24 hours)"
        except (ValueError, TypeError):
            errorsDict["pollingInterval"] = "Polling interval must be a valid number"

        # Validate API timeout (1-60 seconds)
        try:
            timeout = int(valuesDict.get("apiTimeout", 5))
            if timeout < 1:
                errorsDict["apiTimeout"] = "Timeout must be at least 1 second"
            elif timeout > 60:
                errorsDict["apiTimeout"] = "Timeout cannot exceed 60 seconds"
        except (ValueError, TypeError):
            errorsDict["apiTimeout"] = "Timeout must be a valid number"

        # Validate max zone runtime (60-10800 seconds = 1 minute to 3 hours)
        try:
            max_runtime = int(valuesDict.get("maxZoneRunTime", 3600))
            if max_runtime < 60:
                errorsDict["maxZoneRunTime"] = "Max runtime must be at least 60 seconds (1 minute)"
            elif max_runtime > 10800:
                errorsDict["maxZoneRunTime"] = "Max runtime cannot exceed 10800 seconds (3 hours)"
        except (ValueError, TypeError):
            errorsDict["maxZoneRunTime"] = "Max runtime must be a valid number"

        if len(errorsDict):
            return False, valuesDict, errorsDict
        return True, valuesDict

    ########################################
    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        """Called when user closes the plugin config dialog.

        Apply configuration changes without requiring plugin restart.

        Args:
            valuesDict: Configuration values from UI
            userCancelled: True if user cancelled, False if they saved
        """
        if not userCancelled:
            self.logger.threaddebug("closedPrefsConfigUi: Applying configuration changes")

            # Update timeout
            self.timeout = int(valuesDict.get("apiTimeout", 5))

            # Update debug logging
            self.debug = valuesDict.get("showDebugInfo", False)
            if self.debug:
                self.logger.debug("Debug logging enabled")

            # Update polling interval
            try:
                new_polling_interval = int(valuesDict.get("pollingInterval", MINIMUM_POLLING_INTERVAL_MINUTES))
                if new_polling_interval != self.pollingInterval:
                    self.pollingInterval = new_polling_interval
                    self.logger.info(f"Polling interval updated to {self.pollingInterval} minutes")
            except (ValueError, TypeError):
                self.logger.warning("Invalid polling interval value, keeping existing setting")

            # Update max zone runtime
            try:
                new_max_runtime = int(valuesDict.get("maxZoneRunTime", MAX_ZONE_DURATION_SECONDS))
                if new_max_runtime != self.maxZoneRunTime:
                    self.maxZoneRunTime = new_max_runtime
                    self.logger.info(f"Max zone runtime updated to {self.maxZoneRunTime} seconds")
            except (ValueError, TypeError):
                self.logger.warning("Invalid max zone runtime value, keeping existing setting")

    ########################################
    # General device callbacks
    ########################################
    def didDeviceCommPropertyChange(self, origDev, newDev):
        """Check if device communication properties have changed.

        Called when device is edited to determine if communication needs
        to be restarted.

        Args:
            origDev: Original device before edits
            newDev: Updated device after edits

        Returns:
            True if device ID changed (requires reconnection), False otherwise
        """
        self.logger.threaddebug("didDeviceCommPropertyChange")
        return origDev.states["id"] != newDev.states["id"]

    ########################################
    # pylint: disable=unused-argument
    def deviceStartComm(self, dev):
        """Called when device communication should start.

        Triggers an immediate update from the Netro API to populate the
        device's initial state.

        Args:
            dev: Device starting communication
        """
        # Get the full device info and update the newly created device
        # Update all the states here
        self._update_from_netro()


    ########################################
    # pylint: disable=unused-argument
    def deviceStopComm(self, dev):
        """Called when device communication should stop.

        Args:
            dev: Device stopping communication
        """
        self.logger.debug("Stopping device")

    ########################################
    # Event callbacks
    ########################################
    def _fireTrigger(self, event, dev_id=None):
        """Fire Indigo triggers based on plugin events.

        Dispatches events to registered triggers based on trigger type and
        configuration. Handles operational errors, communication errors, and
        other plugin events.

        Args:
            event: Event identifier string (e.g., "startZoneFailed", "rateLimitExceeded")
            dev_id: Device ID associated with event (None for non-device events)
        """
        try:
            for trigger in self.triggerDict.values():
                if trigger.pluginTypeId == "sprinklerError":
                    if int(trigger.pluginProps["id"]) == dev_id:
                        # for the all trigger type, we fire any event that's in the OPERATIONAL_ERROR_EVENTS
                        # list we defined at the top.
                        trigger_type = trigger.pluginProps["errorType"]
                        if trigger_type == "all" and event in OPERATIONAL_ERROR_EVENTS:
                            indigo.trigger.execute(trigger)
                        # then we fire if the event specifically matches the trigger type
                        if trigger_type == event:
                            indigo.trigger.execute(trigger)
                elif trigger.pluginTypeId == "commError":
                    trigger_type = trigger.pluginProps["errorType"]
                    # first we fire the trigger if it's any comm error in the COMM_ERROR_EVENTS list
                    if trigger_type == "allCommErrors" and event in COMM_ERROR_EVENTS:
                        indigo.trigger.execute(trigger)
                    # then we fire if the event specifically matches the trigger type
                    if trigger_type == event:
                        indigo.trigger.execute(trigger)
                elif trigger.pluginTypeId == event:
                    # an update is available, just fire the trigger since there's nothing else to look at
                    indigo.trigger.execute(trigger)
        except Exception:
            self.logger.error("An error occurred during trigger processing")
            self.logger.debug(f"An error occurred during trigger processing: \n{traceback.format_exc(10)}")

    ########################################
    def triggerStartProcessing(self, trigger):
        """Called when a trigger is enabled.

        Adds trigger to internal tracking dict for event dispatch.

        Args:
            trigger: Indigo trigger object
        """
        super().triggerStartProcessing(trigger)
        self.logger.debug(f"Start processing trigger {str(trigger.id)}")
        if trigger.id not in self.triggerDict:
            self.triggerDict[trigger.id] = trigger
        self.logger.debug(f"Start trigger processing list: {str(self.triggerDict)}")

    ########################################
    def triggerStopProcessing(self, trigger):
        """Called when a trigger is disabled.

        Removes trigger from internal tracking dict.

        Args:
            trigger: Indigo trigger object
        """
        super().triggerStopProcessing(trigger)
        self.logger.debug("Stop processing trigger " + str(trigger.id))
        try:
            del self.triggerDict[trigger.id]
        except KeyError:
            # Trigger wasn't in dict - already removed or never added
            self.logger.debug(f"Trigger {trigger.id} not found in triggerDict")
        self.logger.debug(f"Stop trigger processing list: {str(self.triggerDict)}")

    ########################################
    # Sprinkler Control Action callback
    ########################################
    def actionControlSprinkler(self, action, dev):
        """Handle Indigo sprinkler device actions.

        Processes standard Indigo sprinkler actions:
        - Zone On: Start a specific zone
        - All Zones Off: Stop all running zones

        Also checks for throttle state before making API calls and fires
        appropriate triggers on success/failure.

        Args:
            action: Indigo action object with sprinklerAction type
            dev: Sprinkler controller device

        Note:
            Advanced schedule actions (RunNewSchedule, PauseSchedule, etc.)
            are not currently supported due to Netro API limitations.
        """
        # Check if throttle period has expired
        if self.throttle_next_call and datetime.now() < self.throttle_next_call:
            self.logger.error(
                f"API calls have violated rate limit - next connection attempt at "
                f"{self.throttle_next_call:%H:%M:%S}")
            if action.sprinklerAction == indigo.kSprinklerAction.ZoneOn:
                self._fireTrigger("startZoneFailed", dev.id)
            elif action.sprinklerAction == indigo.kSprinklerAction.AllZonesOff:
                self._fireTrigger("stopFailed", dev.id)
            return
        elif self.throttle_next_call:
            # Throttle period has expired, reset it
            self.throttle_next_call = None

        # ZONE ON #
        if action.sprinklerAction == indigo.kSprinklerAction.ZoneOn:
            zone_dict = self._get_zone_dict(dev.states["id"], action.zoneIndex)
            self.logger.debug(f"zone_dict: {zone_dict}")
            if zone_dict:
                zoneName = zone_dict["name"]
                data = {
                    "id": zone_dict["id"],
                    "duration": (zone_dict["maxRuntime"] if zone_dict["maxRuntime"] <= self.maxZoneRunTime
                                 else self.maxZoneRunTime),
                }
                try:
                    self._make_api_call(ZONE_START_ENDPOINT, request_method="put", data=data)
                    self.logger.info(f'sent "{dev.name} - {zoneName}" on')
                    dev.updateStateOnServer("activeZone", action.zoneIndex)
                except requests.exceptions.RequestException:
                    # Network/HTTP error - log with traceback and fire trigger
                    self.logger.exception(f'send "{dev.name} - {zoneName}" on failed')
                    self._fireTrigger("startZoneFailed", dev.id)
                except ThrottleDelayError:
                    self.logger.warning(f'send "{dev.name} - {zoneName}" throttled - in rate limit period')
                    self._fireTrigger("startZoneFailed", dev.id)
            else:
                self.logger.error(
                    f"Zone number {action.zoneIndex} doesn't exist in this controller "
                    f"and can't be enabled.")
                self._fireTrigger("startZoneFailed", dev.id)

        # ALL ZONES OFF #
        elif action.sprinklerAction == indigo.kSprinklerAction.AllZonesOff:
            data = {
                "id": dev.states["id"],
            }
            try:
                self._make_api_call(DEVICE_STOP_WATER_ENDPOINT, request_method="post", data=data)
                self.logger.info(f'sent "{dev.name}" {"all zones off"}')
                dev.updateStateOnServer("activeZone", 0)
            except requests.exceptions.RequestException:
                # Network/HTTP error - log with traceback and fire trigger
                self.logger.exception(f'send "{dev.name}" all zones off failed')
                self._fireTrigger("stopFailed", dev.id)
            except ThrottleDelayError:
                self.logger.warning(f'send "{dev.name}" all zones off throttled - in rate limit period')
                self._fireTrigger("stopFailed", dev.id)

        ############################################
        # TODO: The next sprinkler actions won't currently be called because we haven't set the OverrideScheduleActions
        # property. If we wanted to hand off all scheduling to the Netro, we would need to use these. However, their
        # current API doesn't implement enough required functionality (pause/resume, next/previous zone, etc) for us to
        # actually do that at the moment.
        ############################################
        elif action.sprinklerAction == indigo.kSprinklerAction.RunNewSchedule or \
                action.sprinklerAction == indigo.kSprinklerAction.RunPreviousSchedule or \
                action.sprinklerAction == indigo.kSprinklerAction.PauseSchedule or \
                action.sprinklerAction == indigo.kSprinklerAction.ResumeSchedule or \
                action.sprinklerAction == indigo.kSprinklerAction.StopSchedule or \
                action.sprinklerAction == indigo.kSprinklerAction.PreviousZone or \
                action.sprinklerAction == indigo.kSprinklerAction.NextZone:
            pass

    ########################################
    # General Action callback
    ########################################
    # pylint: disable=unused-argument
    def actionControlUniversal(self, action, dev):
        """Handle universal device actions.

        Processes standard Indigo device actions like status requests.

        Args:
            action: Indigo action object with deviceAction type
            dev: Device to perform action on
        """
        # STATUS REQUEST #
        if action.deviceAction == indigo.kUniversalAction.RequestStatus:
            self._next_weather_update = datetime.now()
            self._update_from_netro()

    ########################################
    # Custom Plugin Action callbacks defined in Actions.xml
    ########################################

    ########################################
    def setNoWater(self, pluginAction, dev):
        """Set rain delay (no watering) for specified number of days.

        Tells Netro to skip automatic watering for the configured number
        of days. Useful for manual rain delays or when performing lawn
        maintenance.

        Args:
            pluginAction: Action parameters containing numDaysNoWater
            dev: Sprinkler controller device
        """
        num_Days = pluginAction.props["numDaysNoWater"]
        dev_dict = self._get_device_dict(dev.states["id"])

        if dev_dict:
            try:
                data = {
                    "key": dev.address,
                    "days": num_Days,
                }
                response = self._make_api_call(DEVICE_NO_WATER_ENDPOINT, request_method="post", data=data)
                response_status = response["status"]
                self.logger.debug(response)
                if response_status == "OK":
                    self.logger.info(f"Stop watering for  '{num_Days}'  day(s)")
                else:
                    self.logger.info("Error setting rain delay")
                return
            except Exception:
                self.logger.debug(f"API error: \n{traceback.format_exc(10)}")
                self._fireTrigger("setNoWater", dev.id)

    ########################################
    def setStandbyMode(self, pluginAction, dev):
        """Set controller standby mode on/off.

        When in standby mode, the controller won't water automatically.
        Useful for winterization or extended absences.

        Args:
            pluginAction: Action parameters containing mode (True=standby, False=online)
            dev: Sprinkler controller device
        """
        try:
            # Set device status: 0 = standby (off), 1 = online (on)
            data = {
                "key": dev.address,
                "status": 0 if pluginAction.props["mode"] else 1,
            }
            self._make_api_call(DEVICE_SET_STATUS_ENDPOINT, request_method="post", data=data)
            mode_status = 'on' if pluginAction.props['mode'] else 'off'
            self.logger.info(f"Standby mode for controller '{dev.name}' turned {mode_status}")
        except Exception:
            self.logger.error("Could not set standby mode - check your controller.")
            self.logger.debug(f"API error: \n{traceback.format_exc(10)}")
            self._fireTrigger("setStandbyFailed", dev.id)

    ########################################
    def startZoneWithDelay(self, pluginAction, dev):
        """Start a zone with optional delay or scheduled start time.

        Args:
            pluginAction: Action parameters containing zone, duration, delay, start_time
            dev: Sprinkler controller device
        """
        try:
            zone_id = pluginAction.props.get("zone")
            duration = int(pluginAction.props.get("duration", 15))
            delay = int(pluginAction.props.get("delay", 0))
            start_time = pluginAction.props.get("start_time", "").strip()

            # Validate parameters
            if not zone_id:
                self.logger.error("No zone selected")
                return

            if duration < 1 or duration > 180:
                self.logger.error(f"Duration must be between 1 and 180 minutes (got {duration})")
                return

            if delay < 0 or delay > 60:
                self.logger.error(f"Delay must be between 0 and 60 minutes (got {delay})")
                return

            # Build API request (use device's serial number, not plugin prefs)
            data = {
                "key": dev.address,
                "zones": [
                    {
                        "id": zone_id,
                        "duration": duration
                    }
                ]
            }

            # Add optional parameters
            if delay > 0:
                data["delay"] = delay

            if start_time:
                try:
                    data["start_time"] = int(start_time)
                except ValueError:
                    self.logger.error(f"Invalid start_time format (must be Unix timestamp): {start_time}")
                    return

            # Make API call
            response = self._make_api_call(DEVICE_WATER_ENDPOINT, request_method="post", data=data)
            response_status = response.get("status")

            if response_status == "OK":
                if start_time:
                    self.logger.info(
                        f"Zone '{zone_id}' scheduled to start at timestamp {start_time} "
                        f"for {duration} minutes")
                elif delay > 0:
                    self.logger.info(f"Zone '{zone_id}' will start in {delay} minutes for {duration} minutes")
                else:
                    self.logger.info(f"Zone '{zone_id}' started for {duration} minutes")
            else:
                self.logger.error(f"Error starting zone: {response}")
                self._fireTrigger("startZoneFailed", dev.id)

        except Exception as exc:
            self.logger.error(f"Could not start zone with delay: {exc}")
            self.logger.debug(f"API error: \n{traceback.format_exc(10)}")
            self._fireTrigger("startZoneFailed", dev.id)

    ########################################
    def reportWeather(self, pluginAction, dev):
        """Report local weather data to Netro to improve scheduling.

        Args:
            pluginAction: Action parameters containing weather data
            dev: Sprinkler controller device
        """
        try:
            # Build weather data payload (use device's serial number, not plugin prefs)
            data = {
                "key": dev.address,
                "condition": int(pluginAction.props.get("condition", 0)),
                "date": pluginAction.props.get("date", "").strip() or date.today().strftime("%Y-%m-%d")
            }

            # Add optional weather parameters if provided
            optional_fields = {
                "temperature": "t",
                "t_max": "t_max",
                "t_min": "t_min",
                "humidity": "humidity",
                "rain": "rain",
                "rain_prob": "rain_prob",
                "wind_speed": "wind_speed",
                "pressure": "pressure"
            }

            for field, api_key in optional_fields.items():
                value = pluginAction.props.get(field, "").strip()
                if value:
                    try:
                        # Convert to appropriate type (float for most, int for humidity/rain_prob)
                        if field in ["humidity", "rain_prob"]:
                            data[api_key] = int(value)
                        else:
                            data[api_key] = float(value)
                    except ValueError:
                        self.logger.warning(f"Invalid value for {field}: {value}, skipping")

            # Validate required temperature field
            if "t" not in data:
                self.logger.error("Current temperature is required for weather reporting")
                return

            # Make API call
            response = self._make_api_call(DEVICE_REPORT_WEATHER_ENDPOINT, request_method="post", data=data)
            response_status = response.get("status")

            if response_status == "OK":
                self.logger.info(
                    f"Weather data reported to Netro for {data['date']}: "
                    f"{data.get('t')}°F, condition={data['condition']}")
            else:
                self.logger.error(f"Error reporting weather: {response}")

        except Exception as exc:
            self.logger.error(f"Could not report weather: {exc}")
            self.logger.debug(f"API error: \n{traceback.format_exc(10)}")

    ########################################
    # pylint: disable=unused-argument
    def getZoneList(self, filter="", valuesDict=None, typeId="", targetId=0):
        """Get list of available zones for the zone dropdown.

        Returns:
            List of tuples (zone_id, zone_name) for zone selection
        """
        try:
            dev = indigo.devices[targetId]
            zone_list = []

            # Get zones from device properties (stored as JSON string)
            if "zones" in dev.pluginProps:
                zones_json = dev.pluginProps["zones"]
                if zones_json:
                    zones = json.loads(zones_json)
                    for zone in zones:
                        zone_id = zone.get("id", "")
                        zone_name = zone.get("name", f"Zone {zone_id}")
                        enabled = zone.get("enabled", True)
                        # Only show enabled zones
                        if zone_id and enabled:
                            zone_list.append((zone_id, zone_name))

            # If no zones found, return a helpful message
            if not zone_list:
                zone_list = [("", "No zones configured - update device first")]

            return zone_list

        except Exception as exc:
            self.logger.debug(f"Error getting zone list: {exc}\n{traceback.format_exc(10)}")
            return [("", "Error loading zones")]

    ########################################
    # Menu callbacks defined in MenuItems.xml
    ########################################
    def toggleDebugging(self):
        """Toggle debug logging on/off via plugin menu.

        Switches between normal and debug logging levels and saves
        the preference so it persists across plugin restarts.
        """
        if self.debug:
            self.logger.info("Turning off debug logging")
            self.pluginPrefs["showDebugInfo"] = False
        else:
            self.logger.info("Turning on debug logging")
            self.pluginPrefs["showDebugInfo"] = True
        self.debug = not self.debug


    ########################################
    def updateAllStatus(self):
        """Force immediate update of all devices via plugin menu.

        Triggers an immediate API poll instead of waiting for the
        next scheduled update from the concurrent thread.
        """
        self._next_weather_update = datetime.now()
        self._update_from_netro()

    ########################################
    # pylint: disable=unused-argument
    def pickController(self, dev_filter=None, valuesDict=None, typeId=0):
        """Get sorted list of controllers for menu selection.

        Args:
            dev_filter: Device filter (unused)
            valuesDict: Current dialog values
            typeId: Device type ID

        Returns:
            Sorted list of tuples (device_id, device_name)
        """
        self.logger.threaddebug("pickController")
        retList = []
        for dev in indigo.devices.iter("self"):
            retList.append((dev.id, dev.name))
        retList.sort(key=lambda tup: tup[1])
        return retList

    ########################################
    def configMenuChanged(self, valuesDict):
        """Handle configuration menu changes.

        Called when menu selections change to trigger dynamic UI updates.
        Returns valuesDict unchanged to force other fields to refresh.

        Args:
            valuesDict: Current dialog values

        Returns:
            valuesDict unchanged
        """
        self.logger.threaddebug("configMenuChanged")
        return valuesDict
