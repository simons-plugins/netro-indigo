# Whisperer ↔ Zone pairing — design

**Issue:** [#54](https://github.com/simons-plugins/netro-indigo/issues/54)
**Date:** 2026-04-23
**Status:** Accepted

## Problem

Netro's `/moistures.json` returns a **smart-model daily prediction** for each
zone — not the paired Whisperer's sensor reading. The Netro mobile app
overlays the Whisperer reading on the zone tile when one is paired; the
public API does not. Result: the Indigo plugin's zone `moisture` state can
diverge dramatically from a paired Whisperer's actual reading (observed:
zone 89% vs Whisperer 24% on the same zone, same moment).

The plugin already reads both values correctly, but they land on separate
Indigo devices with no linkage, so control pages, triggers, and schedules
keyed on zone `moisture` use the forecast, not the sensor.

## Goals

1. Let the user explicitly pair a Whisperer device to a zone device in the
   plugin (no auto-matching).
2. When paired and the Whisperer reading is fresh, zone `moisture` reflects
   the real sensor.
3. Keep the Netro forecast observable alongside (for comparison, schedule
   tuning, and transparent fallback when the sensor goes stale).
4. No Netro API changes — pairing lives entirely in plugin-side state.

## Non-goals

- Auto-pairing by zone/Whisperer name similarity.
- Pairing multiple Whisperers to one zone.
- Writing sensor data back to Netro (we already expose a `set_moisture`
  action; that's unchanged).

## Architecture & data flow

### State model

On the zone device:

- `moisture` (existing, semantics change) — "best available" reading:
  Whisperer if paired and fresh, else the Netro forecast.
- `moistureForecast` (new) — always Netro's `/moistures.json` daily
  prediction. Exposes the prediction even when a Whisperer overrides
  `moisture`, so the user can compare model vs reality and tune schedules.

A new pluginProp on the zone device:

- `linkedWhispererDeviceId` — string holding the Indigo device ID of the
  paired Whisperer, or empty string (= unpaired). Set via a new dropdown
  in the zone ConfigUI.

### Update flow (per zone, on every zone-update cycle)

```
1. Build states from info + schedule data (unchanged).
2. If moistures_response is available:
     forecast_val = ZoneHandler.process_zone_moisture(...)
     write moistureForecast = forecast_val
   Else:
     forecast_val = None  (don't overwrite moistureForecast this cycle)
3. moisture_val, source = _resolve_zone_moisture(zone_dev, forecast_val):
     - No pairing / device missing / disabled  → forecast_val, "forecast"
     - Paired, fresh (age ≤ 12h)                → Whisperer.soilMoisture, "whisperer"
     - Paired, stale (age > 12h)                → forecast_val, "forecast-stale"
4. If moisture_val is not None:
     write moisture = moisture_val, uiValue = "N%"
5. replaceOnServer (unchanged batch write).
```

The Whisperer update loop is unchanged — it still writes only its own
device states. No cross-device writes. The zone loop pulls Whisperer
state out of Indigo's device DB when it runs.

### Design decisions

| Decision | Choice | Reason |
|---|---|---|
| Fallback when paired-but-stale | Fall back to `moistureForecast` | Matches the Netro app's behavior: if the sensor is gone, schedules use the prediction. User can also unpair on the Netro side to force prediction-only mode. |
| Staleness threshold | 12 hours, hardcoded | Whisperers report every 1–6h depending on battery. 12h = 2–12 missed readings, survives brief outages but catches a dead battery within a day. |
| Who writes `moisture` | Zone update loop pulls from Whisperer device | Single writer, staleness logic in one place. Up to ~10min lag — irrelevant for soil moisture. |
| ConfigUI layout | Separator + section label + dropdown + help text | Matches existing style (Whisperer's `sep_api` pattern). |
| Auto-pair by name | No | Explicit config only — prevents brittle matching and silent surprises. |

### Netro-side pairing (open empirical question)

The issue's investigation showed `/moistures.json` returning a
saturation-based prediction (89%) while a working paired Whisperer read
24% at the same moment — suggesting Netro's prediction is independent of
Whisperer pairing on Netro's side. We rely on this: when a Whisperer is
paired in Netro but stops reporting (dead battery, unplugged), we assume
`/moistures.json` keeps producing useful predictions. This should be
dogfooded for a week with a physically disconnected Whisperer before
shipping broadly. Documented in `API_NOTES.md`.

User workflow if a Whisperer dies: either leave it in place (our 12h
fallback takes over after the last reading ages out), or unpair in the
Netro app to force Netro-side prediction-only mode. Our plugin-side
pairing is separate from Netro-side pairing — both can coexist.

## Code changes

### `Devices.xml` — zone device (around line 297)

Add a new visible section to `<ConfigUI>`:

```xml
<Field id="sep_sensor" type="separator"/>
<Field id="sensorLabel" type="label">
    <Label>Soil Moisture Source</Label>
</Field>
<Field id="linkedWhispererDeviceId" type="menu" defaultValue="">
    <Label>Paired Whisperer:</Label>
    <List class="self" method="getWhispererDevices" dynamicReload="true"/>
</Field>
<Field id="sensorHelp" type="label" fontSize="small" fontColor="darkgray"
       alignWithControl="true">
    <Label>When paired, the zone's moisture state mirrors the Whisperer's
    soil reading (if fresh within 12 hours). Otherwise, it shows Netro's
    daily forecast. The forecast is always available separately as
    "moistureForecast".</Label>
</Field>
```

Add a new state:

```xml
<State id="moistureForecast">
    <ValueType>Integer</ValueType>
    <TriggerLabel>Moisture Forecast (%)</TriggerLabel>
    <ControlPageLabel>Moisture Forecast (%)</ControlPageLabel>
</State>
```

`<UiDisplayStateId>moisture</UiDisplayStateId>` unchanged — zone tiles keep
showing the "best available" value, which is the right default.

### `plugin.py` — new dynamic list callback

```python
def getWhispererDevices(self, filter="", valuesDict=None, typeId="", targetId=0):
    """Populate linkedWhispererDeviceId dropdown on zone ConfigUI."""
    options = [("", "(Unpaired — use Netro forecast)")]
    whisperers = sorted(
        (d for d in indigo.devices.iter(filter="self")
         if d.deviceTypeId == "Whisperer"),
        key=lambda d: d.name.lower(),
    )
    options.extend((str(d.id), d.name) for d in whisperers)
    return options
```

### `plugin.py` — new helper `_resolve_zone_moisture`

```python
def _resolve_zone_moisture(self, zone_dev, forecast_val):
    """Resolve the "moisture" state value for a zone device.

    Returns (value_or_none, source_tag) where source_tag is one of:
        "forecast", "whisperer", "forecast-stale",
        "forecast-missing-device", "forecast-disabled-device".
    """
    linked_id = zone_dev.pluginProps.get("linkedWhispererDeviceId", "")
    if not linked_id:
        return forecast_val, "forecast"

    try:
        whisperer = indigo.devices[int(linked_id)]
    except (KeyError, ValueError):
        return forecast_val, "forecast-missing-device"

    if not whisperer.enabled:
        return forecast_val, "forecast-disabled-device"

    soil = whisperer.states.get("soilMoisture")
    reading_time = whisperer.states.get("readingLocalTime", "")
    age_hours = _parse_reading_age_hours(reading_time)  # util helper
    if soil is None or age_hours is None or age_hours > WHISPERER_STALENESS_HOURS:
        return forecast_val, "forecast-stale"

    return int(soil), "whisperer"
```

### `plugin.py` — `_update_zone_devices` call site

After the existing moisture-response handling, rename the emitted state
key and layer the resolver on top:

```python
forecast_val = None
if moisture_response:
    forecast_states = self.zone_handler.process_zone_moisture(
        moisture_response, zone_num)
    for s in forecast_states:
        if s["key"] == "moisture":
            s["key"] = "moistureForecast"
        forecast_val = s["value"]
    states.extend(forecast_states)

moisture_val, source = self._resolve_zone_moisture(zone_dev, forecast_val)
if moisture_val is not None:
    states.append({"key": "moisture", "value": moisture_val,
                   "uiValue": f"{moisture_val}%"})
    self._log_moisture_source_transition(zone_dev, source)
```

### `plugin.py` — transition-aware logging

To avoid log spam, track the last-logged source on the zone device's
pluginProps (`lastMoistureSource`). Only log on transitions between
source categories:

- `whisperer` → `forecast-stale`: **warning** ("Zone X: Whisperer reading
  stale, falling back to Netro forecast").
- `forecast-stale` → `whisperer`: **info** ("Zone X: Whisperer reading
  recovered").
- `whisperer`/`forecast-*` → `forecast-missing-device` /
  `forecast-disabled-device`: **warning** once.
- All others: no log.

### `constants.py`

```python
WHISPERER_STALENESS_HOURS = 12
```

### `device_handlers.py`

No changes. `ZoneHandler.process_zone_moisture` still emits keys named
`"moisture"`; the rename to `"moistureForecast"` happens at the call site
in `_update_zone_devices`, so the handler's unit tests stay stable.

### `utils.py` (or new helper)

Add `_parse_reading_age_hours(reading_local_time: str) -> float | None`.
Parses the Whisperer `readingLocalTime` format (check existing Whisperer
code for the format) and returns hours-since-now in the appropriate
local timezone. Returns `None` on parse failure → resolver treats as
stale.

### Edge cases handled

- Paired Whisperer device deleted → `KeyError` → forecast + warning.
- Paired Whisperer device disabled → forecast + warning.
- `forecast_val is None` (Netro API error) and Whisperer stale → don't
  write `moisture` this cycle; previous value stays.
- `readingLocalTime` unparseable → treated as stale.
- Zone with a Whisperer paired, then the user manually sets `moisture`
  via the existing "Override moisture" action — that action still calls
  Netro's `set_moisture` API, unrelated to this code path. Next poll
  will re-resolve via the new logic.

## Tests

New module `tests/test_zone_moisture_resolution.py`:

1. Unpaired, forecast available → returns forecast, source="forecast".
2. Unpaired, forecast None → returns (None, "forecast").
3. Paired, Whisperer fresh (age < 12h) → returns Whisperer `soilMoisture`.
4. Paired, Whisperer stale (age > 12h) → returns forecast, warning logged.
5. Paired, Whisperer stale, second call same state → warning NOT re-logged.
6. Paired, transitions fresh → stale → warning logged on transition.
7. Paired, transitions stale → fresh → info log ("sensor recovered").
8. Paired, Whisperer device deleted → forecast, warning logged once.
9. Paired, Whisperer device disabled → forecast, warning logged once.
10. Paired, `readingLocalTime` unparseable → treated as stale.
11. Paired, forecast also None (Netro down) → returns (None, …), no crash.

Extend `tests/test_plugin_zone_updates.py` (or equivalent):

12. E2E: paired fresh Whisperer → zone states include `moisture` (= Whisperer)
    AND `moistureForecast` (= Netro).
13. E2E: unpaired zone → `moisture` == `moistureForecast` == Netro val.
14. E2E: missing `moisture_response` → `moistureForecast` not written,
    `moisture` set from Whisperer if fresh-paired.

New test for `getWhispererDevices`:

15. First entry is `("", "(Unpaired — use Netro forecast)")`, followed
    by sorted Whisperer devices.

Use existing Indigo mock fixtures. Use `freezegun` (or monkeypatched
`datetime.now`) for the 12h age arithmetic. Target 100% branch coverage
on the new helper.

## Documentation

1. **`docs/API_NOTES.md` §6** — replace "can be 12–24 hours old" with a
   clear statement that `/moistures.json` is Netro's **smart-model
   prediction** (post-irrigation saturation + daily decay), not a
   sampled sensor value. Can diverge significantly from a paired
   Whisperer's reading. Reference the new `moistureForecast` state as
   the way to observe the prediction alongside the resolved value.
   Note the open empirical question about Netro-side dead-Whisperer
   behavior.

2. **`README.md`** — small note under the Whisperer section explaining
   the new per-zone pairing dropdown and the `moisture` vs
   `moistureForecast` distinction.

## Migration / backwards compat

- Existing zones with no `linkedWhispererDeviceId` prop →
  `dict.get(..., "")` returns `""` → unpaired path → identical to
  today's behavior.
- First poll after upgrade: `moistureForecast` starts populating.
  `moisture` continues to show forecast until user pairs a Whisperer.
  No data backfill required.
- `<UiDisplayStateId>moisture</UiDisplayStateId>` stays — zone tiles
  keep showing the same "primary" field (now resolved).
- No pluginProps schema migration — Indigo handles missing keys
  gracefully via `.get()`.

## Versioning

User-visible feature (new ConfigUI + new state), so **minor** bump of
`PluginVersion` in `Info.plist`: `YYYY.R.P` → `YYYY.(R+1).0`.

## Acceptance criteria (from issue #54)

- [x] Zone device config has a Whisperer dropdown → Devices.xml +
      `getWhispererDevices` callback.
- [x] When paired (and fresh), zone `moisture` state mirrors Whisperer's
      current reading → `_resolve_zone_moisture`.
- [x] `moistureForecast` state exposes the `/moistures.json` daily value
      → new state + call-site key rename.
- [x] Tests covering paired / unpaired / Whisperer unavailable paths →
      `tests/test_zone_moisture_resolution.py` + E2E extensions.
- [x] `API_NOTES.md` updated → §6 rewrite.
