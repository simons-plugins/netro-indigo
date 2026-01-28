# Netro Smart Sprinklers Plugin for Indigo

Professional-grade integration for Netro smart irrigation controllers with the [Indigo Home Automation](https://www.indigodomo.com) platform.

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](https://github.com/simons-plugins/netro-indigo/releases)
[![Indigo API](https://img.shields.io/badge/Indigo%20API-3.6-green.svg)](https://www.indigodomo.com)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org)
[![Code Quality](https://img.shields.io/badge/pylint-9.36%2F10-brightgreen.svg)](https://www.pylint.org)
[![Tests](https://img.shields.io/badge/tests-64%20passing-brightgreen.svg)](#testing)

## Overview

This plugin integrates Netro smart irrigation controllers (Sprite, Pixie, Spark) with Indigo, providing complete control and monitoring of your sprinkler system through home automation.

**Supported Controllers**:
- Netro Sprite
- Netro Pixie
- Netro Spark
- Whisperer soil moisture sensors

## Features

### Core Functionality
- ✅ **Zone Control** - Start/stop individual zones remotely
- ✅ **Real-time Status** - Monitor controller online/offline status
- ✅ **Moisture Tracking** - View soil moisture levels per zone
- ✅ **Schedule Visibility** - See current and upcoming watering schedules
- ✅ **Rain Delays** - Set rain delays (1-100 days)
- ✅ **Standby Mode** - Enable/disable automatic watering

### Advanced Features (v2.0+)
- 🆕 **Delayed Watering** - Start zones with 0-60 minute delay or at specific time
- 🆕 **Weather Reporting** - Send local weather data to improve Netro's AI scheduling
- 🆕 **Next Schedule Info** - See when the next watering will occur and which zone
- 🆕 **Schedule Types** - Distinguish between SMART, AUTOMATIC, FIX, and MANUAL schedules
- 🆕 **API Usage Monitoring** - Track daily API call usage (visible in device states)

### Integration Features
- 📊 Rate limit management (2000 API calls/day)
- 🔔 Indigo triggers for errors and events
- 🌡️ Whisperer sensor support (temperature, humidity, moisture)
- ⚙️ Configurable polling interval (minimum 3 minutes)

## Installation

### For Users

1. Download the latest release from [GitHub Releases](https://github.com/simons-plugins/netro-indigo/releases)
2. Double-click the `.indigoPlugin` file to install
3. Configure the plugin with your Netro controller serial number
4. Create a new "Netro Smart Sprinkler" device in Indigo

### For Developers

See [Development Setup](#development-setup) below.

## Configuration

### Plugin Configuration

1. Go to **Indigo → Plugins → Netro Smart Sprinklers → Configure**
2. Enter your Netro controller serial number (12 hex characters)
3. Set polling interval (minimum 3 minutes, default 3)
4. Configure API timeout (default 5 seconds)
5. Set maximum zone runtime (default 3600 seconds)

### Device Configuration

1. Create a new device: **Devices → New → Type: Netro Smart Sprinkler**
2. Enter the controller serial number (found on the physical device)
3. The plugin will automatically discover zones and configuration

### Finding Your Serial Number

Your Netro controller serial number is:
- Printed on the physical device (12 hex characters)
- Available in the Netro mobile app (Settings → Device Info)
- Format: `0cb8152f9f78` (example)

## Usage Examples

### Indigo Actions

**Start a Zone**:
```python
# Start zone 1 for 10 minutes
indigo.sprinkler.setZone(dev, zoneIndex=1, duration=10)
```

**Set Rain Delay**:
```
# Use plugin action "Set Rain Delay"
# Specify number of days (1-100)
```

**Report Weather** (v2.0+):
```
# Use plugin action "Report Weather to Netro"
# Send current temperature, humidity, precipitation
```

**Start Zone with Delay** (v2.0+):
```
# Use plugin action "Start Zone with Delay"
# Zone will start after specified delay (0-60 minutes)
```

### Indigo Triggers

Available triggers:
- Zone start failed
- Stop failed
- Rate limit exceeded
- Set rain delay failed
- Set standby failed

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
| `token_remaining` | API calls remaining today | `1847` of 2000 |
| `moisture_1` through `moisture_12` | Zone moisture % | `45` |

## API Rate Limits

The Netro API allows **2000 calls per day**. The plugin manages this automatically:

- Default polling: Every 3 minutes = ~480 calls/day
- Rate limit warnings when <200 calls remaining
- Automatic 61-minute backoff on HTTP 429
- Token count visible in `token_remaining` state

**Tip**: If you approach the limit, increase the polling interval in plugin config.

## Development Setup

### Prerequisites

- macOS with Indigo 2023.2+
- Python 3.10+
- Git
- A Netro controller for testing

### Clone and Setup

```bash
# Clone the repository
git clone https://github.com/simons-plugins/netro-indigo.git
cd netro-indigo

# Install development dependencies
pip3 install pytest pytest-cov pytest-mock pylint requests python-dateutil

# Run tests to verify setup
pytest tests/
```

### Project Structure

```
netro/
├── Netro Sprinklers.indigoPlugin/     # Plugin bundle
│   ├── Contents/
│   │   ├── Info.plist                  # Plugin metadata
│   │   └── Server Plugin/
│   │       ├── plugin.py               # Main plugin code (1,194 lines)
│   │       ├── Devices.xml             # Device definitions
│   │       ├── Actions.xml             # Action definitions
│   │       ├── PluginConfig.xml        # Plugin configuration UI
│   │       └── requirements.txt        # Python dependencies
├── tests/                              # Test suite (64 tests)
│   ├── conftest.py                     # Pytest fixtures
│   ├── test_api_client.py              # API tests (17)
│   ├── test_validation.py              # Validation tests (24)
│   └── test_actions.py                 # Action tests (23)
├── CLAUDE.md                           # Architecture documentation
├── TESTING.md                          # Testing guide
├── TROUBLESHOOTING.md                  # User troubleshooting
├── API_NOTES.md                        # API quirks and discoveries
├── NETRO_API.md                        # Complete API reference
└── README.md                           # This file
```

### Making Changes

1. **Create a branch**:
   ```bash
   git checkout -b feature/my-improvement
   ```

2. **Make your changes** to `plugin.py`

3. **Test your changes**:
   ```bash
   # Run automated tests
   pytest tests/ -v

   # Check code quality
   python3 -m pylint plugin.py --max-line-length=120

   # Test with real hardware (see TESTING.md)
   python3 test_local_api.py --serial YOUR_SERIAL
   ```

4. **Install in Indigo** for testing:
   ```bash
   # Copy to Indigo plugins folder
   cp -r "Netro Sprinklers.indigoPlugin" \
     "/Library/Application Support/Perceptive Automation/Indigo 2023.2/Plugins/"

   # Restart plugin in Indigo
   # Plugins → Netro Smart Sprinklers → Reload
   ```

5. **Commit your changes**:
   ```bash
   git add .
   git commit -m "Description of changes"
   git push origin feature/my-improvement
   ```

6. **Create a Pull Request** on GitHub

## Testing

The plugin has comprehensive test coverage (>70%) with 64 automated tests.

### Run All Tests

```bash
cd netro
pytest tests/
```

### Run Specific Test Categories

```bash
# API client tests (17 tests)
pytest tests/test_api_client.py

# Validation tests (24 tests)
pytest tests/test_validation.py

# Action tests (23 tests)
pytest tests/test_actions.py
```

### Run with Coverage

```bash
pytest tests/ --cov --cov-report=html
open htmlcov/index.html
```

### Test Against Real Hardware

```bash
# Interactive testing with your actual controller
python3 test_local_api.py --serial YOUR_SERIAL

# Run specific API tests
python3 test_local_api.py --serial YOUR_SERIAL --test info
python3 test_local_api.py --serial YOUR_SERIAL --test schedules
```

See [TESTING.md](TESTING.md) for complete testing documentation.

## Code Quality

This plugin maintains high code quality standards:

- **Pylint Score**: 9.36/10
- **Test Coverage**: >70%
- **Documentation**: 100% of methods have docstrings
- **Type Safety**: Critical methods use type hints
- **Error Handling**: Comprehensive with actionable messages

### Run Quality Checks

```bash
# Pylint check
python3 -m pylint plugin.py --max-line-length=120

# Verify no syntax errors
python3 -m py_compile plugin.py
```

## Documentation

- **[CLAUDE.md](CLAUDE.md)** - Complete architecture documentation
- **[TESTING.md](TESTING.md)** - How to run and write tests
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Common issues and solutions
- **[API_NOTES.md](API_NOTES.md)** - Netro API quirks and discoveries
- **[NETRO_API.md](NETRO_API.md)** - Complete API endpoint reference
- **[DEPENDENCY_MIGRATION_GUIDE.md](DEPENDENCY_MIGRATION_GUIDE.md)** - Dependency management

## Troubleshooting

### Plugin Won't Load

1. Check Event Log for errors
2. Verify Python dependencies installed: `pip3 show requests`
3. Check serial number format (12 hex characters)
4. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

### API Rate Limiting

**Symptom**: "API calls have violated rate limit" in logs

**Solution**:
- Increase polling interval in plugin config
- Current usage visible in `token_remaining` state
- Limit resets daily at midnight UTC

### Controller Shows Offline

**Possible causes**:
- Controller actually offline (unplugged, no internet)
- Network issues between controller and Netro cloud
- API temporarily unavailable

**Note**: Netro API can be slow to report offline status (30+ minutes)

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for complete troubleshooting guide.

## Contributing

Contributions are welcome! Please:

1. Read the [development setup](#development-setup) guide
2. Review [CLAUDE.md](CLAUDE.md) for architecture details
3. Write tests for new features (see [TESTING.md](TESTING.md))
4. Ensure pylint score remains >8.0
5. Update documentation as needed
6. Create a pull request with clear description

## Version History

### v2.0.0 (2026-01-28)
- **Complete overhaul** - Transformed from basic integration to production-quality plugin
- **New Features**: Delayed watering, weather reporting, next schedule info, schedule types
- **Quality**: Pylint 9.36/10, 64 tests (>70% coverage), full documentation
- **Bug Fixes**: Fixed 20+ bugs including uninitialized variables, API issues, state management
- **API**: Consolidated to requests library, enhanced error handling, proper throttling
- **Docs**: Added TESTING.md, TROUBLESHOOTING.md, API_NOTES.md, complete docstrings

See [Pull Request #5](https://github.com/simons-plugins/netro-indigo/pull/5) for complete details.

### v1.x (Historical)
- Basic zone control and status monitoring
- Original Rachio-based implementation

## License

Copyright (c) 2014-2026, Perceptive Automation, LLC. All rights reserved.

## Support

- **Issues**: [GitHub Issues](https://github.com/simons-plugins/netro-indigo/issues)
- **Forum**: [Indigo Plugin Forum](https://forums.indigodomo.com)
- **Email**: Support via GitHub issues preferred

## Credits

- **Author**: Simon's Plugins
- **Platform**: Indigo Home Automation by Perceptive Automation
- **API**: Netro Public API v1
- **Co-Authored-By**: Claude Sonnet 4.5 (v2.0 development)

## Related Links

- [Netro Official Website](https://netrohome.com)
- [Netro API Documentation](https://api.netrohome.com)
- [Indigo Home Automation](https://www.indigodomo.com)
- [Indigo Plugin Developer Guide](https://www.indigodomo.com/docs/plugin_guide)
