# Netro API Notes & Quirks

Documentation of Netro Public API (NPA) quirks, limitations, and undocumented behavior discovered during development and testing.

## API Overview

- **Base URL**: `http://api.netrohome.com/npa/v1/`
- **Authentication**: Device serial number as URL parameter (`?key={serial}`)
- **Rate Limit**: 2000 calls per day per serial number
- **Response Format**: JSON
- **HTTP Methods**: GET, POST, PUT

## Known Quirks

### 1. Timestamp Format Inconsistency

**Issue**: API docs say timestamps are numbers, but API returns strings

**Discovered**: Live testing (commit 9e93000)

**Example**:
```json
{
  "start_time": "1740664800000"  // String, not number!
}
```

**Workaround**:
```python
# Handle both string and number
start_time_raw = data.get("start_time", 0)
try:
    start_time = float(start_time_raw) if isinstance(start_time_raw, str) else start_time_raw
except (ValueError, TypeError):
    start_time = 0
```

**Affected Fields**:
- `start_time` in schedules
- `time` in various responses
- Any Unix timestamp field

**Fixed in**: plugin.py lines 309-314, 337-344

### 2. Device vs Devices Response

**Issue**: Inconsistent array/object response structure

**API documentation says**: Returns `devices` array

**Reality**: Returns single `device` object

**Example**:
```json
{
  "status": "OK",
  "data": {
    "device": {          // Singular!
      "serial": "...",
      "name": "...",
      "zones": [...]
    }
  }
}
```

**Not**:
```json
{
  "data": {
    "devices": [...]     // This doesn't exist
  }
}
```

**Workaround**:
```python
device = reply_dict["data"]["device"]  // Not devices[0]
```

**Fixed in**: plugin.py line 233, test_local_api.py line 98

### 3. Offline Status Quirks

**Issue**: Controller status changes are slow and inconsistent

**Observations from live testing**:

**When controller turned OFF**:
- Status changes from "ONLINE" to "STANDBY" (not "OFFLINE"!)
- Schedules reduce from 50 to 2
- Last active timestamp updates
- Can take 5-10 minutes to reflect in API

**When controller turned ON**:
- Status changes from "STANDBY" to "ONLINE"
- Schedules repopulate
- Can take even longer (10+ minutes)

**Implications**:
- Don't rely on immediate status changes
- "STANDBY" can mean either user-set standby OR offline
- Use `last_active` timestamp for better offline detection

### 4. Smart Schedule Types

**Issue**: Underdocumented schedule source types

**Observed values**:
- `"AUTOMATIC"` - Auto-generated smart schedule
- `"MANUAL"` - User-created manual schedule
- `"SMART"` - Smart schedule variant
- `"FIX"` - Fixed schedule
- Others unknown

**Also seen**:
- `smart` field can be boolean `true`/`false`
- OR string `"SMART"`/`"MANUAL"`

**Workaround**:
```python
smart = zone.get('smart', 'MANUAL')
# Handle both boolean and string
if isinstance(smart, bool):
    smart_str = "SMART" if smart else "MANUAL"
else:
    smart_str = smart
```

### 5. API Rate Limiting Behavior

**Issue**: Undocumented throttle response format

**When rate limit exceeded**:
- HTTP 429 response
- No specific error message in JSON
- Plugin must track throttle state locally

**Token tracking**:
```json
{
  "meta": {
    "token_remaining": 1847,
    "token_reset": 1609545600  // Unix timestamp
  }
}
```

**Observations**:
- Token count decreases by 1 per call
- Resets at midnight UTC
- Going over limit triggers 61-minute lockout
- Subsequent calls during lockout also return 429

**Best practices**:
- Check `token_remaining` in every response
- Warn user when <100 remaining
- Implement exponential backoff if needed

### 6. Moisture Data Timing

**Issue**: Moisture updates are infrequent

**Observations**:
- Moisture measured once per day (typically)
- Updates happen during scheduled watering or smart schedule evaluation
- Manual watering doesn't always trigger measurement
- Values can be 12-24 hours old

**Response format**:
```json
{
  "moistures": [
    {
      "id": 12345,
      "zone": 1,
      "moisture": 45,
      "date": "2025-01-27"
    }
  ]
}
```

**Workarounds**:
- Sort by ID to get most recent: `sort(key=lambda x: x['id'], reverse=True)`
- Filter by most recent date
- Show date with moisture value so users understand age

### 7. Whisperer Sensor Reporting

**Issue**: Sensor update frequency is variable

**Observations**:
- Sensors report every 4-6 hours normally
- Can be longer if battery low
- No way to force immediate update
- Battery level crucial - <20% = unreliable

**Response structure**:
```json
{
  "sensor_data": [
    {
      "id": 123,
      "moisture": 45,
      "celsius": 22,
      "fahrenheit": 72,
      "sunlight": 1200,
      "battery_level": 85,
      "time": "...",
      "local_date": "2025-01-27",
      "local_time": "14:30:00"
    }
  ]
}
```

**Field notes**:
- `local_date` and `local_time` are STRINGS (not swapped anymore - fixed in commit 617a630)
- `battery_level` is percentage (0-100)
- `sunlight` is in lux
- Most recent reading is first after sorting by ID

### 8. Weather Reporting Quirks

**Issue**: Weather parameters poorly documented

**Required fields**:
- `key`: Serial number
- `t`: Current temperature (Fahrenheit)
- `date`: YYYY-MM-DD format

**Optional fields**:
- `t_max`, `t_min`: High/low temperature
- `humidity`: 0-100 percentage
- `condition`: Weather code (0=clear, others undocumented)
- `rain`: Rainfall amount (units unclear)
- `rain_prob`: Rain probability 0-100
- `wind_speed`: Wind speed (units unclear - likely mph)
- `pressure`: Atmospheric pressure (units unclear - likely inHg)

**Condition codes** (observed/guessed):
```
0  = Clear
1  = Cloudy?
2  = Rain?
3+ = Unknown
```

**Note**: Weather reporting doesn't trigger immediate schedule changes

### 9. Zone Control Limitations

**What works**:
- ✅ Start individual zone with duration
- ✅ Stop all zones
- ✅ Set rain delay
- ✅ Set standby mode

**What doesn't work** (API limitations):
- ❌ Pause/resume individual zones
- ❌ Skip to next zone in schedule
- ❌ Go back to previous zone
- ❌ Modify zone duration while running
- ❌ Create/modify schedules via API
- ❌ Change zone settings (soil type, etc.)

**Advanced features** (available but less tested):
- `delay`: Minutes before starting (0-60)
- `start_time`: Schedule for future (Unix timestamp)

### 10. Error Response Format

**Issue**: Inconsistent error responses

**Success**:
```json
{
  "status": "OK",
  "data": {...},
  "meta": {...}
}
```

**Error examples**:
```json
// HTTP 401
{
  "status": "ERROR",
  "error": "Invalid key"
}

// HTTP 429
{
  "status": "ERROR",
  "error": "Rate limit exceeded"
}

// HTTP 500
{
  "status": "ERROR",
  "error": "Internal server error"
}
```

**Sometimes**: Just HTTP status code, no JSON body

**Workaround**: Check HTTP status first, then parse JSON if available

## Testing Observations

### Live Testing Results (Jan 2025)

**Test controller**: "Clark Castle Spark"
- Serial: 0cb8152f9f78
- 16 zones total
- 8 enabled zones
- API tokens: 1665/2000 remaining

**When ONLINE**:
- 50 schedules returned
- Status: "ONLINE"
- All zone data populated

**When OFFLINE** (controller powered off):
- 2 schedules returned (down from 50)
- Status: "STANDBY" (not "OFFLINE"!)
- Historical moisture data still available
- `last_active` timestamp updates when status changes

**Polling behavior**:
- 3-minute interval: ~480 calls/day (safe)
- 5-minute interval: ~288 calls/day (very safe)
- 1-minute interval: ~1440 calls/day (risky!)

## Recommendations

### For Plugin Developers

1. **Always handle both string and number timestamps**
2. **Don't assume response structure matches docs**
3. **Test with controller both online and offline**
4. **Implement generous error handling**
5. **Log API responses in debug mode**
6. **Check token_remaining in every response**
7. **Use conservative polling intervals (5+ minutes)**

### For Users

1. **Increase polling interval if approaching rate limit**
2. **Don't rely on immediate status updates**
3. **Use Netro app for zone configuration**
4. **Replace sensor batteries when <20%**
5. **Allow 10-15 minutes for status changes**

## Useful Testing Commands

### Test API directly:
```bash
# Device info
curl "http://api.netrohome.com/npa/v1/info.json?key=YOUR_SERIAL"

# Schedules
curl "http://api.netrohome.com/npa/v1/schedules.json?key=YOUR_SERIAL"

# Moisture
curl "http://api.netrohome.com/npa/v1/moistures.json?key=YOUR_SERIAL"
```

### Use test script:
```bash
python3 test_local_api.py --serial YOUR_SERIAL
```

See [LOCAL_TESTING.md](LOCAL_TESTING.md) for details.

## API Documentation

Official (limited) docs:
- https://www.netrohome.com/en/shop/articles/10

Better info sources:
- This file (API_NOTES.md)
- [NETRO_API.md](NETRO_API.md) - Full endpoint documentation
- test_local_api.py source code
- plugin.py _make_api_call() implementation

## Version History

**Discoveries by version**:
- v1.0 (initial): Basic API integration
- v2.0 (overhaul): 
  - Timestamp string/number handling (commit 9e93000)
  - Device vs devices fix (commit 617a630)
  - Offline status observations (Jan 2025 testing)
  - Token warning thresholds added
  - All quirks documented in this file

## Future Watch List

**Behaviors to monitor**:
- Schedule type values (may discover new types)
- Weather condition codes (need complete list)
- Error response formats (may vary)
- New API endpoints (if Netro adds features)
- Rate limit policy changes

**Report issues**:
- Unexpected API responses
- New schedule types
- Different error formats
- Undocumented fields

