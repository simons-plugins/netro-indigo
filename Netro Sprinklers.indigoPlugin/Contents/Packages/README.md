# Bundled Python Packages

This directory contains third-party Python packages bundled with the Netro Sprinklers plugin.

## Why Bundle Packages?

Per Indigo best practices:
- Plugins should be **self-contained** and not rely on system Python packages
- Different users may have different Python environments
- System packages can be upgraded/removed independently
- Bundling ensures consistent behavior across all Indigo installations

**Sources**:
- [Getting Started Guide](https://www.indigodomo.com/docs/plugin_guide)
- Indigo SDK documentation: "Don't use system Python packages - bundle them with plugin"

## Bundled Packages

### requests (2.32.5)
**Purpose**: HTTP client library for Netro API communication

**Dependencies** (automatically bundled):
- certifi (2026.1.4) - SSL certificate verification
- charset_normalizer (3.4.4) - Character encoding detection
- idna (3.11) - Internationalized domain name support
- urllib3 (2.6.3) - HTTP connection pooling

## Installation

These packages were installed using:
```bash
pip3 install --target "Contents/Packages" requests
```

Then cleaned up (removed unnecessary files):
```bash
rm -rf *.dist-info bin/
```

## Size

Total size: ~3.3 MB

## Updating

To update packages:
1. Remove old packages: `rm -rf Contents/Packages/*`
2. Reinstall: `pip3 install --target "Contents/Packages" requests`
3. Clean up: `rm -rf Contents/Packages/*.dist-info Contents/Packages/bin`
4. Test plugin loads correctly in Indigo

## Notes

- The `bin/` directory (if present) contains executables and is not needed for the plugin
- The `*.dist-info/` directories contain package metadata and are not needed at runtime
- These are removed to minimize plugin size
