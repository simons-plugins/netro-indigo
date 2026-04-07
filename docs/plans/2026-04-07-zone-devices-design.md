# Design: Per-Zone Child Devices

**Issue**: simons-plugins/netro-indigo#37
**Date**: 2026-04-07

## Problem

The plugin shows one "next schedule" across the whole controller. Users can't see per-zone schedule details, watering history, or zone-level moisture without digging into raw API data. Additionally, the controller device has 12 hardcoded `zone_N_moisture` states in Devices.xml, which is wrong for both Pixie (1 zone, shows 12) and 16-zone Spark (shows only 12). Devices.xml states are static per device type, so this can't be fixed on the controller.

## Solution

Create a new `zone` custom device type. Each zone on a controller becomes its own Indigo device, auto-created during the parent controller's poll cycle. Remove the hardcoded `zone_N_moisture` states from the controller device.

## Design Decisions

### Device type: `custom` (not `sensor`)

- Sensor devices don't natively support custom actions in Indigo
- Zone devices need a `setZoneMoisture` custom action
- `<UiDisplayStateId>moisture</UiDisplayStateId>` gives the same "65%" display in device lists
- No misleading "Status Request" button (zones can't fetch their own data — the API is per-controller)

### One controller device type (not per-model)

Considered creating model-specific types (Sprint 6, Sprint 12, Spark 8, Spark 16, Pixie, Stream) to get correct zone counts per model. Rejected because zone devices solve this inherently: a Pixie creates 1 zone device, a Spark creates 16. The controller no longer carries per-zone states.

### Watering actions stay on the controller

The Netro `water.json` endpoint is controller-level — it takes a zones array and the controller serial/API key. There is no per-zone watering endpoint. Starting a zone from a zone device would hit the same API as from the controller, risking conflicting commands. All watering actions remain on the controller device.

### Zone moisture variables stay

Zone moisture Indigo variables (`zone_moisture_*` in the "Netro" folder) are an input mechanism, not just display. Users write values to variables via Domio or control pages to set moisture. Zone devices are read-only display. Variables are the write path.

### Variable-to-API auto-link (new)

Instead of requiring users to create triggers to act on variable changes, the plugin subscribes to variable changes via `indigo.variables.subscribeToChanges()`. When a zone moisture variable is updated, `variableUpdated()` looks up the zone, calls `set_moisture` API, and updates the zone device state. No manual trigger setup needed.

## Controller Device Changes

### Removed states

All 12 `zone_N_moisture` states removed from Devices.xml:
- `zone_1_moisture` through `zone_12_moisture`

### Unchanged

All other controller states remain: status, tokens, schedules, model, firmware, standby, etc. All watering actions unchanged. `NumZones` property still set from API response.

## New Zone Device (`zone`)

### Devices.xml

```xml
<Device type="custom" id="zone">
    <Name>Netro Zone</Name>
    <ConfigUI>
        <!-- Hidden fields set during auto-creation -->
        <Field id="parentDeviceId" type="textfield" hidden="true">
            <Label/>
        </Field>
        <Field id="zoneNumber" type="textfield" hidden="true">
            <Label/>
        </Field>
    </ConfigUI>
    <States>
        <State id="moisture">
            <ValueType>Integer</ValueType>
            <TriggerLabel>Moisture Level (%)</TriggerLabel>
            <ControlPageLabel>Moisture Level (%)</ControlPageLabel>
        </State>
        <State id="enabled">
            <ValueType>Boolean</ValueType>
            <TriggerLabel>Zone Enabled</TriggerLabel>
            <ControlPageLabel>Zone Enabled</ControlPageLabel>
        </State>
        <State id="smartMode">
            <ValueType>String</ValueType>
            <TriggerLabel>Smart Mode</TriggerLabel>
            <ControlPageLabel>Smart Mode</ControlPageLabel>
        </State>
        <State id="isIrrigating">
            <ValueType>Boolean</ValueType>
            <TriggerLabel>Currently Irrigating</TriggerLabel>
            <ControlPageLabel>Currently Irrigating</ControlPageLabel>
        </State>
        <State id="lastWateringStart">
            <ValueType>String</ValueType>
            <TriggerLabel>Last Watering Start</TriggerLabel>
            <ControlPageLabel>Last Watering Start</ControlPageLabel>
        </State>
        <State id="lastWateringEnd">
            <ValueType>String</ValueType>
            <TriggerLabel>Last Watering End</TriggerLabel>
            <ControlPageLabel>Last Watering End</ControlPageLabel>
        </State>
        <State id="lastWateringSource">
            <ValueType>String</ValueType>
            <TriggerLabel>Last Watering Source</TriggerLabel>
            <ControlPageLabel>Last Watering Source</ControlPageLabel>
        </State>
        <State id="lastWateringStatus">
            <ValueType>String</ValueType>
            <TriggerLabel>Last Watering Status</TriggerLabel>
            <ControlPageLabel>Last Watering Status</ControlPageLabel>
        </State>
        <State id="nextWateringStart">
            <ValueType>String</ValueType>
            <TriggerLabel>Next Watering Start</TriggerLabel>
            <ControlPageLabel>Next Watering Start</ControlPageLabel>
        </State>
        <State id="nextWateringEnd">
            <ValueType>String</ValueType>
            <TriggerLabel>Next Watering End</TriggerLabel>
            <ControlPageLabel>Next Watering End</ControlPageLabel>
        </State>
        <State id="nextWateringSource">
            <ValueType>String</ValueType>
            <TriggerLabel>Next Watering Source</TriggerLabel>
            <ControlPageLabel>Next Watering Source</ControlPageLabel>
        </State>
    </States>
    <UiDisplayStateId>moisture</UiDisplayStateId>
</Device>
```

### Auto-creation logic

During each controller poll cycle in `_update_sprinkler_device()`:

1. Get zones from `info.json` response (`device_data["zones"]`)
2. Find existing zone devices for this controller (match by `parentDeviceId` in pluginProps)
3. For each API zone:
   - If no matching zone device exists: create one named `"{Controller Name} - {Zone Name}"`
   - If zone device exists but zone was renamed in Netro: update Indigo device name
4. Never delete zone devices

### Zone state population

All data comes from the parent controller's existing API calls (no extra API calls):

- **`info.json`** -> `enabled`, `smartMode` (from zones array)
- **`schedules.json`** -> `isIrrigating` (EXECUTING status filtered by zone), `lastWatering*` (most recent EXECUTED), `nextWatering*` (next VALID)
- **`moistures.json`** -> `moisture` (filtered by zone number)

### Custom action: `setZoneMoisture`

Added to `Actions.xml` on the zone device. Calls `api_client.set_moisture()` for the specific zone using the parent controller's auth credentials.

### Variable-to-API auto-link

```python
def startup(self):
    indigo.variables.subscribeToChanges()

def variableUpdated(self, origVar, newVar):
    # Look up zone from variable ID using zoneVariableMap in pluginProps
    # If matched and value changed, call set_moisture API
    # Update zone device moisture state
```

## New handler: `ZoneHandler`

Added to `device_handlers.py`. Responsible for:

- `process_zone_schedules(schedules, zone_number)` -> per-zone last/next/active schedule states
- `process_zone_moisture(moistures, zone_number)` -> per-zone moisture state
- `extract_zone_states(device_data, zone_number)` -> enabled, smartMode from info response

Pure Python, no Indigo imports, returns state update dicts like existing handlers.

## Data Flow

```
Controller poll cycle
  |
  +-- GET info.json ---------> process_device_info() --> controller states
  |                        \-> extract_zone_info()   --> zone names, enabled, smartMode
  |                        \-> auto-create zone devices
  |
  +-- GET schedules.json ----> process_schedules()   --> controller schedule states
  |                        \-> process_zone_schedules() --> per-zone schedule states
  |
  +-- GET moistures.json ----> process_zone_moisture() --> per-zone moisture states
  |                        \-> _ensure_zone_variables() --> update Indigo variables
  |
  (no extra API calls)
```

## Migration

- **Breaking**: `zone_N_moisture` states removed from controller. Users with triggers or control pages referencing these need to update to zone device states.
- **Non-breaking**: Zone devices are additive. Zone variables unchanged.
- **Version bump**: Minor version bump (feature addition with breaking state removal).
