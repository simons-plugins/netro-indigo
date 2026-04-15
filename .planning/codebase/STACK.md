# STACK.md — Netro Sprinklers Plugin

## Runtime Environment

- **Python**: 3.10+ (Indigo 2023+ requirement). Dev machine runs Python 3.11.6.
  - Interpreter: `/Library/Frameworks/Python.framework/Versions/Current/bin/python3`
  - All code uses f-strings, `match`-compatible syntax, `typing.Final`, `dataclasses`
- **Platform**: macOS (Indigo runs as a macOS daemon)
- **Indigo SDK**: ServerApiVersion `3.6` (declared in
  `Netro Sprinklers.indigoPlugin/Contents/Info.plist`)
  - Plugin inherits from `indigo.PluginBase`
  - Indigo object model accessed via the `indigo` module (injected at runtime)
  - `indigo` is NOT importable outside Indigo runtime — tests must mock it

## Plugin Identity

- **CFBundleIdentifier**: `com.simons-plugins.netro`
- **PluginVersion**: `2026.4.0` (format: `YYYY.R.patch`)
- **CFBundleDisplayName**: Netro Smart Sprinklers

## Runtime Dependencies

Declared in
`Netro Sprinklers.indigoPlugin/Contents/Server Plugin/requirements.txt`:

```
requests==2.32.5
```

Indigo auto-installs packages from `requirements.txt` when the plugin loads.
No `Contents/Packages/` bundle directory is used — `requests` is installed
to the system Python by Indigo's package manager.

## Development Dependencies

Declared in `pyproject.toml` (not `requirements.txt` — kept separate):

```
pytest>=7.4
pytest-cov>=4.1
pytest-mock>=3.12
```

Install manually:
```bash
pip3 install pytest pytest-cov pytest-mock requests
```

## Linting

Configured via `pyproject.toml`:

- **Tool**: `pylint`
- **Target score**: 9.0 (`fail-under = 9.0`)
- **Max line length**: 120
- **py-version**: 3.10
- **Disabled rules** (Indigo-specific exceptions):
  - `too-many-lines` — single-file plugin pattern
  - `too-many-public-methods` — required by Indigo callback API
  - `invalid-name` — Indigo requires camelCase callbacks
- **Method name regex**: `[a-z_][a-zA-Z0-9_]{2,}$` (allows Indigo camelCase)
- **Run**: `python3 -m pylint plugin.py --max-line-length=120`
- **Ignore paths**: `tests/`, `__pycache__/`

## Test Runner

- **Tool**: `pytest`
- **Config**: `pytest.ini` (root) + `pyproject.toml` `[tool.pytest.ini_options]`
- **Test paths**: `tests/`
- **File pattern**: `test_*.py`
- **Coverage**: `pytest-cov` generates HTML to `htmlcov/`
- **Total tests**: 427 collected (as of April 2026)
- **Run**:
  ```bash
  pytest tests/
  pytest tests/ --cov --cov-report=html
  ```

## Module Layout (Server Plugin)

All Python lives in
`Netro Sprinklers.indigoPlugin/Contents/Server Plugin/`:

| File | Purpose |
|------|---------|
| `plugin.py` | Main `Plugin(indigo.PluginBase)` class, ~1900 lines |
| `api_client.py` | `NetroAPIClient` — HTTP + throttle management |
| `device_handlers.py` | `SprinklerHandler`, `WhispererHandler`, `ZoneHandler` |
| `validators.py` | Pure validation functions for ConfigUi callbacks |
| `constants.py` | All URL constants, defaults, thresholds |
| `exceptions.py` | `NetroError` hierarchy |
| `utils.py` | Unit conversion helpers |
| `tomorrow_client.py` | Tomorrow.io weather API client |

## CI / Release

- **Version check**: CI fails if `Info.plist` `PluginVersion` already exists as a git tag
- **Release**: `create-release` workflow auto-creates a GitHub Release with a `.zip`
  bundle on merge to `main`
- **Repo**: https://github.com/simons-plugins/netro-indigo
