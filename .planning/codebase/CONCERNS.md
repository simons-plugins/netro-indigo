# CONCERNS.md — Tech Debt, Known Issues, and TODOs

## TODOs in Source

### `plugin.py` — Sprinkler actions not fully wired

```python
# plugin.py line 1562
# TODO: The next sprinkler actions won't currently be called because we haven't
# set the OverrideScheduleActions property. If we wanted to hand off all
# scheduling to the Netro, we would need to use these. However, their current
# API doesn't implement enough required functionality (pause/resume, next/previous
# zone, etc) for us to actually do that at the moment.
```

`RunNewSchedule`, `RunPreviousSchedule`, `PauseSchedule`, `ResumeSchedule`,
`StopSchedule`, `PreviousZone`, and `NextZone` sprinkler actions are silently
ignored (`pass`). This is a Netro API limitation — those operations are not
supported. The comment is correct but could be a confusing no-op for users
who try these actions from the Indigo UI.

## Tech Debt

### `plugin.py` has no test coverage (0%)

The main `Plugin` class cannot be unit-tested because it requires the Indigo
runtime (`import indigo` fails outside the plugin host). The extracted modules
(`api_client.py`, `device_handlers.py`, etc.) are testable, but `plugin.py`
itself is not, meaning the coordination logic is only tested via real Indigo
integration. See `TESTING.md` for coverage breakdown.

### Type hints absent in `plugin.py`

The main plugin file has no type annotations. The extracted modules
(`api_client.py`, `validators.py`, `device_handlers.py`) use full type hints.
The inconsistency makes refactoring harder.

### Pylint disabled rules

Multiple `# pylint: disable=unused-argument` suppressions in `plugin.py` at
lines 1081, 1103, 1122, 1137, 1151, 1304, 1318, 1835, 1911 — these are
Indigo callback signatures that include parameters not used in the
implementation. Correct by convention but noisy.

### `docs/TESTING.md` references non-existent `tests/fixtures/` directory

`docs/TESTING.md` describes JSON fixture files (`info_response.json`, etc.) in
a `tests/fixtures/` directory that does not exist. All fixture data is now
inline in `conftest.py`. The docs are stale but not harmful.

### `test_api_client.py` duplicates `conftest.py` fixtures

`test_api_client.py` defines its own `mock_logger` and `mock_prefs` fixtures
locally instead of using the shared ones from `conftest.py`. This is
redundant and should be cleaned up.

### Legacy `FORECAST_UPDATE_INTERVAL_MINUTES` constant

```python
# constants.py
FORECAST_UPDATE_INTERVAL_MINUTES: Final[int] = 240
"""Default forecast interval (use DEFAULT_FORECAST_INTERVAL_MINUTES instead)."""
```

Kept for backward compatibility but flagged for removal. No other code should
reference it — new code should use `DEFAULT_FORECAST_INTERVAL_MINUTES`.

## Known API Issues and Workarounds

These are Netro API quirks that require ongoing defensive code (documented
fully in `docs/API_NOTES.md`):

1. **Timestamp strings**: V1 API returns numeric timestamps as JSON strings.
   Handled by `float(raw) if isinstance(raw, str) else raw` pattern throughout
   `device_handlers.py`.

2. **`STANDBY` vs `OFFLINE`**: Ambiguous status — the plugin cannot
   definitively distinguish between "controller is on standby" and "controller
   is unreachable". Only `last_active` timestamp can help infer actual offline.

3. **Moisture data is always stale**: Netro updates moisture once per day at
   most. Plugin cannot force a refresh. Users expect real-time data.

4. **Whisperer battery drain**: Sensors reporting every 4-6 hours degrade
   to unreliable intervals when battery is below 20%. Plugin has no way to
   detect this degradation — it just sees fewer readings.

5. **No pause/resume**: Indigo sprinkler device model supports
   `PauseSchedule`/`ResumeSchedule`/`NextZone` but Netro API does not.
   These actions are silently no-ops (see TODO above).

## Rate Limit Risk

At default polling with all endpoints active and Tomorrow.io enabled:

| Source | Calls/day |
|--------|-----------|
| Device info (10 min) | ~144 |
| Schedules (30 min) | ~48 |
| Moistures (10 min) | ~144 |
| Events (5 min, v2) | ~288 |
| Sensor (30 min) | ~48 |
| Weather reports | ~48 (30 min × 1 device) |
| Forecast reports | ~6 × 3 days = 18 |
| Total | ~738 |

Well within the 2,000/day limit for a single device. With multiple controllers
each consuming tokens independently (per-device budget), the total could
multiply. The proactive pause at 100 tokens prevents hard failures.

## Security

- Serial numbers and API keys are stored in `pluginPrefs` (Indigo-managed
  SQLite). Not exposed in logs (plugin is careful about this).
- `.env` file in repo root is gitignored — used for local test secrets only.
- `test_local_api.py` reads `--serial` from CLI args, not hardcoded.
- `docs/API_NOTES.md` includes a real serial number (`0cb8152f9f78`) in the
  "Testing Observations" section — not a security issue (it is the test
  controller serial, not a production device), but worth noting.

## Future Enhancements (from `docs/CLAUDE.md`)

- Multi-controller support in a single plugin instance (currently requires
  separate plugin instances)
- Forecast integration if Netro adds a forecast API
- Historical moisture graphing
- Zone usage statistics
- Webhook support if Netro adds push
- Increase pylint score to 9.0+ (target already set in `pyproject.toml`,
  current status unclear for `plugin.py`)
- Increase test coverage to 85%+
- Add type hints to `plugin.py`
