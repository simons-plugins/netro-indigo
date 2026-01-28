# Local Testing Guide

This guide explains how to test the Netro plugin API integration locally without running Indigo.

## Prerequisites

- Python 3.10+
- `requests` library
- Your Netro controller serial number
- Internet connection

## Quick Start

### 1. Install Dependencies

```bash
pip3 install requests
```

### 2. Get Your Serial Number

Find your Netro controller serial number:
1. Open the Netro mobile app
2. Go to Settings
3. Look for your controller serial number (e.g., `a4cf12b8d5e2`)

### 3. Run Safe Tests

These tests only READ data from your Netro system (won't trigger watering):

```bash
python3 test_local_api.py --serial YOUR_SERIAL_NUMBER
```

Replace `YOUR_SERIAL_NUMBER` with your actual serial number.

## What Gets Tested

### Safe (Read-Only) Tests

These tests retrieve information but don't control your system:

1. **Device Info**
   - Controller name, model, status
   - Zone configuration and names
   - Standby/paused status

2. **Schedules**
   - Currently executing schedules
   - Upcoming scheduled waterings
   - Schedule types (SMART, MANUAL, FIX)

3. **Moisture Levels**
   - Current moisture percentage per zone
   - Last update dates

### Full Tests (Optional)

With the `--full` flag, also tests write operations:

4. **Report Weather**
   - Sends test weather data to Netro
   - Helps Netro optimize schedules
   - **Safe**: Doesn't trigger watering

## Usage Examples

### Basic Usage

```bash
# Safe read-only tests
python3 test_local_api.py --serial a4cf12b8d5e2
```

### Full Testing

```bash
# Include write operations (weather reporting)
python3 test_local_api.py --serial a4cf12b8d5e2 --full
```

### With Whisperer Sensor

```bash
# Test sensor data retrieval
python3 test_local_api.py --serial a4cf12b8d5e2 --sensor whisperer123
```

### Custom Timeout

```bash
# Increase timeout for slow connections
python3 test_local_api.py --serial a4cf12b8d5e2 --timeout 10
```

## Sample Output

```
======================================================================
RUNNING SAFE (READ-ONLY) TESTS
======================================================================
Serial Number: a4cf12b8d5e2
API Base URL: http://api.netrohome.com/npa/v1/

======================================================================
TEST: Device Info
======================================================================

======================================================================
Request: GET http://api.netrohome.com/npa/v1/info.json?key=a4cf12b8d5e2
Status: 200
Response Status: OK
Tokens Remaining: 1847
Token Reset: 1609545600

✓ Success - Found 1 device(s)

Device 1:
  Name: Front Yard Controller
  Model: Sprite
  Serial: a4cf12b8d5e2
  Status: ONLINE
  Standby: False
  Paused: False
  Zones: 4
    ✓ Zone 1: Front Lawn [SMART]
    ✓ Zone 2: Back Lawn [SMART]
    ✓ Zone 3: Garden Beds [MANUAL]
    ✗ Zone 4: Side Yard [MANUAL]

======================================================================
TEST: Schedules
======================================================================
...

======================================================================
TEST SUMMARY
======================================================================
  ✓ PASS: device_info
  ✓ PASS: schedules
  ✓ PASS: moistures

Total: 3/3 tests passed

🎉 All tests passed!
```

## Environment Variables (Optional)

For convenience, create a `.env` file:

```bash
# Copy the example file
cp .env.example .env

# Edit .env with your values
nano .env
```

Then modify the script to load from `.env`:

```python
from dotenv import load_dotenv
load_dotenv()
serial = os.getenv('NETRO_SERIAL')
```

**Important**: Never commit `.env` to git! It's in `.gitignore`.

## Troubleshooting

### Connection Timeout

```
ERROR: Request timed out after 5 seconds
```

**Solution**: Increase timeout with `--timeout 10`

### Invalid Serial Number

```
Status: 401
Error: Invalid key
```

**Solution**: Check your serial number is correct (found in Netro mobile app)

### Rate Limit Exceeded

```
Status: 429
Error: Rate limit exceeded
```

**Solution**:
- Wait until token reset time (shown in output)
- Netro allows 2000 API calls per day
- Check `Tokens Remaining` in output

### Connection Failed

```
ERROR: Connection failed - check network
```

**Solution**:
- Check internet connection
- Verify Netro API is accessible
- Try: `curl http://api.netrohome.com`

## Safety Notes

### What's Safe

✅ **Read Operations** (default mode):
- `device_info` - Read controller configuration
- `schedules` - View scheduled waterings
- `moistures` - Check moisture levels
- `sensor_data` - Read sensor values

These operations retrieve information only and **cannot**:
- Start watering
- Stop watering
- Change settings
- Modify schedules

### What's Not Included

The test script **intentionally omits** these operations for safety:

❌ **Not tested locally** (use Indigo plugin for these):
- Starting zones
- Stopping watering
- Setting standby mode
- Setting rain delay

These are **write operations** that control your irrigation system and should only be tested through the Indigo plugin on your local network with physical access to your system.

### Full Test Mode

The `--full` flag includes:
- ✅ Weather reporting (sends test weather data)

Weather reporting is safe because:
- Doesn't trigger immediate watering
- Only provides data for Netro's smart scheduling
- Can be sent any time without side effects

## API Token Management

Each API call consumes one token from your daily quota of 2000.

The test script shows:
- `Tokens Remaining` - How many calls left today
- `Token Reset` - When quota resets (Unix timestamp)

**Tokens used by this script:**
- Safe mode: ~3 tokens (device, schedules, moistures)
- Full mode: ~4 tokens (+ weather report)
- With sensor: +1 token

**Tips:**
- Run tests sparingly during development
- Netro resets tokens daily at midnight UTC
- Monitor remaining tokens in output
- Plugin polls every 3-5 minutes in production

## Testing Checklist

Before deploying the plugin:

- [ ] Run safe tests successfully
- [ ] Verify all zones appear correctly
- [ ] Check schedule data looks accurate
- [ ] Confirm moisture levels are reasonable
- [ ] Test with sensor (if you have one)
- [ ] Review token consumption
- [ ] Run full tests (optional)

## Integration with Plugin

This script tests the **same API endpoints** used by the Indigo plugin:

| Script Test | Plugin Method |
|-------------|---------------|
| `test_device_info()` | `_update_from_netro()` |
| `test_schedules()` | Schedule parsing in update |
| `test_moistures()` | `callMoisturesAPI()` |
| `test_sensor_data()` | `callSensorAPI()` |
| `test_report_weather()` | `reportWeather()` action |

If tests pass here, the plugin should work in Indigo.

## Next Steps

After local testing succeeds:

1. **Install in Indigo**:
   ```bash
   cp -r "Netro Sprinklers.indigoPlugin" \
      "/Library/Application Support/Perceptive Automation/Indigo 2023.2/Plugins/"
   ```

2. **Enable Plugin**:
   - Open Indigo
   - Plugins → Manage Plugins
   - Enable "Netro Sprinklers"

3. **Configure Plugin**:
   - Enter your serial number
   - Set polling interval (3-5 minutes recommended)

4. **Create Devices**:
   - Create a sprinkler controller device
   - Add Whisperer sensor devices (if you have them)

5. **Test Actions** (in Indigo):
   - Start a zone for 1 minute (test with small duration!)
   - Set rain delay
   - Report weather

## Additional Resources

- **Netro API Docs**: [NETRO_API.md](NETRO_API.md)
- **Plugin Testing**: [TESTING.md](TESTING.md)
- **Plugin Guide**: [CLAUDE.md](CLAUDE.md)
- **Official Docs**: https://www.netrohome.com/en/shop/articles/10

## Questions?

If you encounter issues:

1. Check this guide's Troubleshooting section
2. Verify your serial number in the Netro app
3. Check your internet connection
4. Review the output for specific error messages
5. Check Netro API status
