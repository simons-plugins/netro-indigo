# Troubleshooting Guide

Common issues and solutions for the Netro Sprinklers plugin.

## Plugin Won't Load

**Symptom**: Plugin doesn't appear or immediately disables

**Checks**:
1. Check Indigo Event Log for Python errors
2. Verify requirements.txt exists in `Contents/Server Plugin/`
3. Check Python version (must be 3.10+)
4. Verify `requests` library installed: `pip3 list | grep requests`

**Solutions**:
```bash
# Reinstall dependencies
pip3 install requests==2.32.5

# Reload plugin
# Indigo → Plugins → Reload Plugin Code
```

## API Connection Failures

### "Unable to contact device"

**Cause**: Controller is offline or unplugged

**Solutions**:
- Check controller has power
- Verify controller is online in Netro mobile app
- Check internet connection
- Wait - API can be slow to report offline status

### "Connection to Netro API server failed"

**Cause**: Network or internet connection issue

**Solutions**:
- Check internet connectivity
- Try: `curl http://api.netrohome.com/npa/v1/`
- Check firewall isn't blocking outbound connections
- Verify Netro API is operational

### "Request timed out"

**Cause**: API timeout (default 5 seconds)

**Solutions**:
- Increase timeout in plugin config (try 10 seconds)
- Check network latency
- Retry - intermittent timeouts are normal

## Rate Limiting

### "API calls throttled until..."

**Cause**: Exceeded 2000 API calls per day limit

**How it happens**:
- Polling every 1-2 minutes = ~720-1440 calls/day
- Manual status updates
- Multiple devices polling simultaneously

**Solutions**:
- **Increase polling interval** (recommended: 5+ minutes)
- Wait 61 minutes for throttle to reset
- Check `token_remaining` state on device
- Reduce manual status update frequency

**Prevention**:
```
Polling Interval | Calls/Day | Safe?
3 minutes        | 480       | ✅ Safe
5 minutes        | 288       | ✅ Very safe
10 minutes       | 144       | ✅ Extremely safe
1 minute         | 1440      | ⚠️  Risky
```

### "Only X calls remaining today"

**Warning levels**:
- <200 remaining: Info message logged
- <100 remaining: Warning message logged

**Actions**:
- Increase polling interval immediately
- Avoid manual updates until reset
- Token reset time shown in device state `token_reset`

## Device Status Issues

### Device shows OFFLINE but controller is on

**Causes**:
- API slow to update (can take 10+ minutes)
- Controller lost internet connection
- Cloud service issue

**Solutions**:
- Wait 10-15 minutes
- Check controller internet in Netro app
- Force status update: Plugins → Netro → Update All Status
- Restart controller

### Zones don't appear or show incorrect names

**Cause**: Device hasn't updated from API yet

**Solutions**:
- Wait for first polling cycle (3-5 minutes)
- Force update: Plugins → Netro → Update All Status
- Check serial number is correct
- Verify zones configured in Netro app

### Moisture levels stuck at old values

**Cause**: Netro only updates moisture periodically (typically daily)

**Not a bug**: This is normal Netro behavior
- Moisture measured once per day
- Values show last measurement date
- Use Netro app to see same data

## Schedule Problems

### "No upcoming schedule" when there should be

**Causes**:
- Controller in standby mode
- Rain delay active
- All zones disabled
- Smart scheduling paused

**Solutions**:
- Check standby state
- Check rain delay in Netro app
- Verify zones enabled
- Check Netro app schedule settings

### Active schedule shows wrong information

**Cause**: Schedule changed recently, cache not updated

**Solutions**:
- Wait for next polling cycle
- Force update manually
- Check Netro app for actual schedule

## Action Failures

### "Zone start failed"

**Causes**:
1. **Throttled**: Wait for throttle to expire
2. **Zone disabled**: Enable zone in Netro app
3. **Controller offline**: Check device status
4. **Invalid zone**: Zone doesn't exist

**Debug**:
- Check Event Log for specific error
- Verify zone exists and is enabled
- Check device online status
- Try starting from Netro app

### "Stop watering failed"

**Causes**:
- API timeout
- Connection error
- Controller offline

**Workaround**:
- Use Netro app to stop
- Wait - zone will stop when duration expires
- Power cycle controller if critical

### Rain delay won't set

**Checks**:
- Valid range: 1-100 days
- Controller online
- Not throttled
- Correct serial number in config

## Configuration Issues

### "Serial number is required"

**Solution**:
- Get serial from Netro mobile app (Settings)
- Format: 12 hex characters (e.g., `a4cf12b8d5e2`)
- Enter in plugin config: Plugins → Configure → Netro

### "Polling interval must be at least 3 minutes"

**Why**: Prevent hitting API rate limit

**Solution**:
- Use 3 minutes minimum
- Recommended: 5 minutes
- Maximum: 1440 minutes (24 hours)

## Whisperer Sensor Issues

### Sensor readings not updating

**Causes**:
- Sensor offline (check battery)
- Wrong serial number
- Sensor hasn't reported recently

**Solutions**:
- Check battery level in sensor states
- Verify sensor serial in Netro app
- Sensors report every 4-6 hours normally
- Replace battery if <20%

### Temperature shows in wrong units

**Solution**:
- Plugin reports Celsius (Netro API default)
- Convert in Indigo: F = (C × 9/5) + 32
- Or use variable/trigger to convert

## Known Limitations

### What the plugin CAN'T do:
- ❌ Pause/resume schedules (API doesn't support)
- ❌ Create new schedules (API doesn't support)
- ❌ Modify zone settings (API doesn't support)
- ❌ Run manual schedules (API limitation)
- ❌ Skip to next/previous zone (API limitation)

### What you MUST use Netro app for:
- Zone configuration (names, soil type, etc.)
- Schedule creation
- Smart scheduling settings
- Controller initial setup
- Firmware updates

## Debugging

### Enable Debug Logging

1. Plugins → Netro Sprinklers → Toggle Debugging
2. Reproduce issue
3. Check Event Log for details
4. Disable debug when done

### Check API Tokens

Device states show:
- `token_remaining`: Calls left today
- `token_reset`: When quota resets (Unix timestamp)
- `last_active`: Last successful API call

### Manual API Test

Test API directly:
```bash
cd /path/to/netro
python3 test_local_api.py --serial YOUR_SERIAL
```

See [LOCAL_TESTING.md](LOCAL_TESTING.md) for details.

### Event Log Messages

**"API calls throttled until..."**
- Wait specified time
- Increase polling interval

**"Only X calls remaining"**
- Increase polling interval now
- Avoid manual updates

**"Connection failed"**
- Network/internet issue
- Check connectivity

**"Unable to contact device"**
- Controller offline
- Check power and connection

## Getting Help

1. **Check this guide** for common issues
2. **Enable debug logging** and reproduce
3. **Check Event Log** for specific errors
4. **Test API directly** with test_local_api.py
5. **Verify in Netro app** that hardware works
6. **Post on forum** with:
   - Indigo version
   - Plugin version
   - Error messages from Event Log
   - Steps to reproduce

## Additional Resources

- [DEPENDENCIES.md](DEPENDENCIES.md) - Package management
- [LOCAL_TESTING.md](LOCAL_TESTING.md) - API testing
- [TESTING.md](TESTING.md) - Test suite
- [NETRO_API.md](NETRO_API.md) - API documentation
- [API_NOTES.md](API_NOTES.md) - API quirks

