# Phase 5: Device Handlers - Context

**Gathered:** 2026-02-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Extract device update logic from monolithic plugin.py into dedicated handler classes (SprinklerHandler and WhispererHandler). Handlers will process API responses and update Indigo device states. The goal is to reduce plugin.py from 1635 lines to ~400 lines while maintaining all existing functionality.

</domain>

<decisions>
## Implementation Decisions

## State Update Patterns
- **Full state replacement**: Handlers provide complete device state on each update, replacing all values
- **Error handling**: When state update fails (unexpected API data), handler logs error and marks device as offline, preserving last known good data
- Device state includes online/offline status as first-class property

### Claude's Discretion
- Device object interaction pattern (receive device and modify directly vs return state dict)
- Data validation level (strict validation, lenient with defaults, or trust API client's schema validation)
- Whether to cache previous state for comparison/logging
- Handler initialization pattern (per-device instances vs shared handlers)

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches that align with existing codebase patterns.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-device-handlers*
*Context gathered: 2026-02-02*
