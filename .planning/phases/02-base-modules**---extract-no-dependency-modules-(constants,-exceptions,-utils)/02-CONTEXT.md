# Phase 2: Base Modules - Context

**Gathered:** 2026-02-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Extract foundation modules (constants, exceptions, utils) from monolithic plugin.py into separate, testable modules. This phase proves that multi-file plugin structure works with Indigo while establishing the foundation for further refactoring.

Scope includes:
- constants.py with API URLs, defaults, and enums
- exceptions.py with custom exception classes
- utils.py with timestamp parsing and helper functions
- Ensuring plugin loads successfully in Indigo
- All 64 existing tests pass with new imports

</domain>

<decisions>
## Implementation Decisions

### Refactoring Approach
- **Balance speed and quality**: Extract code cleanly while fixing obvious issues (not minimal copy-paste, not deep rewrite)
- **Improvements to make during extraction**:
  - Naming improvements: Rename unclear variables/functions
  - Documentation: Add docstrings and type hints where missing
  - Remove dead code: Delete unused constants, commented-out code
  - Type consistency: Fix type inconsistencies (e.g., string vs int constants)
- **Testing**: Add unit tests for extracted modules (not just ensure existing tests pass)
- **Backward compatibility**: Break freely - internal refactor, no need to maintain old import paths

### Constants Structure
- **Naming convention**: SCREAMING_SNAKE_CASE for all constants (e.g., API_BASE_URL, DEFAULT_TIMEOUT)

### Claude's Discretion
- **Organization approach**: Choose between flat module, grouped by category, or mixed based on number of constants and their relationships
- **Constants vs utils boundary**: Decide what belongs in constants.py vs utils.py based on the actual code (literals vs computed values vs functions)
- **Documentation level**: Judge which constants need explanation beyond their names
- **Import patterns**: Choose appropriate import style (explicit imports, re-exports, etc.) based on plugin structure
- **Module file organization**: Directory structure, __init__.py usage

</decisions>

<specifics>
## Specific Ideas

- Focus on proving the multi-file pattern works with Indigo - this is validation that further refactoring phases will succeed
- Foundation for Phase 3 (API Client) and Phase 5 (Device Handlers) - these modules need to be solid

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-base-modules*
*Context gathered: 2026-02-01*
