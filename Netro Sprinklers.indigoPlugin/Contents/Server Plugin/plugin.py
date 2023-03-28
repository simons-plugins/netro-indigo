#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# Copyright (c) 2014, Perceptive Automation, LLC. All rights reserved.
# http://www.indigodomo.com

import indigo
import urllib.request
import requests
import json
import copy
import traceback
from operator import itemgetter
from datetime import datetime, timedelta, time
from dateutil import tz
from distutils.version import LooseVersion
import random

NETRO_API_VERSION = "1"
NETRO_MAX_ZONE_DURATION = 10800
DEFAULT_API_CALL_TIMEOUT = 5  # number of seconds after which we time out any network calls
MINIMUM_POLLING_INTERVAL = 3  # number of minutes between each poll, default is 3 (changed 2/27/2018 to help avoid throttling)
DEFAULT_WEATHER_UPDATE_INTERVAL = 10  # number of minutes between each forecast update, default is 10
THROTTLE_LIMIT_TIMER = 61  # number of minutes to wait if we've received a throttle error before doing any API calls
FORECAST_UPDATE_INTERVAL = 60  # minutes between forecast updates

API_URL = "http://api.netrohome.com/npa/v{apiVersion}/info.json?key="
PERSON_URL = API_URL + "{personId}"
PERSON_INFO_URL = PERSON_URL.format(apiVersion=NETRO_API_VERSION, personId="info")
DEVICE_BASE_URL = API_URL + ""
DEVICE_GET_URL = DEVICE_BASE_URL + "{deviceId}"

DEVICE_CURRENT_SCHEDULE_URL = "http://api.netrohome.com/npa/v{apiVersion}/schedules.json?key=" + "{deviceId}"
DEVICE_STOP_WATERING_URL = DEVICE_BASE_URL + "stop_water"
DEVICE_TURN_OFF_URL = "http://api.netrohome.com/npa/v{apiVersion}/set_status.json"
DEVICE_TURN_ON_URL = "http://api.netrohome.com/npa/v{apiVersion}/set_status.json"
DEVICE_NO_WATER = "http://api.netrohome.com/npa/v{apiVersion}/no_water.json"
# DEVICE_GET_FORECAST_URL = DEVICE_GET_URL + "/forecast?units={units}"
ZONE_URL = API_URL + "zone/"
ZONE_START_URL = ZONE_URL + "start"
# SCHEDULERULE_URL = API_URL + "schedulerule/{scheduleRuleId}"
# SCHEDULERULE_START_URL = SCHEDULERULE_URL.format(apiVersion=NETRO_API_VERSION, scheduleRuleId="start")
# SCHEDULERULE_SEASONAL_ADJ_URL = SCHEDULERULE_URL.format(apiVersion=NETRO_API_VERSION,scheduleRuleId="seasonal_adjustment")


ALL_OPERATIONAL_ERROR_EVENTS = {
    "startZoneFailed",
    "stopFailed",
    "startNetroScheduleFailed",
    "setSeasonalAdjustmentFailed",
    "setStandbyFailed",
}

ALL_COMM_ERROR_EVENTS = {
    "personCall",
    "personInfoCall",
    "getScheduleCall",
    "forecastCall",
}


class ThrottleDelayError(Exception):
    pass


def convert_timestamp(timestamp):
    from_zone = tz.tzutc()
    to_zone = tz.tzlocal()
    time_utc = datetime.utcfromtimestamp(timestamp / 1000)
    time_utc_gmt = time_utc.replace(tzinfo=from_zone)
    return time_utc_gmt.astimezone(to_zone)


def get_key_from_dict(a_key, a_dict):
    try:
        return a_dict[a_key]
    except KeyError:
        return "unavailable from API"
    except (Exception,):
        return "unknown error"


################################################################################
class Plugin(indigo.PluginBase):
    ########################################
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        super(Plugin, self).__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
        # Used to control when to show connection errors (vs just repeated retries)
        #indigo.debugger()
        self._displayed_connection_error = False
        self.pluginId = pluginId
        self.debug = pluginPrefs.get("showDebugInfo", False)
        self.pollingInterval = int(pluginPrefs.get("pollingInterval", MINIMUM_POLLING_INTERVAL))
        self.timeout = int(pluginPrefs.get("apiTimeout", DEFAULT_API_CALL_TIMEOUT))

        self.unused_devices = {}
        self.access_token = pluginPrefs.get("accessToken", None)
        self.person_id = pluginPrefs.get("personId", None)
        self.maxZoneRunTime = int(pluginPrefs.get("maxZoneRunTime", NETRO_MAX_ZONE_DURATION))

        if self.access_token:
            self.headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        else:
            self.logger.warn("You must specify your API token in the plugin's config before the plugin can be used.")
            self.headers = None
        self.triggerDict = {}


    ########################################
    # Internal helper methods
    ########################################

    def _make_api_call(self, url, request_method="get", data=None):
        try:
            indigo.debugger()
            self.logger.debug(url)
            if request_method == "put":
                method = requests.put
            elif request_method == "post":
                method = requests.post
            else:
                method = requests.get
            if data and request_method in ["put", "post"]:
                #indigo.debugger()
                r = method(url, data=json.dumps(data), headers=self.headers)
                if r.status_code == 200:
                    return_val = r.json()
                elif r.status_code == 204:
                    return_val = True
                else:
                    r.raise_for_status()
                    self._displayed_connection_error = False
            else:
                openUrl = urllib.request.urlopen(url)
                if openUrl.getcode() == 200:
                    data = openUrl.read()
                    return_val = json.loads(data)
                else:
                    print("Error receiving data", openUrl.getcode())

            return return_val
        except requests.exceptions.ConnectionError as exc:
            if not self._displayed_connection_error:
                self.logger.error("Connection to Netro API server failed. Will continue to retry silently.")
                self._displayed_connection_error = True
            raise exc
        except requests.exceptions.ReadTimeout as exc:
            if not self._displayed_connection_error:
                self.logger.error(
                    "Unable to contact device - the controller may be offline. Will continue to retry silently.")
                self._displayed_connection_error = True
            raise exc
        except requests.exceptions.Timeout as exc:
            if not self._displayed_connection_error:
                self.logger.error("Connection to Netro API server failed. Will continue to retry silently.")
                self._displayed_connection_error = True
            raise exc
        except requests.exceptions.HTTPError as exc:
            if exc.response.status_code == 429:
                # We've hit the throttle limit - we need to back off on all requests for some period of time
                self.throttle_next_call = datetime.now() + timedelta(minutes=THROTTLE_LIMIT_TIMER)
                self._fireTrigger("rateLimitExceeded")
            raise exc
        except ThrottleDelayError as exc:
            self.logger.error(str(exc))
            self.logger.debug(f"{str(exc)}:\n{traceback.format_exc(10)}")
            raise exc
        except Exception as exc:
            self.logger.error(
                f"Connection to Netro API server failed with exception: {exc.__class__.__name__}. Check the log file for full details.")
            self.logger.debug(
                f"Connection to Netro API server failed with exception:\n{traceback.format_exc(10)}")
            raise exc
        indigo.debugger()
    ########################################
    def _get_device_dict(self, dev_id):
        indigo.debugger()
        dev_list = [dev_dict for dev_dict in self.person["devices"] if dev_dict["id"] == dev_id]
        if len(dev_list):
            return dev_list[0]
        else:
            return None



    ########################################
    def _get_zone_dict(self, dev_id, zoneNumber):
        indigo.debugger()
        dev_dict = self._get_device_dict(dev_id)
        if dev_dict:
            zone_list = [zone_dict for zone_dict in dev_dict["zones"] if zone_dict["ith"] == zoneNumber]
            if len(zone_list):
                return zone_list[0]
        return None

    ########################################
    def _update_from_netro(self):
        self.logger.debug("_update_from_netro")
        try:
            for dev in [s for s in indigo.devices.iter(filter="self") if s.enabled]:
                    # indigo.debugger()

                    # Update defined Netro controllers
                    if dev.deviceTypeId == "sprinkler":
                        try:
                            # indigo.debugger()
                            reply_dict = self._make_api_call(
                                PERSON_URL.format(apiVersion=NETRO_API_VERSION, personId=dev.address))

                            reply_dict_data = reply_dict["data"]
                            reply_dict_device = reply_dict_data["device"]
                            reply_dict_meta = reply_dict["meta"]

                            ######NEED TO CREATE A DICT OF DEVICES CONTAINING ONLY SINGLE DEVICE
                            # insert Netro serial number into dict as "id"
                            netroSerial = reply_dict_device["serial"]
                            reply_dict_device_serial = {"id": netroSerial}

                            # insert on key based on "status"
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
                        except Exception as exc:
                            self.logger.error("Error getting user data from Netro via API.")
                            self.logger.debug(f"API error: \n{traceback.format_exc(10)}")
                            self._fireTrigger("personInfoCall")
                            return
                        #indigo.debugger()
                        update_list = [{"key": "id", "value": reply_dict_device["id"]},
                                       {"key": "api_version", "value": reply_dict_device["version"]},
                                       {"key": "address", "value": get_key_from_dict("macAddress", reply_dict_device)},
                                       {"key": "model", "value": get_key_from_dict("model", reply_dict_device)},
                                       {"key": "paused", "value": get_key_from_dict("paused", reply_dict_device)},
                                       {"key": "scheduleModeType",
                                        "value": get_key_from_dict("scheduleModeType", reply_dict_device)},
                                       {"key": "status", "value": get_key_from_dict("status", reply_dict_device)}]
                        # "status" is ONLINE or OFFLINE - if the latter it's unplugged or otherwise can't communicate with the cloud
                        # note: it often takes a REALLY long time for the API to return OFFLINE, and sometimes it never does.
                        if dev.states["status"] == "OFFLINE":
                            dev.setErrorStateOnServer('unavailable')
                        else:
                            dev.setErrorStateOnServer('')

                        update_list.append({"key": "token_remaining", 'value': reply_dict_device["token_remaining"]})
                        update_list.append({"key": "time", 'value': reply_dict_device["time"]})
                        update_list.append({"key": "last_active", 'value': reply_dict_device["last_active"]})
                        update_list.append({"key": "token_reset", 'value': reply_dict_device["token_reset"]})
                        update_list.append({"key": "name", "value": reply_dict_device["name"]})
                        activeScheduleName = None

                        # Get the current schedule for the device - it will tell us if it's running or not
                        indigo.debugger()
                        try:
                            schedule_dict = self._make_api_call(
                                DEVICE_CURRENT_SCHEDULE_URL.format(apiVersion=NETRO_API_VERSION,
                                                                   deviceId=netroSerial))
                            #loop all possible schedules to find active
                            all_schedules_data = schedule_dict["data"]
                            all_schedules = all_schedules_data["schedules"]

                            for sch_dict in all_schedules:
                                if sch_dict["status"] == "EXECUTING":
                                    current_schedule_dict = sch_dict
                                else:
                                    current_schedule_dict =  ""

                            if len(current_schedule_dict):
                                # Something is running, so we need to figure out if it's a manual or automatic schedule and
                                # if it's automatic (a Netro schedule) then we need to get the name of that schedule
                                update_list.append(
                                    {"key": "activeZone", "value": current_schedule_dict["zone"]})
                                if current_schedule_dict["source"] == "AUTOMATIC":
                                    schedule_detail_dict = self._make_api_call(
                                        SCHEDULERULE_URL.format(apiVersion=NETRO_API_VERSION,
                                                                scheduleRuleId=current_schedule_dict[
                                                                    "scheduleRuleId"]))
                                    update_list.append(
                                        {"key": "activeSchedule", "value": schedule_detail_dict["source"]})
                                    activeScheduleName = schedule_detail_dict["name"]

                                else:
                                    update_list.append(
                                        {"key": "activeSchedule", "value": current_schedule_dict["source"].title()})
                                    activeScheduleName = current_schedule_dict["source"].title()
                            else:
                                update_list.append({"key": "activeSchedule", "value": "No active schedule"})
                                # Show no zones active
                                update_list.append({"key": "activeZone", "value": 0})
                        except Exception as exc:
                            update_list.append({"key": "activeSchedule", "value": "Error getting current schedule"})
                            self.logger.debug("API error: \n{}".format(traceback.format_exc(10)))
                            self._fireTrigger("getScheduleCall")

                        # Send the state updates to the server
                        if len(update_list):
                            dev.updateStatesOnServer(update_list)

                        # Update zone information as necessary - these are properties, not states.
                        zoneNames = ""
                        maxZoneDurations = ""
                        indigo.debugger()
                        dev_dict=ls_reply_dict_devices[0]
                        for zone in sorted(dev_dict["zones"], key=itemgetter('ith')):
                            zoneNames += ", {}".format(zone["name"]) if len(zoneNames) else zone["name"]
                            #if len(maxZoneDurations):
                            #    maxZoneDurations += ", {}".format(zone["maxRuntime"]) if zone["enabled"] else ", 0"
                            #else:
                            #    maxZoneDurations = "{}".format(zone["maxRuntime"]) if zone["enabled"] else "0"
                        props = copy.deepcopy(dev.pluginProps)
                        props["NumZones"] = len(dev_dict["zones"])
                        props["ZoneNames"] = zoneNames
                        props["MaxZoneDurations"] = maxZoneDurations
                        if activeScheduleName:
                            props["ScheduledZoneDurations"] = activeScheduleName
                        dev.replacePluginPropsOnServer(props)

                        # Update Moisture levels per Zone
                        update_moisture = self.callMoisturesAPI(netroSerial)
                        dev.updateStatesOnServer(update_moisture)

                    #Update Whisperer Plant Sensors
                    if dev.deviceTypeId == "Whisperer":
                        self.logger.debug(u"Device ID: " + dev.address)
                        self.serialNo = str(dev.address)
                        if dev.sensorValue is not None:
                            sensorValuesLatest = self.callSensorAPI(self.serialNo)
                            self.refreshDelay = int(dev.ownerProps["refresh"]) * 60
                            indigo.debugger()
                            self.key_val_list = sensorValuesLatest['sensorKeyValuesList']
                            if dev.onState is not None:
                                self.key_val_list.append({'key': 'onOffState', 'value': not dev.onState})
                                dev.updateStatesOnServer(self.key_val_list)
                                if dev.onState:
                                    dev.updateStateImageOnServer(indigo.kStateImageSel.HumiditySensorOn)
                                else:
                                    dev.updateStateImageOnServer(indigo.kStateImageSel.HumiditySensorOn)
                            else:
                                dev.updateStatesOnServer(self.key_val_list)
                                dev.updateStateImageOnServer(indigo.kStateImageSel.HumiditySensor)
                        elif dev.onState is not None:
                            dev.updateStateOnServer("onOffState", not dev.onState)
                            dev.updateStateImageOnServer(indigo.kStateImageSel.Auto)
                        else:
                            dev.updateStateImageOnServer(indigo.kStateImageSel.Auto)
        except Exception as exc:
            self.logger.error("Unknown error:\n{}".format(traceback.format_exc(10)))

    def getResponse(self, url):
        openUrl = urllib.request.urlopen(url)
        if openUrl.getcode() == 200:
            data = openUrl.read()
            jsonData = json.loads(data)
        else:
            print("Error receiving data", openUrl.getcode())
        return jsonData

    def callMoisturesAPI(self,serial):
        urlData = "http://api.netrohome.com/npa/v1/moistures.json?key=" + serial
        jsonData = self.getResponse(urlData)
        jdata = jsonData['data']
        jmoistures = jdata['moistures']
        jmoistures.sort(key=lambda x: x.get('id'), reverse=True)
        currentMoistures = jmoistures[0]
        maxDate = currentMoistures['date']
        maxDateMoistures = list(filter(lambda maxdate: maxdate['date'] == maxDate, jmoistures))
        moisture_keys = []
        moisture_values = []
        i = 1
        for x in maxDateMoistures:
            moisture_keys.append("zone_" + str(i) + "_moisture")
            moisture_values.append(str(x["moisture"]))
            i = i + 1
        current_moistures = []
        lenList = len(moisture_keys)
        for elements in range(0, lenList):
            key = moisture_keys[elements]
            value = moisture_values[elements]
            dict = {"key": key, "value": value}
            current_moistures.append(dict)
        return current_moistures

    def callSensorAPI(self, serial):
        # indigo.debugger()
        urlData = "http://api.netrohome.com/npa/v1/sensor_data.json?key=" + serial
        self.logger.debug(urlData)
        jsonData = self.getResponse(urlData)
        jdata = jsonData['data']
        jmeta = jsonData['meta']
        sensorReadings = jdata['sensor_data']
        sensorReadings.sort(key=lambda x: x.get('id'), reverse=True)
        devStates=sensorReadings[0]
        self.logger.debug(devStates)
        # indigo.debugger()
        key_values_list = [
            {'key': 'sensorValue', 'value': devStates['moisture'], 'uiValue':  f"{devStates['moisture']:.1f} %"},
            {'key': 'humidity', 'value': devStates['moisture']},
            {'key': 'soilMoisture', 'value': devStates['moisture']},
            {'key': 'temperature', 'value': devStates['celsius']},
            {'key': 'soilTemperature', 'value': devStates['celsius']},
            {'key': 'sunlight', 'value': devStates['sunlight']},
            {'key': 'readingID', 'value': devStates['id']},
            {'key': 'readingTime', 'value': devStates['time']},
            {'key': 'readingLocalDate', 'value': devStates['local_time']},
            {'key': 'readingLocalTime', 'value': devStates['local_date']},
            {'key': 'id', 'value': devStates['id']},
            {'key': 'serial', 'value': devStates['id']},
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

        self.logger.info("Netro Sprinklers Started")

    ########################################
    def shutdown(self):
        self.logger.info("Netro Sprinklers Stopped")
        pass

    ########################################
    def runConcurrentThread(self):
        self.logger.debug("Starting concurrent thread")
        while True:
            try:
                self._update_from_netro()
            except (Exception,):
                pass
            self.sleep(self.pollingInterval * 60)


    ########################################



    ########################################
    # Dialog list callbacks
    ########################################
    def availableControllers(self, dev_filter="", valuesDict=None, typeId="", targetId=0):
        self.logger.debug(f"availableControllers {self.unused_devices}")
        controller_list = [(dev_id, dev_dict['name']) for dev_id, dev_dict in self.unused_devices.items()]
        dev = indigo.devices.get(targetId, None)
        if dev and dev.configured:
            dev_dict = self._get_device_dict(dev.states[0])
            controller_list.append((dev.states[0], dev_dict["name"]))
        return controller_list

    ########################################
    def availableSchedules(self, dev_filter="", valuesDict=None, typeId="", targetId=0):
        schedule_list = []
        dev = indigo.devices.get(targetId, None)
        if dev:
            dev_dict = self._get_device_dict(dev.states["id"])
            schedule_list = [(rule_dict["id"], rule_dict['name']) for rule_dict in dev_dict["scheduleRules"]]
        return schedule_list

    ########################################
    def sprinklerList(self, dev_filter="", valuesDict=None, typeId="", targetId=0):
        self.logger.threaddebug(f"sprinklerList")
        return [(s.id, s.name) for s in indigo.devices.iter(filter="self")]

    ########################################
    # Validation callbacks
    ########################################
    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        self.logger.threaddebug(f"validateDeviceConfigUi")
        if typeId == "Whisperer":
            valuesDict["SupportsBatteryLevel"] = True
            valuesDict["NumTemperatureInputs"] = 1
            valuesDict["NumHumidityInputs"] = 1
            valuesDict["SupportsTemperatureReporting"] = True
        return True, valuesDict

    ########################################
    def validateActionConfigUi(self, valuesDict, typeId, devId):
        self.logger.threaddebug(f"validateActionConfigUi")
        errorsDict = indigo.Dict()
        if typeId == "setSeasonalAdjustment":
            try:
                if int(valuesDict["adjustment"]) not in range(-100, 100):
                    raise Exception()
            except (Exception,):
                errorsDict["adjustment"] = "Must be an integer from -100 to 100 (a percentage)"
        if len(errorsDict):
            return False, valuesDict, errorsDict
        return True, valuesDict

    ########################################
    def validateEventConfigUi(self, valuesDict, typeId, devId):
        self.logger.threaddebug(f"validateEventConfigUi")
        errorsDict = indigo.Dict()
        if typeId == "sprinklerError":
            if valuesDict["serial"] == "":
                errorsDict["serial"] = "You must select a Netro Sprinkler device."
        if len(errorsDict):
            return False, valuesDict, errorsDict
        return True, valuesDict

    ########################################
    def validatePrefsConfigUi(self, valuesDict):
        self.logger.threaddebug(f"validatePrefsConfigUi")
        errorsDict = indigo.Dict()
        try:
            if int(valuesDict['pollingInterval']) < 1:
                raise Exception()
        except (Exception,):
            errorsDict["pollingInterval"] = "Must be a number greater than or equal to 1 (minutes)."
        if len(errorsDict):
            return False, valuesDict, errorsDict
        return True, valuesDict

    ########################################
    # General device callbacks
    ########################################
    def didDeviceCommPropertyChange(self, origDev, newDev):
        self.logger.threaddebug(f"didDeviceCommPropertyChange")
        return True if origDev.states["serial"] != newDev.states["serial"] else False

    ########################################
    def deviceStartComm(self, dev):
        # Get the full device info and update the newly created device
        indigo.debugger()
        # Update all the states here
        self._update_from_netro()


    ########################################
    def deviceStopComm(self, dev):
        self.logger.debug("Stopping device")

    ########################################
    # Event callbacks
    ########################################
    #  All things that could trigger an event call this method which will do the dispatch
    ########################################
    def _fireTrigger(self, event, dev_id=None):
        try:
            for triggerId, trigger in self.triggerDict.items():
                if trigger.pluginTypeId == "sprinklerError":
                    if int(trigger.pluginProps["id"]) == dev_id:
                        # for the all trigger type, we fire any event that's in the ALL_OPERATIONAL_ERROR_EVENTS
                        # list we defined at the top.
                        trigger_type = trigger.pluginProps["errorType"]
                        if trigger_type == "all" and event in ALL_OPERATIONAL_ERROR_EVENTS:
                            indigo.trigger.execute(trigger)
                        # then we fire if the event specifically matches the trigger type
                        if trigger_type == event:
                            indigo.trigger.execute(trigger)
                elif trigger.pluginTypeId == "commError":
                    trigger_type = trigger.pluginProps["errorType"]
                    # first we fire the trigger if it's any comm error in the ALL_COMM_ERROR_EVENTS list
                    if trigger_type == "allCommErrors" and event in ALL_COMM_ERROR_EVENTS:
                        indigo.trigger.execute(trigger)
                    # then we fire if the event specifically matches the trigger type
                    if trigger_type == event:
                        indigo.trigger.execute(trigger)
                elif trigger.pluginTypeId == event:
                    # an update is available, just fire the trigger since there's nothing else to look at
                    indigo.trigger.execute(trigger)
        except Exception as exc:
            self.logger.error(u"An error occurred during trigger processing")
            self.logger.debug(f"An error occurred during trigger processing: \n{traceback.format_exc(10)}")

    ########################################
    def triggerStartProcessing(self, trigger):
        super(Plugin, self).triggerStartProcessing(trigger)
        self.logger.debug(f"Start processing trigger {str(trigger.id)}")
        if trigger.id not in self.triggerDict:
            self.triggerDict[trigger.id] = trigger
        self.logger.debug(f"Start trigger processing list: {str(self.triggerDict)}")

    ########################################
    def triggerStopProcessing(self, trigger):
        super(Plugin, self).triggerStopProcessing(trigger)
        self.logger.debug("Stop processing trigger " + str(trigger.id))
        try:
            del self.triggerDict[trigger.id]
        except (Exception,):
            # the trigger isn't in the list for some reason so just skip it
            pass
        self.logger.debug(f"Stop trigger processing list: {str(self.triggerDict)}")

    ########################################
    # Sprinkler Control Action callback
    ########################################
    def actionControlSprinkler(self, action, dev):
        # ZONE ON #
        if action.sprinklerAction == indigo.kSprinklerAction.ZoneOn:
            if self.throttle_next_call:
                self.logger.error(f"API calls have violated rate limit - next connection attempt at {self.throttle_next_call:%H:%M:%S}"
                                  )
                self._fireTrigger("startZoneFailed", dev.id)
            else:
                zone_dict = self._get_zone_dict(dev.states["id"], action.zoneIndex)
                self.logger.debug(f"zone_dict: {zone_dict}")
                if zone_dict:
                    zoneName = zone_dict["name"]
                    data = {
                        "id": zone_dict["id"],
                        "duration": zone_dict["maxRuntime"] if zone_dict["maxRuntime"] <= self.maxZoneRunTime else self.maxZoneRunTime,
                    }
                    try:
                        self._make_api_call(ZONE_START_URL.format(apiVersion=NETRO_API_VERSION), request_method="put",
                                            data=data)
                        self.logger.info(f'sent "{dev.name} - {zoneName}" on')
                        dev.updateStateOnServer("activeZone", action.zoneIndex)
                    except (Exception,):
                        # Else log failure but do NOT update state on Indigo Server. Also, fire any triggers the user has
                        # on zone start failures.
                        self.logger.error(f'send "{dev.name} - {zoneName}" on failed')
                        self.logger.debug(f"API error: \n{traceback.format_exc(10)}")
                        self._fireTrigger("startZoneFailed", dev.id)
                else:
                    self.logger.error(f"Zone number {action.zoneIndex} doesn't exist in this controller and can't be enabled.")
                    self._fireTrigger("startZoneFailed", dev.id)

        # ALL ZONES OFF #
        elif action.sprinklerAction == indigo.kSprinklerAction.AllZonesOff:
            data = {
                "id": dev.states["id"],
            }
            try:
                self._make_api_call(DEVICE_STOP_WATERING_URL.format(apiVersion=NETRO_API_VERSION), request_method="put", data=data)
                self.logger.info(f'sent "{dev.name}" {"all zones off"}')
                dev.updateStateOnServer("activeZone", 0)
            except (Exception,):
                # Else log failure but do NOT update state on Indigo Server.
                self.logger.info(f'send "{dev.name}" {"all zones off"} failed')
                self.logger.debug(f"API error: \n{traceback.format_exc(10)}")
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
    def actionControlUniversal(self, action, dev):
        # STATUS REQUEST #
        if action.deviceAction == indigo.kUniversalAction.RequestStatus:
            self._next_weather_update = datetime.now()
            self._update_from_netro()

    ########################################
    # Custom Plugin Action callbacks defined in Actions.xml
    ########################################
    def runNetroSchedule(self, pluginAction, dev):
        schedule_rule_id = pluginAction.props["scheduleId"]

        dev_dict = self._get_device_dict(dev.states["id"])
        if dev_dict:
            schedule_id_dict = {rule_dict["id"]: rule_dict["name"] for rule_dict in dev_dict["scheduleRules"]}
            if schedule_rule_id in schedule_id_dict.keys():
                try:
                    data = {
                        "id": schedule_rule_id,
                    }
                    self._make_api_call(SCHEDULERULE_START_URL, request_method="put", data=data)
                    self.logger.info(f"Netro schedule '{schedule_id_dict[schedule_rule_id]}' started")
                    self.logger.warn("Note: frequently requesting dynamic status updates may cause failures later because of Netro API polling limits. Use sparingly.")
                    return
                except Exception as exc:
                    self.logger.debug("API error: \n{}".format(traceback.format_exc(10)))
                    self._fireTrigger("startNetroScheduleFailed", dev.id)
        self.logger.error("No Netro schedule found matching action configuration - check your action.")

    ########################################
    def setNoWater(self, pluginAction, dev):
        num_Days = pluginAction.props["numDaysNoWater"]
        dev_dict = self._get_device_dict(dev.states["id"])

        if dev_dict:
                try:
                    data = {
                        "key": self.access_token,
                        "days": num_Days,
                    }
                    url = DEVICE_NO_WATER.format(apiVersion=NETRO_API_VERSION)
                    response = self._make_api_call(url, request_method="post", data=data)
                    response_status= response["status"]
                    self.logger.debug(response)
                    if response_status == "OK":
                        self.logger.info(f"Stop watering for  '{num_Days}'  day(s)")
                    else:
                        self.logger.info(f"Error setting rain delay")
                    #self.logger.warn("Note: frequently requesting dynamic status updates may cause failures later because of Rachio API polling limits. Use sparingly.")
                    return
                except Exception as exc:
                    self.logger.debug("API error: \n{}".format(traceback.format_exc(10)))
                    self._fireTrigger("setNoWater", dev.id)

    ########################################
    def setStandbyMode(self, pluginAction, dev):
        try:
            indigo.debugger()
            if pluginAction.props["mode"]:
                # You turn the device off to put it into standby mode
                data = {
                    "key":self.access_token,
                    "status":0,
                }
                url = DEVICE_TURN_OFF_URL.format(apiVersion=NETRO_API_VERSION, deviceId=self.access_token)
            else:
                # You turn the device on to take it out of standby mode
                data = {
                    "key": self.access_token,
                    "status":1,
                }
                url = DEVICE_TURN_ON_URL.format(apiVersion=NETRO_API_VERSION, deviceId=self.access_token)
            self._make_api_call(url, request_method="post", data=data)
            self.logger.info(f"Standby mode for controller '{dev.name}' turned {'on' if pluginAction.props['mode'] else 'off'}")
        except Exception as exc:
            self.logger.error("Could not set standby mode - check your controller.")
            self.logger.debug(f"API error: \n{traceback.format_exc(10)}")
            self._fireTrigger("setStandbyFailed", dev.id)

    ########################################
    # Menu callbacks defined in MenuItems.xml
    ########################################
    def toggleDebugging(self):
        if self.debug:
            self.logger.info("Turning off debug logging")
            self.pluginPrefs["showDebugInfo"] = False
        else:
            self.logger.info("Turning on debug logging")
            self.pluginPrefs["showDebugInfo"] = True
        self.debug = not self.debug


    ########################################
    def updateAllStatus(self):
        self._next_weather_update = datetime.now()
        self._update_from_netro()

    ########################################
    def pickController(self, dev_filter=None, valuesDict=None, typeId=0):
        self.logger.threaddebug(f"pickController")
        retList = []
        for dev in indigo.devices.iter("self"):
            retList.append((dev.id, dev.name))
        retList.sort(key=lambda tup: tup[1])
        return retList

    # doesn't do anything, just needed to force other menus to dynamically refresh
    def configMenuChanged(self, valuesDict):
        self.logger.threaddebug(f"configMenuChanged")
        return valuesDict
