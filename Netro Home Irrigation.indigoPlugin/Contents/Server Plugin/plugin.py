#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# Copyright (c) 2022, Perceptive Automation, LLC. All rights reserved.
# https://www.indigodomo.com

# ============================== Native Imports ===============================
import urllib.request
import json

# ============================== Custom Imports ===============================
try:
    # noinspection PyUnresolvedReferences
    import indigo
except ImportError:
    pass

# Change to allow pycharm testing without indigo module


#############################
class Plugin(indigo.PluginBase):
    #############################
    def __init__(self, plugin_id, plugin_display_name, plugin_version, plugin_prefs):
        super().__init__(plugin_id, plugin_display_name, plugin_version, plugin_prefs)
        self.debug = True

    ########################################
    def startup(self):
        self.logger.debug("startup called")

    def shutdown(self):
        self.logger.debug("shutdown called")

    ########################################
    def runConcurrentThread(self):
        try:
            while True:
                for dev in indigo.devices.iter("self"):
                    if not dev.enabled or not dev.configured:
                        continue

                    #set device params
                    #testing
                    self.logger.debug(u"Device ID: " + dev.address)
                    self.serialNo = str(dev.address)

                    self.logger.debug("testing testing")
                    #Whisperer Sensor Device Updates
                    if dev.deviceTypeId == "Whisperer":
                        if dev.sensorValue is not None:
                            sensorValuesLatest = self.callSensorAPI(self.serialNo)

                            #debug
                            self.logger.debug("devCustomStates")
                            self.refreshDelay = int(dev.ownerProps["refresh"]) * 60

                            #self.logger.debug(sensorValuesLatest)
                            indigo.debugger()
                            self.key_val_list = sensorValuesLatest['sensorKeyValuesList']
                            if dev.onState is not None:
                                self.key_val_list.append({'key':'onOffState', 'value':not dev.onState})
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

                    #Netro Device Readings Update
                    elif dev.deviceTypeId == "Netro":
                        controllerValuesLatest = self.callControllerAPI(self.serialNo)
                        self.logger.debug("devCustomStates")
                        self.refreshDelay = int(dev.ownerProps["refresh"]) * 60
                        self.logger.debug(controllerValuesLatest)
                        indigo.debugger()
                        self.cd_key_val_list = controllerValuesLatest['controllerKeyValuesList']
                        dev.updateStatesOnServer(self.cd_key_val_list)
                        if dev.onState is not None:
                            dev.updateStateOnServer("onOffState", not dev.onState)
                            dev.updateStateImageOnServer(indigo.kStateImageSel.Auto)
                        else:
                            dev.updateStateImageOnServer(indigo.kStateImageSel.Auto)
                self.sleep(int(self.refreshDelay))
        except self.StopThread:
            pass  # Optionally catch the StopThread exception and do any needed cleanup.

    ########################################
    def validateDeviceConfigUi(self, values_dict, type_id, dev_id):
        if type_id == "Whisperer":
            values_dict["SupportsBatteryLevel"] = True
            values_dict["NumTemperatureInputs"] = 1
            values_dict["NumHumidityInputs"] = 1
            values_dict["SupportsTemperatureReporting"] = True
        elif type_id == "Netro":
            values_dict["SupportsBatteryLevel"] = False
        return True, values_dict

    ########################################
    def deviceStartComm(self, dev):
        # Called when communication with the hardware should be started.
        if dev.deviceTypeId == "sprinkler":
            dev.zoneCount = 12
            self.logger.debug("update zone count")
            dev.replaceOnServer()
        pass

    def deviceStopComm(self, dev):
        # Called when communication with the hardware should be shutdown.
        pass

    def getResponse(self, url):
        self.openUrl = urllib.request.urlopen(url)
        if self.openUrl.getcode() == 200:
            self.data = self.openUrl.read()
            self.jsonData = json.loads(self.data)
        else:
            print("Error receiving data", self.openUrl.getcode())
        return self.jsonData

    def callSensorAPI(self, serial):
        self.urlData = "http://api.netrohome.com/npa/v1/sensor_data.json?key=" + serial
        self.logger.debug(self.urlData)
        self.jsonData = self.getResponse(self.urlData)
        self.jdata = self.jsonData['data']
        self.sensorReadings = self.jdata['sensor_data']
        self.sensorReadings.sort(key=lambda x: x.get('id'), reverse=True)
        self.devStates=self.sensorReadings[0]
        indigo.debugger()
        self.key_values_list = [
            {'key': 'sensorValue', 'value': self.devStates['moisture'], 'uiValue':  f"{self.devStates['moisture']:.1f} %"},
            {'key': 'humidity', 'value': self.devStates['moisture']},
            {'key': 'soilMoisture', 'value': self.devStates['moisture']},
            {'key': 'temperature', 'value': self.devStates['celsius']},
            {'key': 'sunlight', 'value': self.devStates['sunlight']},
            {'key': 'readingID', 'value': self.devStates['id']},
            {'key': 'readingTime', 'value': self.devStates['time']},
            {'key': 'readingLocalDate', 'value': self.devStates['local_time']},
            {'key': 'readingLocalTime', 'value': self.devStates['local_date']},
            {'key': 'batteryLevel', 'value': self.devStates['battery_level']}
        ]
        self.sensorValues = dict()
        self.sensorValues['sensorStatus']=self.jsonData['status']
        self.sensorValues['sensorMeta'] = self.jsonData['meta']
        self.sensorValues['currentReadings'] = self.sensorReadings[0]
        self.sensorValues['sensorKeyValuesList'] = self.key_values_list
        # self.logger.info(u"Latest sensor #readings"+currentReading)
        return self.sensorValues

    def callControllerAPI(self, serial):
        self.cd_urlData = "http://api.netrohome.com/npa/v1/info.json?key=" + serial
        self.cd_jsonData = self.getResponse(self.cd_urlData)
        # print the state id and state name corresponding
        self.cd_jdata = self.cd_jsonData['data']
        self.cd_jmeta = self.cd_jsonData['meta']
        self.cd_jdevice = self.cd_jdata['device']
        self.cd_jzones = self.cd_jdevice['zones']  #zone details
        self.cd_status = self.cd_jsonData['status']

        self.cd_key_values = [
            {'key': 'status', 'value': self.cd_jsonData['status']},
            {'key': 'token_remaining', 'value': self.cd_jmeta['token_remaining']},
            {'key': 'last_active', 'value': self.cd_jmeta['last_active']},
            {'key': 'name', 'value': self.cd_jdevice['name']},
            {'key': 'software_version', 'value': self.cd_jdevice['sw_version']},
            {'key': 'zone_num', 'value': self.cd_jdevice['zone_num']}
        ]

        self.controllerInfo = dict()
        self.controllerInfo['controllerStatus'] = self.cd_jsonData['status']
        self.controllerInfo['controllerMeta'] = self.cd_jsonData['meta']
        self.controllerInfo['controllerDevice'] = self.cd_jdata['device']
        self.controllerInfo['controllerKeyValuesList'] = self.cd_key_values
        # self.logger.info(u"Latest sensor #readings"+currentReading)
        return self.controllerInfo

    #def zonesUpdate(self):
        #self.cd_jzones

    def callSchedulesAPI(self, serial):
        self.sh_urlData = "http://api.netrohome.com/npa/v1/schedules.json?key=" + serial
        self.sh_jsonData = self.getResponse(self.sh_urlData)
        # print the state id and state name corresponding
        self.sh_jdata = self.sh_jsonDatajsonData['data']
        self.sh_jmeta = self.sh_jsonData['meta']
        self.sh_jschedules = self.sh_jdata['schedules']
        # need to bucket each zone schedules into their own dicts
        self.sh_status = self.sh_jsonData['status']
        print(self.sh_status)
        self.sh_jschedules.sort(key=lambda x: x.get('id'), reverse=False)


    #######################
    # Sensor Action callback
    ######################
    def actionControlSensor(self, action, dev):
        ###### TURN ON ######
        # Ignore turn on/off/toggle requests from clients since this is a read-only sensor.
        if action.sensorAction == indigo.kSensorAction.TurnOn:
        #    self.logger.info(f"ignored \"{dev.name}\" on request (sensor is read-only)")
        # But we could request a sensor state update if we wanted like this:
            dev.updateStateOnServer("onOffState", True)

        ###### TURN OFF ######
        # Ignore turn on/off/toggle requests from clients since this is a read-only sensor.
        elif action.sensorAction == indigo.kSensorAction.TurnOff:
        #    self.logger.info(
        #        f"ignored \"{dev.name}\" off request (sensor is read-only)")
        # But we could request a sensor state update if we wanted like this:
            dev.updateStateOnServer("onOffState", False)

        ###### TOGGLE ######
        # Ignore turn on/off/toggle requests from clients since this is a read-only sensor.
        elif action.sensorAction == indigo.kSensorAction.Toggle:
        #    self.logger.info(
        #        f"ignored \"{dev.name}\" toggle request (sensor is read-only)")
        # But we could request a sensor state update if we wanted like this:
            dev.updateStateOnServer("onOffState", not dev.onState)

    ######################
    # General Action callback
    ######################
    def actionControlUniversal(self, action, dev):
        ## BEEP ##
        if action.deviceAction == indigo.kUniversalAction.Beep:
            # Beep the hardware module (dev) here:
            # ** IMPLEMENT ME **
            self.logger.info(f"sent \"{dev.name}\" beep request")

        ##STATUS REQUEST ##
        elif action.deviceAction == indigo.kUniversalAction.RequestStatus:
            self.serialNo = str(dev.address)
            self.refreshDelay = int(dev.ownerProps["refresh"]) * 60
            # Whisperer Sensor Device Updates
            if dev.deviceTypeId == "Whisperer":
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
            elif dev.deviceTypeId == "Netro":
                controllerValuesLatest = self.callControllerAPI(self.serialNo)
                self.cd_key_val_list = controllerValuesLatest['controllerKeyValuesList']
                dev.updateStatesOnServer(self.cd_key_val_list)
            elif dev.onState is not None:
                dev.updateStateOnServer("onOffState", not dev.onState)
                dev.updateStateImageOnServer(indigo.kStateImageSel.Auto)
            else:
                dev.updateStateImageOnServer(indigo.kStateImageSel.Auto)

    ########################################
    # Custom Plugin Action callbacks (defined in Actions.xml)
    ######################

    ########################################
    # Relay / Dimmer Action callback
    ######################
    def actionControlDevice(self, action, dev):
        ###### TURN ON ######
        if action.deviceAction == indigo.kDeviceAction.TurnOn:
            # Command hardware module (dev) to turn ON here:
            # ** IMPLEMENT ME **
            send_success = True        # Set to False if it failed.

            if send_success:
                # If success then log that the command was successfully sent.
                self.logger.info(f"sent \"{dev.name}\" on")

                # And then tell the Indigo Server to update the state.
                dev.updateStateOnServer("onOffState", True)
            else:
                # Else log failure but do NOT update state on Indigo Server.
                self.logger.error(f"send \"{dev.name}\" on failed")

        ###### TURN OFF ######
        elif action.deviceAction == indigo.kDeviceAction.TurnOff:
            # Command hardware module (dev) to turn OFF here:
            # ** IMPLEMENT ME **
            send_success = True        # Set to False if it failed.

            if send_success:
                # If success then log that the command was successfully sent.
                self.logger.info(f"sent \"{dev.name}\" off")

                # And then tell the Indigo Server to update the state:
                dev.updateStateOnServer("onOffState", False)
            else:
                # Else log failure but do NOT update state on Indigo Server.
                self.logger.error(f"send \"{dev.name}\" off failed")


