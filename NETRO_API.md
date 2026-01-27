# Netro Public API (NPA) Reference

**Official Documentation**: https://www.netrohome.com/en/shop/articles/10

## Overview

The Netro Public API provides HTTP-based access to control Netro smart irrigation devices and retrieve sensor data. This API enables third-party integrations with infinite flexibility.

## Authentication

**Method**: Serial number-based authentication

- **Key Parameter**: `key` (device serial number)
- **Location**: Found in Netro mobile app under Settings
- **Security Warning**: Serial numbers grant full API access - keep them confidential

**Usage**:
```
GET /npa/v1/info.json?key=YOUR_SERIAL_NUMBER
POST /npa/v1/water.json (with {"key": "YOUR_SERIAL_NUMBER", ...} in body)
```

## Rate Limiting

**Limits**:
- **Daily Quota**: 2,000 API calls per day
- **Approximate Rate**: ~1 call per minute (83 calls per hour)
- **Reset Time**: Midnight UTC
- **Exceeded Behavior**: Access denied until reset

**Tracking**:
- Monitor via `meta.token_remaining` in responses
- Check next reset time via `meta.token_reset`

**Best Practices**:
- Implement backoff on 429 errors (rate limit exceeded)
- Cache responses when possible
- Use appropriate polling intervals (recommended: 3-10 minutes)

## Base URL

```
http://api.netrohome.com/npa/v1/
```

## Response Format

All API responses return JSON with the following structure:

### Successful Response
```json
{
  "status": "OK",
  "data": {
    // Response data specific to endpoint
  },
  "meta": {
    "time": 1234567890000,        // Server timestamp (milliseconds)
    "tid": "unique-transaction-id",
    "version": 1,
    "token_remaining": 1850,       // Remaining API calls today
    "token_reset": 1234567890,     // Unix timestamp of next reset
    "last_active": 1234567890000   // Last device activity
  }
}
```

### Error Response
```json
{
  "status": "ERROR",
  "errors": [
    {
      "code": 1,
      "message": "Error description"
    }
  ],
  "meta": {
    // Same meta structure as success
  }
}
```

### Error Codes

| Code | Meaning | Solution |
|------|---------|----------|
| 1 | Invalid key | Verify serial number is correct |
| 3 | Rate limit exceeded | Wait until token_reset time |
| 4 | Invalid device/sensor | Check device exists and is active |
| 5 | Internal server error | Retry after delay |
| 6 | Parameter error | Verify request parameters |

## Device APIs

### Get Device Info

**Endpoint**: `GET /npa/v1/info.json?key={serial}`

**Purpose**: Retrieve device details, zone configuration, and current status

**Response Data**:
```json
{
  "device": {
    "id": "device-id",
    "serial": "a4cf12b8d5e2",
    "name": "My Controller",
    "status": "ONLINE",              // ONLINE or OFFLINE
    "version": "1.2.3",
    "model": "Sprite",
    "mac_address": "A4:CF:12:B8:D5:E2",
    "create_time": 1234567890000,
    "start_time": 1234567890000,
    "enable": true,
    "zones": [
      {
        "id": "zone-id",
        "ith": 1,                     // Zone number (1-based)
        "name": "Front Lawn",
        "enabled": true,
        "smart": true
      }
    ]
  }
}
```

**Usage Example**:
```python
url = f"http://api.netrohome.com/npa/v1/info.json?key={serial_number}"
response = requests.get(url)
data = response.json()
if data["status"] == "OK":
    device = data["data"]["device"]
    print(f"Device: {device['name']}, Status: {device['status']}")
```

### Get Schedules

**Endpoint**: `GET /npa/v1/schedules.json?key={serial}&start_date={date}&end_date={date}`

**Purpose**: Retrieve watering schedules within a date range

**Parameters**:
- `key` (required): Device serial number
- `start_date` (optional): Start date (YYYY-MM-DD format)
- `end_date` (optional): End date (YYYY-MM-DD format)

**Response Data**:
```json
{
  "schedules": [
    {
      "id": "schedule-id",
      "zone": 1,
      "zone_name": "Front Lawn",
      "source": "AUTOMATIC",        // AUTOMATIC or MANUAL
      "status": "EXECUTING",        // VALID, EXECUTING, EXECUTED, CANCELLED
      "start_time": 1234567890000,
      "end_time": 1234567890000,
      "duration": 600,              // seconds
      "reason": "SCHEDULE"
    }
  ]
}
```

**Status Values**:
- `VALID`: Scheduled but not started
- `EXECUTING`: Currently running
- `EXECUTED`: Completed
- `CANCELLED`: Cancelled before execution

### Get Moisture Levels

**Endpoint**: `GET /npa/v1/moistures.json?key={serial}&start_date={date}&end_date={date}&zone={zone}`

**Purpose**: Retrieve historical moisture level data

**Parameters**:
- `key` (required): Device serial number
- `start_date` (optional): Start date (YYYY-MM-DD)
- `end_date` (optional): End date (YYYY-MM-DD)
- `zone` (optional): Zone number (1-based)

**Response Data**:
```json
{
  "moistures": [
    {
      "id": "moisture-id",
      "zone": 1,
      "moisture": 65,               // Percentage (0-100)
      "date": 1234567890000
    }
  ]
}
```

### Get Events

**Endpoint**: `GET /npa/v1/events.json?key={serial}&start_date={date}&end_date={date}`

**Purpose**: Retrieve device events (status changes, schedules)

**Parameters**:
- `key` (required): Device serial number
- `start_date` (optional): Start date (YYYY-MM-DD)
- `end_date` (optional): End date (YYYY-MM-DD)

**Response Data**:
```json
{
  "events": [
    {
      "type": "OFFLINE",            // OFFLINE, ONLINE, SCHEDULE_START, SCHEDULE_END
      "time": 1234567890000,
      "details": {
        // Event-specific details
      }
    }
  ]
}
```

### Set Device Status

**Endpoint**: `POST /npa/v1/set_status.json`

**Purpose**: Enable or disable the device (standby mode)

**Request Body**:
```json
{
  "key": "serial-number",
  "status": 1                       // 0 = standby/disabled, 1 = online/enabled
}
```

**Response**: Standard success/error response

**Note**: Standby mode disables all automatic schedules and functions.

### Start Watering

**Endpoint**: `POST /npa/v1/water.json`

**Purpose**: Start immediate or scheduled watering for specific zones

**Request Body**:
```json
{
  "key": "serial-number",
  "zones": [
    {
      "id": "zone-id",              // Zone ID from info.json
      "duration": 10                // Minutes (1-180)
    },
    {
      "id": "zone-id-2",
      "duration": 15
    }
  ],
  "delay": 0,                       // Minutes to delay start (optional)
  "start_time": 1234567890          // Unix timestamp for scheduled start (optional)
}
```

**Parameters**:
- `zones`: Array of zone objects with `id` and `duration`
- `duration`: Watering time in minutes (1-180 minutes max)
- `delay`: Minutes to wait before starting (optional)
- `start_time`: UTC Unix timestamp for scheduled start (optional)

**Response**: Standard success/error response

**Example**:
```python
data = {
    "key": serial_number,
    "zones": [
        {"id": zone_id, "duration": 15}
    ]
}
response = requests.post("http://api.netrohome.com/npa/v1/water.json", json=data)
```

### Stop Watering

**Endpoint**: `POST /npa/v1/stop_water.json`

**Purpose**: Stop all current watering and cancel manual schedules

**Request Body**:
```json
{
  "key": "serial-number"
}
```

**Response**: Standard success/error response

**Note**: Only stops manual watering. Automatic schedules continue unless device is in standby.

### Set Rain Delay (No Water)

**Endpoint**: `POST /npa/v1/no_water.json`

**Purpose**: Prevent watering for a specified number of days

**Request Body**:
```json
{
  "key": "serial-number",
  "days": 3                         // Number of days (1-100)
}
```

**Parameters**:
- `days`: Number of days to block watering (1-100)
  - `1` = today only
  - Default: 1

**Response**: Standard success/error response

**Use Cases**:
- Rain delay
- Maintenance periods
- Temporary suspension

### Set Moisture Override

**Endpoint**: `POST /npa/v1/set_moisture.json`

**Purpose**: Override system moisture estimates with custom values

**Request Body**:
```json
{
  "key": "serial-number",
  "moistures": [
    {
      "zone": 1,
      "moisture": 75                // Percentage (0-100)
    }
  ]
}
```

**Response**: Standard success/error response

**Note**: Overrides Netro's calculated moisture levels. Use cautiously as it affects automatic scheduling decisions.

### Report Weather

**Endpoint**: `POST /npa/v1/report_weather.json`

**Purpose**: Submit local weather data to improve scheduling accuracy

**Request Body**:
```json
{
  "key": "serial-number",
  "condition": 0,                   // Weather condition code (0-4)
  "rain": 0.5,                      // Rainfall in inches
  "rain_prob": 30,                  // Probability of rain (0-100)
  "t_max": 85,                      // Max temperature (Fahrenheit)
  "t_min": 65,                      // Min temperature (Fahrenheit)
  "t": 75,                          // Current temperature (Fahrenheit)
  "humidity": 60,                   // Humidity percentage (0-100)
  "wind_speed": 10,                 // Wind speed (mph)
  "pressure": 30.1,                 // Atmospheric pressure (inHg)
  "date": "2024-01-27"              // Date for this weather data (YYYY-MM-DD)
}
```

**Weather Condition Codes**:
- `0`: Clear
- `1`: Cloudy
- `2`: Rain
- `3`: Snow
- `4`: Wind

**Response**: Standard success/error response

**Note**: Helps Netro make better watering decisions based on actual local conditions.

## Sensor APIs

### Get Whisperer Sensor Data

**Endpoint**: `GET /npa/v1/sensor_data.json?key={serial}&start_date={date}&end_date={date}`

**Purpose**: Retrieve sensor readings from Whisperer plant sensors

**Parameters**:
- `key` (required): Sensor serial number
- `start_date` (optional): Start date (YYYY-MM-DD)
- `end_date` (optional): End date (YYYY-MM-DD)

**Response Data**:
```json
{
  "sensor_data": [
    {
      "id": "reading-id",
      "time": 1234567890000,
      "local_time": "2024-01-27",
      "local_date": "14:30:00",
      "moisture": 45,               // Soil moisture percentage (0-100)
      "celsius": 22,                // Temperature in Celsius
      "fahrenheit": 72,             // Temperature in Fahrenheit
      "sunlight": 25000,            // Light intensity (lux)
      "battery_level": 85           // Battery percentage (0-100)
    }
  ]
}
```

**Sensor Metrics**:
- **Moisture**: Soil moisture percentage (0-100%)
- **Temperature**: Both Celsius and Fahrenheit
- **Sunlight**: Light intensity in lux
- **Battery**: Battery level percentage

**Reading Frequency**: Typically one reading per hour

## Implementation Notes

### Polling Strategy

**Recommended Intervals**:
- Device status: 3-10 minutes
- Moisture levels: 15-30 minutes
- Sensor data: 30-60 minutes
- Active schedule checks: 1-5 minutes (when watering)

**Rate Limit Considerations**:
- 2,000 calls/day = ~1.4 calls/minute maximum
- Leave headroom for user-initiated actions
- Implement exponential backoff on errors

### Error Handling

```python
def make_api_call(url, method="GET", data=None):
    try:
        if method == "POST":
            response = requests.post(url, json=data, timeout=5)
        else:
            response = requests.get(url, timeout=5)

        if response.status_code == 429:
            # Rate limit exceeded
            result = response.json()
            reset_time = result["meta"]["token_reset"]
            # Wait until reset_time before next call
            raise RateLimitError(f"Rate limit exceeded. Reset at {reset_time}")

        response.raise_for_status()
        result = response.json()

        if result["status"] == "ERROR":
            error = result["errors"][0]
            raise APIError(f"API Error {error['code']}: {error['message']}")

        return result["data"]

    except requests.exceptions.Timeout:
        # Handle timeout
        raise
    except requests.exceptions.ConnectionError:
        # Handle connection error
        raise
```

### Timezone Handling

- API timestamps are in **milliseconds** (not seconds)
- Timestamps are **UTC**
- Convert to local time for display:

```python
from datetime import datetime
from dateutil import tz

def convert_timestamp(timestamp_ms):
    utc_time = datetime.utcfromtimestamp(timestamp_ms / 1000)
    utc_time = utc_time.replace(tzinfo=tz.tzutc())
    local_time = utc_time.astimezone(tz.tzlocal())
    return local_time
```

### Duration Limits

**Zone Watering**:
- Minimum: 1 minute
- Maximum: 180 minutes (3 hours) per API call
- Plugin may enforce lower limits (configurable)

**Rain Delay**:
- Minimum: 1 day
- Maximum: 100 days

### Device Status Values

**Status**: `ONLINE` or `OFFLINE`
- `ONLINE`: Device is connected and responsive
- `OFFLINE`: Device is disconnected (unplugged, no internet, etc.)
- **Note**: Status may take significant time to update to OFFLINE

### Best Practices

1. **Cache Device Info**: Zone names and IDs don't change often
2. **Batch Updates**: Combine multiple state updates in one poll cycle
3. **Respect Rate Limits**: Monitor `token_remaining` and adjust polling
4. **Handle OFFLINE**: Don't spam API when device is offline
5. **Timeout Handling**: Use reasonable timeouts (5-10 seconds)
6. **Error Recovery**: Implement retry logic with backoff
7. **Token Monitoring**: Alert users when approaching rate limit

## Version History

- **API Version**: v1
- **Base URL**: http://api.netrohome.com/npa/v1/
- **Documentation**: https://www.netrohome.com/en/shop/articles/10

## Security Considerations

- Serial numbers provide **full control** of devices
- Do not expose serial numbers in:
  - Public repositories
  - Client-side code
  - Log files
  - Error messages
- Store securely in configuration
- Use environment variables or secure storage
- Rotate/change if compromised (contact Netro support)
