# Technology Stack

**Analysis Date:** 2026-02-01

## Languages

**Primary:**
- Python 3.10+ - Main plugin implementation
- XML - Device types, actions, events, plugin configuration

**Secondary:**
- Plist/XML - Plugin metadata and Info.plist

## Runtime

**Environment:**
- Indigo 2023+ (macOS home automation server)
- Python 3.10+ (managed by Indigo)

**Package Manager:**
- pip (Indigo handles automatic installation)
- Lockfile: `requirements.txt` present

## Frameworks

**Core:**
- Indigo PluginBase 3.6 - Plugin framework, inherits from `indigo.PluginBase`
- requests 2.32.5 - HTTP client for Netro API calls

**Testing:**
- pytest 8.0.0+ - Test framework
- pytest-cov 4.1.0+ - Coverage reporting
- pytest-mock 3.12.0+ - Mocking support

**Build/Dev:**
- pylint - Code quality analysis (target score 8.0)

## Key Dependencies

**Critical:**
- requests 2.32.5 - HTTP client for all Netro API communication
  - Location: `Netro Sprinklers.indigoPlugin/Contents/Server Plugin/requirements.txt`
  - Installed automatically by Indigo on plugin load

**Infrastructure:**
- dateutil - Timezone handling in `plugin.py:47`
  - Used for timestamp conversion from UTC to local timezone
  - Pre-installed with Indigo

**Built-in Libraries:**
- json - JSON parsing for API responses
- copy - Deep copying device dictionaries
- traceback - Exception logging
- datetime - Schedule timestamp handling
- operator - itemgetter for sorting zones

## Configuration

**Environment:**
- Plugin preferences stored in Indigo database
- Device configuration per controller (serial number as unique ID)

**Configuration Files:**
- `Info.plist` - Plugin metadata, version (2025.1.7), API versions
- `PluginConfig.xml` - Plugin-level settings UI (polling interval, timeout, max zone runtime)
- `Devices.xml` - Device type definitions (sprinkler, Whisperer)
- `Actions.xml` - Custom action definitions (rain delay, weather reporting, zone delay)
- `Events.xml` - Trigger event definitions
- `MenuItems.xml` - Plugin menu items (debug toggle, force update)

**Key Configuration Settings:**
- `pollingInterval` - Minutes between API polls (minimum 3, default 3)
- `apiTimeout` - API request timeout in seconds (default 5)
- `maxZoneRunTime` - Maximum zone runtime in seconds (default 3600)
- `showDebugInfo` - Debug logging flag (default false)

## Platform Requirements

**Development:**
- macOS (Indigo runs on macOS only)
- Indigo 2023.2+ installed and running
- Python 3.10+ (provided by Indigo)
- Git (for version control)
- pytest, pytest-cov, pytest-mock (for running tests)

**Production:**
- Indigo 2023.2+ running on macOS
- Active internet connection (required for Netro API)
- Netro controller with known serial number
- Indigo server address in DNS/network configuration

**API Requirements:**
- Netro API base: `http://api.netrohome.com/npa/v1/`
- No additional auth beyond device serial number
- Network access to api.netrohome.com on port 80 (HTTP)

## Build & Deployment

**Plugin Installation:**
```bash
# Copy plugin to Indigo plugins directory
cp -r "Netro Sprinklers.indigoPlugin" "/Library/Application Support/Perceptive Automation/Indigo 2023.2/Plugins/"

# Or disabled plugins for development
cp -r "Netro Sprinklers.indigoPlugin" "/Library/Application Support/Perceptive Automation/Indigo 2023.2/Plugins (Disabled)/"
```

**Testing:**
```bash
# Run all tests with coverage
pytest tests/ --cov="Netro Sprinklers.indigoPlugin/Contents/Server Plugin"

# Generate HTML coverage report
pytest tests/ --cov --cov-report=html
```

**Distribution:**
- Plugin packaged as `.indigoPlugin` bundle (contains Contents directory)
- Distributed via GitHub releases
- Double-click to install in Indigo

---

*Stack analysis: 2026-02-01*
