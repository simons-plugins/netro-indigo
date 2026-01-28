# Package Dependencies Management

This document explains how the Netro Sprinklers plugin manages Python package dependencies.

## Approach: Indigo Automatic Installation

**Indigo automatically handles package installation** from `requirements.txt`. No manual work required - neither for developers nor users.

### How It Works

1. Plugin includes [requirements.txt](netro/requirements.txt) listing required packages
2. When plugin loads, Indigo checks if packages are installed
3. If missing, Indigo automatically installs them
4. Plugin starts with all dependencies available

**User experience**: Install plugin → it just works ✓

## Required Packages

Located in: [requirements.txt](netro/requirements.txt)

```txt
# HTTP client for Netro API
requests==2.32.5
```

That's it! Just list the packages and Indigo does the rest.

## For Plugin Developers

### Adding a New Dependency

1. Add to `requirements.txt`:
   ```txt
   requests==2.32.5
   pillow==10.4.0
   ```

2. That's it! Indigo will install it automatically

### Testing Locally

For local development/testing (outside Indigo):

```bash
# Install dependencies for testing
pip3 install -r requirements.txt

# Run tests
pytest tests/
```

### Version Pinning

Always pin exact versions for consistency:

```txt
# Good - exact version
requests==2.32.5

# Bad - unpinned (version may change)
requests
```

## Why This Approach?

### Previous Approaches (Now Outdated)

**❌ System Package Checker** (UK-Trains old approach):
- Checked if packages installed in system Python
- Prompted user to run `pip install`
- User had to manually install
- Different users could have different versions

**❌ Bundled Packages** (Initial Netro approach):
- Copied packages into `Contents/Packages/`
- Plugin bundle became 3+ MB larger
- Had to maintain bundled copies
- Updates required re-bundling

### ✅ Current Approach: Indigo Automatic

- Plugin just lists requirements
- Indigo handles installation
- Works out of the box
- Always up to date
- Clean and simple

## File Structure

```
Netro Sprinklers.indigoPlugin/
├── Contents/
│   ├── Info.plist
│   └── Server Plugin/
│       ├── plugin.py              # Main plugin code
│       ├── requirements.txt       # Package requirements (ONLY THIS NEEDED)
│       ├── Devices.xml
│       ├── Actions.xml
│       └── ...
└── requirements.txt (symlink)     # For convenience
```

## Troubleshooting

### Package Not Found

**Error**: `ModuleNotFoundError: No module named 'requests'`

**Cause**: Indigo couldn't install package

**Fix**:
1. Check `requirements.txt` exists in `Contents/Server Plugin/`
2. Check package name is spelled correctly
3. Check network connection (Indigo needs to download)
4. Manually install: `pip3 install requests`

### Wrong Version Installed

**Error**: Package version mismatch

**Fix**:
1. Check version pinning in `requirements.txt`
2. Reload plugin to trigger reinstall
3. Or manually: `pip3 install requests==2.32.5`

### Indigo Event Log Shows Install Errors

**Check**:
- Network connectivity
- PyPI availability
- Disk space
- Python environment

## Migration from Old Approaches

### From System Package Checker

**Remove**:
- Custom `requirements.py` verification code
- `requirements_check()` function calls
- `import requirements` from plugin.py

**Keep**:
- `requirements.txt` file
- Package version pins

### From Bundled Packages

**Remove**:
- `Contents/Packages/` directory
- Bundled package copies
- Package installation scripts

**Keep**:
- `requirements.txt` file
- Package version pins

## References

- **Indigo Documentation**: Plugin dependency management (handled automatically)
- **requirements.txt Format**: Standard Python requirements file format
- **PyPI**: Python Package Index (where Indigo downloads packages)

## Summary

**For developers**: Just add package names to `requirements.txt`

**For users**: Nothing - plugin works automatically

**For Indigo**: Handles all installation automatically

Simple, clean, and it just works!
