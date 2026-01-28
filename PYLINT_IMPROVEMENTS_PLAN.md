# Pylint Improvements Plan

**Goal**: Increase pylint score from 6.5/10 to 8.0+

**Current Status**: plugin.py has ~150 pylint warnings

## Priority 1: Critical Issues (High Impact on Score)

### 1.1 Fix Indentation in _update_from_netro (Lines 336-542)
**Problem**: Over-indentation throughout the method (20+ instances)
- Lines have 20-40 spaces when should be 16-28
- Affects readability and pylint score significantly

**Fix**: Re-indent entire method block correctly
- for loop content should be 16 spaces (4 indent levels)
- if/try blocks inside should be 20/24 spaces
- Nested blocks adjust accordingly

**Impact**: ~50 warnings fixed

### 1.2 Split Long Lines (>120 chars)
**Problem**: 6 lines exceed 120 character limit
- Line 173: Long warning message
- Line 267: Long comment/code
- Line 370-371: Long state update lines
- Line 377, 386: Long lines

**Fix**: Split across multiple lines with proper continuation
```python
# Before
self.logger.warn("Very long message that exceeds the character limit...")

# After
self.logger.warn(
    "Very long message that exceeds "
    "the character limit..."
)
```

**Impact**: 6 warnings fixed

## Priority 2: Style Issues (Medium Impact)

### 2.1 Fix f-strings Without Interpolation
**Problem**: Using f-strings when regular strings would work
- Lines 839, 858, 927, 947, 1183, 1416, 1436

**Fix**: Remove f-prefix where no variables interpolated
```python
# Before
self.logger.debug(f"sprinklerList")

# After
self.logger.debug("sprinklerList")
```

**Impact**: 7 warnings fixed

### 2.2 Fix Simplifiable Expressions
**Problem**: Expressions that can be simplified
- Line 948: `'on' if mode else 'off'` instead of ternary

**Fix**: Use simpler Python idioms
```python
# Before
reply = {"on": "true"} if online else {"on": "false"}

# After
reply = {"on": str(online).lower()}
```

**Impact**: 2-3 warnings fixed

### 2.3 Use Python 3 style super()
**Problem**: Old-style super() calls
- Lines 1024, 1039

**Fix**: Remove arguments from super()
```python
# Before
super(Plugin, self).triggerStartProcessing(trigger)

# After
super().triggerStartProcessing(trigger)
```

**Impact**: 2 warnings fixed

## Priority 3: Low Impact (Optional)

### 3.1 Unused Arguments in Callbacks
**Problem**: Required Indigo callback parameters marked as unused
- Many callback methods have unused parameters (required by Indigo API)

**Fix**: Prefix with underscore or add pylint disable comment
```python
def callback(self, _unused_param, valuesDict, _typeId):
    # Only use valuesDict
```

**Impact**: ~20 warnings (but necessary for Indigo API)
**Decision**: Add `# pylint: disable=unused-argument` to specific methods

### 3.2 Too Many Branches/Public Methods
**Problem**: Plugin class has many methods (required for Indigo)
- Too many public methods (28/20 limit)
- Too many branches in validation method

**Fix**: Add disable comments for architectural requirements
```python
class Plugin(indigo.PluginBase):  # pylint: disable=too-many-public-methods
```

**Impact**: 2 warnings (but necessary for Indigo architecture)

### 3.3 Reimport and Import Outside Toplevel
**Problem**: datetime imported twice, imports in methods
- Line 817: datetime reimport in method
- Line 1291: date import in method

**Fix**: Move to top-level or use existing import
**Impact**: 2 warnings

## Implementation Strategy

### Phase 1: Automated Fixes (Quick Wins)
Run autopep8 or similar to fix:
- Indentation
- Line lengths
- Whitespace

### Phase 2: Manual Fixes
- f-string removals
- super() updates
- Expression simplification
- Import reorganization

### Phase 3: Strategic Disables
Add targeted disable comments for Indigo API requirements:
- unused-argument on callback methods
- too-many-public-methods on Plugin class
- too-many-branches on validation methods

## Expected Outcome

**Current**: 6.5/10 (150 warnings)

**After Priority 1**: ~7.5/10 (90 warnings)
**After Priority 2**: ~8.0/10 (80 warnings)  ← TARGET
**After Priority 3**: ~8.5/10 (60 warnings)

## Files to Modify

1. **plugin.py** - All fixes apply here

## Testing After Changes

```bash
# Run pylint
python3 -m pylint plugin.py --max-line-length=120

# Run tests to ensure no breakage
pytest tests/

# Test in Indigo
# Load plugin and verify basic functionality
```

## Commit Strategy

1. **Commit 1**: Fix indentation and line lengths (Priority 1)
2. **Commit 2**: Fix style issues (Priority 2)
3. **Commit 3**: Add strategic disables (Priority 3)

Each commit should:
- Run pylint to verify score improvement
- Run tests to ensure no breakage
- Document score change in commit message

## Notes

- Indigo API requires specific method signatures (can't remove "unused" params)
- Plugin architecture requires many public methods (can't reduce count)
- Some warnings are false positives for plugin architecture
- Target 8.0+ is reasonable; 10.0 not realistic for Indigo plugins
