# Phase 4: Validators - Research

**Researched:** 2026-02-01
**Domain:** Python validation functions for Indigo plugin configuration UIs
**Confidence:** HIGH

## Summary

This phase extracts configuration validation logic from plugin.py into a standalone validators.py module. The research analyzed the existing validation callbacks in the Netro plugin (4 methods, ~150 lines of validation logic) and examined Indigo SDK examples to understand the callback interface contract.

The validation callbacks follow a consistent pattern: receive a valuesDict (indigo.Dict), perform validation, and return a tuple indicating success/failure with an optional errors dict. The extraction should create pure validation functions that can be tested independently while maintaining full compatibility with Indigo's callback signature requirements.

**Primary recommendation:** Use a result tuple pattern `(is_valid, sanitized_values, errors_dict)` where validators return all three values consistently, allowing the plugin.py callbacks to remain thin wrappers that just dispatch to the validators module.

## Standard Stack

This phase requires no external libraries - only Python standard library and the existing extracted modules.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib | 3.10+ | Type hints, dataclasses | Already required by project |
| typing | stdlib | Type annotations | Modern Python best practice |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| constants.py | internal | Import MIN/MAX values | Reference bounds for validation |
| re | stdlib | Serial number format validation | If hex pattern matching needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom result type | Named tuple/dataclass | Dataclass adds dependency; tuple matches Indigo pattern |
| pydantic | Custom validation | Overkill for simple validations, adds dependency |
| cerberus | Custom validation | Schema-based validation too heavy for UI config |

**Installation:**
No additional installation required.

## Architecture Patterns

### Recommended Project Structure
```
Server Plugin/
├── plugin.py            # Thin callbacks that dispatch to validators
├── validators.py        # NEW: Pure validation functions
├── constants.py         # Import validation bounds from here
├── exceptions.py        # No changes needed
└── utils.py             # No changes needed
```

### Pattern 1: Pure Validation Functions with Result Tuples

**What:** Each validator is a pure function that takes a dict of values and returns a tuple of (is_valid, sanitized_values, errors_dict).

**When to use:** Always - this is the pattern that matches Indigo's validateConfigUi callback signature.

**Example:**
```python
# Source: Indigo SDK Example Action API plugin.py lines 55-70
from typing import Tuple, Dict, Any

def validate_device_config(
    values: Dict[str, Any],
    type_id: str
) -> Tuple[bool, Dict[str, Any], Dict[str, str]]:
    """Validate device configuration.

    Args:
        values: Configuration values from UI dialog
        type_id: Device type identifier

    Returns:
        Tuple of (is_valid, sanitized_values, errors_dict)
        - is_valid: True if validation passed
        - sanitized_values: Values with any normalization applied
        - errors_dict: Field name -> error message mapping (empty if valid)
    """
    errors: Dict[str, str] = {}

    # Sanitize inputs (strip whitespace)
    sanitized = dict(values)  # Shallow copy to avoid mutating input

    if type_id == "sprinkler":
        serial = str(values.get("address", "")).strip()
        sanitized["address"] = serial  # Store sanitized value

        if not serial:
            errors["address"] = "Serial number is required for Netro controller"
        elif len(serial) < 8:
            errors["address"] = "Serial number appears too short (should be 12 hex characters)"

    return (len(errors) == 0, sanitized, errors)
```

### Pattern 2: Individual Field Validators

**What:** Break validation into small, focused functions that validate single fields or related field groups.

**When to use:** When field validation logic is reused across multiple validators or for complex validation rules.

**Example:**
```python
# Source: Pattern derived from SDK examples and existing plugin.py
from typing import Tuple, Optional
from constants import MINIMUM_POLLING_INTERVAL_MINUTES

def validate_integer_range(
    value: Any,
    field_name: str,
    min_val: int,
    max_val: int,
    default: Optional[int] = None
) -> Tuple[bool, Optional[int], Optional[str]]:
    """Validate an integer is within range.

    Args:
        value: Value to validate (may be string or int)
        field_name: Field name for error messages
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)
        default: Default value if empty/missing

    Returns:
        Tuple of (is_valid, parsed_value, error_message)
    """
    if value is None or value == "":
        if default is not None:
            return (True, default, None)
        return (False, None, f"{field_name} is required")

    try:
        int_val = int(value)
        if int_val < min_val or int_val > max_val:
            return (False, None, f"{field_name} must be between {min_val} and {max_val}")
        return (True, int_val, None)
    except (ValueError, TypeError):
        return (False, None, f"{field_name} must be a valid number")
```

### Pattern 3: Thin Callback Wrapper in plugin.py

**What:** After extraction, plugin.py validation callbacks become thin wrappers that delegate to validators.py.

**When to use:** This is how plugin.py should look after the extraction.

**Example:**
```python
# Source: Pattern derived from SDK Example Action API plugin.py
# In plugin.py after extraction:

from validators import validate_device_config, validate_action_config

class Plugin(indigo.PluginBase):

    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        """Validate device configuration before saving."""
        self.logger.threaddebug("validateDeviceConfigUi")
        is_valid, sanitized, errors = validate_device_config(dict(valuesDict), typeId)

        if is_valid:
            # Convert sanitized dict back to indigo.Dict
            result_dict = indigo.Dict(sanitized)
            return (True, result_dict)
        else:
            errors_dict = indigo.Dict(errors)
            return (False, valuesDict, errors_dict)
```

### Anti-Patterns to Avoid

- **Side effects in validators:** Validators should not log, update device states, or call APIs. They should be pure functions.
- **Mutating input dict:** Always work on a copy of the input values dict; don't modify the original.
- **Inconsistent return signatures:** Always return the full 3-tuple even when validation passes (use empty dict for errors).
- **Hardcoded magic numbers:** Import validation bounds from constants.py for consistency and testability.

## Don't Hand-Roll

Problems that look simple but should use existing patterns:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Type conversion | Manual try/except everywhere | Single validate_integer_range helper | Consistent error messages, DRY |
| Range checking | Inline if statements | Parameterized range validator | Reusable across all int fields |
| Serial number validation | Simple length check | validate_serial_number with format check | Could add hex validation later |
| Error message formatting | Hardcoded strings | Error message templates with field names | Consistent user experience |

**Key insight:** The validation logic is simple enough that a custom validation library would be overkill, but helper functions for common patterns (integer range, required string, optional numeric) significantly reduce duplication.

## Common Pitfalls

### Pitfall 1: indigo.Dict vs dict Confusion

**What goes wrong:** Validators receive indigo.Dict (Indigo's dict subclass) but return values may need to be indigo.Dict for Indigo to accept them.

**Why it happens:** indigo.Dict looks like a regular dict but has subtle differences. Tests might pass with regular dicts but fail in Indigo.

**How to avoid:**
- Accept any dict-like object in validators (use `Dict[str, Any]` type hint)
- Work internally with regular Python dicts
- Convert back to indigo.Dict only in the plugin.py callback wrapper
- Test with both dict and indigo.Dict-like mocks

**Warning signs:** Tests pass but validation fails in Indigo UI; "type object 'Dict' has no attribute" errors.

### Pitfall 2: Missing Default Value Handling

**What goes wrong:** Validators crash when optional fields are missing from valuesDict.

**Why it happens:** New devices may not have all fields populated; UI might not include optional fields.

**How to avoid:**
- Always use `.get()` with explicit defaults: `valuesDict.get("field", default_value)`
- Decide if missing = invalid or missing = use default
- Document which fields are required vs optional

**Warning signs:** KeyError exceptions when creating new devices; works for existing devices but fails for new ones.

### Pitfall 3: String vs Number Type Mismatch

**What goes wrong:** Validators expect int but receive string "15" from UI, or expect string but receive int.

**Why it happens:** Indigo UI fields typically return strings even for numeric inputs.

**How to avoid:**
- Always convert types explicitly: `int(valuesDict.get("duration", "15"))`
- Wrap conversions in try/except to catch invalid values
- Strip whitespace before conversion: `.strip()` on strings

**Warning signs:** TypeError/ValueError on int() calls; validation passes but action fails.

### Pitfall 4: Forgetting to Return Modified valuesDict

**What goes wrong:** Validation sanitizes values but plugin.py doesn't use the sanitized version.

**Why it happens:** Original valuesDict is passed through on success without applying sanitization.

**How to avoid:**
- Always return sanitized values even on success
- Plugin.py callback should use the returned values, not the original
- Test that sanitization is actually applied (e.g., whitespace stripped)

**Warning signs:** Leading/trailing whitespace in stored values; validation passes but values aren't cleaned.

### Pitfall 5: Error Dict Key Mismatch

**What goes wrong:** Error message doesn't appear next to the correct field in Indigo UI.

**Why it happens:** Error dict key doesn't match the field ID in the XML definition.

**How to avoid:**
- Error keys must exactly match field IDs from Devices.xml/Actions.xml
- Case-sensitive: "address" != "Address"
- Check XML definitions when adding new validators

**Warning signs:** Generic error dialog instead of field-specific error highlight; errors shown for wrong fields.

## Code Examples

Verified patterns from official sources and existing codebase:

### Validate Serial Number (from existing plugin.py)
```python
# Source: netro/plugin.py lines 862-876
def validate_serial_number(
    serial: str,
    device_type: str
) -> Tuple[bool, str, Optional[str]]:
    """Validate Netro device serial number.

    Args:
        serial: Serial number string (may have whitespace)
        device_type: "sprinkler" or "Whisperer"

    Returns:
        Tuple of (is_valid, sanitized_serial, error_message)
    """
    sanitized = serial.strip() if serial else ""

    if not sanitized:
        device_name = "Netro controller" if device_type == "sprinkler" else "Whisperer sensor"
        return (False, "", f"Serial number is required for {device_name}")

    if len(sanitized) < 8:
        return (False, sanitized, "Serial number appears too short (should be 12 hex characters)")

    return (True, sanitized, None)
```

### Validate Integer Range (from existing plugin.py patterns)
```python
# Source: Derived from netro/plugin.py lines 1010-1017
from constants import MINIMUM_POLLING_INTERVAL_MINUTES

def validate_polling_interval(value: Any) -> Tuple[bool, Optional[int], Optional[str]]:
    """Validate polling interval setting.

    Args:
        value: Value from config UI (string or int)

    Returns:
        Tuple of (is_valid, parsed_value, error_message)
    """
    try:
        polling = int(value) if value else MINIMUM_POLLING_INTERVAL_MINUTES

        if polling < MINIMUM_POLLING_INTERVAL_MINUTES:
            return (False, None,
                f"Polling interval must be at least {MINIMUM_POLLING_INTERVAL_MINUTES} minutes to avoid API rate limits")

        if polling > 1440:  # 24 hours max
            return (False, None, "Polling interval cannot exceed 1440 minutes (24 hours)")

        return (True, polling, None)

    except (ValueError, TypeError):
        return (False, None, "Polling interval must be a valid number")
```

### Full validateDeviceConfigUi Extraction Pattern
```python
# Source: Pattern from SDK Example Action API validate_device_info_action
def validate_device_config(
    values: Dict[str, Any],
    type_id: str
) -> Tuple[bool, Dict[str, Any], Dict[str, str]]:
    """Validate device configuration.

    This function is pure - no side effects, no logging, no Indigo calls.
    Called by validateDeviceConfigUi callback in plugin.py.

    Args:
        values: Configuration values from UI dialog
        type_id: Device type identifier ("sprinkler" or "Whisperer")

    Returns:
        Tuple of (is_valid, sanitized_values, errors_dict)
    """
    errors: Dict[str, str] = {}
    sanitized = dict(values)  # Work on copy

    if type_id == "sprinkler":
        is_valid, serial, error = validate_serial_number(
            values.get("address", ""), "sprinkler"
        )
        sanitized["address"] = serial
        if not is_valid:
            errors["address"] = error

    elif type_id == "Whisperer":
        is_valid, serial, error = validate_serial_number(
            values.get("address", ""), "Whisperer"
        )
        sanitized["address"] = serial
        if not is_valid:
            errors["address"] = error

        # Set sensor capabilities (as existing code does)
        sanitized["SupportsBatteryLevel"] = True
        sanitized["NumTemperatureInputs"] = 1
        sanitized["NumHumidityInputs"] = 1
        sanitized["SupportsTemperatureReporting"] = True

    return (len(errors) == 0, sanitized, errors)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Inline validation in callbacks | Extract to testable functions | This refactoring | Testability, maintainability |
| Magic numbers in validation | Constants from constants.py | Phase 2 | Single source of truth |
| Bare except handlers | Specific exception handling | Phase 1 | Better error visibility |

**Deprecated/outdated:**
- None for this domain - validation patterns have been stable in Python

## Open Questions

Things that were fully resolved during research:

1. **Return value pattern for validators**
   - What we know: Indigo expects `(True, valuesDict)` or `(False, valuesDict, errorsDict)`
   - Resolution: Validators return consistent 3-tuple; plugin.py wrapper adapts as needed
   - Recommendation: Always return 3-tuple `(is_valid, values, errors)` from validators

2. **Value sanitization in validators**
   - What we know: Current code sanitizes (strips whitespace) and sets capability flags
   - Resolution: Include sanitization in validators; return sanitized values
   - Recommendation: Validators both validate and sanitize; pure transformation with no side effects

## Sources

### Primary (HIGH confidence)
- Existing netro plugin.py validation callbacks (lines 847-1041)
- Indigo SDK Example Action API plugin.py (validate_device_info_action pattern)
- Indigo SDK Example Device - Custom plugin.py (validateDeviceConfigUi example)

### Secondary (MEDIUM confidence)
- Indigo SDK multiple examples showing callback signature patterns
- Project's existing test patterns in test_base_modules.py

### Tertiary (LOW confidence)
- None - all patterns verified against existing code

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - No external dependencies, using Python stdlib
- Architecture: HIGH - Pattern verified against existing code and SDK examples
- Pitfalls: HIGH - Based on actual Indigo plugin development experience in codebase

**Research date:** 2026-02-01
**Valid until:** Stable patterns, no expiration concern
