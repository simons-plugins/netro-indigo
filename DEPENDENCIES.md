# Package Dependencies Management

This document explains how the Netro Sprinklers plugin manages Python package dependencies.

## Approach: Bundled Packages

The plugin follows **Indigo best practices** by bundling all third-party packages inside the plugin bundle.

**Why bundle packages?**
- ✅ Plugin is self-contained and portable
- ✅ No dependency on system Python packages
- ✅ Consistent behavior across all user installations
- ✅ Users don't need to install anything manually
- ✅ Packages can't be accidentally removed or upgraded

**Source**: [Indigo SDK Documentation](Indigo%20SDK/docs/getting-started/README.md)
> "Ensure all required packages are in `Contents/Packages/`"
> "Don't use system Python packages - bundle them with plugin"

## Bundled Packages

Located in: `Netro Sprinklers.indigoPlugin/Contents/Packages/`

### Primary Dependency

- **requests** (2.32.5) - HTTP client for Netro API communication

### Transitive Dependencies

Automatically included with requests:
- **certifi** (2026.1.4) - SSL certificate verification
- **charset_normalizer** (3.4.4) - Character encoding detection
- **idna** (3.11) - Internationalized domain names support
- **urllib3** (2.6.3) - HTTP connection pooling

**Total size**: ~3.3 MB

## Verification System

The plugin includes automatic verification that bundled packages are available:

### requirements.py

[requirements.py](netro/Netro%20Sprinklers.indigoPlugin/Contents/Server%20Plugin/requirements.py) provides:

1. **verify_bundled_packages(plugin_id)** - Checks packages can be imported
2. **get_package_info()** - Returns package versions for debugging

### Automatic Check

The verification runs automatically in `Plugin.__init__()`:

```python
# plugin.py line 83-84
# Verify bundled packages are available
requirements.verify_bundled_packages(pluginId)
```

If packages are missing, the plugin will:
- Refuse to start
- Display helpful error message
- Provide fix instructions

## Installation

Packages are already bundled in the plugin. **Users don't need to do anything.**

## Updating Packages

For plugin developers:

### Update All Packages

```bash
cd "/path/to/Netro Sprinklers.indigoPlugin/Contents"

# Remove old packages
rm -rf Packages/*

# Install fresh copies
pip3 install --target Packages -r ../../requirements.txt

# Clean up unnecessary files
cd Packages
rm -rf *.dist-info bin/
```

### Update Single Package

```bash
pip3 install --target "Netro Sprinklers.indigoPlugin/Contents/Packages" --upgrade requests
cd "Netro Sprinklers.indigoPlugin/Contents/Packages"
rm -rf *.dist-info bin/
```

### Verify Installation

```bash
# Check package sizes
du -sh "Netro Sprinklers.indigoPlugin/Contents/Packages/"

# List bundled packages
ls -la "Netro Sprinklers.indigoPlugin/Contents/Packages/"
```

## Development Dependencies

Not bundled with plugin (install separately for development):

```bash
# Install from requirements.txt
pip3 install pytest pytest-cov pytest-mock

# Or install just testing tools
pip3 install -r requirements.txt
```

## Comparison with Other Approaches

### ❌ System Package Approach (UK-Trains plugin)

**How it works**:
- Checks if packages are installed in system Python
- Prompts user to install if missing
- Uses `pip install <package>`

**Drawbacks**:
- Relies on user's Python environment
- Different users may have different versions
- System packages can be removed/upgraded
- Plugin breaks if system Python changes

### ✅ Bundled Package Approach (Netro plugin)

**How it works**:
- Packages bundled inside plugin
- Verified at plugin startup
- No user action required

**Benefits**:
- Works out of the box
- Consistent across all installations
- Immune to system changes
- True "install and forget"

## Troubleshooting

### ImportError on Plugin Load

**Error**: `ImportError: No module named 'requests'`

**Cause**: Bundled packages missing or corrupted

**Fix**:
1. Reinstall plugin from clean copy
2. Or manually reinstall packages:
   ```bash
   pip3 install --target "Netro Sprinklers.indigoPlugin/Contents/Packages" requests
   cd "Netro Sprinklers.indigoPlugin/Contents/Packages"
   rm -rf *.dist-info bin/
   ```
3. Reload plugin in Indigo

### Wrong Package Version

**Error**: Plugin requires newer version

**Fix**: Update bundled packages (see "Updating Packages" above)

### Packages Directory Missing

**Error**: `ImportError: ... packages are missing!`

**Fix**:
1. Verify `Contents/Packages/` directory exists
2. Reinstall packages
3. Check file permissions

## Files

- **[requirements.py](netro/Netro%20Sprinklers.indigoPlugin/Contents/Server%20Plugin/requirements.py)** - Verification system
- **[requirements.txt](netro/requirements.txt)** - Package list with versions
- **[Contents/Packages/](netro/Netro%20Sprinklers.indigoPlugin/Contents/Packages/)** - Bundled packages
- **[Contents/Packages/README.md](netro/Netro%20Sprinklers.indigoPlugin/Contents/Packages/README.md)** - Bundled packages documentation

## References

- [Indigo SDK - Getting Started](Indigo%20SDK/docs/getting-started/README.md)
- [Indigo SDK - Troubleshooting](Indigo%20SDK/docs/troubleshooting/common-issues.md)
- [Example Action API Plugin](Indigo%20SDK/IndigoSDK-2025.1/Example%20Action%20API.indigoPlugin/) - Reference implementation
