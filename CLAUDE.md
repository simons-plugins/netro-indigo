# CLAUDE.md

Developer guidance for the Netro Sprinklers Indigo plugin.

## Project Overview

**Production-ready Indigo plugin** for Netro smart irrigation controllers and Whisperer soil sensors.

- **Version**: 2.0 (complete overhaul completed Jan 2025)
- **Python**: 3.10+ (Indigo 2023+)
- **API**: Netro Public API (NPA) v1
- **Testing**: 64 automated tests, >70% coverage
- **Status**: ✅ Tested with real hardware

## Quick Links

- **[NETRO_API.md](NETRO_API.md)** - Complete API reference
- **[API_NOTES.md](API_NOTES.md)** - API quirks and discoveries
- **[TESTING.md](TESTING.md)** - Test suite guide
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - User troubleshooting
- **[LOCAL_TESTING.md](LOCAL_TESTING.md)** - Standalone API testing
- **[DEPENDENCIES.md](DEPENDENCIES.md)** - Package management

## Architecture

### Plugin Structure

```
Netro Sprinklers.indigoPlugin/
├── Contents/
│   ├── Info.plist                      # Plugin metadata
│   └── Server Plugin/
│       ├── plugin.py                    # Main implementation (1200+ lines)
│       ├── requirements.txt             # Python dependencies
│       ├── Devices.xml                  # Device definitions
│       ├── Actions.xml                  # Custom actions
│       ├── Events.xml                   # Trigger definitions
│       ├── PluginConfig.xml            # Plugin config UI
│       └── MenuItems.xml               # Plugin menus
└── tests/                              # Test suite (64 tests)
    ├── conftest.py                     # pytest fixtures
    ├── test_api_client.py              # API tests (17)
    ├── test_validation.py              # Config validation (24)
    ├── test_actions.py                 # Action tests (23)
    └── fixtures/                        # Mock API responses
```

### Core Components

#### 1. Plugin Class (`Plugin`)

**Location**: [plugin.py:132-1440](Netro%20Sprinklers.indigoPlugin/Contents/Server%20Plugin/plugin.py)

**Inherits**: `indigo.PluginBase`

**Key Attributes**:
```python
self.serial_number      # Netro controller serial (authentication)
self.pollingInterval    # API poll frequency (minutes, min 3)
self.timeout            # API request timeout (seconds, default 5)
self.throttle_next_call # Throttle expiry datetime (None if not throttled)
self.person             # Cached API device data
self.netro_devices      # List of Netro devices
self.triggerDict        # Active Indigo triggers
```

**Lifecycle**:
1. `__init__()` - Initialize config, create data structures
2. `startup()` - Log startup (no heavy initialization)
3. `runConcurrentThread()` - Poll API every N minutes
4. `shutdown()` - Clean shutdown

#### 2. Device Types

**Sprinkler Controller** (deviceTypeId: "sprinkler"):
- Inherits Indigo sprinkler device type
- Supports up to 16 zones (tested with real hardware)
- Standard actions: Zone On, All Zones Off
- Custom actions: Rain delay, Standby mode, Weather reporting

**Whisperer Sensor** (deviceTypeId: "Whisperer"):
- Soil moisture sensor
- Reports: moisture %, temperature, sunlight, battery level
- Updates every 4-6 hours (Netro limitation)

#### 3. API Integration

**Method**: `_make_api_call(url, method, data)` ([plugin.py:182-279](Netro%20Sprinklers.indigoPlugin/Contents/Server%20Plugin/plugin.py))

**Features**:
- Automatic throttle enforcement (61-min delay after HTTP 429)
- Timeout handling (configurable, default 5s)
- Error suppression after first display
- JSON response parsing
- Trigger firing on errors

**Endpoints**:
```python
# Defined at plugin.py:60-69
DEVICE_INFO_URL          # GET device/zone info
DEVICE_SCHEDULES_URL     # GET active schedules
DEVICE_MOISTURES_URL     # GET moisture levels
DEVICE_SENSOR_DATA_URL   # GET Whisperer readings
DEVICE_WATER_URL         # POST start watering
DEVICE_STOP_WATER_URL    # POST stop all zones
DEVICE_SET_STATUS_URL    # POST standby on/off
DEVICE_NO_WATER_URL      # POST rain delay
DEVICE_REPORT_WEATHER_URL # POST weather data
```

**Authentication**: Serial number as URL parameter (`?key={serial}`)

**Rate Limit**: 2000 calls/day
- 3-min polling = ~480 calls/day ✅ Safe
- 5-min polling = ~288 calls/day ✅ Very safe
- 1-min polling = ~1440 calls/day ⚠️ Risky

#### 4. State Management

**Main Update Loop**: `_update_from_netro()` ([plugin.py:315-542](Netro%20Sprinklers.indigoPlugin/Contents/Server%20Plugin/plugin.py))

**Updates for Sprinkler Controllers**:
1. Device info (status, model, version)
2. Token counts (remaining, reset time)
3. Active schedule (zone, source type)
4. Next schedule (time, zone, duration)
5. Moisture levels per zone
6. Zone configuration (names, enabled status)

**Updates for Whisperer Sensors**:
1. Moisture percentage
2. Temperature (Celsius and Fahrenheit)
3. Sunlight (lux)
4. Battery level
5. Reading timestamps

**State vs Properties**:
- **States**: Frequently changing (status, active zone, moisture)
- **Properties**: Static config (zone names, count)

#### 5. Validation System

**Plugin Config**: `validatePrefsConfigUi()` ([plugin.py:844-895](Netro%20Sprinklers.indigoPlugin/Contents/Server%20Plugin/plugin.py))
- Serial number format (12 hex chars)
- Polling interval (≥3 minutes)
- API timeout (1-60 seconds)
- Max zone runtime (60-10800 seconds)

**Device Config**: `validateDeviceConfigUi()` ([plugin.py:688-725](Netro%20Sprinklers.indigoPlugin/Contents/Server%20Plugin/plugin.py))
- Serial number required
- Whisperer sensor capabilities set

**Action Config**: `validateActionConfigUi()` ([plugin.py:728-821](Netro%20Sprinklers.indigoPlugin/Contents/Server%20Plugin/plugin.py))
- Zone delay parameters (1-180 min duration, 0-60 min delay)
- Weather data ranges
- Date format validation

#### 6. Actions

**Standard Sprinkler Actions**: `actionControlSprinkler()` ([plugin.py:1072-1157](Netro%20Sprinklers.indigoPlugin/Contents/Server%20Plugin/plugin.py))
- Zone On: Start specific zone
- All Zones Off: Stop all watering

**Custom Actions** (defined in [Actions.xml](Netro%20Sprinklers.indigoPlugin/Contents/Server%20Plugin/Actions.xml)):

| Action | Method | Purpose |
|--------|--------|---------|
| Start Zone with Delay | `startZoneWithDelay()` | Advanced zone start with delay/schedule |
| Report Weather | `reportWeather()` | Send local weather to Netro |
| Set Rain Delay | `setNoWater()` | Skip watering for N days |
| Set Standby Mode | `setStandbyMode()` | Pause all automatic watering |

#### 7. Triggers

**Event Types** (defined in [Events.xml](Netro%20Sprinklers.indigoPlugin/Contents/Server%20Plugin/Events.xml)):
- Zone start failed
- Stop watering failed
- Standby mode failed
- Rate limit exceeded
- API communication errors

**Dispatch**: `_fireTrigger(event, dev_id)` ([plugin.py:1020-1055](Netro%20Sprinklers.indigoPlugin/Contents/Server%20Plugin/plugin.py))

## Development Workflow

### Making Changes

1. **Edit code** in appropriate file
2. **Add/update tests** if changing behavior
3. **Run tests**: `pytest tests/`
4. **Test in Indigo**:
   ```bash
   cp -r "Netro Sprinklers.indigoPlugin" "/Library/Application Support/Perceptive Automation/Indigo 2023.2/Plugins/"
   # Then reload in Indigo UI
   ```
5. **Check Event Log** for errors
6. **Commit with descriptive message**

### Testing

**Unit Tests**:
```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov

# Run specific test file
pytest tests/test_api_client.py

# Run specific test
pytest tests/test_api_client.py::test_successful_get_request
```

**Integration Testing**:
```bash
# Test against real Netro API
python3 test_local_api.py --serial YOUR_SERIAL

# Full test with write operations
python3 test_local_api.py --serial YOUR_SERIAL --full
```

See [TESTING.md](TESTING.md) for complete guide.

### Code Quality

**Style**: Google Python Style Guide with Indigo conventions

**Documentation**:
- Module docstrings required
- Method docstrings (Args, Returns, Raises)
- Inline comments for complex logic

**Pylint**: Target score >8.0
```bash
python3 -m pylint plugin.py --max-line-length=120
```

Current score: ~6.5/10 (in progress)

### Dependencies

**Runtime** (auto-installed by Indigo):
- `requests==2.32.5` - HTTP client

**Development**:
- `pytest>=8.0.0` - Test framework
- `pytest-cov>=4.1.0` - Coverage reporting
- `pytest-mock>=3.12.0` - Mocking support

See [DEPENDENCIES.md](DEPENDENCIES.md) for details.

## Key Implementation Details

### API Quirks

**Critical discoveries** (see [API_NOTES.md](API_NOTES.md)):

1. **Timestamps as strings**: API returns timestamps as string numbers
   ```python
   # Handle both formats
   start_time = float(raw) if isinstance(raw, str) else raw
   ```

2. **Device response structure**: Returns `device` object, not `devices` array
   ```python
   device = reply["data"]["device"]  # Not devices[0]
   ```

3. **Offline status**: Controllers show "STANDBY" when offline (not "OFFLINE")

4. **Schedule types**: Can be string ("SMART") or boolean (true)

5. **Moisture updates**: Once per day, can be 12-24 hours old

### Throttle Management

**Implementation**:
- HTTP 429 triggers 61-minute lockout
- Stores expiry in `self.throttle_next_call`
- All API calls check throttle state first
- Fires "rateLimitExceeded" trigger
- Logs warnings when tokens <200

**Prevention**:
- Default 3-minute polling = safe
- Warn user when <100 tokens remain
- Show token count in device states

### Error Handling

**Philosophy**: Fail gracefully, log details, continue operation

**Patterns**:
```python
try:
    result = api_call()
except requests.exceptions.Timeout:
    if not self._displayed_connection_error:
        self.logger.error("Timeout - will retry silently")
        self._displayed_connection_error = True
    raise  # Re-raise for higher-level handling
```

**Trigger on errors**: Let users automate responses

## File Reference

### Core Files

- **[plugin.py](Netro%20Sprinklers.indigoPlugin/Contents/Server%20Plugin/plugin.py)** - Main implementation (1200+ lines)
- **[Devices.xml](Netro%20Sprinklers.indigoPlugin/Contents/Server%20Plugin/Devices.xml)** - Device types
- **[Actions.xml](Netro%20Sprinklers.indigoPlugin/Contents/Server%20Plugin/Actions.xml)** - Custom actions
- **[Events.xml](Netro%20Sprinklers.indigoPlugin/Contents/Server%20Plugin/Events.xml)** - Triggers
- **[PluginConfig.xml](Netro%20Sprinklers.indigoPlugin/Contents/Server%20Plugin/PluginConfig.xml)** - Plugin settings UI
- **[Info.plist](Netro%20Sprinklers.indigoPlugin/Contents/Info.plist)** - Plugin metadata

### Documentation

- **[NETRO_API.md](NETRO_API.md)** - Complete API documentation
- **[API_NOTES.md](API_NOTES.md)** - API quirks and discoveries
- **[TESTING.md](TESTING.md)** - Test suite guide
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - User troubleshooting
- **[LOCAL_TESTING.md](LOCAL_TESTING.md)** - Standalone API testing
- **[DEPENDENCIES.md](DEPENDENCIES.md)** - Package management

### Testing

- **[tests/conftest.py](tests/conftest.py)** - pytest fixtures
- **[tests/test_api_client.py](tests/test_api_client.py)** - API tests (17)
- **[tests/test_validation.py](tests/test_validation.py)** - Validation (24)
- **[tests/test_actions.py](tests/test_actions.py)** - Actions (23)
- **[test_local_api.py](test_local_api.py)** - Standalone API tester

## Version History

### v2.0 (January 2025) - Complete Overhaul

**Phase 1-5 Complete**:
- ✅ Fixed critical bugs (uninitialized variables, dead code)
- ✅ Cleaned API architecture (single HTTP library, consistent patterns)
- ✅ Enhanced configuration & validation
- ✅ Added feature s (zone delays, weather reporting, next schedule)
- ✅ Created test suite (64 tests, >70% coverage)

**Phase 6 Complete**:
- ✅ Comprehensive docstrings (all methods documented)
- ✅ Code quality improvements (pylint 6.5/10, target 8.0)
- ✅ Created TESTING.md, TROUBLESHOOTING.md, API_NOTES.md
- ✅ Updated CLAUDE.md (this file)

**Live Tested**:
- Real hardware: "Clark Castle Spark" controller
- 16 zones, 8 enabled
- Online/offline transitions verified
- API quirks discovered and documented
- Rate limiting tested

### v1.0 (Original)

- Basic Netro integration
- Rachio plugin fork
- 786 lines, multiple bugs
- Incomplete features

## Known Limitations

**API Limitations** (Netro, not plugin):
- ❌ Cannot pause/resume schedules
- ❌ Cannot create/modify schedules
- ❌ Cannot change zone settings
- ❌ Cannot skip to next/previous zone
- ❌ Moisture updates only once per day

**Plugin Limitations**:
- Single controller per plugin instance (use multiple plugin instances for multiple controllers)
- Polling-based updates (no push notifications)
- Requires constant internet connection

**Workarounds**:
- Use Netro mobile app for schedule management
- Use Indigo for automation and custom logic
- Set appropriate polling intervals for use case

## Future Enhancements

**Potential additions**:
- [ ] Multi-controller support in single plugin
- [ ] Forecast integration (if Netro adds API)
- [ ] Historical moisture graphing
- [ ] Zone usage statistics
- [ ] Custom schedule templates
- [ ] Webhook support (if Netro adds)

**Code quality**:
- [ ] Increase pylint score to 8.0+
- [ ] Add type hints throughout
- [ ] Increase test coverage to 85%+

## Support

**For Users**:
1. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
2. Enable debug logging
3. Check Indigo Event Log
4. Test with test_local_api.py
5. Post on Indigo forums with logs

**For Developers**:
1. Review this file (CLAUDE.md)
2. Check relevant documentation
3. Run test suite
4. Add tests for new features
5. Follow code quality guidelines

## Additional Resources

- **Indigo SDK**: See ../Indigo SDK/docs/
- **Netro Support**: https://support.netrohome.com
- **Netro API Docs**: https://www.netrohome.com/en/shop/articles/10
- **Indigo Forums**: https://forums.indigodomo.com

