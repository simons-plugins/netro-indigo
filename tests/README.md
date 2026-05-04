# Netro tests

Two test patterns coexist here.

## Pattern A — pytest with mocked Indigo (default, runs in CI)

`unittest.mock`-based tests in `tests/test_*.py`. Run from netro's main env:

```bash
pytest tests/
```

Fast, no Indigo runtime. The repo's main `pytest.ini` covers this layer
(coverage flags, markers, etc.).

`tests/integration/`, `tests/shared/`, and `tests/venv/` are excluded from
discovery via `norecursedirs` in both `pytest.ini` and `pyproject.toml`.

## Pattern B — TestingBase live integration

Lives in `tests/integration/` and uses the [TestingBase submodule](https://github.com/IndigoDomotics/TestingBase)
at `tests/shared/`. Tests subclass `APIBase` (`unittest.TestCase` + `httpx`)
and exercise a running Indigo server. **Requires Indigo installed locally**
— `APIBase.setUpClass` spawns `/usr/local/indigo/indigo-host` to read the
install path, so tests can only run on a developer machine with Indigo
present (not in CI without an Indigo install).

### One-time setup

```bash
git submodule update --init                          # if you cloned without --recurse-submodules
/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 -m venv tests/venv
source tests/venv/bin/activate
pip install -r tests/testing-requirements.txt       # installs httpx + python-dotenv + pytest
cp tests/.env.example tests/.env
# edit tests/.env, set shared.GOOD_API_KEY to a real Indigo API key
# (Indigo Server menu → "API Keys…" → New API Key)
```

### Running

```bash
source tests/venv/bin/activate
cd tests
pytest integration/                                 # picks up tests/integration/pytest.ini
```

`tests/integration/pytest.ini` makes the integration directory its own
pytest rootdir. That isolates this suite from the main `pytest.ini`'s
coverage flags (which require `pytest-cov`, which the integration venv
deliberately doesn't install — coverage of TestingBase tests against live
Indigo isn't meaningful).

### What's tested

- `tests/integration/test_xml_validation.py` — 5 `ValidateXmlFile` classes
  covering Actions.xml, Devices.xml, Events.xml, MenuItems.xml,
  PluginConfig.xml. Schema validation only; no Indigo runtime needed for
  the validation itself, but `APIBase.setUpClass` still runs (it reads
  the Indigo install folder).
- `tests/integration/test_indigo_smoke.py` — one `APIBase` test asserting
  `com.simons-plugins.netro` appears in Indigo's plugin list and is
  enabled. If your Indigo 2025.2 plugin object uses a different field
  name than `enabled`, the assertion message will dump the full plugin
  dict so you can adjust the test.

### Updating TestingBase

The submodule tracks upstream `main`. Pull changes with:

```bash
git submodule update --recursive --remote tests/shared
```

Per upstream's README, never edit `tests/shared/` locally. File issues
upstream at https://github.com/IndigoDomotics/TestingBase if you need
changes.
