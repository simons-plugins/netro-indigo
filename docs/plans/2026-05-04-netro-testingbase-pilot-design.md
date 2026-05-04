# Netro TestingBase pilot — design

**Date:** 2026-05-04
**Status:** Approved (awaiting implementation plan)

## Context

Indigo 2025.2 ships [`TestingBase`](https://github.com/IndigoDomotics/TestingBase) — a shared submodule for live HTTP integration tests against a running Indigo server. The framework provides `APIBase` (a `unittest.TestCase` subclass that opens an `httpx` session to Indigo's HTTP API) and `ValidateXmlFile` (offline schema validation for plugin XML files).

The workspace's existing test pattern is `unittest.mock`-based pytest tests against in-process plugin code (Pattern A — see `netro/tests/conftest.py` for the canonical example). TestingBase introduces a complementary pattern (Pattern B) that exercises the live runtime.

This pilot adopts Pattern B in netro as a learning vehicle for workspace-wide adoption. **Intent: full adoption signal.** Once the pilot lands successfully, the pattern rolls out to other production-critical plugins (`heatmiser`, `home-intelligence`, `UK-Trains`) and the workspace `CLAUDE.md` is updated to make TestingBase the standard for live integration tests.

## Goal

Stand up TestingBase in netro using the upstream-strict layout, exercise both halves of the framework end-to-end against local Indigo 2025.2, and capture the friction so we know what we're signing up for at scale.

## Approach

**Two-venv layout, upstream-strict.** Pattern A continues to use netro's main pyproject.toml env. TestingBase tests live in `tests/integration/` and run from a separate `tests/venv/` populated from `tests/testing-requirements.txt`. This matches the convention used in IndigoDomotics' own repos and is the only layout that works uniformly across all workspace plugins (most don't have pyproject.toml).

**Live test = plugin-load smoke.** One `APIBase` test that fetches Indigo's plugin list and asserts netro is loaded and enabled. Exercises auth, connectivity, and plugin discovery in a single call — no netro hardware or device fixtures required.

**XML validation = full coverage.** All five netro XML files (`Actions.xml`, `Devices.xml`, `Events.xml`, `MenuItems.xml`, `PluginConfig.xml`) get a `ValidateXmlFile` subclass. These are pure offline schema checks — they don't need Indigo running.

## Architecture

```
netro/
├── tests/                                    # existing — Pattern A (13 tests)
│   ├── conftest.py
│   ├── test_*.py × 13
│   ├── shared/                               # NEW — TestingBase submodule
│   ├── .env                                  # NEW — gitignored, real creds
│   ├── .env.example                          # NEW — committed template
│   ├── testing-requirements.txt              # NEW — chains to shared/module-requirements.txt
│   ├── venv/                                 # NEW — gitignored, separate venv
│   └── integration/                          # NEW — TestingBase test files
│       ├── __init__.py
│       ├── test_xml_validation.py            # 5× ValidateXmlFile classes
│       └── test_indigo_smoke.py              # 1× APIBase smoke test
├── pyproject.toml                            # unchanged — main env stays for Pattern A
└── .gitignore                                # add tests/.env, tests/venv/
```

## Components

### `tests/shared/` (submodule)

Pinned to `IndigoDomotics/TestingBase@main`. Read-only — never edited locally. Per upstream's explicit warning, contributors needing changes go through upstream.

### `tests/testing-requirements.txt`

```
-r shared/module-requirements.txt
```

Nothing else for the pilot. Future tests can add deps below this line.

### `tests/.env.example`

Committed template, mirrors upstream `ENV_TEMPLATE`. Real values go in `tests/.env` (gitignored). Key variables:

```
shared.GOOD_API_KEY=<your-Indigo-API-key>
shared.URL_PREFIX=https://localhost:8176
shared.API_PREFIX=/v2/api
shared.PLUGIN_ID=com.simons-plugins.netro
shared.LOGGING_LEVEL=logging.INFO
shared.PLUGIN_RESTART_WAIT_TIME=5
shared.PAUSE_AFTER_UPDATE=0.0
shared.RESTART_IN_DEBUGGER=false
```

### `tests/integration/test_xml_validation.py`

Five classes, one per XML file. Each subclasses `ValidateXmlFile, APIBase` (in that MRO order — upstream is explicit). `server_plugin_dir_path` resolved relatively:

```python
import os
from shared import APIBase, ValidateXmlFile

PLUGIN_ROOT = os.path.abspath(os.path.join(
    os.path.dirname(__file__),
    "../../Netro Sprinklers.indigoPlugin/Contents/Server Plugin",
))

class TestActionsXml(ValidateXmlFile, APIBase):
    server_plugin_dir_path = PLUGIN_ROOT
    file_name = "Actions.xml"
```

(Repeat for Devices.xml, Events.xml, MenuItems.xml, PluginConfig.xml.)

### `tests/integration/test_indigo_smoke.py`

One class, one test:

```python
from shared import APIBase

class TestNetroPluginLoaded(APIBase):
    def test_plugin_is_loaded_and_enabled(self):
        # Fetch Indigo's plugin list and assert netro is present + enabled.
        # Uses APIBase's send_simple_command / get_indigo_object helpers
        # against the URL_PREFIX from .env.
        ...
```

Exact API call resolved during implementation — `APIBase` wraps Indigo's HTTP API and the upstream README hints at `send_simple_command` for plugin-level interactions.

## Data flow

1. Developer activates the pilot venv: `source tests/venv/bin/activate`.
2. Runs `pytest tests/integration/`.
3. Pytest auto-discovers `unittest.TestCase` subclasses (TestingBase classes).
4. Each test class's `__init__` (inherited from `APIBase`) loads `tests/.env` via `python-dotenv`.
5. `ValidateXmlFile` tests read the XML file from disk and validate the schema. No network.
6. `APIBase` smoke test opens an `httpx` session to `https://localhost:8176/v2/api`, fetches the plugin list, asserts.

## Error handling

- **Submodule not initialized**: `from shared import APIBase` fails at import. Fix: `git submodule update --init`. Documented in `tests/integration/__init__.py` and a future `tests/README.md`.
- **Missing `tests/.env`**: TestingBase fails fast at setUp with a clear error (per upstream).
- **Wrong API key / Indigo not running**: smoke test fails with HTTP error in setUp; XML validation tests still pass (they don't touch Indigo).
- **netro plugin not loaded**: smoke test asserts `loaded=true` and fails informatively.

## Testing the pilot

- All 13 existing Pattern A tests must continue to pass via main env: `pytest tests/` (with `tests/integration/` excluded by pyproject.toml's pytest config).
- New integration tests pass against local Indigo 2025.2: `source tests/venv/bin/activate && pytest tests/integration/` shows 6/6 green (5 XML + 1 smoke).
- `git submodule status` shows `tests/shared` initialised and pinned.
- `tests/.env.example` is committed; `tests/.env` is not.

## Out of scope

- **CI integration** — deferred. Pilot establishes the local pattern. CI access to Indigo (or a running Indigo in CI) is a follow-up.
- **More than one APIBase test** — the framework smoke is enough to validate the integration. Substantive netro-specific live tests (device states, action invocation) come after rollout.
- **Migrating Pattern A tests** — Pattern A and B do different things. They coexist; nothing migrates.
- **Workspace rollout** — separate work after this pilot lands and we know it works.

## Open verification questions for implementation

- Does TestingBase's `APIBase` work on a fresh Indigo 2025.2 with a new API key issued via Indigo's preferences? (Probably yes — verifying this is part of the pilot's value.)
- What's the exact `send_*` call to fetch the plugin list and assert load state? Resolved by reading `shared/classes.py` once the submodule is in.

## Success criteria

- 6/6 integration tests green against local Indigo 2025.2.
- 13/13 Pattern A tests still green.
- Design and resulting friction documented well enough to inform workspace rollout.
- PR opened, reviewed, merged.
