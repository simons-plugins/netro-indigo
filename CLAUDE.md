# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an Indigo home automation plugin for Netro smart irrigation controllers. The plugin integrates Netro sprinkler systems and Whisperer plant sensors with the Indigo home automation platform.

**API Reference**: See [NETRO_API.md](NETRO_API.md) for complete Netro Public API documentation including all endpoints, request/response formats, rate limits, and implementation examples.

## Plugin Structure

Standard Indigo plugin bundle format:
```
Netro Sprinklers.indigoPlugin/
└── Contents/
    ├── Info.plist           # Plugin metadata and version info
    └── Server Plugin/
        ├── plugin.py        # Main plugin implementation
        ├── Devices.xml      # Device type definitions
        ├── Actions.xml      # Custom action definitions
        ├── Events.xml       # Event/trigger definitions
        ├── PluginConfig.xml # Plugin-level configuration UI
        └── MenuItems.xml    # Plugin menu items
```

## Core Architecture

### Main Plugin Class
- Inherits from `indigo.PluginBase` ([plugin.py:84](plugin.py#L84))
- Implements concurrent threading for API polling via `runConcurrentThread()` ([plugin.py:448](plugin.py#L448))
- Maintains connection to Netro API using REST calls

### Device Types
1. **Sprinkler Controller** (deviceTypeId: "sprinkler")
   - Controls multiple irrigation zones (up to 12 zones supported)
   - Tracks zone moisture levels, active schedules, and device status
   - Inherits Indigo's built-in sprinkler device behavior

2. **Whisperer Plant Sensor** (deviceTypeId: "Whisperer")
   - Monitors soil moisture, temperature, sunlight, and battery level
   - Updates sensor values at configurable intervals

### API Integration

**Base URL**: `http://api.netrohome.com/npa/v1/`

**Key Endpoints** (defined at [plugin.py:27-42](plugin.py#L27-L42)):
- Person/device info: `info.json?key={deviceId}`
- Schedules: `schedules.json?key={deviceId}`
- Moisture data: `moistures.json?key={serial}`
- Sensor data: `sensor_data.json?key={serial}`
- Zone control: `zone/start` (PUT)
- Stop watering: `stop_water` (PUT)
- Rain delay: `no_water.json` (POST)
- Standby mode: `set_status.json` (POST)

**Rate Limiting**: Critical implementation detail
- API enforces rate limits (returns HTTP 429 when exceeded)
- Plugin implements 61-minute throttle delay when rate limit hit ([plugin.py:24](plugin.py#L24))
- Check `self.throttle_next_call` before making API requests
- Fires "rateLimitExceeded" trigger when throttled

### Polling & Updates

Main update loop in `_update_from_netro()` ([plugin.py:200](plugin.py#L200)):
1. Iterates through all enabled devices
2. For sprinkler controllers:
   - Fetches device info and status
   - Gets current schedule/active zones
   - Retrieves moisture levels per zone
   - Updates device states and properties
3. For Whisperer sensors:
   - Fetches latest sensor readings
   - Updates moisture, temperature, sunlight values

Polling interval configurable in plugin preferences (default: 3 minutes, min: 1 minute)

### State vs. Properties

**States** (dynamic, frequently updated):
- Device status (ONLINE/OFFLINE)
- Active zone number
- Active schedule name
- Zone moisture levels (zone_1_moisture through zone_12_moisture)
- Token remaining/reset (API rate limit tracking)
- Sensor readings (temperature, moisture, sunlight, battery)

**Properties** (static, infrequently changed):
- Number of zones
- Zone names (comma-separated list)
- Serial numbers and MAC addresses

## Development Guidelines

### Testing Changes

This plugin runs within the Indigo server environment. To test:
1. Plugin must be installed in Indigo's plugin directory
2. Changes require plugin reload in Indigo
3. Monitor Indigo Event Log for debug output
4. Enable debug logging via "Toggle Debugging" menu item

### API Call Best Practices

When adding new API calls:
- Always use `_make_api_call()` method ([plugin.py:116](plugin.py#L116))
- This handles connection errors, timeouts, and throttling automatically
- Wrap in try/except blocks and fire appropriate error triggers
- Respect rate limits to avoid 61-minute lockout

### Device State Updates

Pattern for updating device states:
```python
update_list = [
    {"key": "state_name", "value": value},
    {"key": "another_state", "value": another_value},
]
dev.updateStatesOnServer(update_list)
```

For properties (requires device recreation in Indigo):
```python
props = copy.deepcopy(dev.pluginProps)
props["propertyName"] = value
dev.replacePluginPropsOnServer(props)
```

### Error Handling & Triggers

Plugin defines custom error events ([plugin.py:46-59](plugin.py#L46-L59)):
- Operational errors: startZoneFailed, stopFailed, setStandbyFailed, etc.
- Communication errors: personCall, getScheduleCall, forecastCall, rateLimitExceeded

Fire triggers using `_fireTrigger(event, dev_id)` ([plugin.py:562](plugin.py#L562))

### API Response Structure

**Device/Person Info**:
```python
{
    "data": {
        "device": {
            "serial": "...",
            "status": "ONLINE|OFFLINE",
            "name": "...",
            "zones": [{"id": "...", "ith": 1, "name": "...", "enabled": true}, ...],
            ...
        }
    },
    "meta": {
        "token_remaining": int,
        "token_reset": timestamp,
        ...
    }
}
```

**Schedules**:
```python
{
    "data": {
        "schedules": [
            {
                "status": "EXECUTING|...",
                "zone": zone_number,
                "source": "AUTOMATIC|MANUAL",
                ...
            }
        ]
    }
}
```

### Debugging

- Use `self.logger.debug()` for detailed debugging (only shows when debug enabled)
- Use `self.logger.info()` for user-facing status messages
- Use `self.logger.error()` for errors
- `indigo.debugger()` lines throughout code are breakpoints for Indigo's debugger

## Common Modifications

### Adding New Device States
1. Define state in [Devices.xml](Netro Sprinklers.indigoPlugin/Contents/Server Plugin/Devices.xml) under `<States>`
2. Update state in `_update_from_netro()` method
3. States are automatically available in Indigo triggers and conditions

### Adding New Actions
1. Define action in [Actions.xml](Netro Sprinklers.indigoPlugin/Contents/Server Plugin/Actions.xml)
2. Implement callback method in plugin.py
3. For sprinkler control actions, use `actionControlSprinkler()` ([plugin.py:612](plugin.py#L612))
4. For custom actions, define separate callback methods

### Modifying API Behavior
- API constants defined at top of [plugin.py](plugin.py) (lines 19-42)
- API call timeout: configurable in plugin preferences (default 5 seconds)
- Max zone runtime: configurable in plugin preferences (default 3600 seconds)

## Dependencies

Required Python modules (should be available in Indigo's Python environment):
- indigo (Indigo SDK)
- requests (HTTP library)
- urllib.request
- json
- dateutil (timezone handling)

## Version Info

Current version: 2022.2.7 (per [Info.plist:6](Netro Sprinklers.indigoPlugin/Contents/Info.plist#L6))
Indigo API version: 3.0
Bundle identifier: com.simons-plugins.netro
