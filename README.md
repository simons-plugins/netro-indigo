# Netro Smart Sprinklers Plugin for Indigo

A plugin for integrating Netro smart irrigation controllers with the [Indigo Home Automation](https://www.indigodomo.com) platform.

## Summary

This plugin provides complete control and monitoring of your Netro smart sprinkler system through Indigo home automation. It supports all Netro controllers (Sprite, Pixie, Spark) and Whisperer soil moisture sensors, allowing you to manage your irrigation system alongside your other smart home devices.

With this plugin, you can start and stop zones, set rain delays, monitor soil moisture, view upcoming schedules, and integrate your sprinkler system into Indigo automations and triggers.

## Supported Devices

- Netro Sprite
- Netro Pixie
- Netro Spark
- Whisperer soil moisture sensors

## Features

### Zone Control

Control your sprinkler zones directly from Indigo. Start or stop individual zones remotely, set watering durations, and integrate zone control into your home automation routines.

### Real-time Status Monitoring

Monitor your controller's online/offline status in real-time. The plugin polls your Netro controller at configurable intervals to keep device states current.

### Soil Moisture Tracking

View soil moisture levels for each zone. The plugin retrieves moisture data from your Netro controller and displays it as device states, allowing you to create automations based on soil conditions.

### Schedule Visibility

See your current and upcoming watering schedules directly in Indigo. The plugin displays:
- Next scheduled watering time
- Which zone will be watered next
- Schedule type (Smart, Automatic, Fix, or Manual)
- Watering duration

### Rain Delays

Set rain delays from 1 to 100 days to pause automatic watering during wet weather. This can be triggered manually or through Indigo automations.

### Standby Mode

Enable or disable automatic watering on your controller. When in standby mode, scheduled watering is paused but manual control remains available.

### Delayed Watering

Start zones with a delay of 0 to 60 minutes, or schedule watering for a specific time. This allows for more flexible automation scenarios.

### Weather Reporting

Send local weather data (temperature, humidity, precipitation) to Netro to improve its AI-based scheduling decisions. This is useful if you have local weather sensors integrated with Indigo.

### API Usage Monitoring

Track your daily API call usage directly from Indigo device states. The Netro API allows 2000 calls per day, and the plugin displays your remaining quota.

### Whisperer Sensor Support

Integrate Whisperer soil sensors to monitor temperature, humidity, and moisture levels independently of your sprinkler zones.

### Indigo Triggers

Create automations based on sprinkler events:
- Zone start failed
- Stop failed
- Rate limit exceeded
- Set rain delay failed
- Set standby failed

## Installation

1. Download the latest release from [GitHub Releases](https://github.com/simons-plugins/netro-indigo/releases)
2. Double-click the `.indigoPlugin` file to install
3. Configure the plugin with your Netro controller serial number
4. Create a new "Netro Smart Sprinkler" device in Indigo

## Configuration

### Plugin Configuration

1. Go to **Indigo > Plugins > Netro Smart Sprinklers > Configure**
2. Enter your Netro controller serial number (12 hex characters)
3. Set polling interval (minimum 3 minutes, default 3)
4. Configure API timeout (default 5 seconds)
5. Set maximum zone runtime (default 3600 seconds)

### Device Configuration

1. Create a new device: **Devices > New > Type: Netro Smart Sprinkler**
2. Enter the controller serial number (found on the physical device)
3. The plugin will automatically discover zones and configuration

### Finding Your Serial Number

Your Netro controller serial number is:
- Printed on the physical device (12 hex characters)
- Available in the Netro mobile app (Settings > Device Info)
- Format example: `0cb8152f9f78`

## Usage

### Indigo Actions

**Start a Zone**:
```python
# Start zone 1 for 10 minutes
indigo.sprinkler.setZone(dev, zoneIndex=1, duration=10)
```

**Set Rain Delay**:
Use the plugin action "Set Rain Delay" and specify the number of days (1-100).

**Report Weather**:
Use the plugin action "Report Weather to Netro" to send current temperature, humidity, and precipitation data.

**Start Zone with Delay**:
Use the plugin action "Start Zone with Delay" to start a zone after a specified delay (0-60 minutes).

## Device States

Each controller device exposes these states:

| State | Description | Example |
|-------|-------------|---------|
| `status` | Controller status | `ONLINE`, `OFFLINE` |
| `activeZone` | Currently watering zone | `1`, `0` (none) |
| `activeSchedule` | Current schedule type | `Smart`, `Manual`, `No active schedule` |
| `nextScheduleTime` | When next watering starts | `2026-01-28 14:30:00` |
| `nextScheduleZone` | Next zone to water | `Front Lawn` |
| `nextScheduleSource` | Next schedule type | `Smart`, `Automatic` |
| `nextScheduleDuration` | Next watering duration (min) | `15` |
| `token_remaining` | API calls remaining today | `1847` |
| `moisture_1` through `moisture_12` | Zone moisture % | `45` |

## API Rate Limits

The Netro API allows 2000 calls per day. The plugin manages this automatically:

- Default polling every 3 minutes uses approximately 480 calls per day
- Rate limit warnings appear when fewer than 200 calls remain
- Automatic 61-minute backoff occurs if the rate limit is exceeded
- Current usage is visible in the `token_remaining` device state

If you approach the daily limit, increase the polling interval in the plugin configuration.

## Troubleshooting

### Plugin Won't Load

1. Check the Indigo Event Log for errors
2. Verify the serial number format (12 hex characters)
3. Ensure your Netro controller is online

### API Rate Limiting

**Symptom**: "API calls have violated rate limit" appears in logs

**Solution**:
- Increase the polling interval in plugin configuration
- Check the `token_remaining` state for current usage
- The limit resets daily at midnight UTC

### Controller Shows Offline

Possible causes:
- Controller is unplugged or has no internet connection
- Network issues between the controller and Netro cloud
- Netro API is temporarily unavailable

Note: The Netro API can be slow to report offline status (30+ minutes delay).

## Support

- **Issues**: [GitHub Issues](https://github.com/simons-plugins/netro-indigo/issues)
- **Forum**: [Indigo Plugin Forum](https://forums.indigodomo.com)

## License

Copyright (c) 2014-2026, Perceptive Automation, LLC. All rights reserved.

## Related Links

- [Netro Official Website](https://netrohome.com)
- [Indigo Home Automation](https://www.indigodomo.com)
