#! /usr/bin/env python
# -*- coding: utf-8 -*-
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
from datetime import datetime, date, timedelta

import indigo
import requests

# Import from extracted modules
from constants import (
    MAX_ZONE_DURATION_SECONDS,
    DEFAULT_API_TIMEOUT_SECONDS,
    DEFAULT_WEATHER_UPDATE_INTERVAL_MINUTES,
    FORECAST_UPDATE_INTERVAL_MINUTES,
    MINIMUM_POLLING_INTERVAL_MINUTES,
    ZONE_START_ENDPOINT,
    OPERATIONAL_ERROR_EVENTS,
    COMM_ERROR_EVENTS,
    DEVICE_EVENT_TYPES,
)
from exceptions import ThrottleDelayError
from validators import (
    validate_device_config,
    validate_action_config,
    validate_event_config,
    validate_prefs_config,
)
from api_client import NetroAPIClient
from device_handlers import SprinklerHandler, WhispererHandler, ZoneHandler
from utils import convert_weather_us_to_metric, convert_weather_metric_to_us
from tomorrow_client import TomorrowClient


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
        api_client: NetroAPIClient instance for all API communication
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

        # Initialize Tomorrow.io weather integration
        self._next_weather_update = datetime.now()
        self._next_forecast_update = datetime.now()
        self._weather_update_interval = int(
            pluginPrefs.get("weatherUpdateInterval", DEFAULT_WEATHER_UPDATE_INTERVAL_MINUTES)
        )
        self._tomorrow_client = self._create_tomorrow_client(pluginPrefs)

        # Initialize API client with prefs callbacks for throttle state persistence
        self.api_client = NetroAPIClient(
            timeout=self.timeout,
            logger=self.logger,
            prefs_getter=lambda: dict(self.pluginPrefs),
            prefs_setter=lambda k, v: self.pluginPrefs.__setitem__(k, v)
        )

        # Initialize data structures populated by API calls
        self.person = {}
        self.netro_devices = []
        self.serialNo = None
        self.key_val_list = []

        # Initialize device handlers for state transformation
        self.sprinkler_handler = SprinklerHandler(self.logger)
        self.whisperer_handler = WhispererHandler(self.logger)
        self.zone_handler = ZoneHandler(self.logger)

        # Track last seen event ID per device for v2 event polling
        self._last_event_ids = {}

    ########################################
    # Internal helper methods
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

    def _get_or_create_folder(self, folder_name):
        """Get or create an Indigo variable folder by name.

        Args:
            folder_name: Name of the folder to find or create

        Returns:
            Folder ID (int)
        """
        # Check if folder ID is cached in pluginPrefs
        cached_id = self.pluginPrefs.get("zoneFolderId", 0)
        if cached_id:
            try:
                # Verify folder still exists
                folder = indigo.variables.folders[int(cached_id)]
                return folder.id
            except (KeyError, ValueError):
                pass  # Folder was deleted, recreate

        # Search existing folders
        for folder in indigo.variables.folders:
            if folder.name == folder_name:
                self.pluginPrefs["zoneFolderId"] = folder.id
                return folder.id

        # Create new folder
        folder = indigo.variables.folder.create(folder_name)
        self.pluginPrefs["zoneFolderId"] = folder.id
        self.logger.info(f"Created variable folder '{folder_name}'")
        return folder.id

    @staticmethod
    def _slugify(name):
        """Convert a device/zone name to a safe variable name slug.

        Args:
            name: Human-readable name

        Returns:
            Lowercase alphanumeric string with underscores
        """
        import re
        slug = re.sub(r'[^a-zA-Z0-9]+', '_', name.lower()).strip('_')
        return slug

    def _ensure_zone_variables(self, dev, zones_data):
        """Ensure Indigo variables exist for each zone's moisture level.

        Creates variables in a "Netro" folder. Tracks the mapping
        of zone number → variable ID in device pluginProps. Handles
        zone renames by renaming the variable.

        Args:
            dev: Indigo sprinkler device
            zones_data: List of zone dicts from extract_zone_info
        """
        try:
            folder_id = self._get_or_create_folder("Netro")
            dev_slug = self._slugify(dev.name)

            # Load existing zone→variable mapping from pluginProps
            props = copy.deepcopy(dev.pluginProps)
            mapping_json = props.get("zoneVariableMap", "{}")
            try:
                zone_var_map = json.loads(mapping_json)
            except (json.JSONDecodeError, TypeError):
                zone_var_map = {}

            changed = False
            single_zone = len(zones_data) == 1
            for zone in zones_data:
                zone_num = str(zone["id"])
                zone_name = zone.get("name", "").strip()

                # For single-zone devices (e.g. Pixie) or zones without names,
                # use the device name only. For multi-zone, use zone name.
                if single_zone or not zone_name:
                    var_name = f"zone_moisture_{dev_slug}"
                    zone_name = zone_name or dev.name
                else:
                    zone_slug = self._slugify(zone_name)
                    var_name = f"zone_moisture_{dev_slug}_{zone_slug}"

                if zone_num in zone_var_map:
                    var_id = zone_var_map[zone_num].get("var_id")
                    old_name = zone_var_map[zone_num].get("zone_name", "")
                    # Verify the mapped variable still exists
                    try:
                        var = indigo.variables[int(var_id)]
                        # Variable exists — check if zone was renamed
                        if old_name != zone_name or var.name != var_name:
                            old_var_name = var.name
                            var.name = var_name
                            var.replaceOnServer()
                            zone_var_map[zone_num]["zone_name"] = zone_name
                            zone_var_map[zone_num]["var_name"] = var_name
                            changed = True
                            self.logger.info(
                                f"Zone variable updated: '{old_var_name}' → "
                                f"'{var_name}'"
                            )
                    except (KeyError, ValueError):
                        # Variable was deleted — recreate below
                        del zone_var_map[zone_num]
                        changed = True

                if zone_num not in zone_var_map:
                    # Create new variable for this zone
                    try:
                        var = indigo.variable.create(var_name, value="0", folder=folder_id)
                        zone_var_map[zone_num] = {
                            "var_id": var.id,
                            "var_name": var_name,
                            "zone_name": zone_name,
                        }
                        changed = True
                        self.logger.info(
                            f"Created moisture variable '{var_name}' for "
                            f"zone {zone_num} ({zone_name}) on '{dev.name}'"
                        )
                    except Exception as create_exc:
                        # Variable may already exist (name conflict)
                        try:
                            var = indigo.variables[var_name]
                            zone_var_map[zone_num] = {
                                "var_id": var.id,
                                "var_name": var_name,
                                "zone_name": zone_name,
                            }
                            changed = True
                        except KeyError:
                            self.logger.warning(
                                f"Could not create variable '{var_name}' "
                                f"for zone {zone_num}: {create_exc}"
                            )

            # Save updated mapping back to pluginProps
            if changed:
                props["zoneVariableMap"] = json.dumps(zone_var_map)
                dev.replacePluginPropsOnServer(props)

        except Exception:
            self.logger.warning(
                f"Could not manage zone variables for '{dev.name}': "
                f"\n{traceback.format_exc(10)}"
            )

    @staticmethod
    def _get_device_auth(dev):
        """Get API authentication key and version for a device.

        If the device has an API key configured, uses v2 authentication.
        Otherwise falls back to v1 serial number authentication.

        Args:
            dev: Indigo device with pluginProps

        Returns:
            Tuple of (key, api_version) where key is the auth credential
            and api_version is "1" or "2"
        """
        api_key = dev.pluginProps.get("apiKey", "").strip()
        if api_key:
            return (api_key, "2")
        return (dev.address, "1")

    def _create_tomorrow_client(self, prefs):
        """Create a TomorrowClient if Tomorrow.io weather is configured.

        Args:
            prefs: Plugin preferences dict

        Returns:
            TomorrowClient instance or None if not configured/enabled
        """
        if not prefs.get("tomorrowEnabled", False):
            return None

        api_key = str(prefs.get("tomorrowApiKey", "")).strip()
        location = str(prefs.get("tomorrowLocation", "")).strip()

        if not api_key or not location:
            self.logger.warning(
                "Tomorrow.io weather is enabled but missing required fields "
                "(API key and/or location) — weather integration will not run"
            )
            return None

        return TomorrowClient(
            api_key=api_key,
            location=location,
            logger=self.logger,
            timeout=self.timeout,
        )

    def _update_weather_from_tomorrow(self):
        """Fetch weather from Tomorrow.io and report to all sprinkler devices.

        Called periodically from the polling loop when Tomorrow.io integration
        is enabled. Fetches current weather once, then reports it to each
        enabled sprinkler device via the Netro report_weather endpoint.
        Also updates weather-related device states in Indigo for each
        successfully reported device.

        Uses 1 Tomorrow.io API call + 1 Netro API call per sprinkler device.
        """
        if self._tomorrow_client is None:
            return

        if datetime.now() < self._next_weather_update:
            self.logger.debug(
                f"Next weather update at {self._next_weather_update:%H:%M}, skipping"
            )
            return

        self.logger.info("Fetching weather from Tomorrow.io...")

        # Schedule next update regardless of success/failure
        self._next_weather_update = datetime.now() + timedelta(
            minutes=self._weather_update_interval
        )

        # Fetch weather from Tomorrow.io
        weather_data = self._tomorrow_client.fetch_current_weather()
        if weather_data is None:
            self.logger.warning("Failed to fetch weather from Tomorrow.io, will retry next interval")
            return

        # Map condition codes to human-readable labels
        condition_labels = {0: "Clear", 1: "Cloudy", 2: "Rain", 3: "Snow", 4: "Wind"}
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Report to each enabled sprinkler device
        reported_count = 0
        for dev in [s for s in indigo.devices.iter(filter="self") if s.enabled]:
            if dev.deviceTypeId != "sprinkler":
                continue

            try:
                key, api_version = self._get_device_auth(dev)

                # Tomorrow.io returns metric; convert to US for v1 API
                if api_version == "1":
                    device_weather = convert_weather_metric_to_us(weather_data)
                else:
                    device_weather = dict(weather_data)

                response = self.api_client.report_weather(
                    key, device_weather, api_version=api_version
                )

                if response.get("status") == "OK":
                    reported_count += 1
                    unit_label = "C" if api_version == "2" else "F"
                    self.logger.debug(
                        f"Weather reported to '{dev.name}': "
                        f"{device_weather.get('t')}{unit_label}, "
                        f"condition={device_weather['condition']}"
                    )

                    # Update device states with weather data (always metric from Tomorrow.io)
                    state_updates = [
                        {"key": "weather_condition", "value": condition_labels.get(weather_data["condition"], "Unknown")},
                        {"key": "weather_temperature", "value": weather_data.get("t", 0), "decimalPlaces": 1},
                        {"key": "weather_updated", "value": timestamp},
                    ]
                    if "humidity" in weather_data:
                        state_updates.append({"key": "weather_humidity", "value": weather_data["humidity"]})
                    if "rain" in weather_data:
                        state_updates.append({"key": "weather_rain", "value": weather_data["rain"], "decimalPlaces": 1})
                    if "rain_prob" in weather_data:
                        state_updates.append({"key": "weather_rain_prob", "value": weather_data["rain_prob"]})
                    if "wind_speed" in weather_data:
                        state_updates.append({"key": "weather_wind_speed", "value": weather_data["wind_speed"], "decimalPlaces": 1})
                    if "pressure" in weather_data:
                        state_updates.append({"key": "weather_pressure", "value": weather_data["pressure"], "decimalPlaces": 1})

                    dev.updateStatesOnServer(state_updates)
                else:
                    self.logger.error(
                        f"Error reporting weather to '{dev.name}': {response}"
                    )

            except ThrottleDelayError:
                self.logger.debug(f"Skipping weather report for '{dev.name}' - throttled")
            except Exception as exc:
                self.logger.error(f"Could not report weather to '{dev.name}': {exc}")
                self.logger.debug(f"Weather report error: \n{traceback.format_exc(10)}")

        if reported_count > 0:
            self.logger.info(
                f"Tomorrow.io weather reported to {reported_count} device(s): "
                f"{weather_data.get('t')}C, condition={weather_data['condition']}"
            )

    def _update_forecast_from_tomorrow(self):
        """Fetch daily forecast from Tomorrow.io and report to all sprinkler devices.

        Reports daily forecast data to each sprinkler device via the Netro
        report_weather endpoint. Runs on a separate, longer interval than
        realtime weather updates.

        Uses 1 Tomorrow.io API call + 1 Netro API call per forecast day per device.
        """
        if self._tomorrow_client is None:
            return

        if datetime.now() < self._next_forecast_update:
            return

        self.logger.info("Fetching forecast from Tomorrow.io...")

        # Schedule next update regardless of success/failure
        self._next_forecast_update = datetime.now() + timedelta(
            minutes=FORECAST_UPDATE_INTERVAL_MINUTES
        )

        forecast_data = self._tomorrow_client.fetch_forecast()
        if forecast_data is None:
            self.logger.warning("Failed to fetch forecast from Tomorrow.io, will retry next interval")
            return

        if not forecast_data:
            self.logger.warning("Tomorrow.io returned empty forecast")
            return

        reported_count = 0
        for dev in [s for s in indigo.devices.iter(filter="self") if s.enabled]:
            if dev.deviceTypeId != "sprinkler":
                continue

            try:
                key, api_version = self._get_device_auth(dev)
                days_reported = 0

                for day_weather in forecast_data:
                    # Convert units for v1 devices
                    if api_version == "1":
                        device_weather = convert_weather_metric_to_us(day_weather)
                        # v1 Netro API does not accept t_dew field — strip before sending
                        device_weather.pop("t_dew", None)
                    else:
                        device_weather = dict(day_weather)

                    response = self.api_client.report_weather(
                        key, device_weather, api_version=api_version
                    )

                    if response.get("status") == "OK":
                        days_reported += 1
                    else:
                        self.logger.error(
                            f"Error reporting forecast to '{dev.name}' "
                            f"for {day_weather.get('date')}: {response}"
                        )

                if days_reported > 0:
                    reported_count += 1
                    self.logger.debug(
                        f"Forecast reported to '{dev.name}': {days_reported} days"
                    )

            except ThrottleDelayError:
                self.logger.debug(f"Skipping forecast for '{dev.name}' - throttled")
            except Exception as exc:
                self.logger.error(f"Could not report forecast to '{dev.name}': {exc}")
                self.logger.debug(f"Forecast report error:\n{traceback.format_exc(10)}")

        if reported_count > 0:
            self.logger.info(
                f"Tomorrow.io forecast reported to {reported_count} device(s): "
                f"{len(forecast_data)} days fetched"
            )
        elif forecast_data:
            self.logger.debug("No sprinkler devices available for forecast reporting")

    def _get_zone_devices(self, parent_dev_id):
        """Get all zone devices belonging to a parent controller.

        Args:
            parent_dev_id: Indigo device ID of the parent controller

        Returns:
            Dict mapping zone number (int) to Indigo device
        """
        zone_devs = {}
        for dev in indigo.devices.iter(filter="self.zone"):
            if dev.pluginProps.get("parentDeviceId") == str(parent_dev_id):
                zone_num = int(dev.pluginProps.get("zoneNumber", 0))
                if zone_num > 0:
                    zone_devs[zone_num] = dev
        return zone_devs

    def _ensure_zone_devices(self, parent_dev, zones_data):
        """Create or update zone devices for a parent controller.

        Auto-creates zone devices for zones returned by the API.
        Updates device names if the zone was renamed in Netro.

        Args:
            parent_dev: Indigo sprinkler controller device
            zones_data: List of zone dicts from extract_zone_info
                        (each has "id", "name", "enabled")
        """
        existing = self._get_zone_devices(parent_dev.id)

        for zone in zones_data:
            zone_num = zone["id"]
            zone_name = zone.get("name", "").strip() or f"Zone {zone_num}"
            expected_name = f"{parent_dev.name} - {zone_name}"

            if zone_num in existing:
                zone_dev = existing[zone_num]
                if zone_dev.name != expected_name:
                    self.logger.info(
                        f"Zone renamed: '{zone_dev.name}' -> '{expected_name}'"
                    )
                    zone_dev.name = expected_name
                    try:
                        zone_dev.replaceOnServer()
                    except Exception as exc:
                        self.logger.error(
                            f"Could not rename zone device '{zone_dev.name}' "
                            f"to '{expected_name}': {exc}"
                        )
            else:
                try:
                    props = {
                        "parentDeviceId": str(parent_dev.id),
                        "zoneNumber": str(zone_num),
                    }
                    new_dev = indigo.device.create(
                        protocol=indigo.kProtocol.Plugin,
                        deviceTypeId="zone",
                        name=expected_name,
                        props=props,
                    )
                    new_dev.model = "Netro Zone"
                    new_dev.replaceOnServer()
                    self.logger.info(
                        f"Created zone device '{expected_name}' "
                        f"(zone {zone_num} on '{parent_dev.name}')"
                    )
                except Exception as exc:
                    self.logger.error(
                        f"Could not create zone device for zone {zone_num} "
                        f"on '{parent_dev.name}': {exc}"
                    )

    def _update_zone_devices(self, parent_dev, device_data, schedule_response, moisture_response, api_version):
        """Update all zone devices for a parent controller.

        Args:
            parent_dev: Indigo sprinkler controller device
            device_data: Raw device dict from info API (contains zones array)
            schedule_response: Raw schedules API response (or None)
            moisture_response: Raw moistures API response (or None)
            api_version: "1" or "2"
        """
        zone_devs = self._get_zone_devices(parent_dev.id)
        zones = device_data.get("zones", [])

        for zone_dev in zone_devs.values():
            try:
                zone_num = int(zone_dev.pluginProps.get("zoneNumber", 0))
                if zone_num == 0:
                    continue

                states = []
                zone_states = self.zone_handler.extract_zone_states(zones, zone_num)
                states.extend(zone_states)

                # Check if zone is enabled
                is_enabled = next(
                    (s["value"] for s in zone_states if s["key"] == "enabled"), False
                )

                if is_enabled:
                    if schedule_response:
                        states.extend(
                            self.zone_handler.process_zone_schedules(
                                schedule_response, zone_num, api_version=api_version
                            )
                        )

                    if moisture_response:
                        states.extend(
                            self.zone_handler.process_zone_moisture(moisture_response, zone_num)
                        )

                if states:
                    zone_dev.updateStatesOnServer(states)

                # Set error state and icon after state update
                if not is_enabled:
                    zone_dev.setErrorStateOnServer('disabled')
                    zone_dev.updateStateImageOnServer(indigo.kStateImageSel.NoImage)
                else:
                    zone_dev.setErrorStateOnServer('')
                    is_irrigating = next(
                        (s["value"] for s in states if s["key"] == "isIrrigating"), False
                    )
                    if is_irrigating:
                        zone_dev.updateStateImageOnServer(indigo.kStateImageSel.SprinklerOn)
                    else:
                        zone_dev.updateStateImageOnServer(indigo.kStateImageSel.HumiditySensor)
            except Exception as exc:
                self.logger.error(f"Error updating zone device '{zone_dev.name}': {exc}")
                self.logger.debug(f"Zone update error: \n{traceback.format_exc(10)}")

    ########################################
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
        'Whisperer', making API calls and delegating state transformation
        to the appropriate handler classes.

        Exceptions are caught and logged without interrupting the polling cycle.
        """
        self.logger.debug("_update_from_netro")
        try:
            for dev in [s for s in indigo.devices.iter(filter="self") if s.enabled]:
                if dev.deviceTypeId == "sprinkler":
                    self._update_sprinkler_device(dev)
                elif dev.deviceTypeId == "Whisperer":
                    self._update_whisperer_device(dev)
        except Exception as exc:
            self.logger.error(f"unexpected error updating netro devices: {exc.__class__.__name__}")
            self.logger.debug(f"traceback:\n{traceback.format_exc(10)}")

    def _update_sprinkler_device(self, dev):
        """Update a single sprinkler device from Netro API.

        Args:
            dev: Indigo sprinkler device to update
        """
        try:
            # Get auth credentials (API key for v2, serial for v1)
            key, api_version = self._get_device_auth(dev)
            schedule_dict = None
            moisture_dict = None

            # Get device info
            reply_dict = self.api_client.get_device_info(key, api_version=api_version)

            # Delegate state transformation to handler
            update_list, is_online, device_data = self.sprinkler_handler.process_device_info(
                reply_dict, dev.address, api_version=api_version
            )

            # Update person/netro_devices for legacy compatibility
            netro_serial = device_data.get("serial", dev.address)
            device_data["id"] = netro_serial
            self.person = {"id": netro_serial, "devices": [device_data]}
            self.netro_devices = self.person["devices"]
            self.logger.debug(self.netro_devices)

            # Set error state based on online status
            if not is_online:
                dev.setErrorStateOnServer('unavailable')
            else:
                dev.setErrorStateOnServer('')

            # Get schedule info
            active_schedule_name = None
            try:
                schedule_dict = self.api_client.get_schedules(key, api_version=api_version)
                schedule_states, active_schedule_name = self.sprinkler_handler.process_schedules(
                    schedule_dict, api_version=api_version
                )
                update_list.extend(schedule_states)
            except Exception:
                update_list.append(
                    {"key": "activeSchedule", "value": "Error getting current schedule"})
                self.logger.debug(f"API error: \n{traceback.format_exc(10)}")
                self._fireTrigger("getScheduleCall")

            # Send the state updates to the server
            if update_list:
                dev.updateStatesOnServer(update_list)

            # Update zone information (properties, not states)
            zone_names, max_durations, zones_data = self.sprinkler_handler.extract_zone_info(
                device_data, self.maxZoneRunTime
            )
            props = copy.deepcopy(dev.pluginProps)
            props["NumZones"] = len(device_data.get("zones", []))
            props["ZoneNames"] = zone_names
            props["MaxZoneDurations"] = ", ".join(max_durations)
            props["zones"] = json.dumps(zones_data)
            if active_schedule_name:
                props["ScheduledZoneDurations"] = active_schedule_name
            dev.replacePluginPropsOnServer(props)

            # Fetch moisture levels (used by zone devices below)
            try:
                moisture_dict = self.api_client.get_moistures(key, api_version=api_version)
            except Exception:
                self.logger.warning(f"Moisture API unavailable for '{dev.name}' - zone moisture states may be stale")
                self.logger.debug(f"Moisture API error: \n{traceback.format_exc(10)}")

            # Auto-create and update zone devices
            self._ensure_zone_devices(dev, zones_data)
            self._update_zone_devices(
                dev, device_data, schedule_dict, moisture_dict, api_version
            )

            # Ensure Indigo variables exist for each zone (for variable substitution)
            # Must be after replacePluginPropsOnServer to avoid props overwrite race
            self._ensure_zone_variables(dev, zones_data)

            # Poll device events (v2 only)
            if api_version == "2":
                try:
                    today = date.today().strftime("%Y-%m-%d")
                    events_dict = self.api_client.get_events(key, start_date=today)
                    first_run = dev.id not in self._last_event_ids
                    last_id = self._last_event_ids.get(dev.id, 0)
                    new_events, highest_id = self.sprinkler_handler.process_events(
                        events_dict, last_event_id=last_id
                    )
                    self._last_event_ids[dev.id] = highest_id

                    # Skip firing triggers on first poll after startup to avoid
                    # replaying today's events as duplicate triggers
                    if first_run:
                        self.logger.debug(
                            f"Events catch-up for '{dev.name}': "
                            f"skipped {len(new_events)} existing events"
                        )
                    else:
                        for event in new_events:
                            event_code = event.get("event", 0)
                            event_name = DEVICE_EVENT_TYPES.get(
                                event_code, f"unknown({event_code})"
                            )
                            self.logger.info(
                                f"Device event: '{dev.name}' {event_name} "
                                f"at {event.get('time', 'unknown')}"
                            )
                            self._fireTrigger(
                                f"deviceEvent_{event_code}", dev.id
                            )
                except Exception:
                    self.logger.warning(f"Events API error for '{dev.name}': \n{traceback.format_exc(10)}")

        except ThrottleDelayError:
            # Already logged detailed error in api_client, just skip this device
            pass
        except requests.exceptions.HTTPError as exc:
            self._handle_http_error(exc)
            self._fireTrigger("personInfoCall")
        except Exception:
            self.logger.error("Error getting user data from Netro via API.")
            self.logger.debug(f"API error: \n{traceback.format_exc(10)}")
            self._fireTrigger("personInfoCall")

    def _update_whisperer_device(self, dev):
        """Update a single Whisperer sensor device from Netro API.

        Args:
            dev: Indigo Whisperer device to update
        """
        try:
            # Get auth credentials (API key for v2, serial for v1)
            key, api_version = self._get_device_auth(dev)
            self.logger.debug(f"Device ID: {dev.address} (API v{api_version})")

            if dev.sensorValue is not None:
                # Get sensor data and delegate transformation to handler
                sensor_dict = self.api_client.get_sensor_data(key, api_version=api_version)
                states, has_readings = self.whisperer_handler.process_sensor_data(
                    sensor_dict, dev.address, api_version=api_version
                )

                # Set error state based on readings availability
                if not has_readings:
                    dev.setErrorStateOnServer('sensor offline - no recent data')
                else:
                    dev.setErrorStateOnServer('')

                # Skip state update if the reading hasn't changed — this keeps
                # Indigo's lastChanged reflecting when new sensor data arrived,
                # not when we last polled the API
                new_reading_id = next(
                    (s["value"] for s in states if s["key"] == "readingID"), None
                )
                current_reading_id = dev.states.get("readingID", None)
                if (
                    new_reading_id is not None
                    and current_reading_id is not None
                    and str(new_reading_id) == str(current_reading_id)
                ):
                    self.logger.debug(
                        f"Sensor '{dev.name}' reading unchanged (ID {new_reading_id}), skipping update"
                    )
                    return

                # Update states with onOffState handling
                if dev.onState is not None:
                    states.append({'key': 'onOffState', 'value': not dev.onState})
                    dev.updateStatesOnServer(states)
                    if dev.onState:
                        dev.updateStateImageOnServer(indigo.kStateImageSel.HumiditySensorOn)
                    else:
                        dev.updateStateImageOnServer(indigo.kStateImageSel.HumiditySensor)
                else:
                    dev.updateStatesOnServer(states)
                    dev.updateStateImageOnServer(indigo.kStateImageSel.HumiditySensor)
            elif dev.onState is not None:
                dev.updateStateOnServer("onOffState", not dev.onState)
                dev.updateStateImageOnServer(indigo.kStateImageSel.Auto)
            else:
                dev.updateStateImageOnServer(indigo.kStateImageSel.Auto)

        except ThrottleDelayError:
            # Already logged detailed warning in api_client, just skip this device
            pass
        except Exception:
            self.logger.error(f"error getting sensor data from netro api for device \"{dev.name}\"")
            self.logger.debug(f"API error: \n{traceback.format_exc(10)}")

    def _handle_http_error(self, exc):
        """Handle HTTP errors with appropriate logging.

        Args:
            exc: HTTPError exception to handle
        """
        if hasattr(exc, 'response') and exc.response is not None:
            try:
                error_data = exc.response.json()
                if error_data.get("status") == "ERROR":
                    errors = error_data.get("errors", [])
                    recognized_codes = {1, 3}  # invalid key, rate limit
                    is_recognized = any(
                        error.get("code") in recognized_codes
                        for error in errors
                    )
                    if not is_recognized:
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

    ########################################
    # startup, concurrent thread, and shutdown methods
    ########################################
    def startup(self):
        """Called when plugin is first enabled.

        Logs startup message and API version info per device.
        Main initialization happens in __init__().
        """
        self.logger.info("Netro Sprinklers Started")

        # Log API version for each enabled device (skip zone devices — they use parent auth)
        for dev in [s for s in indigo.devices.iter(filter="self") if s.enabled and s.deviceTypeId != "zone"]:
            _, api_version = self._get_device_auth(dev)
            auth_type = "API key" if api_version == "2" else "serial number"
            self.logger.info(f"Device '{dev.name}' using API v{api_version} ({auth_type} auth)")

        # Notify Indigo to re-read state lists (picks up any Devices.xml changes)
        for dev in indigo.devices.iter(filter="self"):
            dev.stateListOrDisplayStateIdChanged()

        # Log Tomorrow.io weather status
        if self._tomorrow_client is not None:
            self.logger.info(
                f"Tomorrow.io weather integration enabled "
                f"(updating every {self._weather_update_interval} minutes)"
            )
        else:
            self.logger.info("Tomorrow.io weather integration not enabled")

        # Subscribe to variable changes for zone moisture auto-link
        indigo.variables.subscribeToChanges()

    ########################################
    def shutdown(self):
        """Called when plugin is disabled or Indigo quits.

        Logs shutdown message and performs cleanup.
        """
        self.logger.info("Netro Sprinklers Stopped")

    def runConcurrentThread(self):
        """Background thread that polls Netro API periodically.

        This thread runs continuously while the plugin is enabled, calling
        _update_from_netro() every pollingInterval minutes. Uses self.sleep()
        to allow clean shutdown when plugin is disabled.

        The polling interval is configurable but must be at least 3 minutes
        to avoid hitting Netro's API rate limit (2000 calls/day).

        Includes proactive pause when API tokens drop below threshold to
        prevent exhausting the daily limit.

        Exceptions during updates are silently caught to prevent the thread
        from exiting - errors are logged within _update_from_netro().
        """
        self.logger.debug("Starting concurrent thread")
        while True:
            try:
                # Check proactive pause before polling
                if self.api_client.should_pause_polling:
                    self.logger.warning(
                        f"Polling paused: only {self.api_client.token_remaining} tokens "
                        f"remaining (threshold: 100), will resume when tokens reset"
                    )
                else:
                    self._update_from_netro()

                # Tomorrow.io uses its own API; run regardless of Netro token pause
                self._update_weather_from_tomorrow()
                self._update_forecast_from_tomorrow()
            except self.StopThread:
                # Clean shutdown requested by Indigo - must re-raise
                self.logger.debug("Concurrent thread stopping")
                raise
            except Exception:
                # Log error with full traceback but continue polling - thread must not die
                self.logger.exception("Error in polling loop, will retry next interval")
            self.sleep(self.pollingInterval * 60)

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
        """Validate device configuration before saving."""
        self.logger.threaddebug("validateDeviceConfigUi")
        is_valid, sanitized, errors = validate_device_config(dict(valuesDict), typeId)

        if is_valid:
            # Update valuesDict with sanitized values
            for key, value in sanitized.items():
                valuesDict[key] = value
            return True, valuesDict
        errorsDict = indigo.Dict(errors)
        return False, valuesDict, errorsDict

    ########################################
    # pylint: disable=unused-argument
    def validateActionConfigUi(self, valuesDict, typeId, devId):
        """Validate action configuration before saving."""
        self.logger.threaddebug(f"validateActionConfigUi for {typeId}")
        is_valid, sanitized, errors = validate_action_config(dict(valuesDict), typeId)

        if is_valid:
            for key, value in sanitized.items():
                valuesDict[key] = value
            return True, valuesDict
        errorsDict = indigo.Dict(errors)
        return False, valuesDict, errorsDict

    ########################################
    # pylint: disable=unused-argument
    def validateEventConfigUi(self, valuesDict, typeId, devId):
        """Validate event/trigger configuration before saving."""
        self.logger.threaddebug("validateEventConfigUi")
        is_valid, sanitized, errors = validate_event_config(dict(valuesDict), typeId)

        if is_valid:
            for key, value in sanitized.items():
                valuesDict[key] = value
            return True, valuesDict
        errorsDict = indigo.Dict(errors)
        return False, valuesDict, errorsDict

    ########################################
    def validatePrefsConfigUi(self, valuesDict):
        """Validate plugin configuration before saving."""
        self.logger.threaddebug("validatePrefsConfigUi")
        is_valid, sanitized, errors = validate_prefs_config(dict(valuesDict))

        if is_valid:
            for key, value in sanitized.items():
                valuesDict[key] = value
            return True, valuesDict
        errorsDict = indigo.Dict(errors)
        return False, valuesDict, errorsDict

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

            # Update Tomorrow.io weather integration
            weather_settings_changed = False
            try:
                new_interval = int(valuesDict.get(
                    "weatherUpdateInterval", DEFAULT_WEATHER_UPDATE_INTERVAL_MINUTES
                ))
                if new_interval != self._weather_update_interval:
                    self._weather_update_interval = new_interval
                    weather_settings_changed = True
                    self.logger.info(
                        f"Weather update interval updated to {new_interval} minutes"
                    )
            except (ValueError, TypeError):
                self.logger.warning("Invalid weather update interval value, keeping existing setting")

            old_client = self._tomorrow_client
            new_client = self._create_tomorrow_client(valuesDict)
            was_enabled = old_client is not None
            now_enabled = new_client is not None
            if was_enabled and now_enabled:
                weather_settings_changed = weather_settings_changed or (
                    old_client.api_key != new_client.api_key
                    or old_client.location != new_client.location
                )
            self._tomorrow_client = new_client

            if now_enabled and not was_enabled:
                self._next_weather_update = datetime.now()
                self._next_forecast_update = datetime.now()
                self.logger.info("Tomorrow.io weather integration enabled")
            elif not now_enabled and was_enabled:
                self.logger.info("Tomorrow.io weather integration disabled")
            elif now_enabled:
                if weather_settings_changed:
                    self._next_weather_update = datetime.now()
                    self._next_forecast_update = datetime.now()
                self.logger.debug("Tomorrow.io weather settings updated")

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
        if origDev.deviceTypeId == "zone":
            return False
        return origDev.states.get("id") != newDev.states.get("id")

    ########################################
    # pylint: disable=unused-argument
    def deviceStartComm(self, dev):
        """Called when device communication should start.

        The concurrent thread will handle the initial update within seconds,
        so we don't need to make redundant API calls here.

        Args:
            dev: Device starting communication
        """
        # Don't update here - would cause duplicate API calls for each device
        # The concurrent thread handles regular updates
        pass

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
                elif trigger.pluginTypeId == "deviceEvent":
                    # V2 device events — match device ID and event type
                    if event.startswith("deviceEvent_") and dev_id is not None:
                        try:
                            if int(trigger.pluginProps["id"]) == dev_id:
                                trigger_event_type = trigger.pluginProps.get("eventType", "all")
                                event_code = event.split("_", 1)[1]
                                if trigger_event_type == "all" or trigger_event_type == event_code:
                                    indigo.trigger.execute(trigger)
                        except (ValueError, KeyError) as exc:
                            self.logger.warning(
                                f"Skipping deviceEvent trigger {trigger.id}: "
                                f"invalid config — {exc}"
                            )
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

    def variableUpdated(self, origVar, newVar):
        """Called when any subscribed variable changes.

        Checks if the variable is a zone moisture variable. If so,
        calls set_moisture API for the corresponding zone.

        Args:
            origVar: Variable before change
            newVar: Variable after change
        """
        # Only act on value changes
        if origVar.value == newVar.value:
            return

        # Search all sprinkler devices for a zone variable mapping that matches
        for dev in indigo.devices.iter(filter="self.sprinkler"):
            mapping_json = dev.pluginProps.get("zoneVariableMap", "{}")
            try:
                zone_var_map = json.loads(mapping_json)
            except (json.JSONDecodeError, TypeError) as exc:
                self.logger.warning(f"Invalid zoneVariableMap on '{dev.name}': {exc}")
                continue

            for zone_num, var_info in zone_var_map.items():
                if str(var_info.get("var_id")) == str(newVar.id):
                    # Found the matching zone — call set_moisture
                    try:
                        moisture = int(float(newVar.value))
                    except (ValueError, TypeError):
                        self.logger.warning(
                            f"Zone moisture variable '{newVar.name}' has "
                            f"non-numeric value '{newVar.value}', ignoring"
                        )
                        return

                    if moisture < 0 or moisture > 100:
                        self.logger.warning(
                            f"Zone moisture variable '{newVar.name}' value "
                            f"{moisture} out of range (0-100), ignoring"
                        )
                        return

                    key, api_version = self._get_device_auth(dev)
                    try:
                        response = self.api_client.set_moisture(
                            key, int(zone_num), moisture, api_version=api_version
                        )
                        if response.get("status") == "OK":
                            self.logger.info(
                                f"Auto-set moisture for zone {zone_num} on "
                                f"'{dev.name}' to {moisture}% "
                                f"(from variable '{newVar.name}')"
                            )
                            # Update the zone device state too
                            zone_devs = self._get_zone_devices(dev.id)
                            if int(zone_num) in zone_devs:
                                zone_devs[int(zone_num)].updateStateOnServer(
                                    "moisture", moisture, uiValue=f"{moisture}%"
                                )
                        else:
                            self.logger.error(
                                f"Error auto-setting moisture for zone {zone_num}: "
                                f"{response.get('status')}"
                            )
                    except Exception:
                        self.logger.error(
                            f"API error auto-setting moisture for zone {zone_num}"
                        )
                        self.logger.debug(f"API error: \n{traceback.format_exc(10)}")
                    return  # Found match, stop searching

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
        # Check if API is throttled
        if self.api_client.is_throttled:
            self.logger.error(
                f"API calls have violated rate limit - next connection attempt at "
                f"{self.api_client.throttle_expires:%H:%M:%S}")
            if action.sprinklerAction == indigo.kSprinklerAction.ZoneOn:
                self._fireTrigger("startZoneFailed", dev.id)
            elif action.sprinklerAction == indigo.kSprinklerAction.AllZonesOff:
                self._fireTrigger("stopFailed", dev.id)
            return

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
                    self.api_client.make_request(ZONE_START_ENDPOINT, method="put", data=data)
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
            try:
                key, api_version = self._get_device_auth(dev)
                self.api_client.stop_watering(key, api_version=api_version)
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
            self._next_forecast_update = datetime.now()
            self._update_from_netro()
            self._update_weather_from_tomorrow()
            self._update_forecast_from_tomorrow()

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
                key, api_version = self._get_device_auth(dev)
                response = self.api_client.set_no_water(key, num_Days, api_version=api_version)
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
    def setZoneMoisture(self, pluginAction, dev):
        """Override moisture for this zone device.

        Looks up the parent controller's auth credentials and calls
        set_moisture API for this zone.

        Args:
            pluginAction: Action parameters containing moisture value
            dev: Zone device
        """
        try:
            zone_num = int(dev.pluginProps.get("zoneNumber", 0))
            parent_id = int(dev.pluginProps.get("parentDeviceId", 0))
            try:
                parent_dev = indigo.devices[parent_id]
            except KeyError:
                self.logger.error(
                    f"Parent controller (ID {parent_id}) "
                    f"not found for zone '{dev.name}'"
                )
                return

            moisture_raw = self.substitute(pluginAction.props.get("moisture", ""))
            try:
                moisture = int(float(moisture_raw))
            except (ValueError, TypeError):
                self.logger.error(
                    f"Moisture value '{moisture_raw}' is not a valid number"
                )
                return

            if moisture < 0 or moisture > 100:
                self.logger.error(f"Moisture value {moisture} is out of range (0-100)")
                return

            key, api_version = self._get_device_auth(parent_dev)
            response = self.api_client.set_moisture(key, zone_num, moisture, api_version=api_version)
            if response.get("status") == "OK":
                self.logger.info(f"Moisture for '{dev.name}' set to {moisture}%")
                dev.updateStateOnServer("moisture", moisture, uiValue=f"{moisture}%")
            else:
                self.logger.error(f"Error setting moisture for '{dev.name}': {response.get('status')}")
        except Exception:
            self.logger.error(f"Could not set moisture for '{dev.name}'")
            self.logger.debug(f"API error: \n{traceback.format_exc(10)}")

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
            status = 0 if pluginAction.props["mode"] else 1
            key, api_version = self._get_device_auth(dev)
            self.api_client.set_device_status(key, status, api_version=api_version)
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

            # Build zones list for API
            zones = [{"id": zone_id, "duration": duration}]

            # Parse start_time if provided
            start_time_int = None
            if start_time:
                try:
                    start_time_int = int(start_time)
                except ValueError:
                    self.logger.error(f"Invalid start_time format (must be Unix timestamp): {start_time}")
                    return

            # Make API call
            key, api_version = self._get_device_auth(dev)
            response = self.api_client.start_watering(
                key, zones, delay, start_time_int, api_version=api_version
            )
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
            # Build weather data payload
            weather_data = {
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
                            weather_data[api_key] = int(value)
                        else:
                            weather_data[api_key] = float(value)
                    except ValueError:
                        self.logger.warning(f"Invalid value for {field}: {value}, skipping")

            # Validate required temperature field
            if "t" not in weather_data:
                self.logger.error("Current temperature is required for weather reporting")
                return

            # Get auth credentials and convert units if needed
            key, api_version = self._get_device_auth(dev)

            # V2 API expects metric units — convert from US if device uses US units
            if api_version == "2" and dev.pluginProps.get("units", "US") == "US":
                weather_data = convert_weather_us_to_metric(weather_data)

            # Make API call
            response = self.api_client.report_weather(
                key, weather_data, api_version=api_version
            )
            response_status = response.get("status")

            if response_status == "OK":
                unit_label = "C" if api_version == "2" else "F"
                self.logger.info(
                    f"Weather data reported to Netro for {weather_data['date']}: "
                    f"{weather_data.get('t')}{unit_label}, condition={weather_data['condition']}")
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
        self._next_forecast_update = datetime.now()
        self._update_from_netro()
        self._update_weather_from_tomorrow()
        self._update_forecast_from_tomorrow()

    def refreshWeather(self):
        """Force immediate weather and forecast update from Tomorrow.io via plugin menu."""
        if self._tomorrow_client is None:
            self.logger.warning("Tomorrow.io weather integration is not configured")
            return
        self._next_weather_update = datetime.now()
        self._next_forecast_update = datetime.now()
        self._update_weather_from_tomorrow()
        self._update_forecast_from_tomorrow()

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
